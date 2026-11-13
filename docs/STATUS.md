# Current status — 2026-11-12 (America/New_York)

Version: **0.1.0 preview**, Windows desktop application.

## Implemented

- Light capture dashboard, image preview, preferences, system tray, single-instance guard.
- User-configurable global hotkeys with actual registration conflict reporting.
- Region capture to clipboard, paste via Ctrl+V, save latest capture as PNG.
- 0–60 second delayed capture, frozen selection overlay and cancellation.
- Downward manual scrolling capture with automatic stable-frame overlap matching and clipboard output.
- Region MP4 recording at 5–30 FPS, same-hotkey stop, background encoding and finalization.
- Six UI languages, save directory, persistent JSON settings and runtime log.
- Build and desktop shortcut scripts, unit tests and desktop smoke checks.

## Verified

- 9 unit tests passed, including exact multi-frame stitching and rejection of ambiguous/reversed/skipped frames.
- Six language dashboard/settings renders generated; Chinese settings and French dashboard visually inspected.
- Real MSS capture of a synthetic scrolling desktop surface stitched successfully on this machine at 150% display scaling.
- Clipboard image transfer, PNG save, MP4 encoding and decoded dimensions passed; 2.2-second test produced 22 frames at 10 FPS.
- Native app main window and preference controls inspected through desktop UI. Alt+C and Alt+A conflict with existing software on this machine; remaining default keys registered in the first single-instance run.
- GitHub private repository created. Final build and remote sync outcome is recorded in DEVLOG.

## Limitations / next work

1. Validate diverse actual browser pages, sticky headers, nested containers, zoom, lazy loading and smooth scroll. Current algorithm deliberately rejects uncertain matches; use manual slow scrolling and exclude fixed UI.
2. Add automatic scrolling with explicit target-window ownership and abort controls.
3. Test mixed DPI/multi-monitor/HDR/remote desktop. One display per selection in v0.1.
4. Add audio recording, robust real-time timing/performance telemetry, cursor capture, pause/resume.
5. Add annotation tools, screenshot history, OCR, signed installer and update mechanism.
6. Human review of French/Spanish/Korean/Japanese wording, keyboard accessibility and smaller display layouts.

Do not describe this release as fully equivalent to PixPin or as production hardened.
