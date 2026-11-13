"""Developer smoke checks. Run from repository root; artifacts stay untracked."""
import sys
import time
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap
from screencut.app import MainWindow, Selector, STYLE, as_image, capture
from screencut.native import monitor_rect
from screencut.i18n import LANGUAGES
from screencut.recorder import Recorder
from screencut.core import Stitcher

app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
out = Path("artifacts")
out.mkdir(exist_ok=True)
window = MainWindow()
window.hotkeys.clear()
window.show()
app.processEvents()
for language in LANGUAGES:
    window.settings["language"] = language
    window.build_ui()
    window.resize(1080, 860)
    app.processEvents()
    assert window.grab().save(str(out / f"studio-{language}.png"))
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    assert window.grab().save(str(out / f"settings-{language}.png"))
window.settings["language"] = "zh"
window.settings["folder"] = str(out.resolve())
window.set_latest(np.full((160, 240, 3), (51, 102, 220), dtype=np.uint8))
assert QApplication.clipboard().image().size() == window.latest.size()
with patch("screencut.app.QFileDialog.getSaveFileName", return_value=(str(out / "ScreenCut_test.png"), "PNG")):
    window.save_latest()
assert list(out.glob("ScreenCut_*.png"))
window.hide()
selection = Selector(QApplication.primaryScreen(), "ScreenCut selection test")
selected = []
selection.selected.connect(selected.append)
selection.show()
app.processEvents()
QTest.mousePress(selection, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
QTest.mouseMove(selection, QPoint(300, 250))
QTest.mouseRelease(selection, Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
assert selected and selected[0]["width"] >= 200
selection.hide()
selection.deleteLater()
fixture = QLabel()
fixture.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
fixture.setGeometry(150, 150, 500, 600)
rng = np.random.default_rng(123)
page = rng.integers(0, 256, (1800, 500, 3), dtype=np.uint8)
fixture.setPixmap(QPixmap.fromImage(as_image(page[:600])))
fixture.show()
app.processEvents()
screen = fixture.screen()
mx, my, mw, mh = monitor_rect(screen.name(), screen.geometry(), screen.devicePixelRatio())
scale = mw / screen.geometry().width()
point = fixture.mapToGlobal(fixture.rect().topLeft())
region = dict(left=mx+round((point.x()-screen.geometry().x())*scale),
              top=my+round((point.y()-screen.geometry().y())*scale),
              width=round(500*scale), height=round(600*scale))

def settle():
    until = time.monotonic()+.3
    while time.monotonic() < until:
        app.processEvents()
        time.sleep(.01)

settle()
stitch = Stitcher(capture(region))
for offset in (150, 300, 450):
    fixture.setPixmap(QPixmap.fromImage(as_image(page[offset:offset+600])))
    settle()
    result, shift = stitch.append(capture(region))
    assert result == "added", result
assert stitch.height == round(1050*scale), stitch.height
as_image(stitch.image()).save(str(out / "live-stitch.png"))
recorder = Recorder(region, out / "recording-smoke.mp4", 10)
errors = []
recorder.completed.connect(lambda path, error: errors.append(error))
recorder.start()
until = time.monotonic()+2.2
while time.monotonic() < until:
    app.processEvents()
    time.sleep(.02)
recorder.stop_event.set()
assert recorder.wait(15000), "Recording finalization timeout"
app.processEvents()
assert not any(errors), errors
video = cv2.VideoCapture(str(out / "recording-smoke.mp4"))
assert video.isOpened()
frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
assert frames >= 15, frames
ok, frame = video.read()
assert ok and frame.shape[:2] == (region["height"]//2*2, region["width"]//2*2)
video.release()
class SyntheticMicrophone:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
    def start(self):
        self.callback(np.zeros((48000*2, 1), dtype=np.float32), 96000, None, None)
    def stop(self):
        pass
    def close(self):
        pass

with patch("screencut.recorder.sd.query_devices", return_value={"default_samplerate":48000}), patch("screencut.recorder.sd.InputStream", SyntheticMicrophone):
    audio_recorder = Recorder(region, out / "audio-smoke.mp4", 10, True)
    audio_errors = []
    audio_recorder.completed.connect(lambda path, error: audio_errors.append(error))
    audio_recorder.start()
    until = time.monotonic()+1.2
    while time.monotonic() < until:
        app.processEvents()
        time.sleep(.02)
    audio_recorder.stop_event.set()
    assert audio_recorder.wait(15000)
    app.processEvents()
    assert audio_errors == [""], audio_errors
import subprocess
import imageio_ffmpeg
probe = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(out / "audio-smoke.mp4")], capture_output=True, text=True)
assert "Audio: aac" in probe.stderr, probe.stderr
window.open_record_panel()
assert window.mode == "record_ready"
assert not window.mic_button.isChecked()
window.bar.hide()
window.dispatch("record")
assert window.bar.isVisible() and window.mode == "record_ready"
window.cancel_session()
assert window.mode is None
window.hotkeys.clear()
window.tray.hide()
print(f"PASS: six-language UI renders, clipboard, PNG, live capture stitching, MP4 {frames} frames")
