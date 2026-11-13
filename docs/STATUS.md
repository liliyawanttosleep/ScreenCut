# Current status — 2026-11-12 (America/New_York)

Version: **0.1.0 preview**, Windows desktop application.

Audio revision: separate default-output WASAPI loopback and default microphone; separate enable buttons before start and live 0–200% recording gains in the toolbar ellipsis. System audio defaults on, microphone defaults off. Previous notes below about no system audio are historical. Capture is device-wide, not application-specific.

Newest revision: 80ms scroll sampling; compact 270×54 icon toolbar; light/dark/system theme; recording Save As after stop; 5–120 target FPS; RGB high-quality/lossless options preserving odd dimensions. New-install default 60 FPS; existing user FPS is retained. Pixel-exact lossless fixture and 60-FPS target smoke passed. See latest DEVLOG for limits.

Latest revision: Alt+A now selects a fresh capture then opens Save As; configurable blue border and pixel dimensions added. Alt+G opens/restores a full-screen-or-region recording panel with timer, hide menu and opt-in microphone. Microphone setting is fixed during a recording; no system audio. Current-user autostart enabled; PixPin scheduled autostart disabled. See latest DEVLOG entry; earlier verification below describes the initial release.

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
- Packaged EXE main window launched and inspected; desktop shortcut targets the D: build.
- GitHub private repository created and source uploaded to main. CI is a documentation template only because current credentials lack workflow scope.

## Limitations / next work

1. Validate diverse actual browser pages, sticky headers, nested containers, zoom, lazy loading and smooth scroll. Current algorithm deliberately rejects uncertain matches; use manual slow scrolling and exclude fixed UI.
2. Add automatic scrolling with explicit target-window ownership and abort controls.
3. Test mixed DPI/multi-monitor/HDR/remote desktop. One display per selection in v0.1.
4. Add audio recording, robust real-time timing/performance telemetry, cursor capture, pause/resume.
5. Add annotation tools, screenshot history, OCR, signed installer and update mechanism.
6. Human review of French/Spanish/Korean/Japanese wording, keyboard accessibility and smaller display layouts.

Do not describe this release as fully equivalent to PixPin or as production hardened.
