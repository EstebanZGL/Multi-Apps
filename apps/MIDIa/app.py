import os
import sys
import threading
import subprocess
import traceback
import requests
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# IA Model URL (Zenodo)
MODEL_URL = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
MODEL_NAME = "note_F1=0.9677_pedal_F1%3D0.9186.pth"
MODEL_DIR = os.path.join(os.path.expanduser("~"), "piano_transcription_inference_data")

class MIDIaApp(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # State
        self.source_file = ctk.StringVar(value="")
        self.video_file = ctk.StringVar(value="")
        self.is_processing = False
        self.audio_sensitivity = ctk.IntVar(value=30) 
        self.start_time = 0
        
        # Video Calibration State
        self.calib_window = None
        self.calib_y = 0.8 
        self.calib_scale = 1.0 
        self.calib_offset = 0.0 
        self.black_key_width_ratio = 0.6 
        self.black_key_spread = 0.0
        self.visual_zoom = 1.0
        self.analysis_mode = ctk.StringVar(value="barres") 
        
        # Individual Nudges: [offset_x for each of the 88 keys]
        self.key_nudges = [0.0] * 88
        self.selected_key_idx = -1
        
        self.calib_img_tk = None
        self.key_rects = [] 

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkButton(header, text="🏠 Menu", width=80, command=lambda: self.controller.show_menu()).pack(side="left")
        ctk.CTkLabel(header, text="MIDIa - Transcription Studio", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", expand=True, padx=(0, 20))

        self.tabview = ctk.CTkTabview(self, segmented_button_selected_color="#E07A5F", segmented_button_unselected_hover_color="#3a3a50")
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        tab_audio = self.tabview.add("🎵 Audio (IA)")
        tab_video = self.tabview.add("📹 Vidéo (Vision)")

        self._build_audio_tab(tab_audio)
        self._build_video_tab(tab_video)

        self.progress_container = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_container.pack(fill="x", padx=20, pady=5)
        self.progress_bar = ctk.CTkProgressBar(self.progress_container)
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(self, text="Prêt.")
        self.status_label.pack(pady=5)

    def _build_audio_tab(self, parent):
        ctk.CTkLabel(parent, text="Transcription Piano par Intelligence Artificielle", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=40, pady=10)
        self.file_entry = ctk.CTkEntry(f, textvariable=self.source_file, placeholder_text="Chemin vers .mp3 ou .wav", state="disabled")
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(f, text="Parcourir", width=100, command=self._browse_audio).pack(side="left")

        sens_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sens_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(sens_frame, text="Moins de notes\n(Filtre l'écho)", font=ctk.CTkFont(size=10)).pack(side="left")
        self.sens_slider = ctk.CTkSlider(sens_frame, from_=5, to=80, variable=self.audio_sensitivity, button_color="#E07A5F", progress_color="#E07A5F")
        self.sens_slider.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(sens_frame, text="Plus de notes\n(Capture tout)", font=ctk.CTkFont(size=10)).pack(side="left")

        self.audio_btn = ctk.CTkButton(parent, text="🎹 Transcrire l'Audio", font=ctk.CTkFont(size=18, weight="bold"),
                                      height=50, fg_color="#E07A5F", hover_color="#D16043", command=self._start_audio_processing)
        self.audio_btn.pack(pady=30)
        self.timer_label = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=11, slant="italic"))
        self.timer_label.pack()

    def _build_video_tab(self, parent):
        ctk.CTkLabel(parent, text="Transcription de Vidéo Synthesia (Piano Roll)", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=40, pady=10)
        self.video_entry = ctk.CTkEntry(f, textvariable=self.video_file, placeholder_text="Chemin vers .mp4 ou .mkv", state="disabled")
        self.video_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(f, text="Parcourir", width=100, command=self._browse_video).pack(side="left")

        self.video_btn = ctk.CTkButton(parent, text="👁️ Calibrer & Analyser", font=ctk.CTkFont(size=18, weight="bold"),
                                      height=50, fg_color="#2E8B57", hover_color="#1F5F3A", command=self._start_video_processing)
        self.video_btn.pack(pady=30)
        ctk.CTkLabel(parent, text="💡 Mode Vision : Précision parfaite, idéal pour le contenu éducatif.", font=ctk.CTkFont(size=12, slant="italic"), text_color="#aaaaaa").pack(pady=10)

    def _update_timer(self):
        if self.is_processing:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            self.timer_label.configure(text=f"Temps écoulé : {mins:02d}:{secs:02d}")
            self.after(1000, self._update_timer)
        else: self.timer_label.configure(text="")

    def _browse_audio(self):
        f = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
        if f: self.source_file.set(f)

    def _browse_video(self):
        f = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi")])
        if f: self.video_file.set(f)

    def _start_audio_processing(self):
        if not self.source_file.get(): return
        self._set_ui_processing(True, "audio")
        self.start_time = time.time()
        self._update_timer()
        threading.Thread(target=self._run_transcription, daemon=True).start()

    def _start_video_processing(self):
        if not self.video_file.get(): return
        self._open_calibration_window()

    def _open_calibration_window(self):
        import cv2
        from PIL import Image, ImageTk
        cap = cv2.VideoCapture(self.video_file.get())
        ret, frame = cap.read()
        cap.release()
        if not ret: return
        
        self.calib_window = ctk.CTkToplevel(self)
        self.calib_window.title("Calibration Vision (Haute Précision)")
        self.calib_window.geometry("1200x950")
        self.calib_window.transient(self)
        
        # --- TOP CONTROLS ---
        top_frame = ctk.CTkFrame(self.calib_window, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(top_frame, text="Mode d'analyse :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        ctk.CTkRadioButton(top_frame, text="Barres tombantes", variable=self.analysis_mode, value="barres").pack(side="left", padx=10)
        ctk.CTkRadioButton(top_frame, text="Touches pressées", variable=self.analysis_mode, value="touches").pack(side="left", padx=10)
        
        ctk.CTkLabel(top_frame, text=" |  Zoom Visuel :").pack(side="left", padx=10)
        self.vzoom_slider = ctk.CTkSlider(top_frame, from_=1.0, to=4.0, number_of_steps=300, width=150)
        self.vzoom_slider.set(self.visual_zoom)
        self.vzoom_slider.pack(side="left", padx=10)
        
        self.selected_key_label = ctk.CTkLabel(top_frame, text="Touche : Aucune", text_color="#E07A5F")
        self.selected_key_label.pack(side="right", padx=20)
        
        # --- CANVAS ---
        self.calib_canvas = tk.Canvas(self.calib_window, bg="black", highlightthickness=0)
        self.calib_canvas.pack(fill="both", expand=True, padx=20, pady=5)
        
        h, w = frame.shape[:2]
        self.kb_tag = "keyboard_overlay"
        self.drag_data = {"x": 0, "y": 0, "active": False}

        def on_mouse_down(event):
            # 1. Click to select key
            cw = self.calib_canvas.winfo_width()
            ch = self.calib_canvas.winfo_height()
            cx, cy = cw//2, ch//2
            img_left_x = cx - self.vid_w//2
            
            # Find nearest key
            best_dist = 9999
            self.selected_key_idx = -1
            for i, rect in enumerate(self.key_rects):
                x_center = img_left_x + (rect[0] + (rect[1]-rect[0])/2) * self.vid_w
                dist = abs(event.x - x_center)
                if dist < 20 and dist < best_dist:
                    best_dist = dist
                    self.selected_key_idx = i
            
            if self.selected_key_idx != -1:
                note_name = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][(21 + self.selected_key_idx) % 12]
                self.selected_key_label.configure(text=f"Touche : {note_name}{ (21 + self.selected_key_idx) // 12 }")
                self.nudge_slider.set(self.key_nudges[self.selected_key_idx])
            else:
                self.selected_key_label.configure(text="Touche : Aucune")

            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.drag_data["active"] = True
            update_view()

        def on_mouse_drag(event):
            if not self.drag_data["active"]: return
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            
            # Soft Drag
            self.calib_offset += (dx / (self.vid_w * self.visual_zoom * 3.0))
            self.calib_y += (dy / (self.vid_h * self.visual_zoom * 2.0))
            self.calib_y = max(0.0, min(1.0, self.calib_y))
            
            self.y_slider.set(self.calib_y)
            self.pan_slider.set(self.calib_offset)
            update_view()

        def on_mouse_up(event):
            self.drag_data["active"] = False

        self.calib_canvas.bind("<ButtonPress-1>", on_mouse_down)
        self.calib_canvas.bind("<B1-Motion>", on_mouse_drag)
        self.calib_canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        def generate_keyboard_rects(total_width, black_ratio, black_spread):
            white_width = total_width / 52.0
            black_width = white_width * black_ratio
            is_black = [False, True, False]
            for _ in range(7):
                is_black.extend([False, True, False, True, False, False, True, False, True, False, True, False])
            is_black.append(False)
            
            rects = []
            current_white_x = 0
            
            for i, black in enumerate(is_black):
                note_mod = (21 + i) % 12
                # Individual Nudge
                indiv_nudge = self.key_nudges[i] * white_width
                
                if not black:
                    rects.append([current_white_x + indiv_nudge, current_white_x + white_width + indiv_nudge, False, i])
                    current_white_x += white_width
                else:
                    dx = 0
                    if note_mod == 1: dx = -black_spread   # C#
                    elif note_mod == 3: dx = black_spread  # D#
                    elif note_mod == 6: dx = -black_spread # F#
                    elif note_mod == 8: dx = 0             # G#
                    elif note_mod == 10: dx = black_spread # A#
                    
                    center_x = current_white_x + (dx * white_width) + indiv_nudge
                    rects.append([center_x - black_width/2, center_x + black_width/2, True, i])
            return rects

        def update_view(*args):
            self.visual_zoom = float(self.vzoom_slider.get())
            cw = self.calib_canvas.winfo_width()
            ch = self.calib_canvas.winfo_height()
            if cw < 100: cw, ch = 1000, 500
            
            ratio = min(cw/w, ch/h) * self.visual_zoom
            self.vid_w, self.vid_h = int(w*ratio), int(h*ratio)
            
            prev = cv2.resize(frame, (self.vid_w, self.vid_h))
            prev = cv2.cvtColor(prev, cv2.COLOR_BGR2RGB)
            self.calib_img_orig = Image.fromarray(prev)
            self.calib_img_tk = ImageTk.PhotoImage(self.calib_img_orig)
            
            self.calib_canvas.delete("all")
            cx, cy = cw//2, ch//2
            self.calib_canvas.create_image(cx, cy, image=self.calib_img_tk)
            
            self.calib_y = float(self.y_slider.get())
            y_p = cy - self.vid_h//2 + int(self.vid_h * self.calib_y)
            self.calib_canvas.create_line(cx-self.vid_w//2, y_p, cx+self.vid_w//2, y_p, fill="red", width=2)
            
            scale = float(self.zoom_slider.get())
            self.calib_offset = float(self.pan_slider.get())
            offset = self.calib_offset * self.vid_w
            b_ratio = float(self.bw_slider.get())
            b_spread = float(self.bs_slider.get())
            
            self.base_rects = generate_keyboard_rects(self.vid_w, b_ratio, b_spread)
            img_left_x = cx - self.vid_w//2
            self.key_rects = []
            
            for i, r in enumerate(self.base_rects):
                x1 = img_left_x + (r[0] * scale) + offset
                x2 = img_left_x + (r[1] * scale) + offset
                is_black = r[2]
                
                # Relative coords for analysis
                self.key_rects.append([(r[0] * scale + offset)/self.vid_w, (r[1] * scale + offset)/self.vid_w, is_black, r[3]])
                
                if x2 > img_left_x and x1 < img_left_x + self.vid_w:
                    color = "magenta" if is_black else "cyan"
                    width = 2
                    if i == self.selected_key_idx:
                        color = "yellow"
                        width = 3
                    
                    if is_black:
                        self.calib_canvas.create_rectangle(x1, y_p-30, x2, y_p+10, outline=color, width=width, tags=self.kb_tag, fill=color, stipple="gray25")
                    else:
                        self.calib_canvas.create_rectangle(x1, y_p-20, x2, y_p+20, outline=color, width=width, tags=self.kb_tag)

        def update_nudge(val):
            if self.selected_key_idx != -1:
                self.key_nudges[self.selected_key_idx] = float(val)
                update_view()

        # --- CONTROLS ---
        self.calib_window.update()
        
        bot_ctrl = ctk.CTkFrame(self.calib_window)
        bot_ctrl.pack(fill="x", padx=20, pady=10)

        # Row 1: Y & Zoom Visuel
        r1 = ctk.CTkFrame(bot_ctrl, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(r1, text="Analyse Y :").pack(side="left")
        self.y_slider = ctk.CTkSlider(r1, from_=0, to=1, number_of_steps=1000, command=update_view)
        self.y_slider.set(self.calib_y)
        self.y_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        # Row 2: Zoom & Pan
        r2 = ctk.CTkFrame(bot_ctrl, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(r2, text="Échelle X :").pack(side="left")
        self.zoom_slider = ctk.CTkSlider(r2, from_=0.5, to=1.5, number_of_steps=3000, command=update_view)
        self.zoom_slider.set(1.0)
        self.zoom_slider.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(r2, text="Offset X :").pack(side="left")
        self.pan_slider = ctk.CTkSlider(r2, from_=-0.5, to=0.5, number_of_steps=3000, command=update_view)
        self.pan_slider.set(0.0)
        self.pan_slider.pack(side="left", fill="x", expand=True, padx=10)

        # Row 3: Black Keys
        r3 = ctk.CTkFrame(bot_ctrl, fg_color="transparent")
        r3.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(r3, text="Largeur Noires :").pack(side="left")
        self.bw_slider = ctk.CTkSlider(r3, from_=0.2, to=1.0, command=update_view)
        self.bw_slider.set(0.6)
        self.bw_slider.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(r3, text="Écartement Noires :").pack(side="left")
        self.bs_slider = ctk.CTkSlider(r3, from_=-0.3, to=0.3, command=update_view)
        self.bs_slider.set(0.0)
        self.bs_slider.pack(side="left", fill="x", expand=True, padx=10)

        # Row 4: Selected Key Nudge
        r4 = ctk.CTkFrame(bot_ctrl, fg_color="#333333")
        r4.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(r4, text="AJUSTEMENT INDIVIDUEL (Nudge) :", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=10)
        self.nudge_slider = ctk.CTkSlider(r4, from_=-1.0, to=1.0, number_of_steps=200, command=update_nudge)
        self.nudge_slider.set(0.0)
        self.nudge_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        self.vzoom_slider.configure(command=update_view)
        update_view()
        ctk.CTkButton(self.calib_window, text="🚀 Valider et Lancer l'analyse", fg_color="#2E8B57", height=40, command=self._confirm_video_processing).pack(pady=10)

    def _confirm_video_processing(self):
        self.calib_y = self.y_slider.get()
        self.calib_window.destroy()
        self._set_ui_processing(True, "video")
        self.start_time = time.time()
        self._update_timer()
        threading.Thread(target=self._run_video_transcription, daemon=True).start()

    def _run_video_transcription(self):
        try:
            import cv2
            import numpy as np
            import mido
            self._update_status(f"Analyse visuelle ({self.analysis_mode.get()})...")
            v_path = self.video_file.get()
            mid_path = v_path.rsplit('.', 1)[0] + ".mid"
            
            cap = cv2.VideoCapture(v_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w, h = int(cap.get(3)), int(cap.get(4))
            
            target_y = int(h * self.calib_y)
            y_start, y_end = max(0, target_y-3), min(h, target_y+3)

            # --- DIFFERENTIAL CALIBRATION ---
            # Use 10th frame as baseline (assume keyboard is idle)
            for _ in range(10): cap.read()
            ret, baseline_frame = cap.read()
            if not ret: baseline_frame = np.zeros((h, w, 3), np.uint8)
            
            baseline_band = baseline_frame[y_start:y_end, :, :]
            baseline_hsv = cv2.cvtColor(baseline_band, cv2.COLOR_BGR2HSV)
            # --------------------------------
            
            keys = [False] * 88
            events = []
            ticks_per_second = 960.0
            
            f_idx = 11
            while True:
                ret, frame = cap.read()
                if not ret: break
                
                current_ticks = int((f_idx / fps) * ticks_per_second)
                band = frame[y_start:y_end, :, :]
                hsv_band = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
                
                # Difference with baseline
                diff = cv2.absdiff(hsv_band, baseline_hsv)
                
                for i in range(88):
                    rect = self.key_rects[i]
                    xs, xe = int(rect[0] * w), int(rect[1] * w)
                    if xe < 0 or xs > w or xs >= xe: continue
                    
                    is_black = rect[2]
                    zone_curr = hsv_band[:, max(0,xs):min(w,xe), :]
                    if zone_curr.size == 0: continue
                    
                    # --- NOUVELLE LOGIQUE DE DÉTECTION ---
                    # On analyse la luminosité (V) et saturation (S)
                    v_channel = zone_curr[:,:,2]
                    s_channel = zone_curr[:,:,1]
                    
                    if is_black and self.analysis_mode.get() == "barres":
                        # Pour les touches noires, on veut que TOUTE la largeur corresponde
                        # On calcule la moyenne de chaque colonne de la zone
                        col_v = np.mean(v_channel, axis=0)
                        col_s = np.mean(s_channel, axis=0)
                        
                        # Une colonne est active si elle est colorée/vive
                        active_cols = ((col_v > 70) & (col_s > 60)) | (col_v > 180)
                        
                        # On trigger seulement si > 80% de la largeur de la touche est "active"
                        # Cela évite qu'une note blanche voisine ne déclenche la noire par erreur
                        coverage = np.mean(active_cols)
                        is_on = coverage > 0.80
                    else:
                        # Logic standard pour les blanches ou le mode touches
                        val_p90 = np.percentile(v_channel, 90)
                        sat_p90 = np.percentile(s_channel, 90)
                        
                        if self.analysis_mode.get() == "barres":
                            is_on = (val_p90 > 60 and sat_p90 > 60) or (val_p90 > 170)
                        else:
                            # Mode Touches (plus strict pour éviter le clavier statique)
                            is_on = (val_p90 > 130 and sat_p90 > 50) or (val_p90 > 235)

                    if is_on and not keys[i]:
                        keys[i] = True
                        events.append((current_ticks, 'note_on', 21+i, 100))
                    elif not is_on and keys[i]:
                        keys[i] = False
                        events.append((current_ticks, 'note_off', 21+i, 0))
                        
                f_idx += 1
                if f_idx % 30 == 0: self.after(0, lambda p=f_idx/total_f: self.progress_bar.set(p))
            
            cap.release()
            
            self._update_status("Génération MIDI...")
            events.sort(key=lambda x: x[0])
            mid = mido.MidiFile(ticks_per_beat=480)
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
            
            last_tick = 0
            for abs_tick, msg_type, note, vel in events:
                track.append(mido.Message(msg_type, note=note, velocity=vel, time=max(0, abs_tick - last_tick)))
                last_tick = abs_tick

            mid.save(mid_path)
            self.after(0, lambda: self._on_success(mid_path))
        except Exception as e:
            print(traceback.format_exc())
            self.after(0, lambda m=str(e): self._on_error(m))

    def _run_transcription(self):
        try:
            self._update_status("Initialisation IA...")
            try:
                import torch
                from piano_transcription_inference import PianoTranscription, sample_rate
                import librosa
            except ImportError: self.after(0, self._show_dependency_error); return
            self._ensure_ffmpeg()
            os.makedirs(MODEL_DIR, exist_ok=True)
            cp = os.path.join(MODEL_DIR, MODEL_NAME)
            if not os.path.exists(cp):
                r = requests.get(MODEL_URL, stream=True, timeout=30)
                total = int(r.headers.get('content-length', 0))
                dl = 0
                with open(cp, 'wb') as f:
                    for chunk in r.iter_content(1024*1024):
                        if chunk: f.write(chunk); dl += len(chunk); self.after(0, lambda d=dl/total: self.progress_bar.set(d))
            self._update_status("Transcription...")
            dev = 'cuda' if torch.cuda.is_available() else 'cpu'
            trans = PianoTranscription(device=dev, checkpoint_path=cp)
            ap = self.source_file.get()
            raw = ap.rsplit('.', 1)[0] + "_raw.mid"
            final = ap.rsplit('.', 1)[0] + ".mid"
            audio, _ = librosa.load(ap, sr=sample_rate, mono=True)
            trans.transcribe(audio, raw)
            self._filter_midi(raw, final, self.audio_sensitivity.get())
            if os.path.exists(raw): os.remove(raw)
            self.after(0, lambda: self._on_success(final))
        except Exception as e: self.after(0, lambda m=str(e): self._on_error(m))

    def _filter_midi(self, inp, out, sens):
        import mido
        try:
            mid = mido.MidiFile(inp)
            new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)
            thresh = int(50 - (sens * 0.5))
            for track in mid.tracks:
                nt = mido.MidiTrack()
                new_mid.tracks.append(nt)
                accum_time = 0
                for msg in track:
                    accum_time += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0 and msg.velocity < thresh: continue
                    new_msg = msg.copy(time=accum_time)
                    nt.append(new_msg)
                    accum_time = 0
            new_mid.save(out)
        except: import shutil; shutil.copy2(inp, out)

    def _ensure_ffmpeg(self):
        import shutil
        if shutil.which("ffmpeg"): return
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        bd = os.path.join(base, "bin")
        if os.path.exists(os.path.join(bd, "ffmpeg.exe")):
            if bd not in os.environ["PATH"]: os.environ["PATH"] += os.pathsep + bd

    def _set_ui_processing(self, proc, mode="audio"):
        self.is_processing = proc
        s = "disabled" if proc else "normal"
        self.audio_btn.configure(state=s)
        self.video_btn.configure(state=s)
        if proc: self.progress_bar.pack(fill="x", padx=100, pady=10); self.progress_bar.set(0); 
        else: self.progress_bar.stop(); self.progress_bar.pack_forget()

    def _show_dependency_error(self):
        self._set_ui_processing(False)
        if messagebox.askyesno("Dépendances", "Installer les bibliothèques IA ?"):
            threading.Thread(target=self._install_dependencies, daemon=True).start()

    def _install_dependencies(self):
        try:
            self._update_status("Installation...")
            cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "piano_transcription_inference", "mido", "librosa", "opencv-python", "numpy"]
            subprocess.check_call(cmd)
            messagebox.showinfo("Succès", "Prêt !")
        except Exception as e: messagebox.showerror("Erreur", str(e))

    def _update_status(self, msg): self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_success(self, p):
        self._set_ui_processing(False); self.status_label.configure(text="Terminé !")
        if messagebox.askyesno("Succès", f"Généré :\n{p}\n\nOuvrir ?"): os.startfile(os.path.dirname(p))

    def _on_error(self, err): self._set_ui_processing(False); self.status_label.configure(text="Erreur."); messagebox.showerror("Erreur", err)
