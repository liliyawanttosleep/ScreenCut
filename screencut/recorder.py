import threading
import time
import numpy as np
import mss
import imageio_ffmpeg
import subprocess
from pathlib import Path
import sounddevice as sd
import soundfile as sf
import pyaudiowpatch as pa
from PySide6.QtCore import QThread, Signal

class Recorder(QThread):
    completed = Signal(str, str)

    def __init__(self, region, path, fps, microphone=False, quality="high", system_audio=False, mic_gain=1.0, system_gain=1.0):
        super().__init__()
        self.region, self.path, self.fps = region, str(path), fps
        self.stop_event = threading.Event()
        self.microphone = microphone
        self.quality = quality
        self.system_audio = system_audio
        self.mic_gain, self.system_gain = mic_gain, system_gain

    def run(self):
        writer = None
        error = ""
        stream = audio_file = None
        audio_path = self.path + ".wav"
        system_path = self.path + ".system.wav"
        system_stream = system_file = audio_host = None
        audio_started = time.perf_counter()
        try:
            if self.system_audio:
                audio_host = pa.PyAudio()
                device = audio_host.get_default_wasapi_loopback()
                rate_system = int(device["defaultSampleRate"])
                channels = min(2, int(device["maxInputChannels"]))
                system_file = sf.SoundFile(system_path, mode="w", samplerate=rate_system, channels=channels, subtype="FLOAT")
                def system_callback(data, frames, timing, status):
                    # WASAPI can stop delivering buffers during silence. Preserve the timeline.
                    target = max(0, int((time.perf_counter()-audio_started)*rate_system)-frames)
                    gap = target-system_file.tell()
                    if gap > rate_system//10:
                        system_file.write(np.zeros((gap, channels), dtype=np.float32))
                    block = np.frombuffer(data, dtype=np.float32).reshape(-1, channels)
                    system_file.write(block * self.system_gain)
                    return None, pa.paContinue
                system_stream = audio_host.open(format=pa.paFloat32, channels=channels,
                    rate=rate_system, input=True, input_device_index=int(device["index"]),
                    frames_per_buffer=1024, stream_callback=system_callback, start=False)
            if self.microphone:
                rate = int(sd.query_devices(kind="input")["default_samplerate"])
                audio_file = sf.SoundFile(audio_path, mode="w", samplerate=rate, channels=1)
                def audio_callback(data, frames, timing, status):
                    audio_file.write(np.clip(data*self.mic_gain, -1, 1))
                stream = sd.InputStream(samplerate=rate, channels=1, callback=audio_callback)
            width = self.region["width"]
            height = self.region["height"]
            writer = imageio_ffmpeg.write_frames(self.path, (width, height), fps=self.fps,
                codec="libx264rgb", pix_fmt_in="rgb24", pix_fmt_out="bgr24", macro_block_size=1,
                output_params=["-preset", "ultrafast", "-crf", "0" if self.quality == "lossless" else "16", "-movflags", "+faststart"])
            writer.send(None)
            started = time.perf_counter()
            audio_started = started
            if stream:
                stream.start()
            if system_stream:
                system_stream.start_stream()
            count = 0
            with mss.mss() as capture:
                while not self.stop_event.is_set():
                    frame = np.array(capture.grab(self.region))[:height, :width, :3][:, :, ::-1].copy()
                    writer.send(frame)
                    count += 1
                    # Preserve wall-clock duration when capture cannot sustain requested FPS.
                    due = int((time.perf_counter()-started)*self.fps)
                    for _ in range(min(max(0, due-count), self.fps)):
                        writer.send(frame)
                        count += 1
                    self.stop_event.wait(max(0, started + count / self.fps - time.perf_counter()))
        except Exception as exc:
            error = str(exc)
        finally:
            if system_stream:
                system_stream.stop_stream()
                system_stream.close()
            if system_file:
                if system_file.tell() == 0:
                    system_file.write(np.zeros((1024, channels), dtype=np.float32))
                system_file.close()
            if audio_host:
                audio_host.terminate()
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
            if (self.microphone or self.system_audio) and not error:
                try:
                    merged = self.path + ".mux.mp4"
                    tracks = ([audio_path] if self.microphone else []) + ([system_path] if self.system_audio else [])
                    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", self.path]
                    for track in tracks:
                        command += ["-i", track]
                    inputs = "".join(f"[{i+1}:a]" for i in range(len(tracks)))
                    graph = inputs + f"amix=inputs={len(tracks)}:normalize=0,alimiter=limit=0.95:level=0,apad[a]"
                    subprocess.run(command + ["-filter_complex", graph, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", merged],
                        check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    Path(merged).replace(self.path)
                    for track in tracks:
                        Path(track).unlink(missing_ok=True)
                except Exception as exc:
                    error = str(exc)
            self.completed.emit(self.path, error)
