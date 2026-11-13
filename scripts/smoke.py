"""Developer smoke checks. Run from repository root; artifacts stay untracked."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap
from screencut.app import MainWindow, STYLE, as_image, capture
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
window.save_latest()
assert list(out.glob("ScreenCut_*.png"))
window.hide()
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
window.hotkeys.clear()
window.tray.hide()
print(f"PASS: six-language UI renders, clipboard, PNG, live capture stitching, MP4 {frames} frames")
