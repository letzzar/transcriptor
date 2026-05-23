# SESSION_HANDOFF

Bitácora de sesiones de desarrollo. La entrada más reciente arriba.

---

## Sesión — Mac, F2 completada (Motor MLX)

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
