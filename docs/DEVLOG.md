# Development log

## 2026-11-12 — Initial implementation

User requested a Windows screenshot product resembling the supplied PixPin hotkey settings reference, with configurable screenshot/copy/paste/save/scroll/record hotkeys, delayed capture, six languages, D: project storage, desktop shortcut and GitHub progress tracking.

Created ScreenCut with Python 3.13, PySide6, MSS, OpenCV and imageio-ffmpeg. Implemented capture UI, tray, Win32 global shortcuts, persistent settings, selector overlays, scroll stitching, clipboard/PNG export and MP4 worker. Added Chinese/English/French/Spanish/Korean/Japanese catalog.

Important fixes found during validation:
- Anaconda-based virtual environment could not load QtCore. Repointed the project venv to the installed standalone CPython 3.13.
- Qt 6 reports this screen's EDID friendly name instead of the Win32 DISPLAY device name. Added validated geometry/DPI fallback; real capture subsequently passed.
- Suspend global shortcut registration while editing a key sequence and during synthesized paste to prevent interception/recursion.
- Still captures crop the frozen overlay image, preserving delayed capture timing.
- Moved Save preferences outside the scroll area so it stays reachable; corrected UI font selection.

Checks: 9/9 unit tests; six-language UI renders; live synthetic screen stitching; clipboard and PNG; H.264 MP4 round-trip decode (22 frames at 10 FPS in latest run). User desktop inspected: Alt+C and Alt+A are occupied by another application. No other application was terminated.

GitHub: private `liliyawanttosleep/ScreenCut` created in the authenticated browser. The GitHub connector initially returned 404 for the new private repository; Git Credential Manager access via Git works. Use Git for repository sync. Never print stored credentials.

Pending final delivery steps at this entry: finish PyInstaller packaging, create desktop shortcut, launch packaged app, commit and verify remote main hash. Update this log when those steps complete.
