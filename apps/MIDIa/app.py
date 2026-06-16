import os
import sys
import threading
import subprocess
import traceback
import requests
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# IA Model URL (Zenodo)
MODEL_URL = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
MODEL_NAME = "note_F1=0.9677_pedal_F1=0.9186.pth"
MODEL_DIR = os.path.join(os.path.expanduser("~"), "piano_transcription_inference_data")

class MIDIaApp(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # State
        self.source_file = ctk.StringVar(value="")
        self.is_processing = False

        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        
        ctk.CTkButton(header, text="🏠 Menu", width=80, command=lambda: self.controller.show_menu()).pack(side="left")
        ctk.CTkLabel(header, text="MIDIa - Audio to MIDI", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", expand=True, padx=(0, 20))

        # Main Container
        main_box = ctk.CTkFrame(self)
        main_box.pack(fill="both", expand=True, padx=20, pady=10)

        # File Selection
        ctk.CTkLabel(main_box, text="Sélectionnez un fichier audio (Piano solo recommandé)", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        
        file_frame = ctk.CTkFrame(main_box, fg_color="transparent")
        file_frame.pack(fill="x", padx=40, pady=10)
        
        self.file_entry = ctk.CTkEntry(file_frame, textvariable=self.source_file, placeholder_text="Chemin vers .mp3 ou .wav", state="disabled")
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(file_frame, text="Parcourir", width=100, command=self._browse_file).pack(side="left")

        # Info Box
        info_text = "💡 Note : La transcription utilise un modèle d'IA local. \nLe premier lancement téléchargera le modèle (165 Mo)."
        ctk.CTkLabel(main_box, text=info_text, font=ctk.CTkFont(size=12, slant="italic"), text_color="#aaaaaa").pack(pady=10)

        # Process Button
        self.process_btn = ctk.CTkButton(
            main_box, text="🎹 Transcrire en MIDI", 
            font=ctk.CTkFont(size=18, weight="bold"),
            height=50, fg_color="#E07A5F", hover_color="#D16043",
            command=self._start_processing
        )
        self.process_btn.pack(pady=40)

        # Progress
        self.progress_bar = ctk.CTkProgressBar(main_box)
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(main_box, text="Prêt.")
        self.status_label.pack(pady=5)

    def _browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
        if f:
            self.source_file.set(f)

    def _start_processing(self):
        if not self.source_file.get():
            messagebox.showwarning("Attention", "Veuillez sélectionner un fichier source.")
            return
        
        if self.is_processing: return
        
        self.is_processing = True
        self.process_btn.configure(state="disabled", text="Analyse en cours...")
        self.progress_bar.pack(fill="x", padx=100, pady=10)
        self.progress_bar.set(0)
        
        threading.Thread(target=self._run_transcription, daemon=True).start()

    def _run_transcription(self):
        try:
            # 1. Lazy loading
            self._update_status("Initialisation de l'IA...")
            try:
                import torch
                from piano_transcription_inference import PianoTranscription, sample_rate, load_audio
                import audioread
            except ImportError:
                self.after(0, self._show_dependency_error)
                return

            # 2. Ensure FFmpeg is in PATH (Required by audioread)
            self._ensure_ffmpeg()

            # 3. Check and Download Model
            os.makedirs(MODEL_DIR, exist_ok=True)
            checkpoint_path = os.path.join(MODEL_DIR, MODEL_NAME)
            
            if not os.path.exists(checkpoint_path):
                self._update_status("Téléchargement du modèle IA (165 Mo)...")
                try:
                    r = requests.get(MODEL_URL, stream=True, timeout=30)
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    with open(checkpoint_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    self.after(0, lambda d=downloaded/total: self.progress_bar.set(d))
                except Exception as e:
                    if os.path.exists(checkpoint_path): os.remove(checkpoint_path)
                    raise Exception(f"Échec du téléchargement du modèle : {e}")

            # 4. Transcribe
            self._update_status("Chargement du moteur IA...")
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            transcriber = PianoTranscription(device=device, checkpoint_path=checkpoint_path)

            audio_path = self.source_file.get()
            midi_path = audio_path.rsplit('.', 1)[0] + ".mid"

            self._update_status(f"Transcription en cours sur {device}...")
            
            try:
                import librosa
                # Standard librosa load is more reliable than the utility function
                audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
            except Exception as audio_err:
                # Fallback to soundfile if librosa fails (sometimes happens with specific formats)
                try:
                    import soundfile as sf
                    audio, _ = sf.read(audio_path)
                    import numpy as np
                    if len(audio.shape) > 1: audio = np.mean(audio, axis=1) # Mono
                    audio = librosa.resample(audio, orig_sr=_, target_sr=sample_rate)
                except:
                    raise Exception(f"Erreur de lecture audio : {audio_err}\nAssurez-vous que FFmpeg est bien installé via l'installateur.")

            transcriber.transcribe(audio, midi_path)
            
            self.after(0, lambda: self._on_success(midi_path))
        except Exception as e:
            print(traceback.format_exc())
            err_msg = str(e)
            self.after(0, lambda m=err_msg: self._on_error(m))

    def _ensure_ffmpeg(self):
        """Ensures FFmpeg is in the PATH so audioread can find it."""
        import shutil
        if shutil.which("ffmpeg"): return
        
        # Check launcher's bin folder
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        bin_dir = os.path.join(base, "bin")
        
        if os.path.exists(os.path.join(bin_dir, "ffmpeg.exe")):
            if bin_dir not in os.environ["PATH"]:
                os.environ["PATH"] += os.pathsep + bin_dir
                print(f"DEBUG MIDIa: Added {bin_dir} to PATH")

    def _show_dependency_error(self):
        self.is_processing = False
        self.progress_bar.pack_forget()
        self.process_btn.configure(state="normal", text="🎹 Transcrire en MIDI")
        self.status_label.configure(text="Dépendances manquantes.")
        
        if messagebox.askyesno("Dépendances manquantes", "Les bibliothèques IA (torch, piano_transcription_inference) ne sont pas installées.\n\nVoulez-vous tenter de les installer maintenant ? (Environ 1.5 Go)"):
            threading.Thread(target=self._install_dependencies, daemon=True).start()

    def _install_dependencies(self):
        try:
            if getattr(sys, 'frozen', False):
                messagebox.showwarning("Installation impossible", "Utilisez la version source pour installer Torch.")
                return

            self._update_status("Installation de Torch et du moteur...")
            cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "piano_transcription_inference"]
            subprocess.check_call(cmd)
            
            messagebox.showinfo("Succès", "Dépendances installées ! Veuillez relancer la transcription.")
            self._update_status("Prêt (Relancez).")
        except Exception as e:
            messagebox.showerror("Erreur d'installation", str(e))
            self._update_status("Échec installation.")

    def _update_status(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_success(self, midi_path):
        self.is_processing = False
        self.progress_bar.set(1.0)
        self.process_btn.configure(state="normal", text="🎹 Transcrire en MIDI")
        self.status_label.configure(text="Transcription terminée !")
        
        if messagebox.askyesno("Succès", f"Fichier MIDI généré :\n{midi_path}\n\nVoulez-vous ouvrir le dossier ?"):
            os.startfile(os.path.dirname(midi_path))

    def _on_error(self, err):
        self.is_processing = False
        self.progress_bar.pack_forget()
        self.process_btn.configure(state="normal", text="🎹 Transcrire en MIDI")
        self.status_label.configure(text="Erreur.")
        messagebox.showerror("Erreur", f"Une erreur est survenue :\n{err}")

