# Transcriptor — Especificación del proyecto

## 1. Visión

Aplicación de escritorio multiplataforma (Windows y macOS) para transcribir y auditar archivos de audio/vídeo, con diarización automática de hablantes y exportación a PDF. Reescritura del prototipo actual (Tkinter, single-file `app.py`) hacia una arquitectura modular con **PySide6**, motores Whisper optimizados por plataforma y empaquetado nativo (`.app` y `.exe`).

## 2. Alcance

### En alcance
- GUI con PySide6 (Qt 6) que corre idénticamente en Windows y macOS.
- Descarga y gestión de modelos Whisper en formato óptimo para cada SO:
  - macOS Apple Silicon → `mlx-whisper` (modelos `mlx-community/whisper-*`).
  - macOS Intel → `faster-whisper` CPU (int8).
  - Windows con NVIDIA → `faster-whisper` CUDA (float16).
  - Windows sin GPU → `faster-whisper` CPU (int8).
- Diarización con `pyannote.audio` (CUDA, MPS o CPU según disponibilidad).
- Persistencia del `HF_TOKEN` en el keyring del sistema (Keychain / Credential Manager).
- Selección de carpeta de audios y procesado batch.
- Limpieza opcional de audio con filtros FFmpeg.
- Exportación a PDF consolidado con hashes SHA-256 (auditoría).
- Tema claro/oscuro nativo Qt.
- Empaquetado: `.app` + `.dmg` para macOS, `.exe` + instalador para Windows.

### Fuera de alcance (v1)
- Linux (puede funcionar pero no se soporta oficialmente).
- Transcripción en streaming/en vivo.
- Edición manual del texto transcrito en la propia app.
- Sincronización en la nube.

## 3. Decisiones de arquitectura

| Tema | Decisión | Motivo |
|---|---|---|
| Binding Qt | **PySide6** | Licencia LGPL, soporte oficial Qt, mejor para distribuir comercial. |
| Almacén de credenciales | **`keyring`** (Keychain / Credential Manager) | Nunca toca disco en claro. |
| Motor Whisper macOS Apple Silicon | **mlx-whisper** | 3-5× más rápido que faster-whisper en M1-M4 y menos RAM. |
| Motor Whisper resto | **faster-whisper** | Mejor rendimiento CTranslate2 en CUDA y CPU x86. |
| Diarización | **pyannote.audio 3.1** | Único modelo open con calidad razonable hoy. |
| Empaquetado | **Nuitka** | Compila Python a binario nativo. Ejecutable más pequeño y arranque más rápido que alternativas. Decisión del Director (ver `CLAUDE.md` §6). |
| Settings | **QSettings** + **`keyring`** | Settings normales en QSettings; secretos en keyring. |
| Threading | **QThread + signals** | Pattern Qt idiomático; no bloquea la UI. |

## 4. Arquitectura de código

```
transcriptor/
├── pyproject.toml             # Nuitka + deps
├── src/transcriptor/
│   ├── __main__.py            # Entry point
│   ├── app.py                 # QApplication + bootstrap
│   ├── platform.py            # Detección SO / GPU / motor
│   ├── config.py              # QSettings + keyring wrapper
│   ├── models/
│   │   ├── registry.py        # Catálogo de modelos por plataforma
│   │   └── downloader.py      # huggingface_hub con progreso
│   ├── engines/
│   │   ├── base.py            # Interfaz TranscriptionEngine
│   │   ├── mlx_engine.py      # mlx-whisper (macOS ARM)
│   │   └── faster_engine.py   # faster-whisper (CUDA/CPU)
│   ├── pipeline/
│   │   ├── audio.py           # FFmpeg, conversión, filtros
│   │   ├── diarization.py     # pyannote wrapper
│   │   ├── merge.py           # Cruce segmentos ↔ speakers
│   │   └── hashing.py         # SHA-256 + metadatos
│   ├── report/
│   │   ├── pdf.py             # fpdf2 con soporte UTF-8 real
│   │   └── txt.py             # Salida _ANALIZADO.txt
│   ├── ui/
│   │   ├── main_window.py     # QMainWindow
│   │   ├── settings_dialog.py # Token + carpeta modelos + idioma
│   │   ├── model_manager.py   # Diálogo descarga modelos
│   │   ├── progress.py        # Widgets de progreso
│   │   └── theme.py           # Light/dark
│   └── workers/
│       ├── transcribe_worker.py
│       └── download_worker.py
└── tests/
```

