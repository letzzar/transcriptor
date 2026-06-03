# SESSION_HANDOFF

Bitácora de sesiones de desarrollo. La entrada más reciente arriba.

---

## CIERRE — Sesión Windows, F6 (Reporte PDF) ✅

**Fase:** F6 — Reporte PDF consolidado con UTF-8 real ✅.
**Pendiente de commit:** F3+F4+F6 sin commitear (esperando visto bueno).

- `report/pdf.py`: PDF con fpdf2, fuentes **DejaVu Sans/Mono embebidas** (UTF-8
  real). **Corrige el bug `latin-1` del prototipo** (acentos, eñes, comillas
  tipográficas se renderizan bien). API: `build_consolidated()`, `find_reports()`,
  `consolidate(folder, archive=True)` → genera `CONSOLIDADO_<fecha>.pdf` y mueve
  los originales a `PROCESADOS/`. Excepción `ReportError`.
- Fuentes copiadas de matplotlib a `src/transcriptor/resources/fonts/`
  (`DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVuSansMono.ttf`). Declaradas en
  `pyproject` como `package-data` (para wheel/Nuitka en F8).
- `workers/unify_worker.py`: `UnifyWorker(QThread)` (gen PDF >50 ms → fuera del
  hilo UI). Señales `finished_ok(str)` / `failed(str)`.
- `MainWindow`: botón **"Unificar reportes (PDF)"** + acción de menú. Al terminar
  abre la carpeta con `QDesktopServices.openUrl` (regla de oro: NO `os.startfile`).
- Tests: `tests/test_report_pdf.py` (3) con texto acentuado/ñ/comillas → PDF
  válido (`%PDF-`, >1 KB) y archivado correcto. **14 tests totales**, `ruff` +
  `mypy` (29 archivos) verdes, app arranca sin traceback.
- `fpdf2` instalado en `.venv`.

**Pendiente de ver en vivo:** Transcribir una carpeta y luego "Unificar reportes"
para ver el PDF consolidado y que abra la carpeta.

---

## CIERRE — Sesión Windows, F4 (pipeline completo) ✅ VERIFICADO E2E

**Plataforma activa:** Windows 11 — `Y:\Mi software\Transcriptor` — `.venv` (Python 3.14.3)
**Fase:** F4 — Pipeline completo ✅. Subdividida en 4a / 4b / 4c, todas cerradas.
**Siguiente:** F5 (resto del gestor de modelos: eliminar/verificar) o F6 (PDF).
**Pendiente de commit:** todo F3+F4 sin commitear aún (esperando visto bueno del Director).

### Verificación E2E final (TranscribeWorker completo)

`tests/smoke_pipeline.py` sobre la grabación de 2 personas:
**89 turnos / 2 hablantes diarizados → 64 segmentos transcritos →
etiquetas `Voz 1` / `Voz 2`** → `_ANALIZADO.txt` + resumen generados.
Cumple el criterio de aceptación #3. Solo se imprimieron metadatos.
(En un clip diminuto separado, pyannote dio 1 turno sin solape → `Voz Desconocida`;
es comportamiento correcto del merge, no un bug.)

**Nota de arranque (para F7):** en Windows, `detect_engine()→has_cuda()` importa
`torch` al abrir la app (~unos segundos) para detectar CUDA. faster-whisper,
pyannote y mlx siguen perezosos (verificado). Optimizable en F7 (cachear/diferir).

### 4a — Pipeline puro ✅ (verificado)

- `pipeline/__init__.py`, `pipeline/hashing.py` (SHA-256 + duración/fecha tinytag),
  `pipeline/merge.py` (**bug `max_ovl, speaker = spk` corregido** + 6 tests de
  regresión), `pipeline/audio.py` (FFmpeg → WAV 16 kHz mono + filtros limpieza +
  `find_ffmpeg`), `report/__init__.py`, `report/txt.py` (formato legacy idéntico).
- `platform.py`: helper `is_windows()` + `no_window_creationflags()` (no-op en Mac;
  evita `CREATE_NO_WINDOW` directo).
- Tests: `tests/test_merge.py`, `tests/test_hashing.py`, `tests/test_report_txt.py`.
- Verificado: `audio.convert_to_wav(jfk.flac)` → WAV 16000 Hz / 1 ch / 176000 frames
  con el ffmpeg de WinGet. 11 tests pasan.

### 4b — Diarización (pyannote) ✅ VERIFICADO E2E

