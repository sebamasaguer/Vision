param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $Here 'payload'
if (-not (Test-Path $Payload)) { $Payload = $Here }

Write-Host '=== HYS VISION IA - BLOQUE 8 v0.9.0 ANALYTICS + LIMPIEZA CONTROLADA ===' -ForegroundColor Cyan

$ProjectPath = (Resolve-Path $ProjectPath).Path
if (-not (Test-Path (Join-Path $ProjectPath '.env'))) {
    throw 'No se encontro .env en ProjectPath.'
}
if (-not (Test-Path (Join-Path $ProjectPath 'backend\alembic\versions\0009_block7_alerting_monitoring.py'))) {
    throw 'Se requiere Bloque 7 / 0009_block7 instalado.'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker no esta disponible en PATH.'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop no esta iniciado.' }
Set-Location $ProjectPath

Write-Host 'Verificando baseline Alembic 0009_block7...' -ForegroundColor Cyan
$baseLines = @(& docker compose exec -T backend alembic current)
$base = $baseLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $base -notmatch '0009_block7') {
    throw 'Se requiere baseline Alembic 0009_block7.'
}
Write-Host '[OK] Baseline 0009_block7 confirmado.' -ForegroundColor Green

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $ProjectPath "backup-bloque8-v0.9.0-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null
Write-Host "Backup previo: $backup" -ForegroundColor Yellow

$backupFiles = @(
    'compose.yaml', 'README.md', '.env.example',
    'backend\app\models\safety.py',
    'backend\app\bootstrap.py',
    'backend\app\main.py',
    'backend\app\services\alerting.py',
    'backend\app\api\routers\monitoring.py',
    'frontend\src\App.tsx',
    'frontend\src\styles.css',
    'frontend\package.json'
)
foreach ($rel in $backupFiles) {
    $src = Join-Path $ProjectPath $rel
    if (Test-Path $src) {
        $dst = Join-Path $backup $rel
        New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
        Copy-Item $src $dst -Force
    }
}

function Read-Env([string]$Name) {
    $line = Get-Content (Join-Path $ProjectPath '.env') |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}

try {
    $u = Read-Env 'POSTGRES_USER'
    $d = Read-Env 'POSTGRES_DB'
    if ($u -and $d) {
        docker exec hysvision_postgres pg_dump -U $u -d $d -Fc -f /tmp/hys_pre_090.dump
        if ($LASTEXITCODE -eq 0) {
            docker cp 'hysvision_postgres:/tmp/hys_pre_090.dump' (Join-Path $backup 'postgres_pre_bloque8_v0.9.0.dump') *> $null
            docker exec hysvision_postgres rm -f /tmp/hys_pre_090.dump *> $null
            Write-Host '[OK] Backup PostgreSQL previo.' -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[WARN] pg_dump no disponible: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host 'Congelando generacion y escalamiento mientras se prepara la limpieza...' -ForegroundColor Cyan
docker compose stop vision-engine alert-worker *> $null

Write-Host 'Instalando archivos Bloque 8...' -ForegroundColor Cyan
foreach ($dir in @('backend', 'frontend', 'scripts', 'docs')) {
    $src = Join-Path $Payload $dir
    if (Test-Path $src) {
        $dst = Join-Path $ProjectPath $dir
        New-Item -ItemType Directory -Force $dst | Out-Null
        Copy-Item (Join-Path $src '*') $dst -Recurse -Force
    }
}
foreach ($file in @('compose.yaml', 'README.md', 'README_INSTALACION.md', '.env.example')) {
    $src = Join-Path $Payload $file
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $ProjectPath $file) -Force
    }
}

$envPath = Join-Path $ProjectPath '.env'
$envText = Get-Content $envPath -Raw
if ($envText -match '(?m)^APP_VERSION=') {
    $envText = [regex]::Replace($envText, '(?m)^APP_VERSION=.*$', 'APP_VERSION=0.9.0')
} else {
    $envText += "`nAPP_VERSION=0.9.0"
}
$envText | Set-Content $envPath -Encoding UTF8
Write-Host '[OK] APP_VERSION=0.9.0; .env y secretos conservados.' -ForegroundColor Green

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'compose.yaml invalido.' }

Write-Host 'Construyendo backend/frontend v0.9.0...' -ForegroundColor Cyan
docker compose build backend frontend
if ($LASTEXITCODE -ne 0) { throw 'Fallo build v0.9.0.' }

docker compose up -d postgres redis minio
if ($LASTEXITCODE -ne 0) { throw 'Fallo infraestructura.' }

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
    throw "$service no alcanzo healthy"
}

@('postgres', 'redis', 'minio') | ForEach-Object { Wait-Healthy $_ }

Write-Host 'Aplicando Alembic 0010_block8 y bootstrap RBAC...' -ForegroundColor Cyan
docker compose up -d --force-recreate backend
if ($LASTEXITCODE -ne 0) { throw 'Fallo backend Bloque 8.' }
Wait-Healthy 'backend'

Write-Host '=== LIMPIEZA CONTROLADA DEL PILOTO DEMO-HYS ===' -ForegroundColor Magenta
$email = Read-Env 'BOOTSTRAP_ADMIN_EMAIL'
if (-not $email) { $email = 'admin@hysvision.app' }
& docker compose exec -T backend python -m app.pilot_cleanup `
    --organization-code DEMO-HYS `
    --actor-email $email `
    --reason 'Bloque 8 v0.9.0: archivado controlado de QA antes de dashboard ejecutivo'
if ($LASTEXITCODE -ne 0) {
    throw 'Fallo limpieza controlada del piloto. No se continuara.'
}

Write-Host 'Recreando servicios v0.9.0...' -ForegroundColor Cyan
docker compose up -d --force-recreate camera-worker vision-engine alert-worker frontend
if ($LASTEXITCODE -ne 0) { throw 'Fallo servicios Bloque 8.' }
@('camera-worker', 'vision-engine', 'alert-worker', 'frontend') | ForEach-Object { Wait-Healthy $_ }

& (Join-Path $ProjectPath 'scripts\validar_bloque8.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Validacion Bloque 8 fallo.' }

Write-Host "`n[PASS] HYS VISION IA BLOQUE 8 v0.9.0 INSTALADO, PILOTO LIMPIO Y ANALYTICS VALIDADO" -ForegroundColor Green
Write-Host 'UI: http://localhost:5200 -> Analitica' -ForegroundColor Cyan
Write-Host 'DEMO-HYS queda con cumplimiento desactivado; PERSON/EPP siguen disponibles sin generar nuevos Safety Events hasta reactivarlo.' -ForegroundColor Yellow
