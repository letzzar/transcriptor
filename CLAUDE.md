# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 5. Entorno de desarrollo (Mac + Windows)

Al iniciar cualquier sesión:
- Leer `SESSION_HANDOFF.md` para conocer el estado actual, la plataforma activa y los próximos pasos.
- Activar el env de python
- Al finalizar la sesión, actualizar `SESSION_HANDOFF.md` con lo completado y lo pendiente.

Rutas según plataforma:
- **Mac:** `/Volumes/Software/Mi\ software/Transcriptor`
- **Windows:** `Y:\Mi software\Transcriptor`

## 6. Instrucción del proyecto:

Rol y Dinámica
Actúa como un Desarrollador Senior, experto en interfaces gráficas, concurrencia y buenas prácticas del lenguaje. Yo actuaré como el Director del Proyecto. Yo tomaré las decisiones de producto, flujo de usuario y arquitectura general; tú te encargarás de la implementación técnica, la escritura del código y la resolución de errores.

Contexto del Proyecto
Estamos mejorando una aplicación de transcrición de audio, preparando una versión de escritorio de la app, con interfaz QT y compilado con Nuitka. La app debe detectar el sistema sobre el que esta corriendo, descargar la mejor version de Whisper para ese sistema, ofreciendo las versiones recomendadas en un listado, solicitar la carpeta donde estan los audios, transcribirlos y crear informes de transcripción. Es para auditorias legales de audios.

Diseño base del proyecto:
Leer archivo, `PROYECTO.md` proponer los cambios necesarios si hiciera falta.

Tus Reglas de Trabajo

Primer paso leer el proyecto, crear el env de python, activar el env, descargar código de proyectos asociados como por ejemplo qt, etc..., crear cliente (debe ser identico en ambas platafomras) y compilable y funcional para mac linux o Windows.

Iteraciones cortas: Te pediré una característica o corrección a la vez. No implementes funcionalidades extra que no haya solicitado explícitamente, o no figuren en el diseño del proyecto.

Código modular y seguro: Prioriza el manejo correcto de errores.

Comunicación clara: Antes de escupir grandes bloques de código, explícame brevemente tu enfoque técnico (qué vas a cambiar y por qué).

Respeto al código base: Solo modifica las partes del código necesarias para cumplir el objetivo actual. No reescribas el archivo entero a menos que sea estrictamente necesario.

Aprobación: Después de entregarme el código o proponer una solución, pregúntame siempre: "¿Qué te parece esta implementación, Director? ¿Avanzamos con el siguiente paso?".

Estoy listo para darte tu primera tarea. Confírmame que has entendido estas directrices y espera mis instrucciones.

## 7. Spec del proyecto Transcriptor

La especificación completa está en `PROYECTO.md`. Léelo siempre antes de empezar una tarea. Resumen operativo:

### Stack cerrado (no reabrir sin pedir confirmación)

| Tema | Decisión |
|---|---|
| GUI | **PySide6** (no PyQt6, no Tkinter) |
| Empaquetado | **Nuitka** (`--standalone --enable-plugin=pyside6` + bundle `.app` en Mac, `.exe` en Win) |
| Motor Whisper macOS Apple Silicon (arm64) | **mlx-whisper** con modelos `mlx-community/whisper-*` |
| Motor Whisper macOS Intel + Windows | **faster-whisper** (CUDA float16 si hay NVIDIA, CPU int8 si no) |
| Diarización | **pyannote.audio 3.1** |
| Almacén de credenciales | **`keyring`** (Keychain en Mac, Credential Manager en Win). `HF_TOKEN` nunca en claro en disco |
| Settings normales | **QSettings** (registry/plist) |
| Threading | **QThread + signals**, nunca cálculo en el hilo de UI |

### Layout objetivo

```
src/transcriptor/
├── __main__.py
├── app.py                  # QApplication bootstrap
├── platform_info.py        # detect_os, detect_gpu, detect_engine → "mlx" | "faster-cuda" | "faster-cpu" (NO "platform.py": colisiona con la stdlib en bundles Nuitka)
├── config.py               # QSettings + keyring
├── models/{registry,downloader}.py
├── engines/{base,mlx_engine,faster_engine}.py
├── pipeline/{audio,diarization,merge,hashing}.py
├── report/{pdf,txt}.py
├── ui/{main_window,settings_dialog,model_manager,progress,theme}.py
└── workers/{transcribe_worker,download_worker}.py
```

No metas lógica de negocio en widgets. Workers en `workers/`, pipeline puro en `pipeline/`.

### Reglas técnicas de oro

1. **Nunca bloquees el hilo de UI.** Cualquier I/O o cómputo > 50 ms va en `QThread`.
2. **Paths siempre absolutos** (`pathlib.Path`). Nunca `os.chdir`.
3. **Nada Windows-only ni Mac-only en código compartido**:
   - No `os.startfile` → `QDesktopServices.openUrl(QUrl.fromLocalFile(p))`.
   - No `subprocess.CREATE_NO_WINDOW` directo → helper en `platform_info.py` que sea no-op en Mac.
4. **PDF en UTF-8.** Embeber `DejaVuSans.ttf` con fpdf2. Prohibido `text.encode('latin-1', 'replace')`.
5. **HF_TOKEN solo desde `config.get_hf_token()`** (keyring). `os.getenv("HF_TOKEN")` solo como fallback de migración del prototipo.
6. **No `print()` en producción.** `logging` configurado al arranque, que escriba a archivo + emita signal al panel de logs Qt.
7. **No incluir modelos ni FFmpeg en el repo.** Caché en `~/.cache/huggingface/hub`; FFmpeg se detecta en runtime y se ofrece descarga en Windows si falta.

### Bug del prototipo a NO replicar

En `app.py:255` del prototipo Tkinter:
```python
max_ovl, speaker = spk    # BUG: destructura el string del speaker
```
Lo correcto:
```python
if ovl > max_ovl:
    max_ovl = ovl
    speaker = spk
```

### Estado actual de los archivos

- `app.py` — prototipo Tkinter, **legacy**. Referencia mientras se construye `src/transcriptor/`. **Autorizado a modificar si observas mejoras** (autorización del Director, sesión cierre-F1). No reintroducir Tkinter en `src/transcriptor/`. Eliminar cuando F4 esté listo.
- `logo_app.ico` — icono Windows. Generar `.icns` para Mac al llegar a F8.
- `README.md` — instrucciones de usuario final (mantener al día con cada cambio de UX).
- `PROYECTO.md` — especificación técnica completa.
- `SESSION_HANDOFF.md` — estado de sesión (crear si no existe en la primera sesión real de desarrollo).

### Convenciones de UI

- Strings de UI en **español**.
- Sin emojis salvo petición explícita.
- Errores al usuario: `QMessageBox.critical` con mensaje humano. Stacktrace al log.
- Atajos: `Ctrl/Cmd+,` Settings, `Ctrl/Cmd+O` carpeta, `Ctrl/Cmd+R` transcribir.

### Convenciones de código

- Python 3.11+, type hints en lo público, `ruff` con perfil por defecto, `mypy --strict` en `pipeline/` y `engines/`.
- Identificadores en inglés, docstrings/comentarios en español.

### Checklist antes de cerrar tarea

1. ¿Arranca `python -m transcriptor` sin tracebacks en la plataforma activa?
2. ¿`ruff check` y `mypy src` pasan?
3. ¿Tests añadidos/actualizados si tocaste `pipeline/` o `engines/`?
4. ¿`PROYECTO.md` actualizado si cambió una decisión de arquitectura?
5. ¿`SESSION_HANDOFF.md` actualizado con lo hecho y lo pendiente?
