import ctypes
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import mss
import numpy as np
from PySide6.QtCore import Qt, QRect, QTimer, Signal, QLockFile, QEvent
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPen, QPixmap, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QTabWidget, QComboBox, QSpinBox,
    QKeySequenceEdit, QFileDialog, QLineEdit, QSystemTrayIcon, QMenu, QMessageBox,
    QScrollArea, QColorDialog)
from .core import load_settings, save_settings, Stitcher, settings_path
from .i18n import LANGUAGES, translate
from .native import Hotkeys, modifiers_down, paste, user32, monitor_rect
from .recorder import Recorder

STYLE = """
QWidget {font-family: 'Microsoft YaHei UI'; font-size: 14px; color: #24334b;}
QMainWindow, QTabWidget::pane {background: #f5f7fb;}
QTabWidget::pane {border: 0;}
QTabBar::tab {background: transparent; padding: 12px 24px; margin: 0 8px 12px 0; color: #718097;}
QTabBar::tab:selected {background: #e5ebff; color: #455ad5; border-radius: 10px;}
QFrame#card {background: white; border: 1px solid #e5eaf2; border-radius: 16px;}
QLabel#muted {color: #738098;}
QLabel#title {font-size: 29px; font-weight: 650;}
QPushButton {background: #fff; border: 1px solid #dce3ee; border-radius: 9px; padding: 10px 16px;}
QPushButton:hover {background: #eef2ff; border-color: #b5c1fa;}
QPushButton#primary {background: #5367e8; color: white; border: 0; font-weight: 600;}
QPushButton#primary:hover {background: #4357d5;}
QPushButton#danger {color: #c04455; background: #fff0f2; border: 0;}
QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {background: #f9faff; border: 1px solid #dce3ee;
border-radius: 7px; padding: 8px; min-height: 24px;}
QKeySequenceEdit QLineEdit {border: 0; padding: 0;}
QScrollArea {border: 0; background: transparent;}
QWidget#preferences {background: #f5f7fb;}
QToolTip {background: #24334b; color: white; border: 0; padding: 8px;}
"""

