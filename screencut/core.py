"""Capture-independent stitching and persistent settings."""
import json
import os
from pathlib import Path
import cv2
import numpy as np

DEFAULT_KEYS = {"copy": "Alt+C", "paste": "Alt+V", "save": "Alt+A",
                "scroll": "Alt+F", "record": "Alt+G", "delay": "Alt+D"}

def settings_path():
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "ScreenCut" / "settings.json"

def load_settings(path=None):
    path = path or settings_path()
    default = dict(language="zh", folder=str(Path.home() / "Pictures" / "ScreenCut"),
                   delay=3, fps=15, hotkeys=DEFAULT_KEYS.copy())
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        for k in ("language", "folder"):
            if isinstance(raw.get(k), str):
                default[k] = raw[k]
        for k, low, high in (("delay", 0, 60), ("fps", 5, 30)):
            default[k] = max(low, min(high, int(raw.get(k, default[k]))))
        for k, value in raw.get("hotkeys", {}).items():
            if k in DEFAULT_KEYS and isinstance(value, str):
                default["hotkeys"][k] = value
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return default

def save_settings(settings, path=None):
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)

class Stitcher:
    """Append downward scrolls only; reject ambiguous frames instead of inventing content.

    The selected region should exclude browser chrome and sticky headers/footers.
    Keep at least 35% overlap between settled frames. RGB uint8 input.
    """
    def __init__(self, first, max_pixels=70_000_000):
        self.previous = first.copy()
        self.parts = [first.copy()]
        self.height = first.shape[0]
        self.max_pixels = max_pixels

    def append(self, frame):
        prev = self.previous
        if frame.shape != prev.shape:
            return "mismatch", 0
        if np.mean(np.abs(frame.astype(np.int16) - prev.astype(np.int16))) < 1.2:
            return "unchanged", 0
        h, w = frame.shape[:2]
        margin = max(4, w // 12)
        old = cv2.cvtColor(prev[:, margin:w-margin], cv2.COLOR_RGB2GRAY)
        new = cv2.cvtColor(frame[:, margin:w-margin], cv2.COLOR_RGB2GRAY)
        # A band inside the new viewport must have occurred lower in the previous one.
        anchor, band = h // 10, max(24, h // 5)
        template = new[anchor:anchor+band]
        if template.std() < 6:
            return "ambiguous", 0
        result = cv2.matchTemplate(old, template, cv2.TM_CCOEFF_NORMED).ravel()
        end = min(len(result), anchor + int(h * .65))
        candidates = result[anchor+2:end]
        if not len(candidates):
            return "mismatch", 0
        best = int(candidates.argmax()) + anchor + 2
        shift = best - anchor
        score = float(result[best])
        others = candidates.copy()
        at = best - anchor - 2
        others[max(0, at-4):at+5] = -1
        if score < .94 or (len(others) and score - float(others.max()) < .015):
            return "ambiguous", 0
        overlap_old = prev[shift:]
        overlap_new = frame[:h-shift]
        error = np.mean(np.abs(overlap_old.astype(np.int16) - overlap_new.astype(np.int16)))
        if error > 13:
            return "mismatch", 0
        if (self.height + shift) * w > self.max_pixels:
            return "limit", 0
        self.parts.append(frame[-shift:].copy())
        self.height += shift
        self.previous = frame.copy()
        return "added", shift

    def image(self):
        return np.concatenate(self.parts, axis=0)
