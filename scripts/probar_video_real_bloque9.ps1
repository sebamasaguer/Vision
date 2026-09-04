param(
    [string]$ProjectPath = (Get-Location).Path,
    [string]$VideoPath,
    [int]$MaxSeconds = 60
)
$ErrorActionPreference='Stop'
$ProjectPath=(Resolve-Path $ProjectPath).Path
Set-Location $ProjectPath
$model=Join-Path $ProjectPath 'models\bootstrap\intel-worker-safety\model.xml'
if(-not (Test-Path $model)){throw 'Bootstrap Intel no instalado. Ejecute .\scripts\instalar_bootstrap_intel_bloque9.ps1'}
if($VideoPath){
    $src=(Resolve-Path $VideoPath).Path
    $ext=[IO.Path]::GetExtension($src); if(-not $ext){$ext='.mp4'}
    $local=Join-Path $ProjectPath "demo\block9_real_input$ext"
    Copy-Item $src $local -Force
    $containerInput="/demo/block9_real_input$ext"
}else{
    $local=Join-Path $ProjectPath 'demo\intel_worker_safety_test.avi'
    if(-not (Test-Path $local)){throw 'No hay VideoPath ni demo Intel. Reinstale bootstrap sin -SkipSampleVideo.'}
    $containerInput='/demo/intel_worker_safety_test.avi'
}
New-Item -ItemType Directory -Force (Join-Path $ProjectPath 'reports\block9') | Out-Null
Write-Host 'Ejecutando detector REAL de HELMET/VEST sobre video...' -ForegroundColor Cyan
& docker compose exec -T vision-engine python -m app.run_real_video_ppe --input $containerInput --output /reports/block9/real_video_annotated.mp4 --max-seconds $MaxSeconds
if($LASTEXITCODE -ne 0){throw 'Smoke de video real fallo.'}
$out=Join-Path $ProjectPath 'reports\block9\real_video_annotated.mp4'
$json=Join-Path $ProjectPath 'reports\block9\real_video_annotated.json'
if(-not (Test-Path $out)){throw 'No se genero video anotado.'}
Write-Host "[PASS] VIDEO REAL PROCESADO: $out" -ForegroundColor Green
if(Test-Path $json){Get-Content $json}
