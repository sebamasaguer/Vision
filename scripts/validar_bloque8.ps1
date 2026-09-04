$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - BLOQUE 8 v0.9.0 ANALYTICS + LIMPIEZA PILOTO ===' -ForegroundColor Cyan


# Windows PowerShell 5.1 convierte STDERR de procesos nativos en ErrorRecord cuando
# ErrorActionPreference=Stop. Docker Compose escribe mensajes informativos por STDERR,
# por lo que se invoca mediante cmd.exe y se valida exclusivamente el exit code real.
function Invoke-DockerComposeQuiet([ValidateSet('start','stop')][string]$Mode) {
    if ($Mode -eq 'start') {
        & cmd.exe /d /c "docker compose up -d alert-worker >nul 2>&1"
        $code = $LASTEXITCODE
        if ($code -ne 0) { throw "[FAIL] docker compose up -d alert-worker exit=$code" }
        return
    }
    & cmd.exe /d /c "docker compose stop alert-worker >nul 2>&1"
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "[FAIL] docker compose stop alert-worker exit=$code" }
}

# El intento previo puede haber detenido alert-worker antes de entrar al bloque try/finally.
# Lo levantamos de forma idempotente antes de validar los ocho servicios.
Invoke-DockerComposeQuiet 'start'

function Wait-Healthy([string]$service, [int]$attempts = 80) {
    for ($i = 1; $i -le $attempts; $i++) {
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

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend') |
    ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '0.9.0') {
    throw "[FAIL] health status=$($health.status) version=$($health.version)"
}
Write-Host '[OK] Backend v0.9.0' -ForegroundColor Green

$front = Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing
if ($front.StatusCode -ne 200) { throw '[FAIL] Frontend HTTP' }
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

$headLines = @(& docker compose exec -T backend alembic current)
$head = $headLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $head -notmatch '0010_block8') {
    throw '[FAIL] Alembic no esta en 0010_block8'
}
Write-Host '[OK] Alembic 0010_block8' -ForegroundColor Green

Write-Host 'Verificando limpieza controlada...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_block8_runtime
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Runtime limpieza Bloque 8' }

function Read-Env([string]$Name) {
    $line = Get-Content '.env' |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}

$email = Read-Env 'BOOTSTRAP_ADMIN_EMAIL'
$password = Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
if (-not $email -or -not $password) { throw '[FAIL] Credenciales bootstrap ausentes' }

$login = Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' `
    -Method Post `
    -ContentType 'application/json' `
    -Body (@{ email = $email; password = $password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }

Write-Host 'Verificando API Analytics...' -ForegroundColor Cyan
$cleanup = Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/cleanup-status' -Headers $headers
$executive = Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/executive' -Headers $headers
$trend = @(Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/trend' -Headers $headers)
$ppe = @(Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/top-risks?dimension=ppe' -Headers $headers)
$heat = @(Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/heatmap' -Headers $headers)
$report = Invoke-RestMethod 'http://localhost:8160/api/v1/analytics/report' -Headers $headers
$csv = Invoke-WebRequest 'http://localhost:8160/api/v1/analytics/export.csv' -Headers $headers -UseBasicParsing

if ($cleanup.total_runs -lt 1) { throw '[FAIL] Cleanup run ausente' }
if ($cleanup.qa_active_events -ne 0) { throw '[FAIL] Quedaron eventos QA activos' }
if ($csv.StatusCode -ne 200 -or $csv.Content -notmatch 'event_number') { throw '[FAIL] Export CSV' }

Write-Host "[OK] Cleanup runs=$($cleanup.total_runs) archived=$($cleanup.archived_events) qa_active=$($cleanup.qa_active_events) compliance_demo=$($cleanup.compliance_enabled_cameras)" -ForegroundColor Green
Write-Host "[OK] KPI eventos=$($executive.total_events) compliance=$($executive.compliance_rate) ack_sla=$($executive.ack_sla_met_rate) archived_qa=$($executive.archived_qa_events)" -ForegroundColor Green
Write-Host "[OK] trend=$($trend.Count) top_ppe=$($ppe.Count) heatmap=$($heat.Count) report='$($report.title)' CSV=$($csv.RawContentLength)b" -ForegroundColor Green

$monitor = Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/summary' -Headers $headers
if ($monitor.active -ne 0) {
    Write-Host "[WARN] Monitoreo activo=$($monitor.active). Puede haber eventos operativos no-QA creados despues de la limpieza." -ForegroundColor Yellow
} else {
    Write-Host '[OK] Bandeja operativa limpia: active=0' -ForegroundColor Green
}

Write-Host 'Aislando alert-worker durante pytest...' -ForegroundColor Cyan
Invoke-DockerComposeQuiet 'stop'
$testFailed = $false
try {
    Write-Host 'Ejecutando QA focalizado Bloque 8...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q tests/test_analytics.py tests/test_alerting_monitoring.py
    if ($LASTEXITCODE -ne 0) {
        $testFailed = $true
        throw '[FAIL] QA focalizado Bloque 8'
    }

    Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q
    if ($LASTEXITCODE -ne 0) {
        $testFailed = $true
        throw '[FAIL] Suite backend'
    }
} finally {
    Write-Host 'Reiniciando alert-worker...' -ForegroundColor Cyan
    Invoke-DockerComposeQuiet 'start'
    Wait-Healthy 'alert-worker'
}

if ($testFailed) { throw '[FAIL] Tests Bloque 8' }
Write-Host '[PASS] BLOQUE 8 v0.9.0 DASHBOARD + KPIs + ANALITICA + REPORTES + EXPORTACIONES + HEATMAPS VALIDADO' -ForegroundColor Green
