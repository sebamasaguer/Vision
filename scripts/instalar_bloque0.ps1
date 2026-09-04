$ErrorActionPreference = "Stop"
Write-Host "=== HYS VISION IA - BLOQUE 0 v0.1.0 ===" -ForegroundColor Cyan
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker no está disponible en PATH." }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no está iniciado." }

if (-not (Test-Path ".env")) {
    function New-Secret([int]$Bytes = 32) {
        $b = New-Object byte[] $Bytes
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
        return ([Convert]::ToBase64String($b) -replace '[+/=]','x')
    }
    $DbPass = New-Secret 24
    $MinioSecret = New-Secret 28
    $JwtSecret = New-Secret 48
    $AdminPass = "Hys-" + (New-Secret 18) + "!"
    @"
APP_NAME=HYS Vision IA
APP_ENV=development
APP_VERSION=0.1.0
BACKEND_PORT=8160
FRONTEND_PORT=5200
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=hys_vision
POSTGRES_USER=hys_user
POSTGRES_PASSWORD=$DbPass
DATABASE_URL=postgresql+psycopg://hys_user:$DbPass@postgres:5432/hys_vision
REDIS_URL=redis://redis:6379/0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=hysminio
MINIO_SECRET_KEY=$MinioSecret
MINIO_SECURE=false
MINIO_BUCKET_EVIDENCE=hys-evidence
JWT_SECRET=$JwtSecret
JWT_ALGORITHM=HS256
JWT_ACCESS_MINUTES=480
BOOTSTRAP_ADMIN_EMAIL=admin@hysvision.app
BOOTSTRAP_ADMIN_PASSWORD=$AdminPass
CORS_ORIGINS=["http://localhost:5200"]
"@ | Set-Content -Encoding UTF8 ".env"
    Write-Host "Archivo .env generado con secretos aleatorios." -ForegroundColor Green
    Write-Host "CREDENCIAL INICIAL (guardarla y cambiarla luego):" -ForegroundColor Yellow
    Write-Host "  Usuario: admin@hysvision.app"
    Write-Host "  Password: $AdminPass" -ForegroundColor Yellow
} else {
    Write-Host ".env existente: se conserva sin cambios." -ForegroundColor DarkGray
}

Write-Host "Construyendo e iniciando servicios..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose up falló." }

Write-Host "`nServicios:" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5200"
Write-Host "  Backend:  http://localhost:8160"
Write-Host "  Swagger:  http://localhost:8160/docs"
Write-Host "  MinIO:    http://localhost:9031"
Write-Host "`nEjecute: .\scripts\validar_bloque0.ps1" -ForegroundColor Cyan
