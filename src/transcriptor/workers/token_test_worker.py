"""Worker que valida un HF_TOKEN llamando a `huggingface_hub.whoami`.

Corre en un QThread para no bloquear el diálogo de Settings mientras se hace
la llamada HTTP.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class TokenTestWorker(QThread):
    """Comprueba si un token de HuggingFace es válido.

    Emite `result(ok: bool, message: str)`:
        ok=True  → message es el username (`name` que devuelve whoami).
        ok=False → message es una descripción del error humana.
    """

    result = Signal(bool, str)

    def __init__(self, token: str, parent=None) -> None:
        super().__init__(parent)
        self._token = token

    def run(self) -> None:
        try:
            # Import dentro para que la app pueda arrancar sin huggingface_hub
            # si algún día decidimos volverlo opcional.
            from huggingface_hub import HfApi
            from huggingface_hub.errors import HfHubHTTPError

            info = HfApi(token=self._token).whoami()
            name = info.get("name") or info.get("fullname") or "usuario"
            self.result.emit(True, str(name))
        except HfHubHTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 401:
                self.result.emit(False, "Token inválido o sin permisos.")
            else:
                self.result.emit(False, f"Error HTTP {status}: {e}")
        except Exception as e:  # noqa: BLE001 — feedback humano al usuario
            self.result.emit(False, f"No se pudo validar el token: {e}")
