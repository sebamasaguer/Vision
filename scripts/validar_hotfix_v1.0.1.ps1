param([string]$ProjectPath=(Get-Location).Path)
$ErrorActionPreference='Stop'
$ProjectPath=(Resolve-Path $ProjectPath).Path
Set-Location $ProjectPath
Write-Host '=== VALIDACION HYS VISION IA - HOTFIX v1.0.1 OPENVINO RUNTIME ===' -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=120){
  for($i=1;$i-le$attempts;$i++){
    $id=docker compose ps -q $service
    if($id){
      $status=docker inspect -f '{{.State.Status}}' $id
      $health=docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if($status-eq'running'-and($health-eq'healthy'-or$health-eq'n/a')){Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green;return}
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend')|ForEach-Object{Wait-Healthy $_}
$health=Invoke-RestMethod 'http://localhost:8160/health'
if($health.status-ne'ok'-or$health.version-ne'1.0.0'){throw "[FAIL] Backend status/version: $($health.status) $($health.version)"}
Write-Host '[OK] Backend v1.0.0' -ForegroundColor Green

$head=@(& docker compose exec -T backend alembic current)-join"`n"
if($LASTEXITCODE-ne0-or$head-notmatch'0011_block9'){throw '[FAIL] Alembic no esta en 0011_block9'}
Write-Host '[OK] Alembic 0011_block9; sin migraciones nuevas.' -ForegroundColor Green

Write-Host 'Verificando OpenVINO Runtime CPU...' -ForegroundColor Cyan
& docker compose exec -T vision-engine python -c "import openvino as ov; c=ov.Core(); print('OPENVINO_RUNTIME_OK version='+str(ov.__version__)+' devices='+','.join(c.available_devices)); assert any(str(x).startswith('CPU') for x in c.available_devices)"
if($LASTEXITCODE-ne0){throw '[FAIL] OpenVINO Runtime/CPU no disponible'}

Write-Host 'Verificando carga del modelo Intel IR con OpenVINO Runtime...' -ForegroundColor Cyan
& docker compose exec -T vision-engine python -c "from app.services.ppe_runtime import IntelWorkerSafetyPPEDetector; d=IntelWorkerSafetyPPEDetector({'input_size':[600,600]},'bootstrap/intel-worker-safety/model.xml'); print('OPENVINO_INTEL_MODEL_OK input='+str(d.input_size)+' outputs='+str(len(d.output_ports)))"
if($LASTEXITCODE-ne0){throw '[FAIL] Modelo Intel no compila con OpenVINO Runtime'}

Write-Host 'Certificando video real Intel...' -ForegroundColor Cyan
& '.\scripts\probar_video_real_bloque9.ps1' -ProjectPath $ProjectPath -MaxSeconds 20
if($LASTEXITCODE-ne0){throw '[FAIL] Smoke de video real'}
$summary=Get-Content '.\reports\block9\real_video_annotated.json' -Raw|ConvertFrom-Json
$total=[int]$summary.counts.HELMET+[int]$summary.counts.VEST
if($total-lt1){throw '[FAIL] El modelo real no produjo detecciones HELMET/VEST'}
Write-Host "[OK] REAL VIDEO helmet=$($summary.counts.HELMET) vest=$($summary.counts.VEST) person=$($summary.counts.PERSON) frames=$($summary.counts.frames)" -ForegroundColor Green

Write-Host 'Revalidando Bloque 9 completo...' -ForegroundColor Cyan
& '.\scripts\validar_bloque9.ps1'
if($LASTEXITCODE-ne0){throw '[FAIL] Revalidacion Bloque 9'}
Write-Host '[PASS] HOTFIX v1.0.1 OPENVINO RUNTIME + VIDEO REAL VALIDADO' -ForegroundColor Green
