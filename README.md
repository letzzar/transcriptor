# Transcriptor

**English** | [Español](#español)

---

A Python desktop app that transcribes audio and video files using [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) with automatic speaker diarization via [pyannote.audio](https://github.com/pyannote/pyannote-audio), and exports the result as a PDF.

## Features

- Transcribes audio/video files (`.m4a`, `.mp3`, `.wav`, `.mp4`, and more)
- Speaker diarization — identifies who is speaking at each moment
- GPU acceleration: CUDA (NVIDIA) and Apple Silicon (MPS) supported; falls back to CPU
- Exports transcription to a formatted PDF with timestamps and speaker labels
- GUI built with Tkinter
- Configurable Whisper model size (tiny → large)

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Download from [python.org](https://www.python.org/downloads/) |
| **HuggingFace account** | Free — required to accept model licenses. See below. |
| **HF_TOKEN** | Your HuggingFace access token — see below |
| **NVIDIA GPU** *(optional)* | CUDA 11.8+ for GPU acceleration on Windows/Linux |
| **Apple Silicon** *(optional)* | MPS acceleration on macOS M1/M2/M3 |

### Step 1 — Create a HuggingFace account and get a token

1. Sign up at [huggingface.co](https://huggingface.co/join) (free)
2. Go to **Settings → Access Tokens** → **New token** → select *Read* role → click **Generate**
3. Copy the token (starts with `hf_...`)

### Step 2 — Accept the pyannote model licenses

You must accept the license for each pyannote model (one-time, requires being logged in to HuggingFace):

- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) → click **Agree and access repository**
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) → click **Agree and access repository**

## Install

```bash
git clone https://github.com/letzzar/transcriptor.git
cd transcriptor

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install faster-whisper pyannote.audio fpdf2 tinytag torch
```

### GPU support (optional)

**NVIDIA CUDA:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Apple Silicon (MPS):** torch already includes MPS support — no extra step needed.

## Run

```bash
# Set your HuggingFace token
set HF_TOKEN=hf_your_token_here      # Windows
export HF_TOKEN=hf_your_token_here   # macOS/Linux

python app.py
```

## Usage

1. Launch the app
2. Click **Select files** and choose one or more audio/video files
3. Choose the Whisper model size:
   - `tiny` / `base` — fast, less accurate
   - `small` / `medium` — balanced
   - `large` — most accurate, requires more RAM and time
4. Click **Transcribe**
5. The PDF is saved in the same folder as the input files

---

## Español

App de escritorio en Python que transcribe archivos de audio y vídeo usando [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) con diarización automática de hablantes mediante [pyannote.audio](https://github.com/pyannote/pyannote-audio), y exporta el resultado como PDF.

## Características

- Transcribe archivos de audio/vídeo (`.m4a`, `.mp3`, `.wav`, `.mp4` y más)
- Diarización de hablantes — identifica quién habla en cada momento
- Aceleración GPU: CUDA (NVIDIA) y Apple Silicon (MPS); usa CPU si no hay GPU
- Exporta la transcripción a un PDF con marcas de tiempo y etiquetas de hablante
- Interfaz gráfica con Tkinter
- Tamaño de modelo Whisper configurable (tiny → large)

## Requisitos previos

| Requisito | Notas |
|---|---|
| **Python 3.10+** | Descarga desde [python.org](https://www.python.org/downloads/) |
| **Cuenta HuggingFace** | Gratuita — necesaria para aceptar las licencias de los modelos. Ver abajo. |
| **HF_TOKEN** | Tu token de acceso de HuggingFace — ver abajo |
| **GPU NVIDIA** *(opcional)* | CUDA 11.8+ para aceleración GPU en Windows/Linux |
| **Apple Silicon** *(opcional)* | Aceleración MPS en macOS M1/M2/M3 |

### Paso 1 — Crear cuenta en HuggingFace y obtener un token

1. Regístrate en [huggingface.co](https://huggingface.co/join) (gratis)
2. Ve a **Settings → Access Tokens** → **New token** → selecciona el rol *Read* → haz clic en **Generate**
3. Copia el token (empieza por `hf_...`)

### Paso 2 — Aceptar las licencias de los modelos pyannote

Debes aceptar la licencia de cada modelo de pyannote (una sola vez, con sesión iniciada en HuggingFace):

- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) → haz clic en **Agree and access repository**
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) → haz clic en **Agree and access repository**

## Instalar

```bash
git clone https://github.com/letzzar/transcriptor.git
cd transcriptor

# Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# Instalar dependencias
pip install faster-whisper pyannote.audio fpdf2 tinytag torch
```

### Soporte GPU (opcional)

**NVIDIA CUDA:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Apple Silicon (MPS):** torch ya incluye soporte MPS — no se necesita ningún paso adicional.

## Ejecutar

```bash
# Configura tu token de HuggingFace
set HF_TOKEN=hf_tu_token_aqui      # Windows
export HF_TOKEN=hf_tu_token_aqui   # macOS/Linux

python app.py
```

## Uso

1. Lanza la app
2. Haz clic en **Seleccionar archivos** y elige uno o más archivos de audio/vídeo
3. Elige el tamaño del modelo Whisper:
   - `tiny` / `base` — rápido, menos preciso
   - `small` / `medium` — equilibrado
   - `large` — más preciso, requiere más RAM y tiempo
4. Haz clic en **Transcribir**
5. El PDF se guarda en la misma carpeta que los archivos de entrada

## Licencia

GNU General Public License v3.0 — ver [LICENSE](LICENSE)
