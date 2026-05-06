import os
import sys
import shutil
import datetime
import hashlib
import warnings
import threading
import subprocess
import gc
import tempfile
import multiprocessing
import json # <-- Cambiado de plistlib a json
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from fpdf import FPDF
from tinytag import TinyTag

# Importaciones de ML
import torch
from pyannote.audio import Pipeline
from huggingface_hub import login
from faster_whisper import WhisperModel # <-- Reemplaza a mlx_whisper

# --- PARCHE DE COMPATIBILIDAD ---
original_load = torch.load
def patched_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return original_load(*args, **kwargs)
torch.load = patched_load
warnings.filterwarnings("ignore")

# Tu Token de Hugging Face
HF_TOKEN_SECRETO = os.getenv("HF_TOKEN", "")

# Configuraciones para guardado de preferencias (Windows APPDATA)
APP_DIR_NAME = "AuditoriaWhisper"
APPDATA_PATH = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / APP_DIR_NAME
APPDATA_PATH.mkdir(exist_ok=True)
JSON_CONFIG = APPDATA_PATH / "config.json"

# ==========================================
# 1. LOGUEADOR A ARCHIVO PARA VISOR DE LOGS
# ==========================================
class FileLogger:
    def __init__(self, ruta_log):
        self.ruta_log = Path(ruta_log)
        self.ruta_log.parent.mkdir(parents=True, exist_ok=True)
        self.buffer = ""
        self.file = open(self.ruta_log, "a", encoding="utf-8", buffering=1)

    def write(self, text):
        if not text:
            return
        self.buffer += text
        if "\n" in self.buffer:
            self.file.write(self.buffer)
            self.file.flush()
            self.buffer = ""

    def flush(self):
        if self.buffer:
            self.file.write(self.buffer)
            self.file.flush()
            self.buffer = ""

    def close(self):
        self.flush()
        try:
            self.file.close()
        except Exception:
            pass

class GuiFileLogger(FileLogger):
    def __init__(self, ruta_log, text_widget=None):
        super().__init__(ruta_log)
        self.text_widget = text_widget

    def write(self, text):
        super().write(text)
        if text and self.text_widget:
            self._append_text(text)

    def _append_text(self, text):
        def append():
            try:
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", text)
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
            except Exception:
                pass
        try:
            self.text_widget.after(0, append)
        except Exception:
            pass

# ==========================================
# 2. FUNCIONES DE APOYO
# ==========================================
def calcular_sha256(ruta_archivo):
    sha256_hash = hashlib.sha256()
    try:
        with open(ruta_archivo, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except: return "Error-Hash"

def obtener_datos_archivo(ruta):
    try:
        tag = TinyTag.get(ruta)
        dur = f"{int(tag.duration // 60):02d}:{int(tag.duration % 60):02d}"
        ts = getattr(os.stat(ruta), 'st_birthtime', os.stat(ruta).st_ctime)
        return dur, datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    except: return "00:00", "Desconocida"

def convertir_a_wav_temporal(ruta_original, mejorar_audio=False):
    fd, ruta_temp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    ruta_temp = Path(ruta_temp)

    # Buscar ffmpeg en el PATH de Windows o en la carpeta actual
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        local_ffmpeg = Path.cwd() / "ffmpeg.exe"
        if local_ffmpeg.exists():
            ffmpeg_path = str(local_ffmpeg)

    if not ffmpeg_path:
        print("   ❌ Error con FFmpeg: no se encontró 'ffmpeg.exe'. Colócalo en la carpeta de la app o añádelo al PATH de Windows.")
        if ruta_temp.exists():
            try: ruta_temp.unlink()
            except Exception: pass
        return None

    comando = [ffmpeg_path, '-y', '-i', str(ruta_original)]
    
    if mejorar_audio:
        print(f"   ✨ Aplicando filtros de limpieza (Reducción de ruido)...")
        filtros = "highpass=f=200, lowpass=f=3000, afftdn=nr=10:nf=-25, agate=threshold=-30dB:ratio=2"
        comando.extend(['-af', filtros])
    
    comando.extend(['-ar', '16000', '-ac', '1', str(ruta_temp)])
    try:
        subprocess.run(comando, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return ruta_temp
    except subprocess.CalledProcessError as e:
        error_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)
        print(f"   ❌ Error con FFmpeg: {e}. Detalle: {error_text}")
        if ruta_temp.exists():
            try: ruta_temp.unlink()
            except Exception: pass
        return None

# ==========================================
# 3. CLASES PARA REPORTES
# ==========================================
class ReportePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "REPORTE CONSOLIDADO DE AUDITORÍA DE AUDIO", border=False, ln=True, align="C")
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