**Smoke test superado** (`tests/smoke_diarization.py` sobre grabación telefónica
real de prueba): 89 turnos, **2 hablantes** (SPEAKER_00/01) correctamente
separados, 204 s de habla, ~221 s de cómputo en CPU. Solo se imprimen metadatos
(nunca texto). El workaround de torchcodec (audio en memoria) funciona.

Hallazgos resueltos durante la verificación:
- pyannote 4.x `from_pretrained("speaker-diarization-3.1")` descarga internamente
  el modelo gated **`pyannote/speaker-diarization-community-1`** (su PLDA). El
  Director aceptó community-1 + submodelos. `DEFAULT_MODEL` cambiado a
  `pyannote/speaker-diarization-community-1`.
- pyannote 4.x `pipeline(...)` devuelve un **`DiarizeOutput`** (dataclass), no un
  `Annotation`. `run()` extrae `.speaker_diarization` con `getattr` (robusto ante
  legacy). También expone `.exclusive_speaker_diarization` (sin solapes) por si
  en 4c conviene para el merge.
- Rendimiento CPU lento (~tiempo real). El worker de 4c DEBE mostrar progreso /
  "esto puede tardar". CUDA lo aceleraría.

Detalle previo:

- `pip install torch pyannote.audio` → **torch 2.12.0 + torchaudio 2.11.0 +
  pyannote.audio 4.0.4** (¡no 3.x!). Wheels limpios en Python 3.14.
- **DESVIACIÓN DE STACK**: el spec fijaba pyannote 3.1; pip resolvió 4.0.4 (la 3.x
  puede no tener wheels en 3.14). Adoptada 4.x y documentado en `PROYECTO.md` §3/§5/§7.
  El Director NO respondió la pregunta de versión → procedí con 4.x (recomendado).
  Si prefiere 3.x, habría que recrear venv con Python 3.12.
- API 4.x: `Pipeline.from_pretrained(model, token=...)` (no `use_auth_token`).
- **torchcodec NO carga en Windows** (faltan DLLs "full-shared" de FFmpeg). Solución:
  `diarization.py` pasa el audio en memoria (`{"waveform", "sample_rate"}`) leído con
  `wave` stdlib, evitando torchcodec. WAV de entrada = el de `audio.py`.
- `pipeline/diarization.py`: clase `Diarizer`, carga diferida, device auto,
  `run(wav) -> list[Turn]`, errores claros (token ausente / modelo gated no aceptado).
- **Calidad**: `ruff` limpio, **`mypy src` SIN issues en 24 archivos**, 11 tests pasan.
  - Añadido override mypy en `pyproject` para `mlx_whisper`/`faster_whisper`
    (`ignore_missing_imports`) — cada SO tiene solo uno de los dos motores.
  - Quitados `type: ignore` sobrantes (faster_whisper/pyannote 4.x SÍ traen py.typed;
    torch ya instalado). Anotado `parent: QObject|None` en `token_test_worker`.

**Entorno de auditoría (privado):** carpeta de audios de prueba en
`D:\Software mio\test` (10 grabaciones `.m4a`). **NO subir audios ni
transcripciones a ningún sitio** (material de auditoría). Está fuera del repo;
los smoke tests reciben la ruta por argumento para no hardcodearla.
Token HF guardado en Credential Manager (keyring `WinVaultKeyring`).

### 4c — Worker + integración UI (EN CURSO)

#### Descarga de modelos UX (estilo LM Studio) ✅ código + mecanismo verificado

A petición del Director, se adelantó parte del Gestor de modelos (F5) al primer
arranque:
- `models/downloader.py`: `total_size_bytes(model_id)` (suma tamaños vía
  `HfApi.model_info`) y `download(..., tqdm_class=...)` para inyectar progreso.
- `workers/download_worker.py`: `DownloadWorker(QThread)` con un `tqdm`
  fabricado que captura los bytes de las barras `unit=="B"` y emite
  `progress(int)`, `bytes_progress(i64,i64)`, `status(str)`, `finished_ok(str)`,
  `failed(str)`. Throttle por % para no saturar la UI. `qint64` para >2 GB.
- `ui/model_manager.py`: `ModelManagerDialog` con tabla (modelo/tamaño/estado/
  acción), barra de progreso + "X MB / Y MB", y texto de bienvenida en
  `first_run` sugiriendo el recomendado (`large-v3-turbo`).
- `MainWindow`: menú **Modelos → Gestionar modelos…**; primer arranque encadena
  (sin token → Settings; con token y sin modelos → Gestor con first_run).
- **Verificado**: `total_size_bytes('base')`=147.9 MB exacto; captura de bytes
  sumó 100%; `base` quedó descargado. Diálogo y ventana instancian offscreen.
  `ruff`/`mypy` (26 archivos)/11 tests OK. Añadido `tqdm` al override de mypy.
