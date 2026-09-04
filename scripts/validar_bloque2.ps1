$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 2 v0.3.0 ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service, [int]$attempts = 40) {
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

@("postgres","redis","minio","backend","camera-worker","frontend") | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod "http://localhost:8160/health"
if ($health.status -ne "ok" -or $health.version -ne "0.3.0") { throw "[FAIL] Backend /health version/status inesperado: $($health.version)" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green

$ready = Invoke-RestMethod "http://localhost:8160/ready"
if ($ready.status -notin @("ready","degraded")) { throw "[FAIL] Backend /ready" }
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green

$front = Invoke-WebRequest "http://localhost:5200" -UseBasicParsing
if ($front.StatusCode -ne 200) { throw "[FAIL] Frontend HTTP $($front.StatusCode)" }
Write-Host "[OK] Frontend HTTP 200" -ForegroundColor Green

Write-Host "Verificando Alembic..." -ForegroundColor Cyan
$current = docker compose exec -T backend alembic current
if (($current -join "`n") -notmatch "0003_block2") { throw "[FAIL] Alembic no esta en 0003_block2" }
Write-Host "[OK] Alembic 0003_block2" -ForegroundColor Green

Write-Host "Verificando tablas Bloque 2..." -ForegroundColor Cyan
docker compose exec -T backend python -c "from sqlalchemy import inspect; from app.db.session import engine; t=set(inspect(engine).get_table_names()); required={'ppe_types','zones','zone_ppe_rules'}; missing=required-t; assert not missing, missing; print('TABLES OK:', ', '.join(sorted(required)))"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Tablas Bloque 2" }

function Read-Env([string]$Name) {
    $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=',2)[1]
}
$email = Read-Env "BOOTSTRAP_ADMIN_EMAIL"
$password = Read-Env "BOOTSTRAP_ADMIN_PASSWORD"
if (-not $email -or -not $password) { throw "[FAIL] Faltan credenciales bootstrap en .env" }
$loginBody = @{ email=$email; password=$password } | ConvertTo-Json
$session = Invoke-RestMethod "http://localhost:8160/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($session.access_token)" }
# Windows PowerShell 5.1 puede tratar un array JSON devuelto por Invoke-RestMethod
# como un unico objeto de pipeline. Validamos el JSON crudo para que el conteo sea
# deterministico en PowerShell 5.1 y PowerShell 7+.
$ppeResponse = Invoke-WebRequest "http://localhost:8160/api/v1/ppe" -Headers $headers -UseBasicParsing
$ppeJson = [string]$ppeResponse.Content
$ppeCount = [regex]::Matches($ppeJson, '\"code\"\s*:').Count
$hasHelmet = $ppeJson -match '\"code\"\s*:\s*\"HELMET\"'
$hasHarness = $ppeJson -match '\"code\"\s*:\s*\"HARNESS\"'
if ($ppeCount -lt 12 -or -not $hasHelmet -or -not $hasHarness) {
    Write-Host "[DIAG] EPP API count=$ppeCount HELMET=$hasHelmet HARNESS=$hasHarness" -ForegroundColor Yellow
    docker compose exec -T backend python -c "from sqlalchemy import select; from app.db.session import SessionLocal; from app.models.safety import PPEType; db=SessionLocal(); rows=list(db.scalars(select(PPEType).order_by(PPEType.code))); print('DB PPE:', len(rows), ','.join(x.code + ':' + ('A' if x.active else 'I') for x in rows)); db.close()"
    throw "[FAIL] Catalogo EPP inicial incompleto"
}
Write-Host "[OK] Catalogo EPP administrable: $ppeCount elementos activos; HELMET/HARNESS presentes." -ForegroundColor Green

$zones = @(Invoke-RestMethod "http://localhost:8160/api/v1/zones" -Headers $headers)
Write-Host "[OK] API Zonas operativa: $($zones.Count) zonas activas actuales." -ForegroundColor Green

Write-Host "Ejecutando suite backend..." -ForegroundColor Cyan
docker compose exec -T backend sh -lc "PYTHONPATH=/app pytest -q"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Tests backend" }

Write-Host "[PASS] BLOQUE 2 v0.3.0 ZONAS + EPP + REGLAS VALIDADO" -ForegroundColor Green
