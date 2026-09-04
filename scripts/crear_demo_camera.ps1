param([string]$ProjectPath = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = "Stop"
Set-Location $ProjectPath

function Read-Env([string]$Name) {
    $line = Get-Content .env | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split '=',2)[1]
}
$email = Read-Env "BOOTSTRAP_ADMIN_EMAIL"
$password = Read-Env "BOOTSTRAP_ADMIN_PASSWORD"
if (-not $email -or -not $password) { throw "No se pudo leer credencial bootstrap desde .env" }
$base = "http://localhost:8160/api/v1"
$login = Invoke-RestMethod "$base/auth/login" -Method Post -ContentType "application/json" -Body (@{email=$email;password=$password}|ConvertTo-Json)
$headers = @{Authorization="Bearer $($login.access_token)"}
$orgs = @(Invoke-RestMethod "$base/organizations" -Headers $headers)
$org = $orgs | Where-Object {$_.code -eq "DEMO-HYS"} | Select-Object -First 1
if (-not $org) { $org = Invoke-RestMethod "$base/organizations" -Method Post -Headers $headers -ContentType "application/json" -Body (@{code="DEMO-HYS";name="Entorno Demo HYS Vision"}|ConvertTo-Json) }
$sites = @(Invoke-RestMethod "$base/sites?organization_id=$($org.id)" -Headers $headers)
$site = $sites | Where-Object {$_.code -eq "DEMO"} | Select-Object -First 1
if (-not $site) { $site = Invoke-RestMethod "$base/sites" -Method Post -Headers $headers -ContentType "application/json" -Body (@{organization_id=$org.id;code="DEMO";name="Establecimiento Demo";address="Datos de demostracion"}|ConvertTo-Json) }
$plants = @(Invoke-RestMethod "$base/plants?site_id=$($site.id)" -Headers $headers)
$plant = $plants | Where-Object {$_.code -eq "P1"} | Select-Object -First 1
if (-not $plant) { $plant = Invoke-RestMethod "$base/plants" -Method Post -Headers $headers -ContentType "application/json" -Body (@{site_id=$site.id;code="P1";name="Planta Demo"}|ConvertTo-Json) }
$sectors = @(Invoke-RestMethod "$base/sectors?plant_id=$($plant.id)" -Headers $headers)
$sector = $sectors | Where-Object {$_.code -eq "MON"} | Select-Object -First 1
if (-not $sector) { $sector = Invoke-RestMethod "$base/sectors" -Method Post -Headers $headers -ContentType "application/json" -Body (@{plant_id=$plant.id;code="MON";name="Sector Monitoreo Demo"}|ConvertTo-Json) }
$cameras = @(Invoke-RestMethod "$base/cameras" -Headers $headers)
$cam = $cameras | Where-Object {$_.code -eq "DEMO01" -and $_.organization_id -eq $org.id} | Select-Object -First 1
if (-not $cam) { $cam = Invoke-RestMethod "$base/cameras" -Method Post -Headers $headers -ContentType "application/json" -Body (@{sector_id=$sector.id;code="DEMO01";name="Camara Demo MP4";source_type="DEMO_FILE";capture_fps=5;active=$true;ai_enabled=$false}|ConvertTo-Json) }
Write-Host "[OK] Demo Camera creada: $($cam.code) - $($cam.id)" -ForegroundColor Green
Write-Host "Abra http://localhost:5200 -> Camaras para visualizarla." -ForegroundColor Cyan