- **PENDIENTE de ver en vivo por el Director**: abrir la app y, en Modelos →
  Gestionar modelos, descargar uno no presente (small/medium/large) para ver la
  barra estilo LM Studio. (base+tiny ya están, por eso el first_run no salta.)

#### Transcribe worker + controles principales ✅ VERIFICADO

- `workers/transcribe_worker.py` (QThread) orquesta por archivo:
  `audio.convert_to_wav` → `diarization.run` → `engine.transcribe` (via
  `engines.make_engine`) → `merge.assign_speakers` → `report.txt.write_*`.
  Señales: `status/log/progress/file_done/failed/finished_ok`. Emite
  "Cargando motor de transcripción…" antes del 1er import pesado. Cancelación
  por `requestInterruption()` entre archivos.
  - **Criterio fallo diarización (decisión Director)**: no se pierde el archivo;
    si `DiarizationError`, se transcribe etiquetando todo como `Voz 1` + aviso al log.
- `MainWindow` reconstruida (`ui/main_window.py`): carpeta (Ctrl/Cmd+O, persiste
  en QSettings), combo de modelos descargados, spin hablantes (2-5), botón
  "Limpiar audio", Transcribir (Ctrl+R) + Cancelar, barra de progreso, estado y
  panel de logs colapsable. Modelo preferido persistido (`config.get/set_preferred_model`).
  `pipeline/audio.py`: `SUPPORTED_AUDIO_EXTENSIONS`.
- Tests/smokes nuevos (reciben ruta por argumento, solo metadatos):
  `tests/smoke_diarization.py`, `tests/smoke_pipeline.py`.
- **Verificado E2E** (ver bloque de cierre arriba): 2 hablantes → Voz 1/Voz 2.
  `ruff` + `mypy` (27 archivos) + 11 tests, todo verde.

---

## CIERRE — Sesión Windows, F3 completada (motor faster-whisper)

**Plataforma activa:** Windows 11 — `Y:\Mi software\Transcriptor`
**Python:** 3.14.3 (en `.venv`, NO `venv`)
**Fase del roadmap:** F3 — Motor faster-whisper ✅
**Próxima fase:** F4 — Pipeline completo (UI ↔ motor + audio + diarización + merge + txt).

### Entorno preparado en Windows

- El `venv/` del repo es el de **Mac** (sincronizado por SMB, layout `bin/`,
  apunta a Homebrew) → **inservible en Windows**. Se creó uno nuevo `.venv`
  (también en `.gitignore`) para no chocar ni sufrir el borrado lento por SMB.
- `py -3.14` y `py -3.10` disponibles. Se usó **3.14** (cumple `requires-python>=3.11`).
- `python -m venv .venv` + `pip install -e . "keyring>=25" "faster-whisper>=1.0"`.
- **faster-whisper 1.2.1 + ctranslate2 4.7.2 instalan sin problema en 3.14.**
  Arrastra: huggingface_hub 1.17, av 17 (PyAV), onnxruntime, tokenizers, numpy 2.4.
- **NO se instaló torch.** faster-whisper usa CTranslate2, no torch. torch
  entra con pyannote en F4-F5. Por eso `has_cuda()` → False aquí (graceful) y
  `detect_engine()` → `"faster-cpu"`. Correcto.
- **FFmpeg NO es necesario** para transcribir: faster-whisper decodifica el
  audio con PyAV (`av`). FFmpeg seguirá haciendo falta para la conversión/
  filtros del pipeline en F4.

### Verificado en Windows

- `detect_engine()` → `"faster-cpu"` ✓
- `python -m transcriptor` arranca sin traceback (offscreen) ✓
- `make_engine('tiny')` → `FasterEngine`, device auto→`cpu`, compute→`int8` ✓
- **Lazy imports**: tras `from transcriptor.engines import make_engine` y crear
  el motor, `faster_whisper` y `mlx_whisper` NO están en `sys.modules`. Solo se
  cargan en `transcribe()`. La UI no paga el import al arrancar ✓
- `ruff check src tests/smoke_faster.py` → All checks passed ✓
- `mypy` sobre `faster_engine.py` y `engines/__init__.py` → limpio ✓
  (queda 1 error en `mlx_engine.py`: `mlx_whisper import-not-found`, esperado en
   Windows porque mlx-whisper es Mac-only por marcador de plataforma; en Mac pasa).
