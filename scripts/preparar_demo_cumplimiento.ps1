$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
function Read-Env([string]$Name){$line=Get-Content '.env'|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
& (Join-Path $PSScriptRoot 'crear_demo_zonas_epp.ps1')
if($LASTEXITCODE -ne 0){throw 'No se pudo preparar ZONA-DEMO.'}
& (Join-Path $PSScriptRoot 'usar_demo_personas_epp.ps1')
if($LASTEXITCODE -ne 0){throw 'No se pudo activar clip PERSON QA.'}
$email=Read-Env 'BOOTSTRAP_ADMIN_EMAIL';$password=Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
$login=Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password}|ConvertTo-Json)
$h=@{Authorization="Bearer $($login.access_token)"}
$cams=@(Invoke-RestMethod 'http://localhost:8160/api/v1/cameras' -Headers $h);$cam=$cams|Where-Object{$_.code -eq 'DEMO01'}|Select-Object -First 1
if(-not $cam){throw 'DEMO01 inexistente.'}
$body=@{enabled=$true;ppe_enabled=$true;compliance_enabled=$true;inference_fps=1.0;compliance_window_seconds=4.0;compliance_min_persistence_seconds=2.0;compliance_min_consensus_ratio=.70;compliance_min_missing_observations=3;compliance_cooldown_seconds=15.0}|ConvertTo-Json
Invoke-RestMethod "http://localhost:8160/api/v1/vision/cameras/$($cam.id)/settings" -Method Patch -Headers $h -ContentType 'application/json' -Body $body|Out-Null
Write-Host '[OK] DEMO01 preparado para Motor de Cumplimiento.' -ForegroundColor Green
Write-Host 'Esperado: HELMET/VEST pueden generar Safety Event tras persistencia; SAFETY_SHOES=NO_VISIBLE no debe generar evento.' -ForegroundColor Cyan
Write-Host 'Abra http://localhost:5200 -> Visión IA y Safety Events.' -ForegroundColor Cyan
