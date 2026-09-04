$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - HOTFIX v0.7.2 VIDEO BROWSER + RESPONSABLES (QA v0.7.3) ===' -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=60) {
  for ($i=1; $i -le $attempts; $i++) {
    $id = docker compose ps -q $service
    if ($id) {
      $status = docker inspect -f '{{.State.Status}}' $id
      $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if ($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')) {
        Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
        return
      }
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}

function Normalize-Sequence($value) {
  $result = @()
  if ($null -eq $value) { return $result }
  foreach ($item in $value) { $result += $item }
  return $result
}

function Assert-SingleGuid([object]$value,[string]$label) {
  $text = [string]$value
  $parsed = [guid]::Empty
  if (-not [guid]::TryParse($text,[ref]$parsed)) {
    throw "[FAIL] $label no es UUID unico valido: '$text'"
  }
  return $parsed.ToString()
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','frontend') | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '0.7.0') { throw "[FAIL] /health status=$($health.status) version=$($health.version)" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green

Write-Host 'Verificando baseline Alembic 0008_block6...' -ForegroundColor Cyan
$alembicLines = @(& docker compose exec -T backend alembic current)
$alembicExit = $LASTEXITCODE
$alembic = ($alembicLines -join "`n")
if ($alembicExit -ne 0 -or $alembic -notmatch '0008_block6') { Write-Host $alembic; throw '[FAIL] Alembic no esta en 0008_block6' }
Write-Host '[OK] Alembic 0008_block6; sin migraciones nuevas.' -ForegroundColor Green

Write-Host 'Certificando encoder H.264 + transcodificacion de evidencia legacy...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_hotfix072_runtime
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Runtime video Hotfix v0.7.2' }

function Read-Env([string]$Name) {
  $line = Get-Content '.env' | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split '=',2)[1]
}

Write-Host 'Verificando API de responsables y preview browser-compatible...' -ForegroundColor Cyan
$email = Read-Env 'BOOTSTRAP_ADMIN_EMAIL'
$password = Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
if (-not $email -or -not $password) { throw '[FAIL] Credenciales bootstrap ausentes en .env' }
$login = Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password} | ConvertTo-Json)
$headers = @{Authorization="Bearer $($login.access_token)"}

# Windows PowerShell 5.1 puede conservar un JSON array como un unico objeto pipeline.
# Se normaliza explicitamente con foreach y se elige UN solo evento antes de interpolar event_id.
$eventsRaw = Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events?limit=100' -Headers $headers
$events = Normalize-Sequence $eventsRaw
$sample = $null
foreach ($eventItem in $events) {
  if ($null -ne $eventItem -and [int]$eventItem.evidence_count -gt 0) {
    $sample = $eventItem
    break
  }
}

$sampleId = $null
if ($sample) {
  $sampleId = Assert-SingleGuid $sample.id 'sample_event.id'
  Write-Host "[OK] Evento QA unico seleccionado: $sampleId" -ForegroundColor Green
}

if ($sampleId) {
  $assigneesRaw = Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/assignees?event_id=$sampleId" -Headers $headers
} else {
  $assigneesRaw = Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events/assignees' -Headers $headers
}
$assignees = Normalize-Sequence $assigneesRaw
if ($assignees.Count -lt 1) { throw '[FAIL] Selector de responsables sin candidatos' }
$assigneeEmails = @()
foreach ($assignee in $assignees) { if ($assignee.email) { $assigneeEmails += [string]$assignee.email } }
if (-not ($assigneeEmails -contains $email)) { throw "[FAIL] El SUPERADMIN global $email no aparece como responsable asignable" }
Write-Host "[OK] Responsables asignables=$($assignees.Count); SUPERADMIN global visible en selector." -ForegroundColor Green

if ($sampleId) {
  $evidenceRaw = Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/$sampleId/evidence" -Headers $headers
  $evidence = Normalize-Sequence $evidenceRaw
  $clip = $null
  foreach ($ev in $evidence) {
    if ($ev.kind -eq 'CLIP_PRE_EVENT') { $clip = $ev; break }
  }
  if ($clip) {
    $clipId = Assert-SingleGuid $clip.id 'clip.id'
    $tmp = Join-Path $env:TEMP ("hys-preview-v072-" + [guid]::NewGuid().ToString() + '.mp4')
    try {
      Invoke-WebRequest "http://localhost:8160/api/v1/safety-events/evidence/$clipId/preview" -Headers $headers -UseBasicParsing -OutFile $tmp
      $len = (Get-Item $tmp).Length
      if ($len -lt 500) { throw "[FAIL] Preview MP4 demasiado pequeno: $len bytes" }
      docker cp $tmp 'hysvision_backend:/tmp/hys-preview-v072.mp4' *> $null
      if ($LASTEXITCODE -ne 0) { throw '[FAIL] No se pudo copiar preview al contenedor para ffprobe' }
      $probeLines = @(& docker compose exec -T backend ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,codec_tag_string,pix_fmt -of default=noprint_wrappers=1 /tmp/hys-preview-v072.mp4)
      $probeExit = $LASTEXITCODE
      $probe = ($probeLines -join "`n")
      & docker compose exec -T backend rm -f /tmp/hys-preview-v072.mp4 *> $null
      if ($probeExit -ne 0 -or $probe -notmatch 'codec_name=h264' -or $probe -notmatch 'codec_tag_string=avc1' -or $probe -notmatch 'pix_fmt=yuv420p') {
        Write-Host $probe
        throw '[FAIL] Preview no es H.264/avc1/yuv420p'
      }
      Write-Host "[OK] CLIP_PRE_EVENT legacy/nuevo -> preview H.264 browser-compatible ($len bytes)." -ForegroundColor Green
    } finally {
      Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
  } else {
    Write-Host '[WARN] No hay CLIP_PRE_EVENT existente para validar via API; runtime sintetico H.264 ya paso.' -ForegroundColor Yellow
  }
} else {
  Write-Host '[WARN] No hay Safety Events con evidencia; runtime sintetico H.264 ya paso.' -ForegroundColor Yellow
}

Write-Host 'Ejecutando QA focalizado Hotfix v0.7.2...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q tests/test_event_operations.py tests/test_event_evidence_clip.py
if ($LASTEXITCODE -ne 0) { throw '[FAIL] QA focalizado Hotfix v0.7.2' }

Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Tests backend' }

Write-Host '[PASS] HOTFIX v0.7.2 VIDEO BROWSER-COMPATIBLE + SELECTOR RESPONSABLES VALIDADO' -ForegroundColor Green
Write-Host '[PASS] HOTFIX QA v0.7.3 VALIDADOR SINGLE-EVENT POWERSHELL VALIDADO' -ForegroundColor Green
Write-Host '[PASS] BLOQUE 6 v0.7.0 CONTINUA EN 0008_block6 Y QUEDA REVALIDADO' -ForegroundColor Green