# ==========================================
# 4. LÓGICA DE TRANSCRIPCIÓN INTEGRADA (Windows/CUDA/CPU)
# ==========================================
def procesar_transcripcion_local(directorio, token, mejorar, progress_callback=None, modelo="turbo", max_speakers=2):
    print(f"Cambiando a directorio: {directorio}")
    os.chdir(directorio)
    print(f"\n--- 🚀 INICIANDO ANÁLISIS EN: {directorio} ---")
    
    stats_finales = []
    try:
        print(f"Token usado: {token[:10]}...") 
        login(token=token, add_to_git_credential=False)
        print("Login a HF exitoso.")
        
        # --- DETECCIÓN DE HARDWARE ---
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
            print(f"✅ GPU NVIDIA Detectada ({torch.cuda.get_device_name(0)}). Aceleración CUDA Activa.")
        else:
            device = "cpu"
            compute_type = "int8"
            print("⚠️ CUDA no disponible. Usando CPU (Optimizado para AMD/Intel).")

        print("-> Cargando Pyannote para identificar voces...")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        pipeline.to(torch.device(device))

        print(f"-> Cargando WhisperModel ({modelo})...")
        whisper_model = WhisperModel(modelo, device=device, compute_type=compute_type)

        extensiones = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.opus', '.wma'}
        archivos = [f for f in os.listdir('.') if Path(f).suffix.lower() in extensiones]
        
        if not archivos:
            print("❌ No hay archivos compatibles en la carpeta.")
            return

        total_archivos = len(archivos)
        print(f"Total archivos a procesar: {total_archivos}")

        for i, archivo in enumerate(archivos):
            print(f"\n[PROCESANDO: {archivo}]")
            duracion, _ = obtener_datos_archivo(archivo)
            hash_f = calcular_sha256(archivo)
            
            archivo_wav = convertir_a_wav_temporal(archivo, mejorar_audio=mejorar)
            if not archivo_wav: continue

            speakers_map = {}
            speaker_counter = 1
            try:
                print("   - Identificando voces e idioma...")
                diarization = pipeline(str(archivo_wav))

                speaker_durations = {}
                for turn, _, spk in diarization.itertracks(yield_label=True):
                    speaker_durations[spk] = speaker_durations.get(spk, 0.0) + (turn.end - turn.start)

                sorted_speakers = sorted(speaker_durations.items(), key=lambda item: item[1], reverse=True)
                top_speakers = [spk for spk, _ in sorted_speakers[:max_speakers]]
                print(f"   > Voces detectadas: {len(speaker_durations)}. Principales: {', '.join(top_speakers)}")

                # Transcripción con faster-whisper
                segments, info = whisper_model.transcribe(str(archivo_wav), beam_size=5)
                idioma_principal = info.language.upper()
                
                stats_finales.append({'archivo': archivo, 'idioma': idioma_principal, 'duracion': duracion, 'hash': hash_f})

                salida = [
                    f"Análisis de audio - {archivo}",
                    f"Idioma: {idioma_principal} | Limpieza: {'SÍ' if mejorar else 'NO'}",
                    f"Duración: {duracion} | sha256: {hash_f}",
                    "="*60 + "\n"
                ]

                # Iterar sobre los segmentos generados
                for segment in segments:
                    start, end, texto = segment.start, segment.end, segment.text.strip()
                    speaker = "Voz Desconocida"
                    max_ovl = 0
                    for turn, _, spk in diarization.itertracks(yield_label=True):
                        ovl = max(0, min(end, turn.end) - max(start, turn.start))
                        if ovl > max_ovl:
                            max_ovl, speaker = spk

                    if speaker in top_speakers:
                        if speaker not in speakers_map:
                            speakers_map[speaker] = f"Voz {speaker_counter}"
                            speaker_counter += 1
                        speaker_display = speakers_map[speaker]
                    elif speaker == "Voz Desconocida":
                        speaker_display = speaker
                    else:
                        speaker_display = "Interferencia / Voz menor"

                    ts = f"[{int(start//60):02d}:{int(start%60):02d}]"
                    salida.append(f"{ts} ({speaker_display}): {texto}")

                nombre_txt = Path(archivo).stem + "_ANALIZADO.txt"
                with open(nombre_txt, "w", encoding="utf-8") as f:
                    f.write("\n".join(salida))
                print(f"   ✓ Generado: {nombre_txt}")

            except Exception as e:
                print(f"   ❌ Error en archivo {archivo}: {e}")
            finally:
                if archivo_wav.exists(): os.remove(archivo_wav)
                gc.collect()
                if device == "cuda": torch.cuda.empty_cache()

            if progress_callback:
                progress_callback((i + 1) / total_archivos * 100)

        if stats_finales:
            with open("_RESUMEN_EJECUTIVO_AUDITORIA.txt", "w", encoding="utf-8") as f:
                f.write(f"AUDITORÍA - {datetime.datetime.now()}\n")
                f.write(f"Total de archivos procesados: {total_archivos}\n\n")
                for s in stats_finales:
                    f.write(f"{s['archivo']} | {s['idioma']} | {s['duracion']} | sha256: {s['hash']}\n")

        print(f"\n--- ✅ PROCESO FINALIZADO ---")

    except Exception as e:
        print(f"❌ Error crítico en el motor de IA: {e}")
        import traceback
        traceback.print_exc()

