$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - BLOQUE 7 v0.8.0 ALERTAS + SLA + MONITOREO ===' -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=75) {
  for($i=1;$i -le $attempts;$i++) {
    $id = docker compose ps -q $service
    if($id) {
      $status = docker inspect -f '{{.State.Status}}' $id
      $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')) {
        Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green; return
      }
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend') | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if($health.status -ne 'ok' -or $health.version -ne '0.8.0'){throw "[FAIL] /health status=$($health.status) version=$($health.version)"}
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green
$ready=Invoke-RestMethod 'http://localhost:8160/ready'; if($ready.status -notin @('ready','degraded')){throw '[FAIL] /ready'}
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green
$front=Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing; if($front.StatusCode -ne 200){throw '[FAIL] Frontend HTTP'}
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

Write-Host 'Verificando Alembic 0009_block7...' -ForegroundColor Cyan
$alembicLines=@(& docker compose exec -T backend alembic current); $alembicExit=$LASTEXITCODE; $alembic=($alembicLines -join "`n")
if($alembicExit -ne 0 -or $alembic -notmatch '0009_block7'){Write-Host $alembic;throw '[FAIL] Alembic no esta en 0009_block7'}
Write-Host '[OK] Alembic 0009_block7' -ForegroundColor Green

Write-Host 'Verificando esquema, SLA, RBAC y canales...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_block7_runtime
if($LASTEXITCODE -ne 0){throw '[FAIL] Runtime Bloque 7'}

Write-Host 'Verificando heartbeat alert-worker...' -ForegroundColor Cyan
& docker compose exec -T alert-worker python -m app.alert_worker_health
if($LASTEXITCODE -ne 0){throw '[FAIL] alert-worker health'}

function Read-Env([string]$Name){$line=Get-Content '.env'|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
$email=Read-Env 'BOOTSTRAP_ADMIN_EMAIL';$password=Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
if(-not $email -or -not $password){throw '[FAIL] Credenciales bootstrap ausentes en .env'}
$login=Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password}|ConvertTo-Json)
$headers=@{Authorization="Bearer $($login.access_token)"}

Write-Host 'Verificando API de Monitoreo...' -ForegroundColor Cyan
try {
  $worker=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/worker' -Headers $headers
  if($worker.status -ne 'ONLINE'){throw "alert-worker API status=$($worker.status)"}
  $summary=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/summary' -Headers $headers
  $inbox=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/inbox?limit=10' -Headers $headers
  $policies=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/policies' -Headers $headers
  $channels=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/channels' -Headers $headers
  $deliveries=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/deliveries?limit=10' -Headers $headers
  $policyItems=@($policies.items | ForEach-Object { $_ })
  $channelItems=@($channels.items | ForEach-Object { $_ })
  $inboxItems=@($inbox.items | ForEach-Object { $_ })
  $deliveryItems=@($deliveries.items | ForEach-Object { $_ })
  if($policyItems.Count -lt 3){throw "Politicas insuficientes: $($policyItems.Count)"}
  if($channelItems.Count -lt 4){throw "Canales insuficientes: $($channelItems.Count)"}
  $inApp=$channelItems | Where-Object {$_.channel -eq 'IN_APP'} | Select-Object -First 1
  if(-not $inApp -or -not $inApp.enabled -or $inApp.configuration_status -ne 'READY'){throw 'Canal IN_APP no READY'}
  $processed=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/process-once' -Headers $headers -Method Post
  Write-Host "[OK] Monitoring worker=$($worker.status) active=$($summary.active) overdue_ack=$($summary.ack_overdue) overdue_resolve=$($summary.resolution_overdue) escalated=$($summary.escalated)" -ForegroundColor Green
  Write-Host "[OK] Inbox=$($inboxItems.Count) policies=$($policyItems.Count) channels=$($channelItems.Count) deliveries=$($deliveryItems.Count) process_once=$($processed.processed)" -ForegroundColor Green
  Write-Host "[OK] IN_APP enabled=$($inApp.enabled) status=$($inApp.configuration_status)" -ForegroundColor Green
} catch {
  Write-Host '[FAIL] API Monitoreo. Ultimos logs backend/alert-worker:' -ForegroundColor Red
  & docker compose logs backend alert-worker --tail 160
  throw
}

Write-Host 'Ejecutando QA focalizado Bloque 7...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q tests/test_alerting_monitoring.py tests/test_event_operations.py tests/test_event_evidence_clip.py
if($LASTEXITCODE -ne 0){throw '[FAIL] QA focalizado Bloque 7'}

Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if($LASTEXITCODE -ne 0){throw '[FAIL] Tests backend'}
Write-Host '[PASS] BLOQUE 7 v0.8.0 ALERTAS + SLA + ESCALAMIENTO + NOTIFICACIONES + MONITOREO VALIDADO' -ForegroundColor Green