def as_image(array):
    array = np.ascontiguousarray(array)
    h, w = array.shape[:2]
    return QImage(array.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()

def capture(region):
    with mss.mss() as grabber:
        return np.array(grabber.grab(region))[:, :, :3][:, :, ::-1].copy()

def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#5367e8"))
    p.drawRoundedRect(0, 0, 64, 64, 16, 16)
    p.setPen(QPen(QColor("white"), 5))
    for a,b,c,d in [(17,29,17,17),(17,17,29,17),(35,17,47,17),(47,17,47,29),
                     (47,35,47,47),(47,47,35,47),(29,47,17,47),(17,47,17,35)]:
        p.drawLine(a,b,c,d)
    p.end()
    return QIcon(pixmap)

class Selector(QWidget):
    selected = Signal(object)
    cancelled = Signal()

    def __init__(self, screen, text, border="#3985ff"):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.screen_ref = screen
        self.border = QColor(border)
        self.setWindowTitle("ScreenCut — Capture")
        self.background = screen.grabWindow(0)
        self.text = text
        self.start = self.end = None
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.background)
        p.fillRect(self.rect(), QColor(15, 23, 42, 105))
        if self.start is not None:
            rect = QRect(self.start, self.end).normalized()
            p.save()
            p.setClipRect(rect)
            p.drawPixmap(self.rect(), self.background)
            p.restore()
            p.setPen(QPen(self.border, 2))
            p.drawRect(rect)
            ratio = self.screen_ref.devicePixelRatio()
            size_text = f"{round(rect.width()*ratio)} × {round(rect.height()*ratio)} px"
            tag = QRect(rect.left(), max(55, rect.top()-34), 210, 30)
            p.fillRect(tag, QColor(20, 30, 48, 230))
            p.setPen(QColor("white"))
            p.drawText(tag, Qt.AlignmentFlag.AlignCenter, size_text)
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 13))
        p.drawText(self.rect().adjusted(28, 28, -28, -28), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
        else:
            self.start = self.end = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self.end = event.position().toPoint()
        rect = QRect(self.start, self.end).normalized().intersected(self.rect())
        if rect.width() < 32 or rect.height() < 32:
            return
        x, y, w, h = monitor_rect(self.screen_ref.name(), self.screen_ref.geometry(), self.screen_ref.devicePixelRatio())
        sx, sy = w/self.width(), h/self.height()
        self.selected.emit(dict(left=x+round(rect.x()*sx), top=y+round(rect.y()*sy),
                                width=round(rect.width()*sx), height=round(rect.height()*sy)))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

class SessionBar(QWidget):
    def __init__(self, title, finish, cancel, t):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("ScreenCut")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QHBoxLayout(self)
        self.label = QLabel(title)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        btn = QPushButton(t("finish"))
        btn.clicked.connect(finish)
        layout.addWidget(btn)
        btn = QPushButton(t("cancel"))
        btn.clicked.connect(cancel)
        layout.addWidget(btn)
        self.resize(700, 90)
        self.cancel_callback = cancel

    def closeEvent(self, event):
        self.cancel_callback()
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.latest = None
        self.selectors = []
        self.mode = None
        self.bar = None
        self.recorder = None
        self.stitcher = None
        self.quitting = False
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(500)
        self.scroll_timer.timeout.connect(self.scroll_tick)
        self.delay_timer = QTimer(self)
        self.delay_timer.setInterval(1000)
        self.delay_timer.timeout.connect(self.countdown_tick)
        self.hotkeys = Hotkeys(self.dispatch)
        QApplication.instance().installNativeEventFilter(self.hotkeys)
        self.key_status = self.hotkeys.register(self.settings["hotkeys"])
        self.setWindowTitle("ScreenCut")
        self.setWindowIcon(app_icon())
        self.resize(1080, 860)
        self.build_ui()
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("ScreenCut")
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.update_tray()
        self.tray.show()

    def t(self, key):
        return translate(self.settings["language"], key)

    def label(self, text, name=None):
        widget = QLabel(text)
        widget.setWordWrap(True)
        if name:
            widget.setObjectName(name)
        return widget

    def build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(16)
        top = QHBoxLayout()
        brand = self.label("▣  ScreenCut")
        brand.setStyleSheet("font-size: 22px; font-weight: 700; color: #5367e8")
        top.addWidget(brand)
        top.addStretch()
        top.addWidget(self.label("0.1  /  PREVIEW", "muted"))
        layout.addLayout(top)
        layout.addWidget(self.label(self.t("studio"), "title"))
        layout.addWidget(self.label(self.t("subtitle"), "muted"))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        studio = QWidget()
        studio_layout = QVBoxLayout(studio)
        studio_layout.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, action in enumerate(("copy", "scroll", "delay", "record")):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 18, 20, 18)
            heading = QHBoxLayout()
            heading.addWidget(self.label(self.t(action)))
            heading.addStretch()
            shortcut = self.label(self.settings["hotkeys"][action] or "—", "muted")
            heading.addWidget(shortcut)
            box.addLayout(heading)
            desc = self.t(action+"_desc") if action in ("scroll", "record") else (
                self.t("select") if action == "copy" else f'{self.settings["delay"]} s · {self.t("copy")}')
            box.addWidget(self.label(desc, "muted"), 1)
            button = QPushButton(self.t(action) + "  →")
            if action == "copy":
                button.setObjectName("primary")
            button.clicked.connect(lambda checked=False, a=action: self.dispatch(a))
            box.addWidget(button)
            grid.addWidget(card, i//2, i%2)
        studio_layout.addLayout(grid)
        preview_card = QFrame()
        preview_card.setObjectName("card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.addWidget(self.label(self.t("preview"), "muted"))
        self.preview = QLabel(self.t("preview_empty"))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(130)
        preview_layout.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        copy_btn = QPushButton(self.t("copy"))
        copy_btn.clicked.connect(self.copy_latest)
        actions.addWidget(copy_btn)
        save_btn = QPushButton(self.t("save"))
        save_btn.clicked.connect(self.save_latest)
        actions.addWidget(save_btn)
        preview_layout.addLayout(actions)
        studio_layout.addWidget(preview_card, 1)
        self.tabs.addTab(studio, self.t("capture"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        preferences = QWidget()
        preferences.setObjectName("preferences")
        prefs = QVBoxLayout(preferences)
        prefs.setContentsMargins(4, 4, 16, 4)
        prefs.addWidget(self.label(self.t("hotkeys")))
        prefs.addWidget(self.label(self.t("hotkey_help"), "muted"))
        keys = QGridLayout()
        self.editors = {}
        for row, (action, sequence) in enumerate(self.settings["hotkeys"].items()):
            keys.addWidget(QLabel(self.t(action)), row, 0)
            editor = QKeySequenceEdit(QKeySequence(sequence))
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            editor.installEventFilter(self)
            editor.findChild(QLineEdit).installEventFilter(self)
            self.editors[action] = editor
            keys.addWidget(editor, row, 1)
            status = self.key_status[action]
            badge = QLabel(self.t(status))
            badge.setStyleSheet("color: " + ("#23967b" if status == "active" else "#b56b37"))
            keys.addWidget(badge, row, 2)
        prefs.addLayout(keys)
        form = QGridLayout()
        self.languages = QComboBox()
        for code, title in LANGUAGES.items():
            self.languages.addItem(title, code)
        self.languages.setCurrentIndex(max(0, self.languages.findData(self.settings["language"])))
        form.addWidget(QLabel(self.t("language")), 0, 0)
        form.addWidget(self.languages, 0, 1)
        self.folder = QLineEdit(self.settings["folder"])
        form.addWidget(QLabel(self.t("folder")), 1, 0)
        form.addWidget(self.folder, 1, 1)
        browse = QPushButton(self.t("browse"))
        browse.clicked.connect(self.choose_folder)
        form.addWidget(browse, 1, 2)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(self.settings["delay"])
        form.addWidget(QLabel(self.t("seconds")), 2, 0)
        form.addWidget(self.delay_spin, 2, 1)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(5, 30)
        self.fps_spin.setValue(self.settings["fps"])
        form.addWidget(QLabel(self.t("fps")), 3, 0)
        form.addWidget(self.fps_spin, 3, 1)
        prefs.addLayout(form)
        border = QPushButton(self.t("border"))
        border.clicked.connect(self.choose_border)
        prefs.addWidget(border)
        apply = QPushButton(self.t("apply"))
        apply.setObjectName("primary")
        apply.clicked.connect(self.apply_settings)
        prefs.addStretch()
        scroll.setWidget(preferences)
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(scroll, 1)
        settings_layout.addWidget(apply)
        self.tabs.addTab(settings_page, self.t("settings"))
        self.status_label = self.label(self.t("ready"), "muted")
        layout.addWidget(self.status_label)
        layout.addWidget(self.label(self.t("local"), "muted"))
        self.setCentralWidget(root)
        self.update_preview()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            self.hotkeys.clear()
        elif event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self.restore_hotkeys_after_edit)
        return super().eventFilter(watched, event)

    def restore_hotkeys_after_edit(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, QKeySequenceEdit) or (focus and isinstance(focus.parent(), QKeySequenceEdit)):
            return
        self.key_status = self.hotkeys.register(self.settings["hotkeys"])

    def update_tray(self):
        menu = QMenu(self)
        menu.addAction(self.t("show"), self.showNormal)
        for action in ("copy", "scroll", "delay", "record", "save"):
            menu.addAction(self.t(action), lambda a=action: self.dispatch(a))
        menu.addSeparator()
        menu.addAction(self.t("quit"), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray_menu = menu

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.t("folder"), self.folder.text())
        if folder:
            self.folder.setText(folder)

    def choose_border(self):
        color = QColorDialog.getColor(QColor(self.settings.get("border", "#3985ff")), self)
        if color.isValid():
            self.settings["border"] = color.name()
            save_settings(self.settings)

    def apply_settings(self):
        candidate = dict(self.settings, language=self.languages.currentData(),
            folder=self.folder.text().strip(), delay=self.delay_spin.value(), fps=self.fps_spin.value(),
            hotkeys={a:e.keySequence().toString(QKeySequence.SequenceFormat.PortableText) for a,e in self.editors.items()})
        try:
            if not Path(candidate["folder"]).is_absolute():
                raise ValueError(self.t("folder"))
            Path(candidate["folder"]).mkdir(parents=True, exist_ok=True)
            save_settings(candidate)
        except Exception as exc:
            self.fail(exc)
            return
        self.settings = candidate
        self.key_status = self.hotkeys.register(candidate["hotkeys"])
        self.build_ui()
        self.tabs.setCurrentIndex(1)
        self.update_tray()
        self.notify(self.t("saved_settings"))

    def notify(self, message):
        self.status_label.setText(message)
        if not self.isVisible():
            self.tray.showMessage("ScreenCut", message, QSystemTrayIcon.MessageIcon.Information, 2200)

    def fail(self, exc):
        logging.exception("Operation failed", exc_info=exc)
        self.notify(self.t("error") + ": " + str(exc))

    def dispatch(self, action):
        try:
            if action == "record":
                if self.mode in ("record", "record_ready", "finalizing"):
                    self.bar.show()
                    self.bar.raise_()
                elif self.mode is None:
                    self.open_record_panel()
                return
            if action == "paste":
                if self.mode is None:
                    self.paste_target = user32.GetForegroundWindow()
                    self.paste_deadline = time.monotonic() + 3
                    QTimer.singleShot(30, self.paste_when_released)
                return
            if self.mode is not None:
                if action == "scroll" and self.mode == "scroll":
                    self.finish_scroll()
                elif action == "record" and self.mode == "record":
                    self.stop_recording()
                return
            self.mode = "selecting"
            self.pending_action = action
            self.hide()
            if action == "delay":
                self.mode = "delay"
                self.remaining = self.settings["delay"]
                self.bar = SessionBar(self.t("countdown"), self.cancel_session, self.cancel_session, self.t)
                self.bar.show()
                self.countdown_tick()
                if self.mode == "delay":
                    self.delay_timer.start()
            else:
                QTimer.singleShot(250, self.select_region)
        except Exception as exc:
            self.cancel_session()
            self.fail(exc)

    def paste_when_released(self):
        if user32.GetForegroundWindow() != self.paste_target:
            return
        if modifiers_down():
            if time.monotonic() < self.paste_deadline:
                QTimer.singleShot(30, self.paste_when_released)
            return
        # Temporarily unregister to avoid recursion if the user mapped an action to Ctrl+V.
        self.hotkeys.clear()
        if not paste():
            self.notify(self.t("paste_failed"))
        QTimer.singleShot(200, self.restore_hotkeys_after_edit)

    def countdown_tick(self):
        if self.remaining <= 0:
            self.delay_timer.stop()
            self.close_bar()
            self.mode = "selecting"
            QTimer.singleShot(200, self.select_region)
            return
        self.bar.label.setText(f'{self.t("countdown")} · {self.remaining}')
        self.remaining -= 1

    def select_region(self):
        if self.mode != "selecting":
            return
        try:
            self.selectors = [Selector(screen, self.t("select"), self.settings.get("border", "#3985ff")) for screen in QApplication.screens()]
            for overlay in self.selectors:
                overlay.selected.connect(self.region_selected)
                overlay.cancelled.connect(self.cancel_session)
                overlay.show()
            self.selectors[0].activateWindow()
        except Exception as exc:
            self.cancel_session()
            self.fail(exc)

    def close_selectors(self):
        for overlay in self.selectors:
            overlay.hide()
            overlay.deleteLater()
        self.selectors = []

    def region_selected(self, region):
        self.region = region
        overlay = self.sender()
        if isinstance(overlay, Selector):
            screen = overlay.screen_ref
            x, y, _, _ = monitor_rect(screen.name(), screen.geometry(), screen.devicePixelRatio())
            self.selection_image = overlay.background.toImage().copy(
                region["left"]-x, region["top"]-y, region["width"], region["height"])
            self.selection_image.setDevicePixelRatio(1)
        self.close_selectors()
        QTimer.singleShot(200, self.capture_selected)

    def capture_selected(self):
        if self.mode != "selecting":
            return
        try:
            if self.pending_action == "record":
                self.mode = "record_ready"
                self.bar.show()
            elif self.pending_action == "scroll":
                self.mode = "scroll"
                self.stitcher = Stitcher(capture(self.region))
                self.settle_frame = None
                self.bar = SessionBar(self.t("scrolling"), self.finish_scroll, self.cancel_session, self.t)
                self.show_bar_outside_capture()
                self.scroll_timer.start()
            else:
                self.latest = self.selection_image
                self.update_preview()
                self.copy_latest()
                self.mode = None
                if self.pending_action == "save":
                    self.save_latest()
        except Exception as exc:
            self.cancel_session()
            self.fail(exc)

    def show_bar_outside_capture(self):
        # Exclude utility window from screen capture (Windows 10 2004+).
        user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.SetWindowDisplayAffinity(int(self.bar.winId()), 0x11)
        self.bar.move(QApplication.primaryScreen().availableGeometry().topLeft())
        self.bar.show()

    def scroll_tick(self):
        try:
            frame = capture(self.region)
            # Require two stable samples so scrolling animation is never stitched mid-frame.
            if self.settle_frame is not None and np.mean(np.abs(frame.astype(np.int16)-self.settle_frame.astype(np.int16))) < 1.2:
                status, amount = self.stitcher.append(frame)
                text = self.t("scrolling") if status in ("added", "unchanged") else self.t("limit" if status == "limit" else "ambiguous")
                self.bar.label.setText(f'{text} · {self.stitcher.height} px')
            self.settle_frame = frame
        except Exception as exc:
            self.scroll_timer.stop()
            self.fail(exc)
            self.cancel_session()

    def finish_scroll(self):
        if self.mode != "scroll":
            return
        self.scroll_timer.stop()
        # Include the final settled frame if the user finishes between timer samples.
        try:
            self.stitcher.append(capture(self.region))
            self.set_latest(self.stitcher.image())
        except Exception as exc:
            self.fail(exc)
        self.stitcher = None
        self.close_bar()
        self.mode = None

    def output_path(self, suffix):
        folder = Path(self.settings["folder"])
        folder.mkdir(parents=True, exist_ok=True)
        return folder / ("ScreenCut_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + suffix)

    def start_recording(self):
        if self.mode != "record_ready":
            return
        self.mode = "record"
        self.record_started = time.monotonic()
        self.recorder = Recorder(self.region, self.output_path(".mp4"), self.settings["fps"], self.mic_button.isChecked())
        self.recorder.completed.connect(self.recording_completed)
        self.start_button.setEnabled(False)
        self.region_button.setEnabled(False)
        self.mic_button.setEnabled(False)
        self.record_clock.start()
        self.recorder.start()

    def open_record_panel(self):
        screen = QApplication.primaryScreen()
        x, y, w, h = monitor_rect(screen.name(), screen.geometry(), screen.devicePixelRatio())
        self.region = dict(left=x, top=y, width=w, height=h)
        self.mode = "record_ready"
        self.bar = SessionBar("00:00 · " + self.t("fullscreen"), self.stop_recording, self.cancel_session, self.t)
        for button in self.bar.findChildren(QPushButton):
            button.hide()
        row = self.bar.layout()
        self.mic_button = QPushButton("🎤 " + self.t("microphone"))
        self.mic_button.setCheckable(True)
        self.mic_button.setToolTip(self.t("mic_help"))
        row.addWidget(self.mic_button)
        self.region_button = QPushButton(self.t("region"))
        self.region_button.clicked.connect(self.record_select_region)
        row.addWidget(self.region_button)
        self.start_button = QPushButton(self.t("start"))
        self.start_button.clicked.connect(self.start_recording)
        row.addWidget(self.start_button)
        stop = QPushButton(self.t("stop"))
        stop.clicked.connect(self.stop_recording)
        row.addWidget(stop)
        self.bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bar.customContextMenuRequested.connect(self.record_context_menu)
        self.record_clock = QTimer(self.bar)
        self.record_clock.setInterval(250)
        self.record_clock.timeout.connect(self.update_record_clock)
        self.hide()
        self.show_bar_outside_capture()

    def record_context_menu(self, point):
        menu = QMenu(self.bar)
        menu.addAction(self.t("hide"), self.bar.hide)
        menu.exec(self.bar.mapToGlobal(point))

    def update_record_clock(self):
        elapsed = int(time.monotonic() - self.record_started)
        self.bar.label.setText(f"● {elapsed//60:02d}:{elapsed%60:02d}")

    def record_select_region(self):
        self.bar.hide()
        self.pending_action = "record"
        self.mode = "selecting"
        QTimer.singleShot(200, self.select_region)

    def stop_recording(self):
        if self.recorder and self.mode == "record":
            self.mode = "finalizing"
            self.record_clock.stop()
            self.recorder.stop_event.set()
            if self.bar:
                self.bar.label.setText(self.t("finalizing"))

    def recording_completed(self, path, error):
        self.recorder.wait()
        self.recorder.deleteLater()
        self.recorder = None
        self.mode = None
        self.close_bar()
        if error:
            self.fail(RuntimeError(error))
        else:
            self.notify(self.t("saved") + path)
        if self.quitting:
            QApplication.quit()

    def close_bar(self):
        if self.bar:
            self.bar.hide()
            self.bar.deleteLater()
            self.bar = None

    def cancel_session(self):
        if self.mode in ("record", "finalizing"):
            self.stop_recording()
            return
        self.scroll_timer.stop()
        self.delay_timer.stop()
        self.close_selectors()
        self.close_bar()
        self.stitcher = None
        self.mode = None
        self.showNormal()

    def set_latest(self, array):
        self.latest = as_image(array)
        self.update_preview()
        self.copy_latest()

    def update_preview(self):
        if self.latest is not None:
            pixmap = QPixmap.fromImage(self.latest).scaled(780, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(pixmap)

    def copy_latest(self):
        if self.latest is None:
            self.notify(self.t("empty"))
            return
        QApplication.clipboard().setImage(self.latest)
        self.notify(self.t("copied"))

    def save_latest(self):
        if self.latest is None:
            self.notify(self.t("empty"))
            return
        try:
            path = self.output_path(".png")
            chosen, _ = QFileDialog.getSaveFileName(self, self.t("save"), str(path), "PNG (*.png)")
            if not chosen:
                return
            path = Path(chosen)
            if not path.suffix:
                path = path.with_suffix(".png")
            if not self.latest.save(str(path), "PNG"):
                raise OSError(str(path))
            self.notify(self.t("saved") + str(path))
        except Exception as exc:
            self.fail(exc)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.notify(self.t("tray"))

    def quit_app(self):
        self.hotkeys.clear()
        self.quitting = True
        if self.recorder:
            self.stop_recording()
        else:
            QApplication.quit()

def main():
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenCut")
    app.setOrganizationName("ScreenCut")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    directory = settings_path().parent
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=directory / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    lock = QLockFile(str(directory / "instance.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "ScreenCut", translate(load_settings()["language"], "tray"))
        return 0
    window = MainWindow()
    app.aboutToQuit.connect(window.hotkeys.clear)
    window.show()
    result = app.exec()
    lock.unlock()
    return result