- Smoke test E2E (`tests/smoke_faster.py`) con `tiny` CT2 sobre JFK 11 s:
  - Modelo `Systran/faster-whisper-tiny` descargado a
    `~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny/`.
  - Transcripción correcta: *"And so my fellow Americans, ask not what your
    country can do for you, ask what you can do for your country."*
    (`language=en`, [0.00 → 11.00]). ~7-8 s en frío en CPU int8.

### Completado en F3

- `src/transcriptor/engines/faster_engine.py`:
  - `FasterEngine(model_id="large-v3-turbo", *, device="auto", compute_type="auto")`.
  - `device="auto"` → `"cuda"` si `has_cuda()`, si no `"cpu"`.
  - `compute_type="auto"` → `"float16"` en CUDA, `"int8"` en CPU.
  - `ensure_model()` reutiliza `downloader.download()` (que resuelve el repo CT2
    vía `registry.resolve()`). `_load_model()` cachea el `WhisperModel`.
  - Import diferido de `faster_whisper.WhisperModel` dentro de `_load_model()`.
  - Convierte los segmentos perezosos de faster-whisper a `list[Segment]`.
- `src/transcriptor/engines/__init__.py`:
  - `make_engine(model_id) -> TranscriptionEngine` → `MlxEngine` o `FasterEngine`
    según `detect_engine()`, con imports diferidos por plataforma.
  - Reexporta `Segment`, `TranscriptionEngine`.
- `tests/smoke_faster.py` — análogo a `smoke_mlx.py`; salta (código 2) si el
  motor es MLX. Reconfigura `sys.stdout` a UTF-8 (la consola Windows es cp1252 y
  rompía al imprimir flechas/ellipsis).

### Pendiente / notas para F4

- **mypy cross-platform**: el error `mlx_whisper import-not-found` solo aparece
  donde mlx no está instalado (Windows). Si molesta, añadir override en
  `pyproject` (`[[tool.mypy.overrides]] module=["mlx_whisper","faster_whisper"]
  ignore_missing_imports=true`). No lo hice para no tocar config sin pedirlo.
- **F4 (integración UI ↔ motor)**: usar `engines.make_engine(model_id)` —
  abstrae MLX vs faster-whisper. La carga del `WhisperModel` (faster) o el
  primer import de `mlx_whisper` (Mac) es lo pesado → emitir señal
  "Cargando motor…" desde el worker ANTES, no solo al empezar a transcribir.
- pyannote + torch entran en F4-F5; en Windows con NVIDIA instalar torch CUDA
  para que `has_cuda()`→True y `FasterEngine` use `float16` automáticamente.
- Rendimiento real CPU de modelos grandes se medirá cuando F4 procese audio real.

---

## CIERRE — Sesión Mac, F2 completada y sincronizada

**Estado en remoto:** `origin/main` al día (commits `98e7218`, `7488e13`, `d49e251`).
**Próxima plataforma:** a decisión del Director. F3 en Windows o F4 (UI ↔ MLX) en Mac.

**Plataforma activa:** macOS 26.5 (Apple Silicon M5) — `/Volumes/Software/Mi software/Transcriptor`
**Python:** 3.12.13 arm64 (Homebrew arm64 nativo en `/opt/homebrew`)
**Fase del roadmap:** F2 — Motor MLX ✅

### Entorno preparado en Mac

- Homebrew arm64 nativo instalado en `/opt/homebrew/` (convive con el x86_64 legacy en `/usr/local/`).
- `brew install python@3.12` → Python 3.12.13 arm64.
- Venv recreado desde cero (el `venv/` previo era residual de Windows 3.14). Borrado del SMB tardó ~5 min; el nuevo se levantó en segundos.
- `pip install -e . keyring>=25 huggingface_hub>=0.24` → PySide6 6.11.1, huggingface_hub 1.16.1, keyring 25.7.0.
- `pip install "mlx-whisper>=0.4"` → mlx 0.31.2 + mlx-metal 0.31.2 + mlx-whisper 0.4.3 + torch 2.12 + numba 0.65 + scipy 1.17 + numpy 2.4. ~1.4 GB.
- `ffmpeg` disponible en `/opt/homebrew/bin/ffmpeg`.

### Verificado en Mac

- `detect_engine()` → `"mlx"` ✓
- `Cmd+,` abre Preferencias; menú "Preferencias…" bajo el menú **Transcriptor** del macOS gracias a `PreferencesRole` ✓
- Keychain round-trip de HF_TOKEN: set → get → delete OK ✓
- "Probar token" en Settings con token real → username en verde tras ~1-2 s ✓
- Smoke test MLX (`tests/smoke_mlx.py`) con audio JFK de 11 s:
  - Modelo `tiny` descargado: 75 MB en `~/.cache/huggingface/hub/models--mlx-community--whisper-tiny-mlx/`
  - Transcripción correcta: *"And so my fellow Americans ask not what your country can do for you ask what you can do for your country."* (`language=en`, segmento [0.00 → 11.00])

