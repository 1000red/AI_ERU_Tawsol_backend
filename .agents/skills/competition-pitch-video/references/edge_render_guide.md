# Headless Edge RGBA 32-Bit Transparency Guide

When rendering presentation slides with transparent glassmorphism over dynamic video backgrounds, headless Chromium/Edge provides pixel-perfect typography, modern CSS layouts (`backdrop-filter`, CSS grids, custom webfonts), and true 32-bit alpha channel export.

## Edge Binary Detection
Locate Microsoft Edge on Windows:
```powershell
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edgePath)) {
    $edgePath = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
}
```

## Mandatory CLI Flags for Transparent Screenshots
* `--headless=new`: Utilizes the modern headless implementation which supports full CSS filters, web fonts, and accurate layout calculation.
* `--window-size=1920,1080`: Locks viewport resolution to 1080p full HD.
* `--default-background-color=00000000`: Sets the default canvas background to completely transparent (RGBA 0,0,0,0) instead of the default solid white.
* `--hide-scrollbars`: Hides scrollbars from captured screenshots.
* `--virtual-time-budget=2000`: Allows 2 seconds for external Google Fonts (`Cairo`, `Inter`) and inline base64 images to settle before capturing.

## Batch Render Script Snippet
```powershell
param([string]$htmlDir, [string]$outDir)

Get-ChildItem -Path $htmlDir -Filter "*.html" | ForEach-Object {
    $slideName = $_.BaseName
    $outFile = Join-Path $outDir "$slideName.png"
    $url = "file:///" + $_.FullName.Replace('\', '/')
    
    & $edgePath --headless=new `
      --screenshot="$outFile" `
      --window-size=1920,1080 `
      --default-background-color=00000000 `
      --hide-scrollbars `
      --virtual-time-budget=2000 `
      "$url"
}
```
