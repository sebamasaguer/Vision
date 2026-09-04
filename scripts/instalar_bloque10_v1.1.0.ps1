param(
    [Parameter(Mandatory = $true)][string]$ProjectPath
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $Here 'payload'
if (-not (Test-Path $Payload)) { $Payload = $Here }

Write-Host '=== HYS VISION IA - BLOQUE 10 v1.1.0 DATASET VISUAL + GROUND TRUTH + SHADOW ===' -ForegroundColor Cyan
$ProjectPath = (Resolve-Path $ProjectPath).Path
if (-not (Test-Path (Join-Path $ProjectPath '.env'))) { throw 'No se encontro .env en ProjectPath.' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker no esta disponible en PATH.' }
& cmd.exe /d /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop no esta iniciado.' }
Set-Location $ProjectPath

Write-Host 'Verificando baseline Alembic 0011_block9...' -ForegroundColor Cyan
$baseLines = @(& docker compose exec -T backend alembic current)
$base = $baseLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $base -notmatch '0011_block9') { throw 'Se requiere baseline Alembic 0011_block9 (Bloque 9 certificado).' }
Write-Host '[OK] Baseline 0011_block9 confirmado.' -ForegroundColor Green

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $ProjectPath "backup-bloque10-v1.1.0-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null
Write-Host "Backup previo: $backup" -ForegroundColor Yellow
$backupFiles = @(
    'compose.yaml','README.md','.env','backend\requirements.txt','backend\app\bootstrap.py','backend\app\main.py',
    'backend\app\vision_engine.py','backend\app\services\ppe_runtime.py','frontend\src\App.tsx','frontend\src\CamerasPage.tsx',
    'frontend\src\MLPage.tsx','frontend\src\styles.css'
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
    $line = Get-Content (Join-Path $ProjectPath '.env') | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1]
}
try {
    $u = Read-Env 'POSTGRES_USER'; $d = Read-Env 'POSTGRES_DB'
    if ($u -and $d) {
        & docker exec hysvision_postgres pg_dump -U $u -d $d -Fc -f /tmp/hys_pre_110.dump
        if ($LASTEXITCODE -eq 0) {
            & docker cp 'hysvision_postgres:/tmp/hys_pre_110.dump' (Join-Path $backup 'postgres_pre_bloque10_v1.1.0.dump')
            & docker exec hysvision_postgres rm -f /tmp/hys_pre_110.dump
            Write-Host '[OK] Backup PostgreSQL previo.' -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[WARN] pg_dump: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host 'Instalando archivos Bloque 10...' -ForegroundColor Cyan
foreach ($dir in @('backend','frontend','scripts','docs')) {
    $src = Join-Path $Payload $dir
    if (Test-Path $src) {
        $dst = Join-Path $ProjectPath $dir
        New-Item -ItemType Directory -Force $dst | Out-Null
        Copy-Item (Join-Path $src '*') $dst -Recurse -Force
    }
}
foreach ($file in @('compose.yaml','README.md','README_INSTALACION.md','README_BLOQUE10_v1.1.0.md','.env.example')) {
    $src = Join-Path $Payload $file
    if (Test-Path $src) { Copy-Item $src (Join-Path $ProjectPath $file) -Force }
}

$envPath = Join-Path $ProjectPath '.env'
$envText = Get-Content $envPath -Raw
if ($envText -match '(?m)^APP_VERSION=') {
    $envText = [regex]::Replace($envText, '(?m)^APP_VERSION=.*$', 'APP_VERSION=1.1.0')
} else { $envText += "`nAPP_VERSION=1.1.0" }
if ($envText -match '(?m)^DEMO_VIDEO_PATH=') {
    $envText = [regex]::Replace($envText, '(?m)^DEMO_VIDEO_PATH=.*$', 'DEMO_VIDEO_PATH=/demo/intel_worker_safety_test.avi')
} else { $envText += "`nDEMO_VIDEO_PATH=/demo/intel_worker_safety_test.avi" }
$envText | Set-Content $envPath -Encoding UTF8

$realVideo = Join-Path $ProjectPath 'demo\intel_worker_safety_test.avi'
if (-not (Test-Path $realVideo)) {
    Write-Host '[WARN] Video Intel ausente; descargando bootstrap oficial fijado por commit...' -ForegroundColor Yellow
    & (Join-Path $ProjectPath 'scripts\instalar_bootstrap_intel_bloque9.ps1') -ProjectPath $ProjectPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $realVideo)) { throw 'No se pudo obtener el video EPP real requerido para reemplazar el demo anterior.' }
}
Write-Host '[OK] APP_VERSION=1.1.0; DEMO01 apuntara al video EPP real; secretos conservados.' -ForegroundColor Green

& docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'compose.yaml invalido.' }
Write-Host 'Construyendo backend/frontend v1.1.0...' -ForegroundColor Cyan
& docker compose build backend frontend
if ($LASTEXITCODE -ne 0) { throw 'Fallo build backend/frontend v1.1.0.' }
& docker compose up -d postgres redis minio
if ($LASTEXITCODE -ne 0) { throw 'Fallo infraestructura.' }

function Wait-Healthy([string]$service, [int]$attempts = 110) {
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
@('postgres','redis','minio') | ForEach-Object { Wait-Healthy $_ }

Write-Host 'Aplicando Alembic 0012_block10 y bootstrap Dataset Manager...' -ForegroundColor Cyan
& docker compose up -d --force-recreate backend
if ($LASTEXITCODE -ne 0) { throw 'Fallo backend Bloque 10.' }
Wait-Healthy 'backend'

Write-Host 'Preparando DEMO01: video EPP real + PERSON/EPP visual + SHADOW; compliance OFF...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.block10_demo_setup
if ($LASTEXITCODE -ne 0) { throw 'Fallo setup demo Bloque 10.' }

Write-Host 'Recreando runtime v1.1.0...' -ForegroundColor Cyan
& docker compose up -d --force-recreate camera-worker vision-engine alert-worker frontend
if ($LASTEXITCODE -ne 0) { throw 'Fallo servicios Bloque 10.' }
@('camera-worker','vision-engine','alert-worker','frontend') | ForEach-Object { Wait-Healthy $_ }

& (Join-Path $ProjectPath 'scripts\validar_bloque10.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Validacion Bloque 10 fallo.' }
Write-Host "`n[PASS] HYS VISION IA BLOQUE 10 v1.1.0 INSTALADO Y VALIDADO" -ForegroundColor Green
Write-Host 'UI: http://localhost:5200 -> Dataset IA' -ForegroundColor Cyan
Write-Host 'CAMARAS: DEMO01 ya no usa la imagen demo anterior; usa video EPP real con overlay SHADOW.' -ForegroundColor Cyan
