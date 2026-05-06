# Transcriptor

**English** | [Español](#español)

---

A Python desktop app that transcribes audio and video files using [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) with automatic speaker diarization via [pyannote.audio](https://github.com/pyannote/pyannote-audio), and exports the result as a PDF.

## Features

- Transcribes audio/video files (`.m4a`, `.mp3`, `.wav`, `.mp4`, and more)
- Speaker diarization — identifies who is speaking at each moment
- GPU acceleration (CUDA) and Apple Silicon (MPS) support
- Exports transcription to a formatted PDF with timestamps and speaker labels
- GUI built with Tkinter
- Configurable Whisper model size (tiny → large)

## Requirements

- Python 3.10+
- A [HuggingFace account](https://huggingface.co/) with access to:
  - `pyannote/speaker-diarization-3.1`
  - `pyannote/segmentation-3.0`
- `HF_TOKEN` environment variable set to your HuggingFace access token

```bash
pip install faster-whisper pyannote.audio torch fpdf2 tinytag
```

For GPU (CUDA):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Setup

```bash
# Set your HuggingFace token
export HF_TOKEN=hf_your_token_here   # Linux/macOS
set HF_TOKEN=hf_your_token_here      # Windows

python app.py
```

## Usage

1. Launch the app
2. Select one or more audio/video files
3. Choose the Whisper model size (larger = more accurate, slower)
4. Click **Transcribe**
5. The PDF is saved in the same folder as the input files

---

## Español

App de escritorio en Python que transcribe archivos de audio y vídeo usando [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) con diarización automática de hablantes mediante [pyannote.audio](https://github.com/pyannote/pyannote-audio), y exporta el resultado como PDF.

## Características

- Transcribe archivos de audio/vídeo (`.m4a`, `.mp3`, `.wav`, `.mp4` y más)
- Diarización de hablantes — identifica quién habla en cada momento
- Aceleración GPU (CUDA) y Apple Silicon (MPS)
- Exporta la transcripción a un PDF con marcas de tiempo y etiquetas de hablante
- Interfaz gráfica con Tkinter
- Tamaño de modelo Whisper configurable (tiny → large)

## Requisitos

- Python 3.10+
- Una [cuenta de HuggingFace](https://huggingface.co/) con acceso a:
  - `pyannote/speaker-diarization-3.1`
  - `pyannote/segmentation-3.0`
- Variable de entorno `HF_TOKEN` con tu token de acceso de HuggingFace

```bash
pip install faster-whisper pyannote.audio torch fpdf2 tinytag
```

Para GPU (CUDA):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Configuración

```bash
# Configura tu token de HuggingFace
export HF_TOKEN=hf_tu_token_aqui   # Linux/macOS
set HF_TOKEN=hf_tu_token_aqui      # Windows

python app.py
```

## Uso

1. Lanza la app
2. Selecciona uno o más archivos de audio/vídeo
3. Elige el tamaño del modelo Whisper (más grande = más preciso, más lento)
4. Haz clic en **Transcribir**
5. El PDF se guarda en la misma carpeta que los archivos de entrada

## Licencia

MIT © 2026 letzzar
