$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - BLOQUE 10 v1.1.0 DATASET VISUAL + GROUND TRUTH + SHADOW ===' -ForegroundColor Cyan

function Invoke-ComposeQuiet([ValidateSet('start','stop')][string]$Mode) {
    if ($Mode -eq 'stop') {
        & cmd.exe /d /c "docker compose stop camera-worker vision-engine alert-worker >nul 2>&1"
    } else {
        & cmd.exe /d /c "docker compose up -d camera-worker vision-engine alert-worker >nul 2>&1"
    }
    if ($LASTEXITCODE -ne 0) { throw "[FAIL] docker compose $Mode workers" }
}

function Wait-Healthy([string]$service, [int]$attempts = 100) {
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

function Expand-JsonItems([object]$Value) {
    if ($null -eq $Value) { return }
    if ($Value -is [System.Array]) {
        foreach ($entry in $Value) { Expand-JsonItems $entry }
        return
    }
    Write-Output $Value
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend') |
    ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '1.1.0') {
    throw "[FAIL] Backend status=$($health.status) version=$($health.version)"
}
Write-Host '[OK] Backend v1.1.0' -ForegroundColor Green

$front = Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing
if ($front.StatusCode -ne 200) { throw '[FAIL] Frontend HTTP' }
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

$headLines = @(& docker compose exec -T backend alembic current)
$head = $headLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $head -notmatch '0012_block10') { throw '[FAIL] Alembic no esta en 0012_block10' }
Write-Host '[OK] Alembic 0012_block10' -ForegroundColor Green

& docker compose exec -T backend python -m app.validate_block10_runtime
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Runtime Block10' }

function Read-Env([string]$Name) {
    $line = Get-Content '.env' | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}
$email = Read-Env 'BOOTSTRAP_ADMIN_EMAIL'
$password = Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
if (-not $email -or -not $password) { throw '[FAIL] Credenciales bootstrap ausentes' }

$login = Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{ email=$email; password=$password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$rawOrgs = Invoke-RestMethod 'http://localhost:8160/api/v1/organizations' -Headers $headers
$orgs = @(Expand-JsonItems $rawOrgs)
$demo = $orgs | Where-Object { $_.code -eq 'DEMO-HYS' } | Select-Object -First 1
if (-not $demo) { throw '[FAIL] DEMO-HYS ausente' }

$ml = Invoke-RestMethod "http://localhost:8160/api/v1/ml/overview?organization_id=$($demo.id)" -Headers $headers
$datasets = @(Expand-JsonItems $ml.datasets)
$ds = $datasets | Where-Object { $_.code -eq 'HYS-PPE-REAL' } | Select-Object -First 1
if (-not $ds) { throw '[FAIL] Dataset HYS-PPE-REAL ausente' }
$ws = Invoke-RestMethod "http://localhost:8160/api/v1/ml/datasets/$($ds.id)/workspace" -Headers $headers
Write-Host "[OK] Dataset Visual code=$($ws.dataset.code) total=$($ws.stats.TOTAL) verified=$($ws.stats.VERIFIED) annotations=$($ws.stats.ANNOTATIONS)" -ForegroundColor Green

$shadow = Invoke-RestMethod "http://localhost:8160/api/v1/ml/shadow/by-camera?organization_id=$($demo.id)" -Headers $headers
$shadowRows = @(Expand-JsonItems $shadow)
$demoShadow = $shadowRows | Where-Object { $_.camera_code -eq 'DEMO01' } | Select-Object -First 1
if (-not $demoShadow) { throw '[FAIL] Metricas SHADOW DEMO01 ausentes' }
Write-Host "[OK] SHADOW por camara DEMO01 samples=$($demoShadow.samples) agreement=$($demoShadow.agreement_ratio)" -ForegroundColor Green

$demoPath = Read-Env 'DEMO_VIDEO_PATH'
if ($demoPath -ne '/demo/intel_worker_safety_test.avi') { throw "[FAIL] DEMO_VIDEO_PATH=$demoPath" }
Write-Host '[OK] Camara demo migrada a video EPP real del Bloque 9.' -ForegroundColor Green

Write-Host 'Aislando workers durante pytest...' -ForegroundColor Cyan
Invoke-ComposeQuiet 'stop'
try {
    Write-Host 'Ejecutando QA focalizado Bloque 10...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q tests/test_block10_dataset_visual.py
    if ($LASTEXITCODE -ne 0) { throw '[FAIL] QA Bloque 10' }

    Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q
    if ($LASTEXITCODE -ne 0) { throw '[FAIL] Suite backend' }
} finally {
    Write-Host 'Reiniciando workers...' -ForegroundColor Cyan
    Invoke-ComposeQuiet 'start'
    @('camera-worker','vision-engine','alert-worker') | ForEach-Object { Wait-Healthy $_ }
}
Write-Host '[PASS] BLOQUE 10 v1.1.0 DATASET MANAGER VISUAL + GROUND TRUTH + SHADOW + PROMOCION CONTROLADA VALIDADO' -ForegroundColor Green
