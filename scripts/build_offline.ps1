# =============================================================================
#  Prepara y compila el instalador OFFLINE de Transcriptor (CPU + CUDA, todo).
#
#  Pasos:
#   1. Descarga el wheelhouse (torch cpu + cu126 + motores + deps) a
#      dist\offline_payload\wheels\{cpu,cu126}.
#   2. Copia los modelos HF (Whisper turbo, pyannote, genero) a
#      dist\offline_payload\hf_cache\hub.
#   3. Copia ffmpeg.exe a dist\offline_payload.
#   4. Compila dist\Transcriptor-Setup-Offline.exe con Inno Setup.
#
#  Requisito previo: haber compilado el bundle con scripts\build_windows.bat
#  (debe existir dist\Transcriptor\Transcriptor.exe) y tener los modelos en la
#  cache HF del usuario.
#
#  Uso:  powershell -ExecutionPolicy Bypass -File scripts\build_offline.ps1
# =============================================================================
param(
    [string]$Python = ".venv\Scripts\python.exe",
    [switch]$SkipWheels,   # reutiliza wheels ya descargados
    [switch]$SkipModels    # reutiliza modelos ya copiados
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path "dist\Transcriptor\Transcriptor.exe")) {
    throw "Falta dist\Transcriptor: compila antes con scripts\build_windows.bat"
}

$payload = "dist\offline_payload"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { throw "No se encontro Inno Setup (ISCC.exe)" }

# --- 1) Wheelhouse cpu + cu126 ------------------------------------------------
$variants = [ordered]@{
    cpu   = "https://download.pytorch.org/whl/cpu"
    cu126 = "https://download.pytorch.org/whl/cu126"
}
if (-not $SkipWheels) {
    foreach ($v in $variants.Keys) {
        $dest = "$payload\wheels\$v"
        New-Item -ItemType Directory -Force $dest | Out-Null
        Write-Host "==> Descargando wheels [$v] ..." -ForegroundColor Cyan
        & $Python -m pip download --only-binary=:all: `
            --index-url $variants[$v] --extra-index-url https://pypi.org/simple `
            -d $dest `
            torch faster-whisper==1.2.1 pyannote.audio==4.0.4 transformers==5.10.2
        if ($LASTEXITCODE -ne 0) { throw "pip download fallo para la variante $v" }
    }
}

# --- 2) Modelos HF ------------------------------------------------------------
if (-not $SkipModels) {
    $hub = "$env:USERPROFILE\.cache\huggingface\hub"
    $dstHub = "$payload\hf_cache\hub"
    New-Item -ItemType Directory -Force $dstHub | Out-Null
    $models = @(
        "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
        "models--pyannote--speaker-diarization-community-1",
        "models--pyannote--segmentation-3.0",
        "models--pyannote--speaker-diarization-3.1",
        "models--alefiury--wav2vec2-large-xlsr-53-gender-recognition-librispeech"
    )
    foreach ($m in $models) {
        $src = Join-Path $hub $m
        if (Test-Path $src) {
            Write-Host "==> Copiando modelo $m ..." -ForegroundColor Cyan
            robocopy $src (Join-Path $dstHub $m) /MIR /NFL /NDL /NJH /NJS /NC /NS | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "robocopy fallo copiando $m" }
        } else {
            Write-Warning "Modelo no encontrado en cache: $m"
        }
    }
}

# --- 3) FFmpeg ----------------------------------------------------------------
$ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if ($ff) {
    # WinGet expone un symlink en Links\; resolvemos el binario real.
    $item = Get-Item $ff
    $real = if ($item.LinkType) { $item.ResolveLinkTarget($true).FullName } else { $ff }
    Copy-Item $real "$payload\ffmpeg.exe" -Force
    Write-Host "==> FFmpeg incluido desde: $real" -ForegroundColor Cyan
} else {
    Write-Warning "ffmpeg no esta en PATH; el instalador NO llevara ffmpeg (la app lo pedira por winget en el 1er uso)."
}

# --- 4) Instalador ------------------------------------------------------------
Write-Host "==> Compilando instalador offline (puede tardar varios minutos)..." -ForegroundColor Cyan
& $iscc "scripts\installer_offline.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC fallo" }

Write-Host "`nLISTO: dist\Transcriptor-Setup-Offline.exe" -ForegroundColor Green
