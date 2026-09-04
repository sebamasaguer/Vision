$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$src=Join-Path $root 'demo\person_demo_pd.mp4'
$dst=Join-Path $root 'demo\demo_camera.mp4'
if (-not (Test-Path $src)) { throw 'Falta demo/person_demo_pd.mp4' }
if (Test-Path $dst) { Copy-Item $dst (Join-Path $root ("demo\demo_camera.pre-ppe-"+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.mp4')) -Force }
Copy-Item $src $dst -Force
Write-Host '[OK] Demo Camera cambiada al clip PERSON QA.' -ForegroundColor Green
Write-Host 'En Visión IA: active IA PERSONAS + IA EPP. Esperado: HELMET=NO_DETECTADO, VEST=NO_DETECTADO, SAFETY_SHOES=NO_VISIBLE.' -ForegroundColor Cyan