## 5. Dependencias

```
# Runtime
PySide6>=6.7
pyannote.audio>=3.3
faster-whisper>=1.0           # Windows + Mac Intel
mlx-whisper>=0.4 ; sys_platform == "darwin" and platform_machine == "arm64"
huggingface_hub>=0.24
keyring>=25
torch>=2.3                    # CPU por defecto; CUDA wheel separado en Windows
fpdf2>=2.7
tinytag>=2.0
ffmpeg-python>=0.2            # opcional, wrapper

# Dev
nuitka>=2.4
pytest>=8
ruff>=0.6
mypy>=1.10
imageio                       # requerido por Nuitka para iconos
```

### FFmpeg
Binario externo, no se distribuye con la app (licencia). Estrategia:
1. Detectar en `PATH`.
2. Detectar bundle local (`./ffmpeg` o `./ffmpeg.exe` junto al ejecutable).
3. En macOS, sugerir `brew install ffmpeg`.
4. En Windows, ofrecer descarga automática desde `https://www.gyan.dev/ffmpeg/builds/` a la carpeta de la app (con consentimiento del usuario).

## 6. Modelos Whisper

### Catálogo (`src/transcriptor/models/registry.py`)

| ID lógico | macOS ARM (MLX) | Windows / Mac Intel (CTranslate2) | Tamaño aprox |
|---|---|---|---|
| `tiny` | `mlx-community/whisper-tiny-mlx` | `Systran/faster-whisper-tiny` | 75 MB |
| `base` | `mlx-community/whisper-base-mlx` | `Systran/faster-whisper-base` | 145 MB |
| `small` | `mlx-community/whisper-small-mlx` | `Systran/faster-whisper-small` | 480 MB |
| `medium` | `mlx-community/whisper-medium-mlx` | `Systran/faster-whisper-medium` | 1.5 GB |
| `large-v3` | `mlx-community/whisper-large-v3-mlx` | `Systran/faster-whisper-large-v3` | 3 GB |
| `large-v3-turbo` | `mlx-community/whisper-large-v3-turbo` | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | 1.6 GB |

`registry.py` expone `resolve(model_id) -> HFRepo` que devuelve el repo correcto según `platform.detect_engine()`.

### Descarga
- `huggingface_hub.snapshot_download` con `tqdm` redirigido a `QProgressBar` vía signals.
- Caché en `~/.cache/huggingface/hub` por defecto, configurable.
- Verificación de checksum opcional.

## 7. Pipeline de transcripción

Por archivo:

```
input.{mp3,m4a,wav,mp4,...}
   │
   ▼  audio.convert_to_wav(rate=16000, mono=True, filters=optional)
tmp.wav
   │
   ├──► diarization.run(tmp.wav)              → List[Turn(speaker, start, end)]
   │
   └──► engine.transcribe(tmp.wav, model)     → List[Segment(text, start, end)]
                                │
                                ▼
                       merge.assign_speakers(segments, turns, max_speakers)
                                │
                                ▼
                    report.txt.write(...) + report.pdf.append(...)
                                │
                                ▼
                       hashing.sha256(input) → registrado en resumen
```

### Bug a corregir del prototipo
[app.py:255](app.py:255) actual: `max_ovl, speaker = spk` (destructura el string del speaker). Debe ser:
```python
if ovl > max_ovl:
    max_ovl = ovl
    speaker = spk
```

## 8. Pantallas / UX

