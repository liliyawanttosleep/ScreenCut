import threading
import time
import numpy as np
import mss
import imageio_ffmpeg
from PySide6.QtCore import QThread, Signal

class Recorder(QThread):
    completed = Signal(str, str)

    def __init__(self, region, path, fps):
        super().__init__()
        self.region, self.path, self.fps = region, str(path), fps
        self.stop_event = threading.Event()

    def run(self):
        writer = None
        error = ""
        try:
            width = self.region["width"] // 2 * 2
            height = self.region["height"] // 2 * 2
            writer = imageio_ffmpeg.write_frames(self.path, (width, height), fps=self.fps,
                codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p", macro_block_size=1,
                output_params=["-preset", "ultrafast", "-crf", "22", "-movflags", "+faststart"])
            writer.send(None)
            started = time.perf_counter()
            count = 0
            with mss.mss() as capture:
                while not self.stop_event.is_set():
                    frame = np.array(capture.grab(self.region))[:height, :width, :3][:, :, ::-1].copy()
                    writer.send(frame)
                    count += 1
                    self.stop_event.wait(max(0, started + count / self.fps - time.perf_counter()))
        except Exception as exc:
            error = str(exc)
        finally:
            if writer:
                try:
                    writer.close()
                except Exception as exc:
                    error = error or str(exc)
            self.completed.emit(self.path, error)
