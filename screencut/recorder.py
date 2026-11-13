import threading
import time
import numpy as np
import mss
import imageio_ffmpeg
import subprocess
from pathlib import Path
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QThread, Signal

class Recorder(QThread):
    completed = Signal(str, str)

    def __init__(self, region, path, fps, microphone=False):
        super().__init__()
        self.region, self.path, self.fps = region, str(path), fps
        self.stop_event = threading.Event()
        self.microphone = microphone

    def run(self):
        writer = None
        error = ""
        stream = audio_file = None
        audio_path = self.path + ".wav"
        try:
            if self.microphone:
                rate = int(sd.query_devices(kind="input")["default_samplerate"])
                audio_file = sf.SoundFile(audio_path, mode="w", samplerate=rate, channels=1)
                def audio_callback(data, frames, timing, status):
                    audio_file.write(data)
                stream = sd.InputStream(samplerate=rate, channels=1, callback=audio_callback)
                stream.start()
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
            if stream:
                stream.stop()
                stream.close()
            if audio_file:
                audio_file.close()
            if writer:
                try:
                    writer.close()
                except Exception as exc:
                    error = error or str(exc)
            if self.microphone and not error:
                try:
                    merged = self.path + ".mux.mp4"
                    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", self.path,
                        "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-shortest", merged],
                        check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    Path(merged).replace(self.path)
                    Path(audio_path).unlink(missing_ok=True)
                except Exception as exc:
                    error = str(exc)
            self.completed.emit(self.path, error)