### 8.1 Ventana principal
- Barra superior: indicador de motor activo (MLX / CUDA / CPU) + botón Settings + toggle tema.
- Bloque "Carpeta de audios" con botón **Seleccionar** y label de ruta.
- Bloque "Modelo" con `QComboBox` de modelos disponibles + botón **Gestionar modelos** (abre diálogo de descarga).
- Bloque "Hablantes" con `QSpinBox` (2-5) y checkbox "Limpiar audio (FFmpeg)".
- Botones grandes: **Transcribir** y **Unificar reportes** (PDF).
- `QProgressBar` por archivo + `QProgressBar` global.
- Panel colapsable de logs (`QPlainTextEdit` readonly).

### 8.2 Diálogo Settings
- Campo `HF_TOKEN` (mostrar/ocultar) → guardar en keyring al aceptar.
- Botón "Probar token" que llama a `huggingface_hub.whoami`.
- Ruta de caché de modelos (con `QFileDialog`).
- Idioma forzado (auto / es / en / …) — pasa a Whisper.
- Tema (auto / claro / oscuro).

### 8.3 Diálogo Gestor de modelos
- Tabla con: nombre, tamaño, estado (no descargado / descargado / actualización disponible).
- Acciones por fila: Descargar, Eliminar, Verificar.
- `QProgressDialog` durante descargas.

### 8.4 Primer arranque
- Si no hay token en keyring → forzar Settings con foco en el campo del token y enlace a la guía de creación.
- Si no hay modelo descargado → sugerir `base` o `large-v3-turbo` según GPU detectada.

## 9. Persistencia

| Dato | Dónde | Por qué |
|---|---|---|
| `HF_TOKEN` | `keyring` (servicio `transcriptor`, user `hf_token`) | Secreto. |
| Última carpeta usada | `QSettings` | Conveniencia. |
| Modelo preferido | `QSettings` | Conveniencia. |
| Tema | `QSettings` | Conveniencia. |
| Ruta de caché de modelos | `QSettings` (default `~/.cache/huggingface/hub`) | Configurable. |
| Idioma forzado | `QSettings` | Conveniencia. |

`QSettings` resuelve automáticamente:
- macOS → `~/Library/Preferences/com.transcriptor.app.plist`
- Windows → `HKCU\Software\Transcriptor\App`

## 10. Threading

Regla: **ningún cálculo en el hilo de UI**.

- `TranscribeWorker(QThread)` ejecuta `pipeline` por archivo y emite `progress(int)`, `file_done(path)`, `error(str)`, `finished()`.
- `DownloadWorker(QThread)` envuelve `snapshot_download` con callback de progreso.
- La cancelación se hace con `QThread.requestInterruption()` + chequeos en el bucle de archivos.

## 11. Empaquetado

### Nuitka

Compilamos a binario nativo con Nuitka. Plugin de PySide6 obligatorio. Stdlib y dependencias se incluyen con `--standalone`. Se distribuye en bundle: `.app` en macOS y carpeta + instalador en Windows.

#### Build macOS (Apple Silicon + Intel)

```bash
python -m nuitka \
  --standalone \
  --macos-create-app-bundle \
  --macos-app-icon=src/transcriptor/resources/logo_app.icns \
  --macos-app-name=Transcriptor \
  --macos-app-version=0.2.0 \
  --macos-signed-app-name=com.letzzar.transcriptor \
  --enable-plugin=pyside6 \
  --include-package=transcriptor \
  --include-package-data=pyannote \
  --include-package-data=faster_whisper \
  --include-package-data=mlx_whisper \
  --output-dir=dist \
  src/transcriptor/__main__.py
```

Para universal binary (arm64 + x86_64), añadir `--macos-target-arch=universal`. Ojo: si se incluye `mlx-whisper`, debe ser solo arm64 (MLX no soporta x86_64).

#### Build Windows

```bash
python -m nuitka ^
  --standalone ^
  --windows-icon-from-ico=logo_app.ico ^
  --windows-console-mode=disable ^
  --windows-company-name=letzzar ^
  --windows-product-name=Transcriptor ^
  --windows-file-version=0.2.0 ^
  --enable-plugin=pyside6 ^
  --include-package=transcriptor ^
  --include-package-data=pyannote ^
  --include-package-data=faster_whisper ^
  --output-dir=dist ^
  src\transcriptor\__main__.py
```

