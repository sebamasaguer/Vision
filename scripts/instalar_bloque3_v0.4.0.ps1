param([Parameter(Mandatory=$true)][string]$ProjectPath)
$ErrorActionPreference="Stop"
Write-Host "=== HYS VISION IA - BLOQUE 3 v0.4.0 VISION ARTIFICIAL BASE ===" -ForegroundColor Cyan
$ProjectPath=(Resolve-Path $ProjectPath).Path
$Payload=Join-Path $PSScriptRoot "payload"
if (-not (Test-Path $Payload)) { throw "Payload del Bloque 3 inexistente." }
if (-not (Test-Path (Join-Path $ProjectPath ".env"))) { throw "Falta .env. Instale y certifique Bloque 2 primero." }
if (-not (Test-Path (Join-Path $ProjectPath "backend\alembic\versions\0003_block2_zones_ppe.py"))) { throw "No se detecto baseline Bloque 2." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker no esta disponible en PATH." }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no esta iniciado." }
Set-Location $ProjectPath
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$backup=Join-Path $ProjectPath "backup-bloque3-v0.4.0-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null
Write-Host "Backup previo: $backup" -ForegroundColor Yellow
foreach($item in @("backend","frontend","scripts","docs","compose.yaml","README.md","MANIFEST_FILES.txt")){ $src=Join-Path $ProjectPath $item; if(Test-Path $src){Copy-Item $src (Join-Path $backup $item) -Recurse -Force} }
function Read-Env([string]$Name){$line=Get-Content (Join-Path $ProjectPath ".env")|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
try{$pgId=docker compose ps -q postgres;if($pgId){$st=docker inspect -f '{{.State.Status}}' $pgId;if($st -eq 'running'){$u=Read-Env 'POSTGRES_USER';$d=Read-Env 'POSTGRES_DB';if($u -and $d){docker exec hysvision_postgres pg_dump -U $u -d $d -Fc -f /tmp/hys_pre_b3.dump;if($LASTEXITCODE -eq 0){docker cp "hysvision_postgres:/tmp/hys_pre_b3.dump" (Join-Path $backup "postgres_pre_bloque3.dump") *> $null;docker exec hysvision_postgres rm -f /tmp/hys_pre_b3.dump *> $null;Write-Host "[OK] Backup PostgreSQL previo." -ForegroundColor Green}}}}}catch{Write-Host "[WARN] Dump PostgreSQL no disponible: $($_.Exception.Message)" -ForegroundColor Yellow}
Write-Host "Instalando archivos Bloque 3..." -ForegroundColor Cyan
foreach($dir in @("backend","frontend","demo","docs","scripts")){ $src=Join-Path $Payload $dir;if(Test-Path $src){$dst=Join-Path $ProjectPath $dir;New-Item -ItemType Directory -Force $dst|Out-Null;Copy-Item (Join-Path $src "*") $dst -Recurse -Force} }
foreach($file in @("compose.yaml","README.md","MANIFEST_FILES.txt",".env.example")){ $src=Join-Path $Payload $file;if(Test-Path $src){Copy-Item $src (Join-Path $ProjectPath $file) -Force} }
$envPath=Join-Path $ProjectPath ".env";$envText=Get-Content $envPath -Raw
if($envText -match '(?m)^APP_VERSION='){$envText=[regex]::Replace($envText,'(?m)^APP_VERSION=.*$','APP_VERSION=0.4.0')}else{$envText+="`nAPP_VERSION=0.4.0"}
if($envText -notmatch '(?m)^VISION_RESULT_TTL_SECONDS='){$envText+="`nVISION_RESULT_TTL_SECONDS=10"}
$envText|Set-Content $envPath -Encoding UTF8
Write-Host "[OK] .env conservado; APP_VERSION=0.4.0. Secretos sin cambios." -ForegroundColor Green
Write-Host "Validando Compose..." -ForegroundColor Cyan
docker compose config --quiet
if($LASTEXITCODE -ne 0){throw "compose.yaml invalido."}
Write-Host "Construyendo backend/frontend v0.4.0..." -ForegroundColor Cyan
docker compose build backend frontend
if($LASTEXITCODE -ne 0){throw "Fallo build Bloque 3."}
Write-Host "Iniciando infraestructura..." -ForegroundColor Cyan
docker compose up -d postgres redis minio
if($LASTEXITCODE -ne 0){throw "Fallo infraestructura."}
function Wait-Healthy([string]$service,[int]$attempts=40){for($i=1;$i -le $attempts;$i++){$id=docker compose ps -q $service;if($id){$status=docker inspect -f '{{.State.Status}}' $id;$health=docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id;if($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')){Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green;return}};Start-Sleep -Seconds 2};throw "$service no alcanzo estado healthy."}
@("postgres","redis","minio")|ForEach-Object{Wait-Healthy $_}
Write-Host "Aplicando migracion 0004_block3..." -ForegroundColor Cyan
docker compose run --rm --no-deps backend alembic upgrade head
if($LASTEXITCODE -ne 0){throw "Fallo Alembic Bloque 3."}
docker compose run --rm --no-deps backend python -m app.bootstrap
if($LASTEXITCODE -ne 0){throw "Fallo bootstrap Bloque 3."}
Write-Host "Levantando backend, camera-worker, vision-engine y frontend..." -ForegroundColor Cyan
docker compose up -d backend camera-worker vision-engine frontend
if($LASTEXITCODE -ne 0){throw "Fallo al levantar servicios Bloque 3."}
& (Join-Path $ProjectPath "scripts\validar_bloque3.ps1")
if($LASTEXITCODE -ne 0){throw "Validacion Bloque 3 fallo."}
Write-Host "`n[PASS] HYS VISION IA BLOQUE 3 v0.4.0 INSTALADO" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5200 -> Vision IA" -ForegroundColor Cyan
Write-Host "Swagger:  http://localhost:8160/docs" -ForegroundColor Cyan
