param([string]$ProjectPath=(Get-Location).Path)
$ErrorActionPreference='Stop'
$ProjectPath=(Resolve-Path $ProjectPath).Path
Set-Location $ProjectPath
Write-Host '=== VALIDACION HYS VISION IA - HOTFIX v1.0.2 OPENVINO INPUT SHAPE + GETI OUTPUTS ===' -ForegroundColor Cyan

function Wait-Healthy([string]$service,[int]$attempts=120){
  for($i=1;$i-le$attempts;$i++){
    $id=docker compose ps -q $service
    if($id){
      $status=docker inspect -f '{{.State.Status}}' $id
      $health=docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
      if($status-eq'running'-and($health-eq'healthy'-or$health-eq'n/a')){Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green;return}
      Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
  }
  throw "[FAIL] $service no alcanzo healthy"
}

@('postgres','redis','minio','backend','camera-worker','vision-engine','alert-worker','frontend')|ForEach-Object{Wait-Healthy $_}
$health=Invoke-RestMethod 'http://localhost:8160/health'
if($health.status-ne'ok'-or$health.version-ne'1.0.0'){throw "[FAIL] Backend status/version: $($health.status) $($health.version)"}
Write-Host '[OK] Backend v1.0.0' -ForegroundColor Green

$head=@(& docker compose exec -T backend alembic current)-join"`n"
if($LASTEXITCODE-ne0-or$head-notmatch'0011_block9'){throw '[FAIL] Alembic no esta en 0011_block9'}
Write-Host '[OK] Alembic 0011_block9; sin migraciones nuevas.' -ForegroundColor Green

Write-Host 'Verificando que el graph OpenVINO mande sobre metadata 600x600 obsoleta...' -ForegroundColor Cyan
$shapeCode = @'
from app.services.ppe_runtime import IntelWorkerSafetyPPEDetector,_ov_port_name
import numpy as np
m={'input_size':[600,600],'default_threshold':.35,'helmet_threshold':.57,'vest_threshold':.525,'detection_output_label_map':{'1':'HELMET','2':'VEST'}}
d=IntelWorkerSafetyPPEDetector(m,'bootstrap/intel-worker-safety/model.xml')
outs=[(_ov_port_name(p),tuple(int(x) for x in p.shape)) for p in d.output_ports]
print('OPENVINO_GRAPH_SHAPE_OK graph='+str(d.input_size)+' registry='+str(d.registry_input_size)+' outputs='+str(outs))
assert tuple(d.input_size)==(640,640), d.input_size
x=np.zeros((720,1280,3),dtype=np.uint8)
y=d._detect_crop(x,threshold=.35)
print('OPENVINO_INFER_OK detections='+str(len(y)))
'@
& docker compose exec -T vision-engine python -c $shapeCode
if($LASTEXITCODE-ne0){throw '[FAIL] Autodeteccion 640x640 / parser Geti'}

Write-Host 'Certificando video real Intel con input 640x640 y outputs Geti...' -ForegroundColor Cyan
& '.\scripts\probar_video_real_bloque9.ps1' -ProjectPath $ProjectPath -MaxSeconds 20
if($LASTEXITCODE-ne0){throw '[FAIL] Smoke de video real'}
$summary=Get-Content '.\reports\block9\real_video_annotated.json' -Raw|ConvertFrom-Json
$total=[int]$summary.counts.HELMET+[int]$summary.counts.VEST
if($total-lt1){throw '[FAIL] El modelo real no produjo detecciones HELMET/VEST'}
Write-Host "[OK] REAL VIDEO helmet=$($summary.counts.HELMET) vest=$($summary.counts.VEST) person=$($summary.counts.PERSON) frames=$($summary.counts.frames)" -ForegroundColor Green

Write-Host 'Revalidando Bloque 9 completo sin repetir el video...' -ForegroundColor Cyan
& '.\scripts\validar_bloque9.ps1' -SkipRealVideo
if($LASTEXITCODE-ne0){throw '[FAIL] Revalidacion Bloque 9'}
Write-Host '[PASS] HOTFIX v1.0.2 OPENVINO INPUT SHAPE + GETI OUTPUT PARSER VALIDADO' -ForegroundColor Green
