$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
function Read-Env([string]$Name) {
    $line = Get-Content ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=',2)[1]
}
$email=Read-Env "BOOTSTRAP_ADMIN_EMAIL"; $password=Read-Env "BOOTSTRAP_ADMIN_PASSWORD"
$login=Invoke-RestMethod "http://localhost:8160/api/v1/auth/login" -Method Post -ContentType "application/json" -Body (@{email=$email;password=$password}|ConvertTo-Json)
$headers=@{Authorization="Bearer $($login.access_token)"}
$cameras=@(Invoke-RestMethod "http://localhost:8160/api/v1/cameras" -Headers $headers)
$cam=$cameras | Where-Object {$_.code -eq "DEMO01"} | Select-Object -First 1
if (-not $cam) { throw "No existe DEMO01. Ejecute primero .\scripts\crear_demo_camera.ps1" }
$zones=@(Invoke-RestMethod "http://localhost:8160/api/v1/zones?camera_id=$($cam.id)" -Headers $headers)
$zone=$zones | Where-Object {$_.code -eq "ZONA-DEMO"} | Select-Object -First 1
if (-not $zone) {
    $body=@{camera_id=$cam.id;code="ZONA-DEMO";name="Zona Demo EPP";description="Zona QA creada por script Bloque 2";polygon_points=@(@{x=.20;y=.18},@{x=.80;y=.18},@{x=.82;y=.82},@{x=.18;y=.82})}|ConvertTo-Json -Depth 5
    $zone=Invoke-RestMethod "http://localhost:8160/api/v1/zones" -Method Post -Headers $headers -ContentType "application/json" -Body $body
}
$ppe=@(Invoke-RestMethod "http://localhost:8160/api/v1/ppe" -Headers $headers)
$helmet=$ppe|Where-Object {$_.code -eq "HELMET"}|Select-Object -First 1
$vest=$ppe|Where-Object {$_.code -eq "VEST"}|Select-Object -First 1
$shoes=$ppe|Where-Object {$_.code -eq "SAFETY_SHOES"}|Select-Object -First 1
$rules=@{rules=@(
    @{ppe_type_id=$helmet.id;requirement="REQUIRED";severity="ALTA";active=$true},
    @{ppe_type_id=$vest.id;requirement="REQUIRED";severity="ALTA";active=$true},
    @{ppe_type_id=$shoes.id;requirement="REQUIRED";severity="ALTA";active=$true}
)}|ConvertTo-Json -Depth 5
Invoke-RestMethod "http://localhost:8160/api/v1/zones/$($zone.id)/rules" -Method Put -Headers $headers -ContentType "application/json" -Body $rules | Out-Null
Write-Host "[OK] ZONA-DEMO preparada en DEMO01 con Casco + Chaleco + Calzado obligatorios." -ForegroundColor Green
Write-Host "Abra http://localhost:5200 -> Zonas y EPP" -ForegroundColor Cyan
