param([Parameter(Mandatory=$true)][string]$ModelCode,[string]$CameraCode='DEMO01',[string]$OrganizationCode='DEMO-HYS',[int]$MinSamples=300,[double]$MinAgreement=.85,[string]$ProjectPath=(Get-Location).Path)
$ErrorActionPreference='Stop'; Set-Location (Resolve-Path $ProjectPath).Path
& docker compose exec -T backend python -m app.ml_cli promote --model $ModelCode --organization $OrganizationCode --camera $CameraCode --min-samples $MinSamples --min-agreement $MinAgreement
if($LASTEXITCODE -ne 0){throw 'Promocion bloqueada: SHADOW/criterios insuficientes.'}
& cmd.exe /d /c "docker compose restart vision-engine >nul 2>&1"
Write-Host '[PASS] MODELO HYS PROMOVIDO A PRODUCCION' -ForegroundColor Green