Recomendado añadir `--lto=yes` y `--jobs=N` para acelerar.

#### Scripts de build

Bajo `scripts/`:
- `build_macos.sh` — build + creación de `.dmg` con `create-dmg` o `hdiutil`.
- `build_windows.bat` — build + instalador con Inno Setup (`scripts/installer.iss`).

#### Tamaño

PyTorch + CUDA DLLs son grandes (~2 GB en Windows). Estrategia:
- **Mac arm64**: incluir solo MLX (no torch CUDA, no aplica).
- **Mac Intel**: incluir torch CPU.
- **Windows**: dos builds:
  - `Transcriptor-Setup-CPU.exe` (~500 MB) sin CUDA.
  - `Transcriptor-Setup-CUDA.exe` (~2 GB) con CUDA wheels.

Alternativa: un único instalador que descargue torch+CUDA al primer arranque desde el index oficial. Decisión a tomar al llegar a F8.

#### Firma

- **macOS**: firmar con `codesign` usando Developer ID y notarizar con `notarytool`. Nuitka acepta firmar al final pasando `--macos-signed-app-name` + ejecución manual de `codesign --deep --force --options runtime --sign ...`.
- **Windows**: firmar el `.exe` resultante con `signtool` y certificado de code signing (opcional, evita SmartScreen).

## 12. Roadmap

| Fase | Entrega |
|---|---|
| **F0 — Esqueleto** | `pyproject.toml`, layout `src/transcriptor/`, ventana vacía PySide6 que abre en Mac y Win. |
| **F1 — Settings + detección** | Diálogo settings, keyring, `platform.detect_engine()`, persistencia. |
| **F2 — Motor MLX** | `MlxEngine` funcionando en Mac ARM con un modelo. |
| **F3 — Motor faster-whisper** | `FasterEngine` con CPU + CUDA. |
| **F4 — Pipeline completo** | Audio → diarización → merge → txt. |
| **F5 — Gestor de modelos** | Descargar/eliminar con progreso. |
| **F6 — Reporte PDF** | fpdf2 con UTF-8 (fuente DejaVu embebida). |
| **F7 — Tema + pulido UX** | Light/dark, atajos, mensajes de error humanos. |
| **F8 — Nuitka** | Builds `.app` y `.exe` con Nuitka, scripts `build_macos.sh` / `build_windows.bat`, firmas. |

## 13. Cambios respecto al prototipo

| Antes (`app.py`) | Ahora |
|---|---|
| Tkinter, single-file | PySide6, modular |
| `os.startfile` (Windows-only) | `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` |
| `subprocess.CREATE_NO_WINDOW` | `QProcess` o subprocess multiplataforma con detección |
| `os.chdir(directorio)` | Paths absolutos siempre |
| PDF en `latin-1` con `'replace'` | PDF UTF-8 con fuente embebida (DejaVu Sans) |
| `HF_TOKEN` en env var | Diálogo Settings + keyring |
| Bug `max_ovl, speaker = spk` | Corregido |
| Sin `requirements.txt` | `pyproject.toml` + scripts de build con Nuitka |
| Solo `faster-whisper` | MLX en Mac ARM, faster-whisper en el resto |
| Hardcoded "Windows Edition" en el título | Título neutral, indicador dinámico del motor |

## 14. Criterios de aceptación v1

1. La app abre en macOS 13+ (Apple Silicon e Intel) y Windows 10/11 sin errores.
2. El primer arranque guía al usuario a meter el `HF_TOKEN` y descargar un modelo.
3. Transcripción de un `.m4a` de 5 min produce `_ANALIZADO.txt` con timestamps y al menos 2 hablantes correctamente etiquetados.
4. El PDF consolidado renderiza correctamente caracteres acentuados, eñes y comillas tipográficas.
5. La UI no se congela durante transcripción ni descarga.
6. La app empaquetada arranca sin requerir Python instalado.