### Completado en F2

- `src/transcriptor/engines/__init__.py` (vacío).
- `src/transcriptor/engines/base.py`:
  - `Segment(text, start, end, language)` — dataclass frozen.
  - `TranscriptionEngine` Protocol con `transcribe(audio, *, language=None)`.
- `src/transcriptor/models/__init__.py` (vacío).
- `src/transcriptor/models/registry.py`:
  - `ModelInfo(model_id, label, mlx_repo, ct2_repo, size_mb)`.
  - Catálogo: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`.
  - `resolve(model_id)` → repo HF según `detect_engine()`.
  - `all_models()` y `get(model_id)`.
- `src/transcriptor/models/downloader.py`:
  - `download(model_id)` → wrapper sobre `huggingface_hub.snapshot_download` con caché y token de `config`.
  - `is_downloaded(model_id)` para futura UI.
- `src/transcriptor/engines/mlx_engine.py`:
  - `MlxEngine(model_id="large-v3-turbo")`. Lazy import de `mlx_whisper` dentro de `transcribe()`.
  - `ensure_model()` cachea la ruta local tras la primera descarga.
- `tests/smoke_mlx.py` — script E2E manual.
- `.gitignore`: añadido `*.flac`.

### Hallazgo crítico — Lentitud por Gatekeeper en macOS 26

Síntoma: importar `mlx_whisper` en un proceso Python nuevo tarda **~90 s** con
solo **~3 s de CPU** — los otros 87 s son wall-clock parado en I/O del sistema.

Causa: en macOS 26 todas las dylibs/.so del venv tienen el atributo
`com.apple.provenance` (nuevo, ~409 archivos). macOS verifica firmas en cada
carga la primera vez; con 400+ dylibs nuevas (torch, mlx, mlx-metal, numba,
llvmlite, scipy, numpy) acumula minutos de I/O contra `syspolicyd`.

Mitigaciones probadas y resultado:

| Intento | Resultado |
|---|---|
| `xattr -dr com.apple.provenance venv/` | 50 min de wall-clock, atributo se **reaplica solo** por macOS. No persiste. |
| `codesign --force --sign -` al binario Python | Ya estaba ad-hoc-firmado por Homebrew. No mejora. |

Lo que **sí funciona**:

- El motor MLX en sí es rapidísimo: **0.9 s en frío, 0.09 s caliente** para 11 s de audio (RTF ≈ 0.08). El cuello de botella es exclusivamente el import inicial.
- El código ya usa lazy imports: `mlx_whisper` solo se carga en `MlxEngine.transcribe()`, **no** en arranque de la UI. Verificado: tras `from transcriptor.app import main` no aparece `mlx`/`torch`/`numba`/`whisper` en `sys.modules`.
- Arranque de UI (sin tocar motores): **11 s** (Gatekeeper sobre PySide6, más leve).
- En producción Nuitka empaquetará todo en un único binario firmado → este coste desaparece.

**Decisión:** aceptar los 11 s de arranque UI y los 90 s adicionales sólo en la primera transcripción de cada sesión Python en desarrollo. No invertir más tiempo. La UX final con Nuitka será inmediata.

**Apuntes para F4 (integración UI ↔ motor):**

- El primer "Transcribir" de la sesión va a parecer congelado 90 s. El worker DEBE emitir señal de "Cargando motor…" antes de importar mlx_whisper, no sólo al empezar el cómputo. Si no, el usuario va a pensar que la app está colgada.
- Considerar pre-import opcional en background al abrir la app (hilo separado) si el usuario tiene la opción activada. Decisión para F4.

### Pendiente verificar / pulir en F2

- [ ] `ruff check` y `mypy src` — `dev` extras aún no instalados.
- [ ] Smoke test convertido a pytest formal (decisión postponed).
- [ ] Documentar en `PROYECTO.md §8` (Empaquetado) la nota sobre Gatekeeper y por qué el binario Nuitka no la sufre.

### Próximos pasos — F3 (motor faster-whisper)

F3 es para Windows + Mac Intel + Linux. En Mac Apple Silicon usaremos siempre MLX. Aún así, en este Mac M5 podemos validar que el wrapper `FasterEngine` se carga e instancia (sin GPU CUDA, fallback CPU int8). El rendimiento real CPU se medirá en Windows.

Instalación pendiente (no la hago hasta abrir F3):

```bash
pip install "faster-whisper>=1.0"
# torch ya está instalado por mlx-whisper.
# pyannote entra en F4-F5, no en F3.
```

Archivos a crear en F3:

1. `src/transcriptor/engines/faster_engine.py`:
   - `FasterEngine(model_id="large-v3-turbo", device="auto", compute_type="auto")`.
   - `device="auto"` → `"cuda"` si `platform.has_cuda()`, si no `"cpu"`.
   - `compute_type="auto"` → `"float16"` en CUDA, `"int8"` en CPU.
   - Lazy import de `faster_whisper.WhisperModel` dentro de `transcribe()`.
   - Convertir `Segment` de faster-whisper al `Segment` nuestro.
2. `src/transcriptor/engines/factory.py` (o función `make_engine()` en `engines/__init__.py`):
   - `make_engine(model_id) -> TranscriptionEngine` que devuelve `MlxEngine` o `FasterEngine` según `detect_engine()`.
3. `tests/smoke_faster.py` — análogo a `smoke_mlx.py`, marcado para correr cuando `detect_engine() != "mlx"` (Windows/Intel/Linux).

No tocar `MainWindow` ni `SettingsDialog` en F3. La integración UI ↔ motor sigue siendo F4.

---

## CIERRE — Cambio de plataforma: continuar en Mac

**Última plataforma:** Windows (`Y:\Mi software\Transcriptor`)
**Próxima plataforma:** macOS (`/Volumes/Software/Mi\ software/Transcriptor`)
**Fases cerradas:** F0, F1
**Siguiente fase:** F2 — Motor MLX (Apple Silicon)

### Autorización ampliada del Director

El Director **autoriza tocar el código legacy** (`app.py` del prototipo Tkinter)
si se observan mejoras. Hasta ahora la regla era "intocable, solo referencia".
Esta autorización aplica de aquí en adelante. Sigue vigente la regla de no
reintroducir Tkinter en `src/transcriptor/`.

#### Mejoras observadas en `app.py` (no aplicadas, decisión en Mac)

1. **`app.py:255` — bug real**:
   ```python
   max_ovl, speaker = spk    # destructura un string
   ```
   Debe ser:
   ```python
   if ovl > max_ovl:
       max_ovl = ovl
       speaker = spk
   ```
   Ya está documentado en `PROYECTO.md §7` y `CLAUDE.md §7`. Arreglar al
   abrir Mac es trivial y rompe nada.

2. **`app.py:588` — pérdida de caracteres en PDF**:
   ```python
   pdf.multi_cell(0, 5, texto.encode('latin-1', 'replace').decode('latin-1'))
   ```
   Pierde acentos, eñes y comillas tipográficas. Solución: añadir DejaVu Sans
   y `pdf.set_font("DejaVu", size=9)` con `pdf.add_font(..., uni=True)`.
   Esto ya está previsto para el módulo `report/pdf.py` en F6 — quizá no
   merece tocarlo en el legacy.

3. **`app.py:597` — `os.startfile` solo Windows**: si vamos a usar el legacy
   también desde Mac mientras llegamos a F4, sustituir por
   `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` o `subprocess.run(["open", ...])`.
   Probablemente no merece la pena; el legacy desaparece al cerrar F4.

**Recomendación:** aplicar (1) sí, dejar (2) y (3) hasta que los módulos
nuevos los hagan obsoletos.

### Cómo arrancar la sesión en Mac

```bash
cd /Volumes/Software/Mi\ software/Transcriptor

