import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

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
        info_text = "💡 Note : La transcription utilise un modèle d'IA local. \nLe premier lancement peut être long car les bibliothèques d'IA seront chargées."
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
        self.progress_bar.start()
        
        threading.Thread(target=self._run_transcription, daemon=True).start()

    def _run_transcription(self):
        try:
            # Here we will do the lazy loading of torch and piano_transcription_inference
            self._update_status("Chargement du moteur d'IA...")
            
            # --- SIMULATION (A remplacer par le code réel) ---
            import time
            time.sleep(3)
            # ------------------------------------------------
            
            self.after(0, self._on_success)
        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))

    def _update_status(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_success(self):
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.process_btn.configure(state="normal", text="🎹 Transcrire en MIDI")
        self.status_label.configure(text="Transcription terminée !")
        messagebox.showinfo("Succès", "Le fichier MIDI a été généré avec succès !")

    def _on_error(self, err):
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.process_btn.configure(state="normal", text="🎹 Transcrire en MIDI")
        self.status_label.configure(text="Erreur.")
        messagebox.showerror("Erreur", f"Une erreur est survenue :\n{err}")
