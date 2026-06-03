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


def _cache_repo_dir(model_id: str) -> Path:
    """Carpeta `models--<repo>` del modelo en la caché de HuggingFace."""
    repo = registry.resolve(model_id)
    return config.get_models_cache_dir() / f"models--{repo.replace('/', '--')}"


def is_downloaded(model_id: str) -> bool:
    """Devuelve True si el snapshot del modelo ya existe en la caché.

    No verifica integridad; solo presencia. Útil para decidir si mostrar
    "Descargar" o "Listo" en la UI.
    """
    snapshots = _cache_repo_dir(model_id) / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def local_size_bytes(model_id: str) -> int:
    """Tamaño en disco del modelo en la caché (0 si no está)."""
    repo_dir = _cache_repo_dir(model_id)
    if not repo_dir.exists():
        return 0
    return sum(f.stat().st_size for f in repo_dir.rglob("*") if f.is_file())


def delete(model_id: str) -> int:
    """Borra el modelo de la caché. Devuelve los bytes liberados (0 si no estaba)."""
    import shutil

    repo_dir = _cache_repo_dir(model_id)
    if not repo_dir.exists():
        return 0
    freed = local_size_bytes(model_id)
    shutil.rmtree(repo_dir, ignore_errors=True)
    return freed


def verify(model_id: str) -> bool:
    """Comprueba que el snapshot está completo en la caché (sin red).

    Usa `snapshot_download(local_files_only=True)`: si falta algún archivo,
    lanza y devolvemos False. No es un checksum, pero detecta descargas
    incompletas o cachés corrompidas.
    """
    from huggingface_hub import snapshot_download

    if not is_downloaded(model_id):
        return False
    try:
        snapshot_download(
            repo_id=registry.resolve(model_id),
            cache_dir=str(config.get_models_cache_dir()),
            local_files_only=True,
        )
    except Exception:
        return False
    return True


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
