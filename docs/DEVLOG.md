# Development log

## 2026-11-12 — Faster scroll sampling, themes and compact recording toolbar

Changed scroll timer from 500ms to 80ms (target, not guaranteed end-to-end throughput); sampled stability comparisons and horizontal template columns reduce matching work without reducing vertical resolution. Reliability gates remain in place.

Added persisted light/dark/system themes, tighter typography and window proportions. Replaced recording controls with a 270×54 dark frameless toolbar at top-left: timer, vector region/start/stop/microphone icons; context-menu hide and Alt+G restore retained. No emoji microphone artwork.

Recording settings now allow 5–120 FPS (new-install default 60). RGB 4:4:4 high-quality and lossless H.264 modes preserve original pixel dimensions, including odd sizes. Slow capture repeats frames to better preserve duration; this does not create missing motion frames. Hardware encoder/HDR and sustained 120 FPS at full desktop resolution remain unverified. RGB H.264 playback compatibility is narrower than yuv420p.

After encoding finishes, Save As opens at the configured folder. Cancelling keeps the existing recording in that folder; relocation failure retains the original. Tests: 9 core tests; theme/toolbar renders inspected; 60-FPS target smoke produced 128 frames over ~2.2 seconds, odd-dimension lossless decoded RGB matched captured pixels exactly; AAC mux passed. This fixture is not a full-screen performance benchmark.

## 2026-11-12 — Capture semantics and recording controls revision

User clarified Alt+C clipboard-only, Alt+A a fresh selection followed by Save As initialized at the configured folder, Alt+F direct scrolling mode, and Alt+G a reusable recording panel. Implemented these semantics, live selection pixel dimensions, configurable blue-default border, recording panel start/stop, elapsed timer, context-menu hide and Alt+G restore. Full-screen is default; region selection is optional. Microphone is opt-in before recording; WAV capture is muxed into AAC MP4 after video finalization. System audio and mid-recording microphone toggling are not implemented.

Enabled current-user Run entry ScreenCut pointing to the installed D: EXE. Located PixPin startup in scheduled task `\PixPin\Autorun for Wentao` and verified it is Disabled. Did not terminate PixPin; existing hotkey conflicts can remain until PixPin exits.

Validation includes existing core tests, source UI/selection smoke, silent MP4 decode and synthetic-microphone AAC mux verification. Synthetic audio verifies the pipeline, not physical microphone permissions/quality. No personal microphone audio is captured by these tests.

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

## 2026-11-12 — Packaging and repository delivery

PyInstaller initially collected a conflicting ICU DLL from unrelated tools in the inherited PATH, causing QtCore import failure in the EXE. Isolated the build PATH to Windows + standalone Python and rebuilt successfully. Added startup-error.log for future import diagnostics and a custom application icon. The packaged desktop main window was then observed running successfully.

Created `ScreenCut.lnk` on the user's Windows desktop, targeting `D:\Projects\ScreenCut\dist\ScreenCut\ScreenCut.exe`. Added a titled capture overlay and a Qt mouse-selection smoke check to improve testability.

Uploaded source, tests and handoff documents to private GitHub main. The first upload was rejected because the existing OAuth credential lacks `workflow` scope. Kept the CI configuration as `docs/windows-ci.yml` instead of requesting broader permissions; it is a template, not an active GitHub Actions workflow. Source upload subsequently succeeded.

Current boundaries remain manual downward scrolling, no recording audio and no mixed-monitor qualification. Follow-up features are listed in STATUS. Do not commit local artifacts or personal media.