# Pull si hay cambios remotos
git status
git pull

# Crear venv NUEVO con Python 3.11 o 3.12 (NO 3.14 — mlx-whisper y pyannote
# pueden no tener wheels). Comprobar con `python3.12 --version` primero.
python3.12 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -e .                                # base (PySide6)
pip install "keyring>=25" "huggingface_hub>=0.24"   # ya usadas por F1

# Arranque smoke test
python -m transcriptor
# Debe mostrar:
#   Sistema operativo: Darwin
#   Motor recomendado: MLX (Apple Silicon)
# y, si no hay token en Keychain, abrir el diálogo Preferencias con foco.
```

### Checklist de verificación en Mac antes de empezar F2

- [ ] `python -m transcriptor` arranca sin tracebacks.
- [ ] `detect_engine()` devuelve `"mlx"` (no `"faster-cpu"`).
- [ ] `Cmd+,` abre el diálogo Preferencias.
- [ ] El menú "Preferencias…" aparece bajo el menú **Transcriptor** del macOS
      (no bajo "Archivo"), gracias a `PreferencesRole`.
- [ ] Guardar token y reiniciar la app conserva el token en Keychain
      (Aplicación "Acceso a Llaveros" debe mostrar entry
      `service=transcriptor user=hf_token`).
- [ ] "Probar token" con el token real devuelve el username en verde.

### Plan F2 — Motor MLX (Mac Apple Silicon)

```bash
# Instalar deps de motor + modelos
pip install "mlx-whisper>=0.4"
# NB: pyannote y faster-whisper entran en F3, no en F2.
```

Archivos a crear:

1. **`src/transcriptor/engines/__init__.py`** — vacío.
2. **`src/transcriptor/engines/base.py`**:
   ```python
   from dataclasses import dataclass
   from pathlib import Path
   from typing import Iterable, Protocol

   @dataclass(frozen=True)
   class Segment:
       text: str
       start: float
       end: float
       language: str | None = None

   class TranscriptionEngine(Protocol):
       def transcribe(self, audio: Path, *, language: str | None = None) -> Iterable[Segment]: ...
   ```
3. **`src/transcriptor/models/__init__.py`** + **`models/registry.py`**:
   Tabla `model_id → HFRepo` con dos columnas (MLX, CT2). Función
   `resolve(model_id) → str` que devuelve el repo correcto según
   `platform.detect_engine()`.
4. **`src/transcriptor/models/downloader.py`**: wrapper sobre
   `huggingface_hub.snapshot_download(repo_id, cache_dir=config.get_models_cache_dir(), token=config.get_hf_token())`.
5. **`src/transcriptor/engines/mlx_engine.py`**: implementación que llama a
   `mlx_whisper.transcribe(audio_path, path_or_hf_repo=resolved_repo)` y
   convierte el resultado en `list[Segment]`.
6. **Smoke test E2E**: descargar `tiny` y transcribir 10 segundos de un audio
   de prueba; verificar que devuelve segmentos no vacíos.

No tocar `MainWindow` ni `SettingsDialog` en F2. La integración UI ↔ motor
llega en F4 (pipeline completo).

### Pendientes Mac

- [ ] Generar `logo_app.icns` desde `logo_app.ico` (con `iconutil` o
      `image2icon`). Posponible hasta F8 (empaquetado).
- [ ] Decidir si en Mac queremos detectar también MPS para pyannote
      (usar `torch.backends.mps.is_available()`).

---

## Sesión — Windows, F1 completada

**Plataforma activa:** Windows (`Y:\Mi software\Transcriptor`)
**Python:** 3.14.3 (en `venv/`)
**Fase del roadmap:** F1 — Settings + detección ✅

### Completado

- `src/transcriptor/config.py` — API única de configuración:
  - `get_hf_token() / set_hf_token() / delete_hf_token()` via `keyring`.
    Fallback de migración: si encuentra `HF_TOKEN` en env y no en keyring,
    lo importa al keyring.
  - `get/set_models_cache_dir()` con default `~/.cache/huggingface/hub`.
  - `default_models_cache_dir()` expuesta para que la UI pueda mostrarla.
  - `get/set_last_folder()` (para F4).
  - `get/set_theme()` con valores `auto | claro | oscuro`.
  - `get/set_language()` con valores `auto | es | en | fr | de | it | pt | ca | eu | gl`.
- `src/transcriptor/workers/token_test_worker.py` — `TokenTestWorker(QThread)`
  que valida un HF_TOKEN llamando a `HfApi.whoami` y emite `result(ok, msg)`.
- `src/transcriptor/ui/settings_dialog.py` — `QDialog` modal con cuatro grupos:
  HuggingFace (token + show/hide + "Probar token" + enlace a HF),
  Modelos (ruta caché + Examinar + Predeterminado),
  Transcripción (idioma forzado),
  Apariencia (tema).
- `MainWindow`:
  - Barra de menú "Archivo" → "Preferencias…" con atajo nativo
    (`Ctrl+,` en Win, `Cmd+,` en Mac) y `PreferencesRole` para que macOS
    lo mueva al menú de la app.
  - "Salir" con `QuitRole`.
  - Al arrancar sin token: `QTimer.singleShot(0, ...)` abre Settings con
    foco en el campo.
- `pip install keyring>=25 huggingface_hub>=0.24` instalados en el venv.

### Verificado en Windows (offscreen)

- `config.set_hf_token('hf_dummy')` → `keyring` guarda y devuelve el valor.
- `set_language('es')`, `set_theme('oscuro')` → persistido vía QSettings
  (namespace `letzzar / TranscriptorTest_F1` para no contaminar la app real).
- `MainWindow` con token presente: arranca sin abrir Settings.
- `MainWindow` sin token: invoca `open_settings(focus_token=True)`.

### Pendiente verificar en Mac

- `python -m transcriptor` abre la ventana en Mac.
- `detect_engine()` devuelve `"mlx"` en Apple Silicon.
- Atajo `Cmd+,` y el menú "Preferencias" aparece en el menú de la app
  (gracias a `PreferencesRole`).
- `keyring` usa Keychain (login keychain accesible).

### Próximos pasos (F2 — Motor MLX, solo en Mac)

1. `src/transcriptor/engines/base.py` — interfaz abstracta `TranscriptionEngine`
   con `transcribe(audio_path) -> Iterable[Segment]`. Estructura `Segment(text, start, end)`.
2. `src/transcriptor/engines/mlx_engine.py` — wrapper sobre `mlx-whisper`.
3. `src/transcriptor/models/registry.py` — catálogo modelo-lógico → repo HF.
4. `src/transcriptor/models/downloader.py` — `snapshot_download` con progreso.
5. Prueba E2E mínima: descargar `mlx-community/whisper-tiny-mlx`, transcribir
   un audio corto y devolver segmentos.

**Nota:** F2 solo aplica en Mac Apple Silicon. En Windows seguiremos
directamente a F3 (faster-whisper).

---

## Sesión — Windows, primera sesión real (F0 completada)

**Plataforma activa:** Windows (`Y:\Mi software\Transcriptor`)
**Python:** 3.14.3 (en `venv/`)
**Fase del roadmap:** F0 — Esqueleto ✅

### Completado

- `pyproject.toml` con metadata + dependencias mínimas (PySide6) y extras por fase (`engines`, `mlx`, `report`, `secrets`, `dev`).
- Layout `src/transcriptor/` con `__init__.py`, `__main__.py`, `app.py`, `platform.py`, `ui/main_window.py`.
- `platform.py`: `detect_os()`, `is_apple_silicon()`, `has_cuda()`, `detect_engine() → "mlx" | "faster-cuda" | "faster-cpu"`, `engine_label()`.
- `MainWindow` vacía mostrando título "Transcriptor", SO detectado y motor recomendado.
- `pip install -e .` funciona; `python -m transcriptor` levanta la ventana sin tracebacks.
- Smoke test offscreen pasa (`QT_QPA_PLATFORM=offscreen`).
- `.gitignore` ampliado: `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.cache/`, salidas del prototipo.

### Verificado en Windows

```
OS: Windows
Engine: faster-cpu - faster-whisper (CPU)
Exit code: 0
Window title: Transcriptor 0.2.0
```

### Pendiente verificar en Mac

- `pip install -e .` con Python 3.11+ en Mac.
- `python -m transcriptor` abre la ventana.
- `detect_engine()` devuelve `"mlx"` en Apple Silicon.

### Próximos pasos (F1 — Settings + detección)

1. `src/transcriptor/config.py` — wrapper sobre `QSettings` + `keyring` (`get/set_hf_token`, `get/set_models_cache_dir`, `get/set_last_folder`, `get/set_theme`, `get/set_language`).
2. `src/transcriptor/ui/settings_dialog.py` — `QDialog` con campo `HF_TOKEN` (toggle mostrar), botón "Probar token" (llama a `huggingface_hub.whoami`), ruta de caché de modelos, idioma forzado, tema.
3. Atajo `Ctrl/Cmd+,` para abrir Settings desde `MainWindow`.
4. Si no hay token al arrancar → mostrar diálogo con foco en el campo.
5. Persistencia probada: cerrar/abrir la app conserva la config (QSettings) y el token sigue en keyring.

### Decisiones tomadas en la sesión

- **PySide6 6.11.1** (la última estable; `>=6.7` en `pyproject.toml`).
- **No** instalo aún `torch+CUDA`, `pyannote`, `faster-whisper`, `mlx-whisper`, `keyring` ni `huggingface_hub` — entran cuando los necesite cada fase. El `pyproject.toml` los declara como extras.
- **Python 3.14** en el venv actual; la spec pide `>=3.11`. Si pyannote/faster-whisper dan guerra con 3.14 en F2/F3, recrear venv con 3.11 o 3.12.

### Notas

- El prototipo `app.py` (Tkinter) sigue intacto como referencia. Eliminar al cerrar F4.
- `logo_app.ico` aún no integrado en la ventana; lo hacemos en F7 (tema + pulido).
- Falta generar `logo_app.icns` para el bundle Mac (F8).
