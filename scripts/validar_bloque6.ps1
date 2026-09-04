$ErrorActionPreference = "Stop"
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 6 v0.7.0 GESTION OPERATIVA + EVIDENCIAS ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=60) {
  for ($i=1; $i -le $attempts; $i++) {
    $id = docker compose ps -q $service
    if ($id) {
      $status = docker inspect -f '{{.State.Status}}' $id
      $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if ($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')) {
        Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green; return
      }
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}
@('postgres','redis','minio','backend','camera-worker','vision-engine','frontend') | ForEach-Object { Wait-Healthy $_ }

$health=Invoke-RestMethod 'http://localhost:8160/health'
if($health.status -ne 'ok' -or $health.version -ne '0.7.0'){throw "[FAIL] /health version=$($health.version)"}
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green
$ready=Invoke-RestMethod 'http://localhost:8160/ready'; if($ready.status -notin @('ready','degraded')){throw '[FAIL] /ready'}
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green
$front=Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing; if($front.StatusCode -ne 200){throw '[FAIL] Frontend HTTP'}
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

Write-Host 'Verificando Alembic 0008_block6...' -ForegroundColor Cyan
$alembicLines=@(& docker compose exec -T backend alembic current); $alembicExit=$LASTEXITCODE; $alembic=($alembicLines -join "`n")
if($alembicExit -ne 0 -or $alembic -notmatch '0008_block6'){Write-Host $alembic;throw '[FAIL] Alembic no esta en 0008_block6'}
Write-Host '[OK] Alembic 0008_block6' -ForegroundColor Green

Write-Host 'Verificando esquema, RBAC y almacenamiento MinIO...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_block6_runtime
if($LASTEXITCODE -ne 0){throw '[FAIL] Runtime Bloque 6'}

Write-Host 'Verificando API de gestion operativa...' -ForegroundColor Cyan
function Read-Env([string]$Name){$line=Get-Content '.env'|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
$email=Read-Env 'BOOTSTRAP_ADMIN_EMAIL';$password=Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
$login=Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password}|ConvertTo-Json)
$headers=@{Authorization="Bearer $($login.access_token)"}
try {
  $summary=Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events/summary' -Headers $headers
  $events=@(Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events?limit=5' -Headers $headers)
  $assignees=@(Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events/assignees' -Headers $headers)
  if($events.Count -gt 0){
    $detail=Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/$($events[0].id)" -Headers $headers
    if($null -eq $detail.operational_status -or $null -eq $detail.evidence_status){throw 'Campos operativos ausentes'}
    $evidence=@(Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/$($events[0].id)/evidence" -Headers $headers)
    $timeline=@(Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/$($events[0].id)/timeline" -Headers $headers)
    Write-Host "[OK] API Block6 sample=$($events.Count) evidence=$($evidence.Count) timeline=$($timeline.Count)" -ForegroundColor Green
  } else {
    Write-Host '[OK] API Block6 sin eventos actuales; endpoints responden correctamente.' -ForegroundColor Green
  }
  Write-Host "[OK] Summary active=$($summary.active) total=$($summary.total) assignees=$($assignees.Count)" -ForegroundColor Green
} catch {
  Write-Host '[FAIL] API Bloque 6. Ultimos logs backend:' -ForegroundColor Red
  & docker compose logs backend --tail 150
  throw
}

Write-Host 'Ejecutando QA focalizado de operaciones y evidencia...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q tests/test_event_operations.py tests/test_event_evidence_clip.py
if($LASTEXITCODE -ne 0){throw '[FAIL] QA focalizado Bloque 6'}

Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if($LASTEXITCODE -ne 0){throw '[FAIL] Tests backend'}
Write-Host '[PASS] BLOQUE 6 v0.7.0 GESTION OPERATIVA + EVIDENCIAS + REVISION HUMANA INICIAL VALIDADO' -ForegroundColor Green
