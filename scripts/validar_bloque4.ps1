$ErrorActionPreference = "Stop"
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 4 v0.5.0 IA EPP ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=40) {
  for ($i=1; $i -le $attempts; $i++) {
    $id = docker compose ps -q $service
    if ($id) {
      $status = docker inspect -f '{{.State.Status}}' $id
      $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if ($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')) {
        Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
        return
      }
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','frontend') | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '0.5.0') { throw "[FAIL] /health version=$($health.version)" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green

$ready = Invoke-RestMethod 'http://localhost:8160/ready'
if ($ready.status -notin @('ready','degraded')) { throw '[FAIL] Backend /ready' }
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green

$front = Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing
if ($front.StatusCode -ne 200) { throw '[FAIL] Frontend HTTP' }
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

Write-Host 'Verificando Alembic 0006_block4...' -ForegroundColor Cyan
# v0.5.1 QA: usar el backend ya healthy. Evita `docker compose run`, cuyo
# mensaje "Container ... Creating" llega por stderr y PowerShell 5.1 puede
# convertirlo en NativeCommandError bajo ErrorActionPreference=Stop.
$alembicLines = @(& docker compose exec -T backend alembic current)
$alembicExit = $LASTEXITCODE
$alembic = ($alembicLines -join "`n")
if ($alembicExit -ne 0) { throw "[FAIL] alembic current exit=$alembicExit" }
if ($alembic -notmatch '0006_block4') { Write-Host $alembic; throw '[FAIL] Alembic no esta en 0006_block4' }
Write-Host '[OK] Alembic 0006_block4' -ForegroundColor Green

Write-Host 'Verificando modelo y columnas EPP...' -ForegroundColor Cyan
$py = "from app.db.session import SessionLocal; from app.models.vision import VisionModelVersion,CameraVisionSetting; from sqlalchemy import select; db=SessionLocal(); m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='PPE_REGION_SVM_BASELINE')); print('PPE_MODEL',m.code,m.backend,m.version,m.license_name,m.commercial_use); cols=['ppe_enabled','ppe_model_version_id','ppe_min_visibility_ratio','ppe_uncertainty_margin']; print('PPE_COLUMNS',','.join(cols)); db.close()"
$checkLines = @(& docker compose exec -T backend python -c $py)
$checkExit = $LASTEXITCODE
$check = ($checkLines -join "`n")
if ($checkExit -ne 0) { throw "[FAIL] Verificacion modelo PPE exit=$checkExit" }
Write-Host $check.Trim()
if ($check -notmatch 'PPE_MODEL PPE_REGION_SVM_BASELINE opencv_svm_regions') { throw '[FAIL] Modelo PPE no registrado' }
if ($check -notmatch 'PPE_COLUMNS') { throw '[FAIL] Columnas PPE ausentes' }

Write-Host 'QA negativo EPP...' -ForegroundColor Cyan
# camera-worker ya monta ./demo:/demo:ro, por lo que no hace falta crear un
# contenedor temporal con un volumen adicional.
& docker compose exec -T camera-worker python -m app.validate_ppe_negative
if ($LASTEXITCODE -ne 0) { throw '[FAIL] QA negativo EPP' }

Write-Host 'QA positivo EPP...' -ForegroundColor Cyan
& docker compose exec -T camera-worker python -m app.validate_ppe_demo
if ($LASTEXITCODE -ne 0) { throw '[FAIL] QA positivo EPP' }

Write-Host 'Ejecutando suite backend...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Tests backend' }

Write-Host '[PASS] BLOQUE 4 v0.5.0 IA EPP REAL BASELINE VALIDADO' -ForegroundColor Green
