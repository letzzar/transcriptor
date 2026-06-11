"""Provisión del backend pesado (torch + motores) en el primer arranque.

El bundle distribuido es ligero (UI + código). El stack pesado (torch,
faster-whisper, pyannote, transformers) se descarga la primera vez en una
carpeta del usuario, eligiendo la variante CUDA o CPU según la GPU detectada.
"""
