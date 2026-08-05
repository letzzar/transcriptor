# Guía de Configuración y Despliegue de OpenAI Whisper en GPUs AMD

Esta guía proporciona las instrucciones necesarias para integrar aceleración por hardware en modelos de transcripción **OpenAI Whisper** utilizando tarjetas gráficas **AMD** (vía **ROCm** o **Vulkan**).

---

## Índice
1. [Opción 1: PyTorch nativo con ROCm (Recomendado para Linux / Docker)](#opción-1-pytorch-nativo-con-rocm)
   - [Instalación de dependencias](#11-instalación-de-dependencias)
   - [Variables de entorno para GPUs de consumo (RDNA2 / RDNA3)](#12-variables-de-entorno)
   - [Script de integración en Python](#13-script-de-integración-en-python)
2. [Opción 2: whisper.cpp con Vulkan (Recomendado para Windows / Binarios ligeros)](#opción-2-whispercpp-con-vulkan)
   - [Compilación con soporte Vulkan](#21-compilación-con-soporte-vulkan)
   - [Descarga de modelos y ejecución](#22-descarga-de-modelos-y-ejecución)
3. [Comparativa de Rendimiento y Arquitectura](#comparativa-de-rendimiento-y-arquitectura)

---

## Opción 1: PyTorch nativo con ROCm

La pila **ROCm** de AMD permite que PyTorch detecte la GPU AMD a través del alias `cuda`, manteniendo compatibilidad directa con el código existente.

### 1.1 Instalación de dependencias

Instala la versión de PyTorch compilada específicamente para ROCm (ejemplo con ROCm 6.1):

```bash
# Instalación de PyTorch con soporte ROCm
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.1

# Dependencias del proyecto Whisper y procesamiento de audio
pip install openai-whisper ffmpeg-python
```

> **Requisito del sistema:** Asegúrate de tener instalado `ffmpeg` a nivel de sistema operativo (`sudo apt install ffmpeg` en Ubuntu/Debian).

### 1.2 Variables de entorno

En GPUs AMD Radeon de consumo (series RX 6000/7000), es posible que ROCm no identifique automáticamente el identificador de la arquitectura GFX. Exporta la variable correspondiente antes de ejecutar el programa:

```bash
# Para GPUs Radeon RX 7000 series (RDNA3)
export HSA_OVERRIDE_GFX_VERSION=11.0.0

# Para GPUs Radeon RX 6000 series (RDNA2)
export HSA_OVERRIDE_GFX_VERSION=10.3.0
```

### 1.3 Script de integración en Python

Muestra de implementación con fallback automático a CPU en caso de no detectar dispositivo compatible:

```python
import torch
import whisper

def transcribir_audio(ruta_audio: str, modelo_nombre: str = "medium"):
    # Comprobar disponibilidad de GPU vía ROCm (mapeado como 'cuda')
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Dispositivo de ejecución: {device}")
    
    if device == "cuda":
        print(f"[INFO] GPU AMD Detectada: {torch.cuda.get_device_name(0)}")

    # Cargar modelo en memoria
    model = whisper.load_model(modelo_nombre, device=device)

    # Procesar transcripción (fp16 habilitado si corre en GPU)
    resultado = model.transcribe(
        ruta_audio,
        fp16=(device == "cuda"),
        verbose=False
    )

    return resultado["text"]

if __name__ == "__main__":
    texto = transcribir_audio("audio.mp3", modelo_nombre="medium")
    print("
--- Resultado de Transcripción ---")
    print(texto)
```

---

## Opción 2: whisper.cpp con Vulkan

Para implementaciones ligeras o entornos fuera de Linux (ej. Windows nativo), `whisper.cpp` permite ejecutar modelos cuantiados GGML utilizando **Vulkan API**.

### 2.1 Compilación con soporte Vulkan

```bash
# Clonar repositorio oficial
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Generar proyecto y compilar activando el backend Vulkan
cmake -B build -DGGML_VULKAN=1
cmake --build build --config Release
```

### 2.2 Descarga de modelos y ejecución

```bash
# Descargar modelo conversor GGML (ej. medium)
bash ./models/download-ggml-model.sh medium

# Ejecución por línea de comandos utilizando aceleración por GPU AMD
./build/bin/whisper-cli -m models/ggml-medium.bin -f audio.wav -l es
```

---

## Comparativa de Rendimiento y Arquitectura

| Criterio | PyTorch + ROCm | whisper.cpp + Vulkan |
| :--- | :--- | :--- |
| **Plataforma Objetivo** | Linux, Docker, Servidores | Windows, Linux, macOS |
| **Uso de Memoria (VRAM)** | Normal (FP16/FP32 nativo) | Muy Bajo (Soporta cuantización 4/5/8-bit) |
| **Facilidad de Integración** | Nativa en Python (`openai-whisper`) | Binario C++ / Bindings para C# / Python |
| **Rendimiento Relativo** | Alto en procesamiento por lotes | Alto en latencia y arranque rápido |
