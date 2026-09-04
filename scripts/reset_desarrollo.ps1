$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "ATENCION: esto elimina los volúmenes de desarrollo de HYS Vision." -ForegroundColor Yellow
$confirm = Read-Host "Escriba RESET para continuar"
if ($confirm -ne "RESET") { Write-Host "Cancelado."; exit 0 }
docker compose down -v
docker compose up -d --build
