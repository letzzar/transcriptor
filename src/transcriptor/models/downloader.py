"""Descarga de modelos desde HuggingFace al caché local.

Wrapper fino sobre `huggingface_hub.snapshot_download`. El progreso por UI
se conectará en F4 (workers/download_worker).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptor import config
from transcriptor.models import registry


def total_size_bytes(model_id: str) -> int | None:
    """Suma el tamaño de los archivos del repo en HuggingFace.

    Devuelve None si no se puede consultar (sin red, etc.). Útil para mostrar
    una barra de progreso de bytes antes de descargar.
    """
    from huggingface_hub import HfApi

    repo = registry.resolve(model_id)
    try:
        info = HfApi().model_info(repo, files_metadata=True, token=config.get_hf_token())
    except Exception:
        return None
    total = 0
    for sibling in info.siblings or []:
        if sibling.size:
            total += sibling.size
    return total or None


def is_downloaded(model_id: str) -> bool:
    """Devuelve True si el snapshot del modelo ya existe en la caché.

    No verifica integridad; solo presencia. Útil para decidir si mostrar
    "Descargar" o "Listo" en la UI.
    """
    repo = registry.resolve(model_id)
    cache_dir = config.get_models_cache_dir()
    snapshots = cache_dir / f"models--{repo.replace('/', '--')}" / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def download(model_id: str, *, tqdm_class: Any | None = None) -> Path:
    """Descarga el modelo (si falta) y devuelve la ruta local al snapshot.

    Reutiliza la caché de HuggingFace si el modelo ya está descargado.
    `tqdm_class` permite inyectar una barra de progreso personalizada (la usa
    `DownloadWorker` para emitir el avance a la UI).

    Lanza `huggingface_hub.errors.HfHubHTTPError` si la descarga falla
    (token inválido para modelos gated, sin conexión, etc.).
    """
    from huggingface_hub import snapshot_download

    repo = registry.resolve(model_id)
    kwargs: dict[str, Any] = {
        "repo_id": repo,
        "cache_dir": str(config.get_models_cache_dir()),
        "token": config.get_hf_token(),
    }
    if tqdm_class is not None:
        kwargs["tqdm_class"] = tqdm_class
    local_path = snapshot_download(**kwargs)
    return Path(local_path)
