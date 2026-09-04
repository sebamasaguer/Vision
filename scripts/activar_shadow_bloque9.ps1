param([Parameter(Mandatory=$true)][string]$ModelCode,[string]$CameraCode='DEMO01',[string]$OrganizationCode='DEMO-HYS',[string]$ProjectPath=(Get-Location).Path)
$ErrorActionPreference='Stop'; Set-Location (Resolve-Path $ProjectPath).Path
& docker compose exec -T backend python -m app.ml_cli deploy --model $ModelCode --mode SHADOW --organization $OrganizationCode --camera $CameraCode
if($LASTEXITCODE -ne 0){throw 'Deploy SHADOW fallo.'}
& cmd.exe /d /c "docker compose restart vision-engine >nul 2>&1"
Write-Host '[PASS] MODELO EN SHADOW. No controla Safety Events.' -ForegroundColor Green
