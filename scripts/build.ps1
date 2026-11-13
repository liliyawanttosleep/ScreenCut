$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    python -m venv .venv
}
& $python -m pip install -r requirements.txt 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
$previousPath = $env:PATH
try {
    # Prevent unrelated apps (Conda, PDF tools, etc.) from supplying incompatible ICU/CRT DLLs.
    $basePython = & $python -c 'import sys; print(sys.base_prefix)'
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$basePython;$(Split-Path $python)"
    & $python -m PyInstaller --clean --noconfirm --windowed --onedir --name ScreenCut --icon assets/screencut.ico --collect-all imageio_ffmpeg --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets run.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    $env:PATH = $previousPath
}
