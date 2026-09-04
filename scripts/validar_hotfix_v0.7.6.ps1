$ErrorActionPreference = 'Stop'
Write-Host '=== VALIDACION HYS VISION IA - HOTFIX QA v0.7.6 POWERSHELL JSON ARRAY NORMALIZATION ===' -ForegroundColor Cyan

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

function Assert-SingleGuid([object]$value,[string]$label) {
  $text = [string]$value
  $parsed = [guid]::Empty
  if (-not [guid]::TryParse($text,[ref]$parsed)) { throw "[FAIL] $label no es UUID unico valido: '$text'" }
  return $parsed.ToString()
}

# Windows PowerShell 5.1 puede devolver desde Invoke-RestMethod:
#   - PSCustomObject para un singleton,
#   - Object[] para una lista,
#   - Object[] que contiene otro Object[] cuando el resultado fue envuelto previamente.
# Esta funcion emite ELEMENTOS, no un array empaquetado, y aplana arrays recursivamente.
function Expand-JsonItems([object]$Value) {
  if ($null -eq $Value) { return }
  if ($Value -is [System.Array]) {
    foreach ($entry in $Value) { Expand-JsonItems $entry }
    return
  }
  Write-Output $Value
}

function Read-Env([string]$Name) {
  $line = Get-Content '.env' | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split '=',2)[1]
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','frontend') | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod 'http://localhost:8160/health'
if ($health.status -ne 'ok' -or $health.version -ne '0.7.0') { throw "[FAIL] /health status=$($health.status) version=$($health.version)" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green

$alembicLines = @(& docker compose exec -T backend alembic current)
$alembicExit = $LASTEXITCODE
$alembic = ($alembicLines -join "`n")
if ($alembicExit -ne 0 -or $alembic -notmatch '0008_block6') { Write-Host $alembic; throw '[FAIL] Alembic no esta en 0008_block6' }
Write-Host '[OK] Alembic 0008_block6; sin migraciones nuevas.' -ForegroundColor Green

Write-Host 'Certificando que Hotfix v0.7.2 de video sigue vigente...' -ForegroundColor Cyan
& docker compose exec -T backend python -m app.validate_hotfix072_runtime
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Runtime video Hotfix v0.7.2' }

$email = Read-Env 'BOOTSTRAP_ADMIN_EMAIL'
$password = Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
if (-not $email -or -not $password) { throw '[FAIL] Credenciales bootstrap ausentes en .env' }
$login = Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password} | ConvertTo-Json)
$headers = @{Authorization="Bearer $($login.access_token)"}
$me = Invoke-RestMethod 'http://localhost:8160/api/v1/auth/me' -Headers $headers
if (-not ($me.role_codes -contains 'SUPERADMIN')) { throw "[FAIL] Usuario bootstrap no es SUPERADMIN: $($me.role_codes -join ',')" }
Write-Host "[OK] Actor QA: $($me.email) roles=$($me.role_codes -join ',') org=$($me.organization_id)" -ForegroundColor Green

$rawEvents = Invoke-RestMethod 'http://localhost:8160/api/v1/safety-events?limit=100' -Headers $headers
$events = @(Expand-JsonItems $rawEvents)
Write-Host "[INFO] Safety Events normalizados=$($events.Count)" -ForegroundColor DarkGray

$sample = $null
foreach ($item in $events) {
  if ($null -eq $item) { continue }
  $evidenceCount = 0
  $prop = $item.PSObject.Properties['evidence_count']
  if ($null -ne $prop) { [void][int]::TryParse([string]$item.evidence_count,[ref]$evidenceCount) }
  if ($evidenceCount -gt 0) { $sample=$item; break }
}
if (-not $sample -and $events.Count -gt 0) { $sample=$events[0] }
if (-not $sample) { throw '[FAIL] No hay Safety Events para validar responsables/preview' }

$sampleId=Assert-SingleGuid $sample.id 'sample_event.id'
Write-Host "[OK] Evento QA unico seleccionado: $sampleId" -ForegroundColor Green

