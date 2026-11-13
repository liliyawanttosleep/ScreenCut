# Architecture

- `run.py`: executable entry.
- `screencut/app.py`: Qt main window, preferences, tray, screen selection overlays, capture state machine and scroll sampling timer.
- `screencut/core.py`: atomic JSON preferences, RGB downward scroll stitcher independent of UI.
- `screencut/native.py`: Win32 RegisterHotKey/UnregisterHotKey, WM_HOTKEY event filter, SendInput paste, physical display enumeration.
- `screencut/recorder.py`: worker QThread with MSS screen capture and bundled imageio-ffmpeg H.264 writer.
- `screencut/i18n.py`: six-column complete translation catalog.

State transitions: idle → selecting → copy/save → idle; idle → delay → selecting → copy; idle → selecting → scroll → finish/cancel → idle; idle → selecting → record → finalizing → idle. A second capture request during an active session is ignored except the corresponding stop shortcut.

Screenshot overlays freeze each screen before selection. Logical Qt selection coordinates map to native physical pixels using Win32 display rectangles and per-screen scale. The frozen image is cropped for still captures; MSS captures live pixels for scrolling and video. Qt 6 may return EDID monitor names rather than DISPLAY names; native lookup has a checked origin/size fallback.

Scrolling samples twice per second and compares successive samples for stability. Template matching finds the vertical displacement against the last accepted frame. A correlation threshold, uniqueness margin and full overlap error check reject uncertain matches. Only the new bottom strip is appended. Memory is bounded by a 70-million-pixel output limit; concatenation temporarily increases peak memory. Long pages should be split when the limit is reached.

Hotkeys use MOD_NOREPEAT. Editing a shortcut temporarily unregisters ScreenCut keys so key recording is possible. Paste waits for modifiers to be released and checks the foreground window has not changed; registration is briefly suspended during Ctrl+V injection to prevent shortcut recursion. Integrity-level restrictions may block SendInput.

Recording runs outside the UI thread. Stop signals an Event, then closes the encoder and emits completion. Normal quit waits for finalization. Force termination can lose an MP4. Odd dimensions are trimmed by at most one pixel for yuv420p. No audio and no mouse cursor overlay.

References:
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
- https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractNativeEventFilter.html
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput

Known engineering debt: scroll matching is on the UI thread; move to a bounded worker for very large selections. Add foreground-window/occlusion tracking for scroll capture, richer stability heuristics and video timing telemetry. Add IPC to reopen the original window when a second instance starts (currently it shows a tray reminder).
