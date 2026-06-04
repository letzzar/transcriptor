"""Catálogo de modelos Whisper.

Cada `model_id` lógico mapea a dos repositorios de HuggingFace:
    - MLX: para Mac Apple Silicon (usado por mlx-whisper).
    - CT2: faster-whisper (CTranslate2), usado en Windows/Linux/Mac Intel.

La función `resolve(model_id)` mira `platform.detect_engine()` y devuelve
el repo apropiado al motor activo. Si el id no existe, lanza `KeyError`.
"""

from __future__ import annotations

from dataclasses import dataclass

from transcriptor.platform_info import detect_engine


@dataclass(frozen=True)
class ModelInfo:
    """Metadatos de un modelo Whisper en el catálogo."""

    model_id: str
    label: str          # mostrado en UI
    mlx_repo: str       # repo HF para mlx-whisper
    ct2_repo: str       # repo HF para faster-whisper (CTranslate2)
    size_mb: int        # tamaño aproximado del modelo MLX


# Tabla de modelos recomendados. Los modelos `large-v3-turbo` son la mejor
# relación calidad/velocidad para auditorías legales en español.
_MODELS: dict[str, ModelInfo] = {
    "tiny": ModelInfo(
        model_id="tiny",
        label="Tiny (≈75 MB, rápido, baja precisión)",
        mlx_repo="mlx-community/whisper-tiny-mlx",
        ct2_repo="Systran/faster-whisper-tiny",
        size_mb=75,
    ),
    "base": ModelInfo(
        model_id="base",
        label="Base (≈145 MB)",
        mlx_repo="mlx-community/whisper-base-mlx",
        ct2_repo="Systran/faster-whisper-base",
        size_mb=145,
    ),
    "small": ModelInfo(
        model_id="small",
        label="Small (≈465 MB)",
        mlx_repo="mlx-community/whisper-small-mlx",
        ct2_repo="Systran/faster-whisper-small",
        size_mb=465,
    ),
    "medium": ModelInfo(
        model_id="medium",
        label="Medium (≈1.5 GB)",
        mlx_repo="mlx-community/whisper-medium-mlx",
        ct2_repo="Systran/faster-whisper-medium",
        size_mb=1500,
    ),
    "large-v3": ModelInfo(
        model_id="large-v3",
        label="Large v3 (≈2.9 GB, máxima precisión)",
        mlx_repo="mlx-community/whisper-large-v3-mlx",
        ct2_repo="Systran/faster-whisper-large-v3",
        size_mb=2900,
    ),
    "large-v3-turbo": ModelInfo(
        model_id="large-v3-turbo",
        label="Large v3 Turbo (≈1.6 GB, recomendado)",
        mlx_repo="mlx-community/whisper-large-v3-turbo",
        ct2_repo="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        size_mb=1600,
    ),
}


def all_models() -> list[ModelInfo]:
    """Devuelve los modelos del catálogo en el orden definido."""
    return list(_MODELS.values())


def get(model_id: str) -> ModelInfo:
    """Devuelve los metadatos del modelo. KeyError si no existe."""
    return _MODELS[model_id]


def resolve(model_id: str) -> str:
    """Devuelve el repo de HF correcto para el motor activo en esta máquina."""
    info = get(model_id)
    engine = detect_engine()
    if engine == "mlx":
        return info.mlx_repo
    return info.ct2_repo  # faster-whisper en CUDA o CPU usa los mismos repos CT2
