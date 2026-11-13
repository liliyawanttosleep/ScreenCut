if __name__ == "__main__":
    try:
        from screencut.app import main
        raise SystemExit(main())
    except Exception:
        import os
        import traceback
        from pathlib import Path
        folder = Path(os.environ.get("APPDATA", str(Path.home()))) / "ScreenCut"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
