$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 3 + HOTFIX v0.4.1 ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service, [int]$attempts = 50) {
    for ($i = 1; $i -le $attempts; $i++) {
        $id = docker compose ps -q $service
        if ($id) {
            $status = docker inspect -f '{{.State.Status}}' $id
            $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
            if ($status -eq "running" -and ($health -eq "healthy" -or $health -eq "n/a")) {
                Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
                return
            }
            Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
        }
        Start-Sleep -Seconds 2
    }
    throw "[FAIL] $service no alcanzo estado healthy."
}

@("postgres","redis","minio","backend","camera-worker","vision-engine","frontend") | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod "http://localhost:8160/health"
if ($health.status -ne "ok" -or $health.version -ne "0.4.1") { throw "[FAIL] Backend /health version/status inesperado: $($health.version)" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green
$ready = Invoke-RestMethod "http://localhost:8160/ready"
if ($ready.status -notin @("ready","degraded")) { throw "[FAIL] Backend /ready" }
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green
$front = Invoke-WebRequest "http://localhost:5200" -UseBasicParsing
if ($front.StatusCode -ne 200) { throw "[FAIL] Frontend HTTP $($front.StatusCode)" }
Write-Host "[OK] Frontend HTTP 200" -ForegroundColor Green

Write-Host "Verificando Alembic y columnas de hardening..." -ForegroundColor Cyan
$current = docker compose exec -T backend alembic current
if (($current -join "`n") -notmatch "0005_hotfix041") { throw "[FAIL] Alembic no esta en 0005_hotfix041" }
Write-Host "[OK] Alembic 0005_hotfix041" -ForegroundColor Green

docker compose exec -T backend python -c "from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); cols={x['name'] for x in i.get_columns('camera_vision_settings')}; r={'tracker_min_hits_to_confirm','min_box_area_ratio','max_box_area_ratio','min_height_ratio','min_aspect_ratio','max_aspect_ratio','top_band_reject_y_ratio','top_band_reject_bottom_ratio'}; m=r-cols; assert not m,m; print('HARDENING COLUMNS OK:', ', '.join(sorted(r)))"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Columnas hardening" }

docker compose exec -T backend python -c "from sqlalchemy import select; from app.db.session import SessionLocal; from app.models.vision import VisionModelVersion; db=SessionLocal(); m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='OPENCV_HOG_PERSON_BASELINE')); assert m and m.active and m.commercial_use and m.license_name=='Apache-2.0' and 'HARDENED-0.4.1' in m.version; print('MODEL OK:',m.code,m.backend,m.version,m.license_name); db.close()"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Modelo PERSON hardened" }

Write-Host "Verificando heartbeat vision-engine..." -ForegroundColor Cyan
docker compose exec -T vision-engine python -m app.vision_worker_health
if ($LASTEXITCODE -ne 0) { throw "[FAIL] vision-engine heartbeat" }

Write-Host "Ejecutando detector PERSON endurecido sobre frame real..." -ForegroundColor Cyan
docker compose exec -T vision-engine python -m app.validate_vision_frame
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Smoke detector PERSON hardened" }

Write-Host "Certificando QA negativo + positivo..." -ForegroundColor Cyan
docker compose run --rm --no-deps camera-worker python -m app.validate_person_hardening
if ($LASTEXITCODE -ne 0) { throw "[FAIL] QA PERSON hardening" }

Write-Host "Ejecutando suite backend..." -ForegroundColor Cyan
docker compose exec -T backend sh -lc "PYTHONPATH=/app pytest -q"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Tests backend" }

Write-Host "[PASS] BLOQUE 3 + HOTFIX v0.4.1 PERSON DETECTOR HARDENING VALIDADO" -ForegroundColor Green
