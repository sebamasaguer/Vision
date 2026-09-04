param([Parameter(Mandatory=$true)][string]$VideoPath)
$ErrorActionPreference="Stop"
$ProjectPath=Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
$src=(Resolve-Path $VideoPath).Path
$dst=Join-Path $ProjectPath "demo\demo_camera.mp4"
if (Test-Path $dst) { Copy-Item $dst (Join-Path $ProjectPath ("demo\demo_camera_backup_"+(Get-Date -Format 'yyyyMMdd-HHmmss')+".mp4")) -Force }
Copy-Item $src $dst -Force
Write-Host "[OK] MP4 copiado a demo\demo_camera.mp4" -ForegroundColor Green
# La imagen backend incluye ffprobe (paquete ffmpeg).
docker compose run --rm --no-deps camera-worker ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -of default=nw=1 /demo/demo_camera.mp4
if ($LASTEXITCODE -ne 0) { throw "Video MP4 no validado por ffprobe." }
docker compose restart camera-worker vision-engine
Write-Host "[OK] camera-worker y vision-engine reiniciados." -ForegroundColor Green
Write-Host "Abra http://localhost:5200 -> Vision IA y active IA PERSONAS para DEMO01." -ForegroundColor Cyan
