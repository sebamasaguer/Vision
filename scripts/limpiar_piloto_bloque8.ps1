param([string]$OrganizationCode='DEMO-HYS')
$ErrorActionPreference='Stop'
Write-Host '=== HYS VISION IA - LIMPIEZA CONTROLADA PILOTO BLOQUE 8 ===' -ForegroundColor Cyan
$head=@(& docker compose exec -T backend alembic current) -join "`n"
if($head -notmatch '0010_block8'){throw 'Se requiere Alembic 0010_block8 para archivar el piloto sin borrar datos.'}
Write-Host '[INFO] Deteniendo temporalmente vision-engine y alert-worker...' -ForegroundColor Yellow
docker compose stop vision-engine alert-worker *> $null
try {
  & docker compose exec -T backend python -m app.pilot_cleanup --organization-code $OrganizationCode
  if($LASTEXITCODE -ne 0){throw 'Fallo limpieza controlada.'}
} finally {
  Write-Host '[INFO] Reiniciando workers...' -ForegroundColor Yellow
  docker compose up -d vision-engine alert-worker *> $null
}
Write-Host '[PASS] Limpieza controlada completada: evidencias/auditoria preservadas, eventos QA archivados y SLA restaurados.' -ForegroundColor Green
