param(
 [string]$ProjectPath=(Get-Location).Path,[string]$Version='v0001',[int]$Epochs=50,[int]$ImageSize=416,[int]$Batch=8,[string]$RunId
)
$ErrorActionPreference='Stop'; $ProjectPath=(Resolve-Path $ProjectPath).Path; Set-Location $ProjectPath
if(-not $RunId){$RunId='hys-'+(Get-Date -Format 'yyyyMMdd-HHmmss')}
$manifest=Join-Path $ProjectPath "datasets\HYS-PPE\$Version\COCO\DATASET_MANIFEST.json"
if(-not (Test-Path $manifest)){throw 'Dataset COCO no construido.'}
Write-Host 'Construyendo trainer YOLOX 0.3.0 (Apache-2.0). NO usa Ultralytics...' -ForegroundColor Cyan
& docker compose --profile training build trainer
if($LASTEXITCODE -ne 0){throw 'Build trainer fallo.'}
Write-Host 'Entrenamiento requiere NVIDIA/CUDA. En equipos CPU use este dataset en una GPU/Colab y registre luego el ONNX.' -ForegroundColor Yellow
& docker compose --profile training run --rm trainer --dataset "/datasets/HYS-PPE/$Version/COCO" --run-id $RunId --base yolox_nano --epochs $Epochs --img-size $ImageSize --batch $Batch --device cuda --classes HELMET,VEST,SAFETY_SHOES
if($LASTEXITCODE -ne 0){throw 'Training/export YOLOX fallo. Verifique NVIDIA Container Toolkit/CUDA.'}
$artifactRel="hys/$RunId/HYS_PPE_$RunId.onnx"; $manifestContainer="/models/hys/$RunId/MODEL_MANIFEST.json"
& docker compose exec -T backend python -m app.ml_cli register-onnx --manifest $manifestContainer --artifact-uri $artifactRel --organization DEMO-HYS --code ("HYS_PPE_"+$RunId.Replace('-','_').ToUpper()) --version 1.0.0
if($LASTEXITCODE -ne 0){throw 'Registro ONNX fallo.'}
Write-Host "[PASS] MODELO HYS ENTRENADO, ONNX Y REGISTRADO: $artifactRel" -ForegroundColor Green
