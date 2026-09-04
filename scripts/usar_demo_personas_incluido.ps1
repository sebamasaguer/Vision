$ErrorActionPreference="Stop"
$ProjectPath=Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
$src=Join-Path $ProjectPath "demo\person_demo_pd.mp4"
$dst=Join-Path $ProjectPath "demo\demo_camera.mp4"
if(-not (Test-Path $src)){throw "Falta demo\person_demo_pd.mp4"}
if(Test-Path $dst){Copy-Item $dst (Join-Path $ProjectPath ("demo\demo_camera_backup_"+(Get-Date -Format 'yyyyMMdd-HHmmss')+".mp4")) -Force}
Copy-Item $src $dst -Force
Write-Host "[OK] Demo de persona publica activada como demo_camera.mp4." -ForegroundColor Green
docker compose restart camera-worker vision-engine
Write-Host "Abra http://localhost:5200 -> Vision IA y active IA PERSONAS para DEMO01." -ForegroundColor Cyan
