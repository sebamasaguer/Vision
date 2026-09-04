param(
    [string]$ProjectPath = (Get-Location).Path,
    [switch]$SkipSampleVideo,
    [switch]$SkipShadow
)
$ErrorActionPreference='Stop'
$ProjectPath=(Resolve-Path $ProjectPath).Path
Set-Location $ProjectPath
Write-Host '=== BLOQUE 9 - INSTALAR BOOTSTRAP INTEL WORKER SAFETY (MIT) ===' -ForegroundColor Cyan

$commit='edd25f37c324a9ef73df1642354b2ba5fa7b7df5'
$modelUrl="https://raw.githubusercontent.com/open-edge-platform/edge-ai-resources/$commit/models/worker-safety-gear-detection.zip"
$videoUrl="https://raw.githubusercontent.com/open-edge-platform/edge-ai-resources/$commit/videos/Safety_Full_Hat_and_Vest.avi"
$target=Join-Path $ProjectPath 'models\bootstrap\intel-worker-safety'
New-Item -ItemType Directory -Force $target | Out-Null
$tmp=Join-Path $env:TEMP "hys-intel-bootstrap-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $zip=Join-Path $tmp 'worker-safety-gear-detection.zip'
    Write-Host 'Descargando modelo oficial Intel Edge AI Resources (commit fijado)...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri $modelUrl -OutFile $zip -UseBasicParsing
    $zipHash=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    Expand-Archive $zip (Join-Path $tmp 'model') -Force
    $xml=Get-ChildItem (Join-Path $tmp 'model') -Recurse -Filter 'model.xml' | Select-Object -First 1
    if(-not $xml){$xml=Get-ChildItem (Join-Path $tmp 'model') -Recurse -Filter '*.xml' | Select-Object -First 1}
    if(-not $xml){throw 'No se encontro model.xml en el paquete Intel.'}
    $bin=[IO.Path]::ChangeExtension($xml.FullName,'.bin')
    if(-not (Test-Path $bin)){throw "No se encontro BIN pareado para $($xml.FullName)"}
    Copy-Item $xml.FullName (Join-Path $target 'model.xml') -Force
    Copy-Item $bin (Join-Path $target 'model.bin') -Force
    $xmlHash=(Get-FileHash (Join-Path $target 'model.xml') -Algorithm SHA256).Hash.ToLower()
    $binHash=(Get-FileHash (Join-Path $target 'model.bin') -Algorithm SHA256).Hash.ToLower()
    $manifest=[ordered]@{
        name='Intel Worker Safety Gear Detection Bootstrap'; license='MIT'; source='Intel Edge AI Resources';
        source_url=$modelUrl; source_commit=$commit; downloaded_at=(Get-Date).ToUniversalTime().ToString('o');
        zip_sha256=$zipHash; model_xml_sha256=$xmlHash; model_bin_sha256=$binHash;
        classes=@('HELMET','VEST'); label_map=@{'1'='HELMET';'2'='VEST'};
        note='Bootstrap real para puesta en marcha/shadow. SAFETY_SHOES no soportado. No es modelo HYS certificado.'
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $target 'SOURCE_MANIFEST.json') -Encoding UTF8
    @"
Intel Worker Safety Gear Detection bootstrap
License: MIT
Source commit: $commit
Source: $modelUrl
HYS mapping verified against Intel sample code: DetectionOutput 1=safety_helmet, 2=safety_jacket.
The original model artifacts remain unmodified; HYS only stores source and SHA-256 provenance.
"@ | Set-Content (Join-Path $target 'THIRD_PARTY_NOTICE.txt') -Encoding UTF8
    Write-Host "[OK] model.xml SHA256=$xmlHash" -ForegroundColor Green
    Write-Host "[OK] model.bin SHA256=$binHash" -ForegroundColor Green

    if(-not $SkipSampleVideo){
        $demo=Join-Path $ProjectPath 'demo\intel_worker_safety_test.avi'
        Write-Host 'Descargando video real de prueba oficial Intel...' -ForegroundColor Cyan
        Invoke-WebRequest -Uri $videoUrl -OutFile $demo -UseBasicParsing
        Write-Host "[OK] Video de prueba: $demo" -ForegroundColor Green
    }

    & docker compose exec -T backend python -m app.ml_cli activate-intel
    if($LASTEXITCODE -ne 0){throw 'No se pudo activar modelo Intel en Model Registry.'}
    if(-not $SkipShadow){
        & docker compose exec -T backend python -m app.ml_cli deploy --model INTEL_WORKER_SAFETY_BOOTSTRAP --mode SHADOW --organization DEMO-HYS --camera DEMO01
        if($LASTEXITCODE -ne 0){Write-Host '[WARN] No se pudo desplegar SHADOW en DEMO01; el video offline sigue disponible.' -ForegroundColor Yellow}
    }
    & cmd.exe /d /c "docker compose restart vision-engine >nul 2>&1"
    if($LASTEXITCODE -ne 0){throw 'No se pudo reiniciar vision-engine.'}
    Write-Host '[PASS] BOOTSTRAP INTEL INSTALADO Y REGISTRADO' -ForegroundColor Green
} finally { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
