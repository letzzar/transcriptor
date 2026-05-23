"""Descarga de modelos desde HuggingFace al caché local.

Wrapper fino sobre `huggingface_hub.snapshot_download`. El progreso por UI
se conectará en F4 (workers/download_worker).
"""

from __future__ import annotations

from pathlib import Path

from transcriptor import config
from transcriptor.models import registry


def is_downloaded(model_id: str) -> bool:
    """Devuelve True si el snapshot del modelo ya existe en la caché.

    No verifica integridad; solo presencia. Útil para decidir si mostrar
    "Descargar" o "Listo" en la UI.
    """
    repo = registry.resolve(model_id)
    cache_dir = config.get_models_cache_dir()
    snapshots = cache_dir / f"models--{repo.replace('/', '--')}" / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def download(model_id: str) -> Path:
    """Descarga el modelo (si falta) y devuelve la ruta local al snapshot.

    Reutiliza la caché de HuggingFace si el modelo ya está descargado.
    Lanza `huggingface_hub.errors.HfHubHTTPError` si la descarga falla
    (token inválido para modelos gated, sin conexión, etc.).
    """
    from huggingface_hub import snapshot_download

    repo = registry.resolve(model_id)
    local_path = snapshot_download(
        repo_id=repo,
        cache_dir=str(config.get_models_cache_dir()),
        token=config.get_hf_token(),
    )
    return Path(local_path)