$url="http://localhost:8160/api/v1/safety-events/assignees?event_id=$sampleId"
$rawAssignees = Invoke-RestMethod $url -Headers $headers
$assignees = @(Expand-JsonItems $rawAssignees)
Write-Host "[INFO] Responsables API normalizados=$($assignees.Count)" -ForegroundColor DarkGray
foreach ($candidate in $assignees) {
  Write-Host "[INFO] candidato=$($candidate.email) id=$($candidate.id)" -ForegroundColor DarkGray
}
if ($assignees.Count -lt 1) { throw '[FAIL] Selector de responsables sigue sin candidatos' }
$emails=@($assignees | ForEach-Object { [string]$_.email })
if (-not ($emails -contains $email)) { throw "[FAIL] SUPERADMIN autenticado $email no aparece como candidato" }
Write-Host "[OK] Responsables asignables=$($assignees.Count); SUPERADMIN autenticado visible." -ForegroundColor Green

$rawEvidence = Invoke-RestMethod "http://localhost:8160/api/v1/safety-events/$sampleId/evidence" -Headers $headers
$evidence = @(Expand-JsonItems $rawEvidence)
Write-Host "[INFO] Evidencias normalizadas=$($evidence.Count)" -ForegroundColor DarkGray
$clip=$null
foreach ($ev in $evidence) { if ($ev.kind -eq 'CLIP_PRE_EVENT') { $clip=$ev; break } }
if ($clip) {
  $clipId=Assert-SingleGuid $clip.id 'clip.id'
  $tmp=Join-Path $env:TEMP ("hys-preview-v076-"+[guid]::NewGuid().ToString()+'.mp4')
  try {
    Invoke-WebRequest "http://localhost:8160/api/v1/safety-events/evidence/$clipId/preview" -Headers $headers -UseBasicParsing -OutFile $tmp
    $len=(Get-Item $tmp).Length
    if ($len -lt 500) { throw "[FAIL] Preview MP4 demasiado pequeno: $len bytes" }
    docker cp $tmp 'hysvision_backend:/tmp/hys-preview-v076.mp4' *> $null
    if ($LASTEXITCODE -ne 0) { throw '[FAIL] docker cp preview' }
    $probeLines=@(& docker compose exec -T backend ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,codec_tag_string,pix_fmt -show_entries format=duration -of default=noprint_wrappers=1 /tmp/hys-preview-v076.mp4)
    $probeExit=$LASTEXITCODE; $probe=($probeLines -join "`n")
    & docker compose exec -T backend rm -f /tmp/hys-preview-v076.mp4 *> $null
    if ($probeExit -ne 0 -or $probe -notmatch 'codec_name=h264' -or $probe -notmatch 'codec_tag_string=avc1' -or $probe -notmatch 'pix_fmt=yuv420p') { Write-Host $probe; throw '[FAIL] Preview no H.264/avc1/yuv420p' }
    Write-Host "[OK] CLIP_PRE_EVENT preview browser-compatible ($len bytes)." -ForegroundColor Green
  } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
} else {
  Write-Host '[WARN] Evento QA sin CLIP_PRE_EVENT; runtime sintetico H.264 ya paso.' -ForegroundColor Yellow
}

Write-Host 'Ejecutando QA focalizado v0.7.4...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q tests/test_event_operations.py tests/test_event_evidence_clip.py
if ($LASTEXITCODE -ne 0) { throw '[FAIL] QA focalizado v0.7.4' }

Write-Host 'Ejecutando suite backend completa...' -ForegroundColor Cyan
& docker compose exec -T backend pytest -q
if ($LASTEXITCODE -ne 0) { throw '[FAIL] Tests backend' }

Write-Host '[PASS] HOTFIX v0.7.4 RESPONSABLES PRODUCCION VALIDADO' -ForegroundColor Green
Write-Host '[PASS] HOTFIX v0.7.2 VIDEO BROWSER-COMPATIBLE CONTINUA VALIDADO' -ForegroundColor Green
Write-Host '[PASS] HOTFIX QA v0.7.6 POWERSHELL JSON ARRAY NORMALIZATION VALIDADO' -ForegroundColor Green
Write-Host '[PASS] BLOQUE 6 v0.7.0 CONTINUA EN 0008_block6 Y QUEDA REVALIDADO' -ForegroundColor Green
