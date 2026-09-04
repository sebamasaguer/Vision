param(
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [switch]$SkipIntelBootstrap
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $Here 'payload'
if (-not (Test-Path $Payload)) { $Payload = $Here }
Write-Host '=== HYS VISION IA - BLOQUE 9 v1.0.0 DATASET HYS + YOLOX + ONNX + SHADOW ===' -ForegroundColor Cyan
$ProjectPath = (Resolve-Path $ProjectPath).Path
if (-not (Test-Path (Join-Path $ProjectPath '.env'))) { throw 'No se encontro .env en ProjectPath.' }
if (-not (Test-Path (Join-Path $ProjectPath 'backend\alembic\versions\0010_block8_analytics_cleanup.py'))) { throw 'Se requiere Bloque 8 / 0010_block8 instalado.' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker no esta disponible en PATH.' }
& cmd.exe /d /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop no esta iniciado.' }
Set-Location $ProjectPath

Write-Host 'Verificando baseline Alembic 0010_block8...' -ForegroundColor Cyan
$baseLines = @(& docker compose exec -T backend alembic current)
$base = $baseLines -join "`n"
if ($LASTEXITCODE -ne 0 -or $base -notmatch '0010_block8') { throw 'Se requiere baseline Alembic 0010_block8.' }
Write-Host '[OK] Baseline 0010_block8 confirmado.' -ForegroundColor Green

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $ProjectPath "backup-bloque9-v1.0.0-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null
Write-Host "Backup previo: $backup" -ForegroundColor Yellow
$backupFiles = @('compose.yaml','README.md','.env.example','backend\requirements.txt','backend\app\bootstrap.py','backend\app\main.py','backend\app\vision_engine.py','backend\app\services\ppe_runtime.py','frontend\src\App.tsx','frontend\src\styles.css')
foreach ($rel in $backupFiles) { $src=Join-Path $ProjectPath $rel; if(Test-Path $src){$dst=Join-Path $backup $rel;New-Item -ItemType Directory -Force (Split-Path -Parent $dst)|Out-Null;Copy-Item $src $dst -Force} }
function Read-Env([string]$Name){$line=Get-Content (Join-Path $ProjectPath '.env')|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not$line){return $null};return($line-split'=',2)[1]}
try {
    $u=Read-Env 'POSTGRES_USER';$d=Read-Env 'POSTGRES_DB'
    if($u-and$d){& docker exec hysvision_postgres pg_dump -U $u -d $d -Fc -f /tmp/hys_pre_100.dump;if($LASTEXITCODE-eq 0){& docker cp 'hysvision_postgres:/tmp/hys_pre_100.dump' (Join-Path $backup 'postgres_pre_bloque9_v1.0.0.dump');& docker exec hysvision_postgres rm -f /tmp/hys_pre_100.dump;Write-Host '[OK] Backup PostgreSQL previo.' -ForegroundColor Green}}
} catch { Write-Host "[WARN] pg_dump no disponible: $($_.Exception.Message)" -ForegroundColor Yellow }

Write-Host 'Instalando archivos Bloque 9...' -ForegroundColor Cyan
foreach($dir in @('backend','frontend','scripts','docs','training')){$src=Join-Path $Payload $dir;if(Test-Path $src){$dst=Join-Path $ProjectPath $dir;New-Item -ItemType Directory -Force $dst|Out-Null;Copy-Item (Join-Path $src '*') $dst -Recurse -Force}}
foreach($dir in @('models','datasets','reports')){New-Item -ItemType Directory -Force (Join-Path $ProjectPath $dir)|Out-Null}
foreach($file in @('compose.yaml','README.md','README_INSTALACION.md','README_BLOQUE9_v1.0.0.md','.env.example')){$src=Join-Path $Payload $file;if(Test-Path $src){Copy-Item $src (Join-Path $ProjectPath $file) -Force}}
$envPath=Join-Path $ProjectPath '.env';$envText=Get-Content $envPath -Raw
if($envText-match'(?m)^APP_VERSION='){$envText=[regex]::Replace($envText,'(?m)^APP_VERSION=.*$','APP_VERSION=1.0.0')}else{$envText+="`nAPP_VERSION=1.0.0"}
$envText|Set-Content $envPath -Encoding UTF8
Write-Host '[OK] APP_VERSION=1.0.0; .env y secretos conservados.' -ForegroundColor Green

& docker compose config --quiet
if($LASTEXITCODE-ne 0){throw 'compose.yaml invalido.'}
Write-Host 'Construyendo runtime v1.0.0 (trainer GPU queda bajo profile training)...' -ForegroundColor Cyan
& docker compose build backend frontend
if($LASTEXITCODE-ne 0){throw 'Fallo build backend/frontend v1.0.0.'}
& docker compose up -d postgres redis minio
if($LASTEXITCODE-ne 0){throw 'Fallo infraestructura.'}

function Wait-Healthy([string]$service,[int]$attempts=100){for($i=1;$i-le$attempts;$i++){$id=docker compose ps -q $service;if($id){$status=docker inspect -f '{{.State.Status}}' $id;$health=docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id;if($status-eq'running'-and($health-eq'healthy'-or$health-eq'n/a')){Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green;return};Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray};Start-Sleep 2};throw "$service no alcanzo healthy"}
@('postgres','redis','minio')|ForEach-Object{Wait-Healthy $_}

Write-Host 'Aplicando Alembic 0011_block9 y bootstrap RBAC/Model Registry...' -ForegroundColor Cyan
& docker compose up -d --force-recreate backend
if($LASTEXITCODE-ne 0){throw 'Fallo backend Bloque 9.'};Wait-Healthy 'backend'

Write-Host 'Recreando runtime v1.0.0...' -ForegroundColor Cyan
& docker compose up -d --force-recreate camera-worker vision-engine alert-worker frontend
if($LASTEXITCODE-ne 0){throw 'Fallo servicios Bloque 9.'}
@('camera-worker','vision-engine','alert-worker','frontend')|ForEach-Object{Wait-Healthy $_}

if(-not$SkipIntelBootstrap){
    Write-Host 'Instalando bootstrap MIT para dejar video real funcional ahora...' -ForegroundColor Magenta
    & (Join-Path $ProjectPath 'scripts\instalar_bootstrap_intel_bloque9.ps1') -ProjectPath $ProjectPath
    if($LASTEXITCODE-ne 0){throw 'Fallo bootstrap Intel. Use -SkipIntelBootstrap solo si desea instalar ML pipeline sin demo real.'}
    Wait-Healthy 'vision-engine'
}else{Write-Host '[WARN] Intel bootstrap omitido; training/model registry quedan instalados pero el smoke de video real se omite.' -ForegroundColor Yellow}

if($SkipIntelBootstrap){& (Join-Path $ProjectPath 'scripts\validar_bloque9.ps1') -SkipRealVideo}else{& (Join-Path $ProjectPath 'scripts\validar_bloque9.ps1')}
if($LASTEXITCODE-ne 0){throw 'Validacion Bloque 9 fallo.'}
Write-Host "`n[PASS] HYS VISION IA BLOQUE 9 v1.0.0 INSTALADO Y VALIDADO" -ForegroundColor Green
Write-Host 'UI: http://localhost:5200 -> Modelos IA' -ForegroundColor Cyan
Write-Host 'VIDEO REAL: reports\block9\real_video_annotated.mp4' -ForegroundColor Cyan
Write-Host 'El bootstrap Intel queda SHADOW; NO controla Safety Events. Produccion requiere modelo HYS + criterios SHADOW.' -ForegroundColor Yellow
