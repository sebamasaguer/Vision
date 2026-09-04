param(
    [Parameter(Mandatory=$true)][string]$VideoPath,
    [string]$ProjectPath=(Get-Location).Path,
    [string]$Version='v0001',
    [double]$EverySeconds=1.0,
    [int]$MaxImages=500
)
$ErrorActionPreference='Stop'; $ProjectPath=(Resolve-Path $ProjectPath).Path; Set-Location $ProjectPath
$src=(Resolve-Path $VideoPath).Path; $ext=[IO.Path]::GetExtension($src); if(-not $ext){$ext='.mp4'}
$dst=Join-Path $ProjectPath "demo\dataset_source$ext"; Copy-Item $src $dst -Force
$containerInput="/demo/dataset_source$ext"; $containerOut="/opt/hys-datasets/HYS-PPE/$Version/source"
& docker compose exec -T backend python -m app.dataset_tool extract --input $containerInput --output $containerOut --every-seconds $EverySeconds --max-images $MaxImages
if($LASTEXITCODE -ne 0){throw 'Extraccion dataset fallo.'}
$labels=Join-Path $ProjectPath "datasets\HYS-PPE\$Version\source\labels"; New-Item -ItemType Directory -Force $labels | Out-Null
Write-Host '[PASS] FRAMES HYS EXTRAIDOS' -ForegroundColor Green
Write-Host "Etiquete cada imagen con YOLO normalized en: $labels" -ForegroundColor Cyan
Write-Host 'Clases: 0=HELMET 1=VEST 2=SAFETY_SHOES' -ForegroundColor Cyan