# ==========================================
# 5. INTERFAZ GRÁFICA (GUI)
# ==========================================
class AppAuditoria(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Transcriptor y Auditoría de Audio (Windows Edition)")
        self.geometry("900x750")
        try:
            self.iconbitmap("logo_app.ico")
        except:
            pass # Si no encuentra el logo, no crashea
        self.configure(padx=20, pady=20)
        
        self.directorio_seleccionado = ""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Variables de Diseño ---
        self.temas = {
            "oscuro": {
                "bg_main": "#1e1e1e", "fg_main": "white", "bg_elementos": "#2c2c2c",
                "bg_entradas": "#383838", "btn_bg": "#2c2c2c", "switch_track": "#4CAF50", "success_fg": "#4CAF50"
            },
            "claro": {
                "bg_main": "#f5f5f5", "fg_main": "#333333", "bg_elementos": "#ffffff",
                "bg_entradas": "#ffffff", "btn_bg": "#e0e0e0", "switch_track": "#cccccc", "success_fg": "#28a745"
            }
        }
        
        self.modo_oscuro = True 
        self.etiquetas = []
        self.botones = []
        self.frames = []

        self.button_style = {
            'bd': 0, 'highlightthickness': 0, 'relief': 'flat',
            'font': ('Arial', 10, 'bold'), 'cursor': 'hand2', 'padx': 12, 'pady': 6
        }

        # --- Layout Principal ---
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)
        self.frames.append(self.main_frame)

        self.frame_switch = tk.Frame(self.main_frame)
        self.frame_switch.pack(anchor="ne", pady=(0, 10))
        self.frames.append(self.frame_switch)
        
        self.lbl_tema = tk.Label(self.frame_switch, text="Modo Oscuro", font=("Arial", 9))
        self.lbl_tema.pack(side="left", padx=(0, 5))
        
        self.canvas_switch = tk.Canvas(self.frame_switch, width=40, height=20, highlightthickness=0, bd=0, cursor="hand2")
        self.canvas_switch.pack(side="left")
        
        self.track = self.canvas_switch.create_oval(0, 0, 40, 20, fill=self.temas["oscuro"]["switch_track"], outline="")
        self.knob = self.canvas_switch.create_oval(22, 2, 38, 18, fill="white", outline="")
        self.canvas_switch.bind("<Button-1>", self.toggle_tema)

        self.lbl_estado = tk.Label(self.main_frame, text="✅ Windows Build: Token Verificado", font=("Arial", 12, "bold"))
        self.lbl_estado.pack(pady=(0, 15))

        self.btn_dir = tk.Button(self.main_frame, text="📂 Seleccionar Carpeta de Audios", command=self.seleccionar_carpeta, **self.button_style)
        self.btn_dir.pack(fill="x", pady=5)
        self.botones.append(self.btn_dir)

        self.lbl_ruta = tk.Label(self.main_frame, text="Carpeta no seleccionada", font=("Arial", 9), wraplength=800)
        self.lbl_ruta.pack(pady=5)
        self.etiquetas.append(self.lbl_ruta)

        self.var_mejorar = tk.BooleanVar(value=False)
        self.chk_mejorar = tk.Checkbutton(self.main_frame, text="Limpiar audio con FFmpeg (Reducción de ruido)", variable=self.var_mejorar, font=("Arial", 10))
        self.chk_mejorar.pack(pady=5)

        lbl_modelo = tk.Label(self.main_frame, text="Modelo de Whisper (Faster-Whisper):", font=("Arial", 10, "bold"))
        lbl_modelo.pack(pady=(10, 2))
        self.etiquetas.append(lbl_modelo)
        
        # Opciones cambiadas a los estándares de faster-whisper
        self.modelo_var = tk.StringVar(value="turbo")
        modelos = ["turbo", "large-v3", "medium", "base", "tiny"]
        self.modelo_combo = ttk.Combobox(self.main_frame, textvariable=self.modelo_var, values=modelos, state="readonly", width=40)
        self.modelo_combo.pack(pady=5)

        lbl_voces = tk.Label(self.main_frame, text="Máximo de voces a identificar:", font=("Arial", 10, "bold"))
        lbl_voces.pack(pady=(10, 2))
        self.etiquetas.append(lbl_voces)
        
        self.max_speakers_var = tk.IntVar(value=2)
        self.max_speakers_spin = tk.Spinbox(self.main_frame, from_=2, to=5, textvariable=self.max_speakers_var, width=5, font=("Arial", 10))
        self.max_speakers_spin.pack(pady=5)

        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=15)

        self.btn_frame = tk.Frame(self.main_frame)
        self.btn_frame.pack(fill="x", pady=10)
        self.frames.append(self.btn_frame)

        self.btn_transcribir = tk.Button(self.btn_frame, text="🎙️ INICIAR TRANSCRIPCIÓN", command=self.ejecutar_transcripcion, **self.button_style)
        self.btn_transcribir.pack(side="left", expand=True, fill="x", padx=5)
        self.botones.append(self.btn_transcribir)

        self.btn_unificar = tk.Button(self.btn_frame, text="📑 UNIFICAR REPORTES", command=self.ejecutar_unificacion, **self.button_style)
        self.btn_unificar.pack(side="left", expand=True, fill="x", padx=5)
        self.botones.append(self.btn_unificar)

        self.lbl_log = tk.Label(self.main_frame, text="Visor de logs: ninguna carpeta seleccionada", font=("Arial", 9), wraplength=800)
        self.lbl_log.pack(pady=10)
        self.etiquetas.append(self.lbl_log)

        self.btn_toggle_logs = tk.Button(self.main_frame, text="Mostrar logs", command=self.toggle_logs, **self.button_style)
        self.btn_toggle_logs.pack(fill="x", pady=5)
        self.botones.append(self.btn_toggle_logs)

        self.log_text = ScrolledText(self.main_frame, height=12, wrap="word", font=("Courier", 10), state="disabled", relief="flat", bd=0, highlightthickness=1)
        self.logs_visible = False

        self.log_logger = None
        self.log_path = None

        self.cargar_config()
        self.aplicar_tema()
        print("--- SISTEMA INICIALIZADO ---")

    def toggle_tema(self, event=None):
        self.modo_oscuro = not self.modo_oscuro
        if self.modo_oscuro:
            self.canvas_switch.coords(self.knob, 22, 2, 38, 18)
            self.lbl_tema.config(text="Modo Oscuro")
        else:
            self.canvas_switch.coords(self.knob, 2, 2, 18, 18)
            self.lbl_tema.config(text="Modo Claro")
        self.aplicar_tema()
        self.guardar_config()

    def aplicar_tema(self):
        tema = self.temas["oscuro"] if self.modo_oscuro else self.temas["claro"]
        self.configure(bg=tema["bg_main"])
        for frame in self.frames: frame.configure(bg=tema["bg_main"])
        self.canvas_switch.itemconfig(self.track, fill=tema["switch_track"])
        self.canvas_switch.configure(bg=tema["bg_main"])
        self.lbl_tema.configure(bg=tema["bg_main"], fg=tema["fg_main"])
        self.lbl_estado.configure(bg=tema["bg_main"], fg=tema["success_fg"])
        for lbl in self.etiquetas: lbl.configure(bg=tema["bg_main"], fg=tema["fg_main"])
        self.chk_mejorar.configure(bg=tema["bg_main"], fg=tema["fg_main"], activebackground=tema["bg_main"], activeforeground=tema["fg_main"], selectcolor=tema["bg_elementos"])
        self.max_speakers_spin.configure(bg=tema["bg_entradas"], fg=tema["fg_main"], insertbackground=tema["fg_main"], buttonbackground=tema["btn_bg"], highlightbackground=tema["bg_main"], highlightcolor=tema["fg_main"])
        self.log_text.configure(bg=tema["bg_elementos"], fg=tema["fg_main"], insertbackground=tema["fg_main"], highlightbackground=tema["bg_main"])
        estilo_btn = {'bg': tema["btn_bg"], 'fg': tema["fg_main"], 'activebackground': tema["bg_entradas"], 'activeforeground': tema["fg_main"]}
        for btn in self.botones: btn.configure(**estilo_btn)

    def cargar_config(self):
        datos = {}
        if JSON_CONFIG.exists():
            try:
                with open(JSON_CONFIG, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
            except: pass
        
        if datos:
            dir_guardado = datos.get("directorio", "")
            if dir_guardado and os.path.exists(dir_guardado):
                self.configurar_directorio(dir_guardado)
            self.modo_oscuro = datos.get("modo_oscuro", True)
                
        if self.modo_oscuro:
            self.canvas_switch.coords(self.knob, 22, 2, 38, 18)
            self.lbl_tema.config(text="Modo Oscuro")
        else:
            self.canvas_switch.coords(self.knob, 2, 2, 18, 18)
            self.lbl_tema.config(text="Modo Claro")

    def guardar_config(self):
        datos = {"directorio": self.directorio_seleccionado, "modo_oscuro": self.modo_oscuro}
        try:
            with open(JSON_CONFIG, 'w', encoding='utf-8') as f:
                json.dump(datos, f)
        except: pass

    def toggle_logs(self):
        if self.logs_visible:
            self.log_text.pack_forget()
            self.btn_toggle_logs.config(text="Mostrar logs")
            self.logs_visible = False
        else:
            self.log_text.pack(fill="both", expand=True, pady=(10, 0))
            self.btn_toggle_logs.config(text="Ocultar logs")
            self.logs_visible = True

    def on_close(self):
        try:
            if self.log_logger: self.log_logger.close()
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
        except Exception: pass
        self.destroy()
        os._exit(0)

    def configurar_directorio(self, carpeta):
        self.directorio_seleccionado = carpeta
        self.log_path = Path(carpeta) / "_AUDITORIA_LOG.txt"
        self.log_path.write_text("", encoding='utf-8')
        self.log_logger = GuiFileLogger(self.log_path, text_widget=self.log_text)
        sys.stdout = self.log_logger
        sys.stderr = self.log_logger
        self.lbl_ruta.config(text=f"Directorio: {carpeta}")
        self.lbl_log.config(text=f"Logs: {self.log_path}")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        if not self.logs_visible:
            self.log_text.pack(fill="both", expand=True, pady=(10, 0))
            self.btn_toggle_logs.config(text="Ocultar logs")
            self.logs_visible = True

    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.configurar_directorio(carpeta)
            self.guardar_config()

    def ejecutar_transcripcion(self):
        if not self.directorio_seleccionado:
            messagebox.showwarning("Error", "Seleccione una carpeta primero.")
            return
        print(f"Directorio seleccionado: {self.directorio_seleccionado}")
        self.btn_transcribir.config(state="disabled")
        threading.Thread(target=self._hilo_transcripcion, daemon=True).start()

    def _hilo_transcripcion(self):
        try:
            self.progress['value'] = 0
            procesar_transcripcion_local(
                self.directorio_seleccionado,
                HF_TOKEN_SECRETO,
                self.var_mejorar.get(),
                progress_callback=self._update_progress,
                modelo=self.modelo_var.get(),
                max_speakers=self.max_speakers_var.get()
            )
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            self.after(0, lambda: self.btn_transcribir.config(state="normal"))
            self.after(0, lambda: self.progress.config(value=100))

    def _update_progress(self, value):
        self.after(0, lambda: self.progress.config(value=value))

    def ejecutar_unificacion(self):
        if not self.directorio_seleccionado:
            messagebox.showwarning("Error", "Seleccione una carpeta.")
            return
        
        print("\n--- 📑 INICIANDO UNIFICACIÓN ---")
        try:
            os.chdir(self.directorio_seleccionado)
            fecha_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            nombre_pdf = f"CONSOLIDADO_{fecha_str}.pdf"
            carpeta_destino = Path("PROCESADOS")
            
            archivos_analisis = sorted([f for f in os.listdir('.') if f.endswith('_ANALIZADO.txt')])
            resumen_ejecutivo = "_RESUMEN_EJECUTIVO_AUDITORIA.txt"
            
            if not archivos_analisis and not os.path.exists(resumen_ejecutivo):
                print("❌ No hay archivos para unificar.")
                return

            pdf = ReportePDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            if os.path.exists(resumen_ejecutivo):
                with open(resumen_ejecutivo, "r", encoding="utf-8") as f:
                    pdf.set_font("Courier", "B", 11)
                    pdf.multi_cell(0, 6, "RESUMEN EJECUTIVO")
                    pdf.set_font("Courier", size=8)
                    pdf.multi_cell(0, 4, f.read())
                    pdf.add_page()

            for archivo in archivos_analisis:
                print(f"-> Unificando: {archivo}")
                with open(archivo, "r", encoding="utf-8") as f:
                    texto = f.read()
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 8, f"ORIGEN: {archivo}", ln=True)
                    pdf.set_font("Helvetica", size=9)
                    pdf.multi_cell(0, 5, texto.encode('latin-1', 'replace').decode('latin-1'))

            pdf.output(nombre_pdf)
            if not carpeta_destino.exists(): carpeta_destino.mkdir()
            for arc in archivos_analisis + ([resumen_ejecutivo] if os.path.exists(resumen_ejecutivo) else []):
                shutil.move(arc, carpeta_destino / arc)

            print(f"✅ UNIFICACIÓN COMPLETADA: {nombre_pdf}")
            # Reemplazo del "open" de Mac por la API de Windows
            os.startfile(os.getcwd())
            
        except Exception as e:
            print(f"❌ Error unificando: {e}")

if __name__ == "__main__":
    multiprocessing.freeze_support() 
    app = AppAuditoria()
    app.mainloop()