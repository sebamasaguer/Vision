param([switch]$SkipRealVideo)
$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - BLOQUE 9 v1.0.0 DATASET + ML + ONNX + SHADOW ===' -ForegroundColor Cyan

function Invoke-ComposeQuiet([ValidateSet('start','stop')][string]$Mode) {
    if ($Mode -eq 'stop') {
        & cmd.exe /d /c "docker compose stop camera-worker vision-engine alert-worker >nul 2>&1"
    } else {
        & cmd.exe /d /c "docker compose up -d camera-worker vision-engine alert-worker >nul 2>&1"
    }
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "[FAIL] docker compose $Mode workers exit=$code" }
}


function Expand-JsonItems([object]$Value) {
    if ($null -eq $Value) { return }
    if ($Value -is [System.Array]) {
        foreach ($entry in $Value) { Expand-JsonItems $entry }
        return
    }
    Write-Output $Value
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

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend') |
    ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '1.0.0') {
    throw "[FAIL] backend status=$($health.status) version=$($health.version)"
}
Write-Host '[OK] Backend v1.0.0' -ForegroundColor Green

$front = Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing
if ($front.StatusCode -ne 200) { throw '[FAIL] Frontend HTTP' }
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

$headLines = @(& docker compose exec -T backend alembic current)
$head = $headLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $head -notmatch '0011_block9') {
    throw '[FAIL] Alembic no esta en 0011_block9'
}
Write-Host '[OK] Alembic 0011_block9' -ForegroundColor Green

& docker compose exec -T backend python -m app.validate_block9_runtime
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Runtime ML Block9' }

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
    -Method Post -ContentType 'application/json' `
    -Body (@{ email = $email; password = $password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$rawOrgs = Invoke-RestMethod 'http://localhost:8160/api/v1/organizations' -Headers $headers
$orgs = @(Expand-JsonItems $rawOrgs)
$demo = $orgs | Where-Object { $_.code -eq 'DEMO-HYS' } | Select-Object -First 1
if (-not $demo) { throw '[FAIL] DEMO-HYS ausente' }

$ml = Invoke-RestMethod "http://localhost:8160/api/v1/ml/overview?organization_id=$($demo.id)" -Headers $headers
if ($ml.policy.ultralytics_used -ne $false) { throw '[FAIL] Ultralytics no debe formar parte del pipeline' }
$models = @(Expand-JsonItems $ml.models)
$datasets = @(Expand-JsonItems $ml.datasets)
$intel = $models | Where-Object { $_.code -eq 'INTEL_WORKER_SAFETY_BOOTSTRAP' } | Select-Object -First 1
Write-Host "[OK] ML Overview models=$($models.Count) datasets=$($datasets.Count) shadow_samples=$($ml.shadow.samples) Ultralytics=False" -ForegroundColor Green
if (-not $SkipRealVideo) {
    if (-not $intel -or -not $intel.available) { throw '[FAIL] Bootstrap Intel no disponible' }
    Write-Host '[OK] Intel bootstrap artifact READY (MIT)' -ForegroundColor Green
    Write-Host 'Certificando deteccion real sobre video Intel...' -ForegroundColor Cyan
    & '.\scripts\probar_video_real_bloque9.ps1' -ProjectPath (Get-Location).Path -MaxSeconds 20
    if ($LASTEXITCODE -ne 0) { throw '[FAIL] Video real' }
    $summary = Get-Content '.\reports\block9\real_video_annotated.json' -Raw | ConvertFrom-Json
    if (($summary.counts.HELMET + $summary.counts.VEST) -lt 1) { throw '[FAIL] El video real no produjo detecciones HELMET/VEST' }
    Write-Host "[OK] Video real frames=$($summary.counts.frames) helmet=$($summary.counts.HELMET) vest=$($summary.counts.VEST) persons=$($summary.counts.PERSON)" -ForegroundColor Green
} else {
    Write-Host '[WARN] Smoke de video real omitido por -SkipRealVideo.' -ForegroundColor Yellow
}

Write-Host 'Aislando workers durante pytest...' -ForegroundColor Cyan
Invoke-ComposeQuiet 'stop'
$testFailed = $false
try {
    Write-Host 'Ejecutando QA focalizado Bloque 9...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q tests/test_ml_pipeline.py
    if ($LASTEXITCODE -ne 0) { $testFailed = $true; throw '[FAIL] QA Bloque 9' }

    Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
    & docker compose exec -T backend pytest -q
    if ($LASTEXITCODE -ne 0) { $testFailed = $true; throw '[FAIL] Suite backend' }
} finally {
    Write-Host 'Reiniciando workers...' -ForegroundColor Cyan
    Invoke-ComposeQuiet 'start'
    @('camera-worker','vision-engine','alert-worker') | ForEach-Object { Wait-Healthy $_ }
}
if ($testFailed) { throw '[FAIL] Tests Bloque 9' }
Write-Host '[PASS] BLOQUE 9 v1.0.0 DATASET HYS + TRAINING APACHE-2.0 + MODEL REGISTRY + ONNX + SHADOW VALIDADO' -ForegroundColor Green
