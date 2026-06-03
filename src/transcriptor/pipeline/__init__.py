"""Pipeline puro de transcripción: audio → diarización → merge → reporte.

Los módulos de este paquete no dependen de Qt ni de la UI. La orquestación
por archivo y la emisión de señales de progreso viven en
`transcriptor.workers.transcribe_worker` (F4c).
"""
