$ErrorActionPreference = "Stop"
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 5 v0.6.0 CUMPLIMIENTO + SAFETY EVENTS ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=50) {
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
if($health.status -ne 'ok' -or $health.version -ne '0.6.0'){throw "[FAIL] /health version=$($health.version)"}
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green
$ready=Invoke-RestMethod 'http://localhost:8160/ready'; if($ready.status -notin @('ready','degraded')){throw '[FAIL] /ready'}
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green
$front=Invoke-WebRequest 'http://localhost:5200' -UseBasicParsing; if($front.StatusCode -ne 200){throw '[FAIL] Frontend HTTP'}
Write-Host '[OK] Frontend HTTP 200' -ForegroundColor Green

Write-Host 'Verificando Alembic 0007_block5...' -ForegroundColor Cyan
$alembicLines=@(& docker compose exec -T backend alembic current); $alembicExit=$LASTEXITCODE; $alembic=($alembicLines -join "`n")
if($alembicExit -ne 0 -or $alembic -notmatch '0007_block5'){Write-Host $alembic;throw '[FAIL] Alembic no esta en 0007_block5'}
Write-Host '[OK] Alembic 0007_block5' -ForegroundColor Green

Write-Host 'Verificando tablas, columnas y permisos Bloque 5...' -ForegroundColor Cyan
$py = "from app.db.session import SessionLocal; from sqlalchemy import inspect,select; from app.models.access import Permission; db=SessionLocal(); i=inspect(db.bind); tables=set(i.get_table_names()); need={'safety_detection_events','compliance_evaluations'}; assert need<=tables,(need-tables); cols={c['name'] for c in i.get_columns('camera_vision_settings')}; req={'compliance_enabled','compliance_window_seconds','compliance_min_persistence_seconds','compliance_min_consensus_ratio','compliance_min_missing_observations','compliance_cooldown_seconds','compliance_clear_grace_seconds','compliance_track_absence_close_seconds'}; assert req<=cols,(req-cols); assert db.scalar(select(Permission).where(Permission.code=='safety_event.read')); print('BLOCK5_SCHEMA_OK',','.join(sorted(need))); print('COMPLIANCE_COLUMNS_OK',len(req)); db.close()"
& docker compose exec -T backend python -c $py
if($LASTEXITCODE -ne 0){throw '[FAIL] Esquema/permisos Bloque 5'}

Write-Host 'Ejecutando QA deterministico del motor temporal...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_compliance_engine
if($LASTEXITCODE -ne 0){throw '[FAIL] QA motor cumplimiento'}

Write-Host 'Verificando API Safety Events...' -ForegroundColor Cyan
function Read-Env([string]$Name){$line=Get-Content '.env'|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
$email=Read-Env 'BOOTSTRAP_ADMIN_EMAIL';$password=Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
$login=Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password}|ConvertTo-Json)
$headers=@{Authorization="Bearer $($login.access_token)"}
try {
  $summary=Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events/summary' -Headers $headers
  $events=@(Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events?limit=5' -Headers $headers)
  Write-Host "[OK] Safety Events API active=$($summary.active) closed_today=$($summary.closed_today) total=$($summary.total) sample=$($events.Count)" -ForegroundColor Green
} catch {
  Write-Host '[FAIL] Safety Events API. Ultimos logs backend:' -ForegroundColor Red
  & docker compose logs backend --tail 120
  throw
}

Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if($LASTEXITCODE -ne 0){throw '[FAIL] Tests backend'}
Write-Host '[PASS] BLOQUE 5 v0.6.0 MOTOR DE CUMPLIMIENTO + SAFETY EVENTS VALIDADO' -ForegroundColor Green
