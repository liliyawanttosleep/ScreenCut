$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$executable = Join-Path $project 'dist\ScreenCut\ScreenCut.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Build ScreenCut first' }
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $desktop 'ScreenCut.lnk'))
$link.TargetPath = $executable
$link.WorkingDirectory = $project
$link.Description = 'ScreenCut - Capture, scroll and record'
$link.Save()
