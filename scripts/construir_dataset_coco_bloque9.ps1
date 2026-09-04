param([string]$ProjectPath=(Get-Location).Path,[string]$Version='v0001')
$ErrorActionPreference='Stop'; $ProjectPath=(Resolve-Path $ProjectPath).Path; Set-Location $ProjectPath
$source="/opt/hys-datasets/HYS-PPE/$Version/source"; $out="/opt/hys-datasets/HYS-PPE/$Version/COCO"
& docker compose exec -T backend python -m app.dataset_tool build-coco --source $source --output $out --classes HELMET,VEST,SAFETY_SHOES --version $Version --license PROPRIETARY-HYS
if($LASTEXITCODE -ne 0){throw 'Build COCO fallo.'}
$manifest="/opt/hys-datasets/HYS-PPE/$Version/COCO/DATASET_MANIFEST.json"
& docker compose exec -T backend python -m app.ml_cli register-dataset --manifest $manifest --storage-path "HYS-PPE/$Version/COCO" --organization DEMO-HYS --code HYS-PPE --name 'HYS PPE Dataset'
if($LASTEXITCODE -ne 0){throw 'Registro dataset fallo.'}
Write-Host '[PASS] DATASET HYS COCO CONGELADO Y REGISTRADO' -ForegroundColor Green
