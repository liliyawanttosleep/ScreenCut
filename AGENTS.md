# ScreenCut agent handoff

## Start here

1. Read `docs/STATUS.md`, `docs/DEVLOG.md`, and `docs/ARCHITECTURE.md` before editing.
2. Canonical user project: `D:\Projects\ScreenCut`. The Codex bootstrap workspace was `C:\Users\Wentao\Documents\ChatGPT\screencut`; it is a synchronized development copy, not the installed application. Work in D: for future changes and avoid diverging copies.
3. Inspect `git status`, branch and remote. Preserve user changes. Remote: `https://github.com/liliyawanttosleep/ScreenCut.git` (private).
4. Use the project `.venv` with standalone CPython, not Anaconda. Do not change global Python packages.

## Product contract

- Windows native desktop app, clean light UI, six languages (zh/en/fr/es/ko/ja).
- Preserve configurable default hotkeys: Alt+C copy capture; Alt+V paste; Alt+A fresh selection then Save As; Alt+F scrolling capture toggle; Alt+G open/restore recording controls (never stops recording); Alt+D delayed capture.
- Recording starts/stops from its panel; default full screen with optional region. Microphone is opt-in before recording. Preserve timer, hide context menu and restore shortcut. Default selection border is blue; show physical pixel dimensions.
- System audio uses default-output WASAPI loopback and is independent from microphone input. Preserve separate toggles and live recording gains (0–200%) in the toolbar ellipsis. These must never modify OS volume. Enable sources before recording; zero gain mutes during recording. Test real loopback with `scripts/smoke.py --loopback`; it plays a quiet synthetic tone and uses a synthetic microphone.
- Report global shortcut conflicts; never silently steal keys or terminate another program.
- Capture only on explicit user action. Never upload screenshots or recordings. Keep personal output and settings out of Git.
- Reject uncertain scroll matches rather than silently corrupting long images. Preserve cancel/finish controls and bounded memory use.
- Keep the desktop shortcut pointing to the current D: build.
- No agent delegation unless the user asks for it.

## Verification and handoff

- Run `python -m unittest discover -s tests -v` for core changes.
- Run `python scripts/smoke.py` for capture/recording/UI changes on an unlocked desktop; this changes the clipboard and records only the synthetic test surface.
- Test real user flows separately. Synthetic stitching tests do not prove browser compatibility; file generation does not prove audio support.
- Update STATUS, append DEVLOG with changes, tests, limits and next steps; commit and push when the user asks to sync progress. Do not claim remote upload without verifying the remote hash.
- Avoid committing `.venv`, binaries, personal captures, logs, settings or tokens. Publish build artifacts separately when authorized.

## Persistent user LaTeX preference

If any later task introduces LaTeX, compile the real editable source with `-synctex=1` and `-recorder`; keep matching `.synctex.gz` beside the exact viewed PDF. Preserve a single main/root file, engine, job name and output directory (existing LaTeX Workshop default `%DIR%/output/pdf`). Rebuild and validate both `synctex view` and `synctex edit`. Keep internal PDF viewing, reverse-sync double-click and `wentao-local.latex-click-sync` enabled. Use XeLaTeX/LuaLaTeX for Chinese. Validate Codex UI navigation separately and never claim UI gestures were tested from mapping files alone. Do not promise character-accurate mapping for macros/math/raster images.
