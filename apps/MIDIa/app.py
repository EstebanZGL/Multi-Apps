import os
import sys
import threading
import queue
import traceback
import requests
import time
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import cv2
import numpy as np
import mido
from PIL import Image, ImageTk

# IA Model URL (Zenodo)
MODEL_URL = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
MODEL_NAME = "note_F1=0.9677_pedal_F1=0.9186.pth"
MODEL_DIR = os.path.join(os.path.expanduser("~"), "piano_transcription_inference_data")

# --- Constants for New Video Engine ---
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def midi_to_note_name(n):
    octave = (n // 12) - 1
    name = NOTE_NAMES[n % 12]
    return f"{name}{octave}"

def is_midi_note_white(n):
    return (n % 12) not in [1, 3, 6, 8, 10]

MIDI_NOTES_ALL = {n: f"{midi_to_note_name(n)} ({n})" for n in range(21, 109)}


class NewVideoEngine(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # Application state
        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.fps = 30.0
        self.video_width = 0
        self.video_height = 0
        
        self.current_frame_idx = 0
        self.current_video_frame = None  
        self.current_tk_image = None     
        self.display_scale = 1.0
        
        # Warp coordinates: TL, TR, BR, BL
        self.corners = {}
        self.active_corner = None
        self.corner_radius = 8
        
        # Warping resolution
        self.W_WIDTH = 1200
        self.W_HEIGHT = 80
        
        # Note mapping & Calibration
        self.start_note = 21  
        self.end_note = 108   
        self.white_keys = []
        self.note_coords = {} 
        self.note_nudges = {} # note -> [dx, dy] (nudge offsets)
        self.selected_note = None # Currently selected note for nudging
        self.idle_warped_frame = None
        self.idle_colors = {} 
        
        # Threading & Queue
        self.transcribe_thread = None
        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()
        
        # Setup UI
        self.create_layout()
        self.update_keyboard_layout()
        
        self.after(100, self.check_progress_queue)

    def create_layout(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left Panel 
        self.left_panel = ctk.CTkFrame(main_container, width=380)
        self.left_panel.pack(side="left", fill="y", padx=(0, 10), pady=0)
        self.left_panel.pack_propagate(False)
        
        # Right Panel 
        self.right_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True, pady=0)
        
        self.build_left_panel()
        self.build_right_panel()

    def build_left_panel(self):
        container = ctk.CTkScrollableFrame(self.left_panel, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # --- Section 1: Video File ---
        ctk.CTkLabel(container, text="1. Fichier Source", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.btn_load = ctk.CTkButton(container, text="Ouvrir une vidéo", command=self.load_video_dialog)
        self.btn_load.pack(fill="x", pady=(5, 5))
        
        self.lbl_video_info = ctk.CTkLabel(container, text="Aucune vidéo.", text_color="gray", justify="left")
        self.lbl_video_info.pack(fill="x", anchor="w")
        
        # --- Section 2: Key Range Presets ---
        ctk.CTkLabel(container, text="2. Plage du Clavier", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15,0))
        
        preset_frame = ctk.CTkFrame(container, fg_color="transparent")
        preset_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(preset_frame, text="Preset:").pack(side="left")
        self.combo_preset = ctk.CTkComboBox(preset_frame, values=["Piano Complet (88)", "61 Touches (C2-C7)", "76 Touches (E1-G7)", "49 Touches (C3-C7)", "Custom"], command=self.on_preset_change)
        self.combo_preset.set("Piano Complet (88)")
        self.combo_preset.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        range_frame = ctk.CTkFrame(container, fg_color="transparent")
        range_frame.pack(fill="x")
        
        ctk.CTkLabel(range_frame, text="Début:").pack(side="left")
        self.combo_start = ctk.CTkComboBox(range_frame, values=list(MIDI_NOTES_ALL.values()), width=90, command=self.on_note_range_ui_change)
        self.combo_start.set(MIDI_NOTES_ALL[21]) 
        self.combo_start.pack(side="left", padx=(5, 10))
        
        ctk.CTkLabel(range_frame, text="Fin:").pack(side="left")
        self.combo_end = ctk.CTkComboBox(range_frame, values=list(MIDI_NOTES_ALL.values()), width=90, command=self.on_note_range_ui_change)
        self.combo_end.set(MIDI_NOTES_ALL[108]) 
        self.combo_end.pack(side="left", padx=(5, 0))
        
        # --- Section 3: Detection Parameters ---
        ctk.CTkLabel(container, text="3. Paramètres de Détection", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15,0))
        
        self.thresh_val = ctk.IntVar(value=50)
        t_frame = ctk.CTkFrame(container, fg_color="transparent")
        t_frame.pack(fill="x")
        ctk.CTkLabel(t_frame, text="Sensibilité (Diff):").pack(side="left")
        ctk.CTkLabel(t_frame, textvariable=self.thresh_val, text_color="#10B981").pack(side="right")
        self.scale_thresh = ctk.CTkSlider(container, from_=10, to=150, variable=self.thresh_val, command=lambda v: self.update_frame_preview())
        self.scale_thresh.pack(fill="x", pady=5)
        
        self.wy_val = ctk.IntVar(value=75)
        wy_frame = ctk.CTkFrame(container, fg_color="transparent")
        wy_frame.pack(fill="x")
        ctk.CTkLabel(wy_frame, text="Y Touches Blanches (%):").pack(side="left")
        ctk.CTkLabel(wy_frame, textvariable=self.wy_val, text_color="#10B981").pack(side="right")
        self.scale_wy = ctk.CTkSlider(container, from_=10, to=90, variable=self.wy_val, command=lambda v: [self.update_keyboard_layout(), self.update_frame_preview()])
        self.scale_wy.pack(fill="x", pady=5)
        
        self.by_val = ctk.IntVar(value=30)
        by_frame = ctk.CTkFrame(container, fg_color="transparent")
        by_frame.pack(fill="x")
        ctk.CTkLabel(by_frame, text="Y Touches Noires (%):").pack(side="left")
        ctk.CTkLabel(by_frame, textvariable=self.by_val, text_color="#10B981").pack(side="right")
        self.scale_by = ctk.CTkSlider(container, from_=5, to=80, variable=self.by_val, command=lambda v: [self.update_keyboard_layout(), self.update_frame_preview()])
        self.scale_by.pack(fill="x", pady=5)
        
        # --- Nudge Section ---
        nudge_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=8)
        nudge_frame.pack(fill="x", pady=10, padx=5)
        
        self.lbl_selected_note = ctk.CTkLabel(nudge_frame, text="Touche : Aucune", font=ctk.CTkFont(weight="bold", size=12), text_color="#E07A5F")
        self.lbl_selected_note.pack(pady=(5,0))
        ctk.CTkLabel(nudge_frame, text="(Cliquez sur l'Aperçu redressé pour sélectionner)").pack(pady=(0,5))
        
        self.nudge_x_val = ctk.DoubleVar(value=0)
        nx_row = ctk.CTkFrame(nudge_frame, fg_color="transparent")
        nx_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(nx_row, text="Nudge X :", width=60).pack(side="left")
        self.scale_nudge_x = ctk.CTkSlider(nx_row, from_=-20, to=20, variable=self.nudge_x_val, command=self.on_nudge_change, state="disabled")
        self.scale_nudge_x.pack(side="left", fill="x", expand=True)
        
        self.nudge_y_val = ctk.DoubleVar(value=0)
        ny_row = ctk.CTkFrame(nudge_frame, fg_color="transparent")
        ny_row.pack(fill="x", padx=10, pady=(2,10))
        ctk.CTkLabel(ny_row, text="Nudge Y :", width=60).pack(side="left")
        self.scale_nudge_y = ctk.CTkSlider(ny_row, from_=-20, to=20, variable=self.nudge_y_val, command=self.on_nudge_change, state="disabled")
        self.scale_nudge_y.pack(side="left", fill="x", expand=True)

        filter_frame = ctk.CTkFrame(container, fg_color="transparent")
        filter_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(filter_frame, text="Min ON (Frames):").pack(side="left")
        self.spin_on = ctk.CTkEntry(filter_frame, width=40)
        self.spin_on.insert(0, "1")
        self.spin_on.pack(side="left", padx=5)
        ctk.CTkLabel(filter_frame, text="Min OFF (Frames):").pack(side="left")
        self.spin_off = ctk.CTkEntry(filter_frame, width=40)
        self.spin_off.insert(0, "2")
        self.spin_off.pack(side="left", padx=5)
        
        # --- Section 4: Calibration & Controls ---
        ctk.CTkLabel(container, text="4. Calibration & Export", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15,0))
        
        self.frame_val = ctk.IntVar(value=0)
        scrub_frame = ctk.CTkFrame(container, fg_color="transparent")
        scrub_frame.pack(fill="x")
        ctk.CTkLabel(scrub_frame, text="Scrub Vidéo:").pack(side="left")
        self.lbl_frame_idx = ctk.CTkLabel(scrub_frame, text="0 / 0", text_color="gray")
        self.lbl_frame_idx.pack(side="right")
        self.scale_frame = ctk.CTkSlider(container, from_=0, to=100, variable=self.frame_val, command=self.on_frame_scrub)
        self.scale_frame.pack(fill="x", pady=5)
        
        self.btn_capture_idle = ctk.CTkButton(container, text="1. Capturer l'état au repos", fg_color="#475569", hover_color="#334155", command=self.capture_idle_state)
        self.btn_capture_idle.pack(fill="x", pady=(10, 5))
        
        self.btn_transcribe = ctk.CTkButton(container, text="2. Convertir en MIDI", fg_color="#10B981", hover_color="#059669", command=self.start_transcription)
        self.btn_transcribe.pack(fill="x", pady=5)
        
        self.btn_cancel = ctk.CTkButton(container, text="Annuler", fg_color="#EF4444", hover_color="#DC2626", state="disabled", command=self.cancel_transcription)
        self.btn_cancel.pack(fill="x")
        
        self.progress_bar = ctk.CTkProgressBar(container)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(15, 5))
        
        self.lbl_status = ctk.CTkLabel(container, text="Prêt.", text_color="gray", font=ctk.CTkFont(slant="italic"))
        self.lbl_status.pack(fill="x", anchor="w")

    def build_right_panel(self):
        self.lbl_view_title = ctk.CTkLabel(self.right_panel, text="Étape 1 : Ouvrez une vidéo pour calibrer", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_view_title.pack(anchor="w", pady=(0, 10))
        
        video_outer = tk.Frame(self.right_panel, bg="#2D2D34", bd=1)
        video_outer.pack(fill="both", expand=True)
        
        self.video_canvas = tk.Canvas(video_outer, bg="#121214", bd=0, highlightthickness=0, cursor="crosshair")
        self.video_canvas.pack(fill="both", expand=True)
        
        self.video_canvas.bind("<Button-1>", self.on_canvas_press)
        self.video_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.video_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        self.lbl_instr = ctk.CTkLabel(self.right_panel, text="Calibration : Déplacez les 4 points (TL, TR, BR, BL) pour encadrer parfaitement le clavier du piano.\nLe bandeau ci-dessous vous montrera le clavier redressé (warped).", text_color="gray", font=ctk.CTkFont(size=11, slant="italic"), justify="left")
        self.lbl_instr.pack(fill="x", pady=5)
        
        warped_outer = ctk.CTkFrame(self.right_panel)
        warped_outer.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(warped_outer, text="Aperçu redressé (1200x80) :", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=5)
        
        self.warped_canvas = tk.Canvas(warped_outer, bg="#121214", height=60, bd=0, highlightthickness=0, cursor="hand2")
        self.warped_canvas.pack(fill="x", padx=5, pady=5)
        self.warped_canvas.bind("<Button-1>", self.on_warped_canvas_click)
        
        self.lbl_resolution_info = ctk.CTkLabel(self.right_panel, text="Résolution: 0x0", text_color="gray", font=ctk.CTkFont(size=10))
        self.lbl_resolution_info.pack(anchor="e")

    # --- Preset Configuration Handler ---
    def on_preset_change(self, val):
        preset = self.combo_preset.get()
        if "88" in preset:
            self.combo_start.set(MIDI_NOTES_ALL[21])  # A0
            self.combo_end.set(MIDI_NOTES_ALL[108])  # C8
        elif "61" in preset:
            self.combo_start.set(MIDI_NOTES_ALL[36])  # C2
            self.combo_end.set(MIDI_NOTES_ALL[96])   # C7
        elif "76" in preset:
            self.combo_start.set(MIDI_NOTES_ALL[28])  # E1
            self.combo_end.set(MIDI_NOTES_ALL[103])  # G7
        elif "49" in preset:
            self.combo_start.set(MIDI_NOTES_ALL[48])  # C3
            self.combo_end.set(MIDI_NOTES_ALL[96])   # C7
        
        self.update_keyboard_layout()
        self.update_frame_preview()

    def on_note_range_ui_change(self, val):
        self.combo_preset.set("Custom")
        self.update_keyboard_layout()
        self.update_frame_preview()

    def on_warped_canvas_click(self, event):
        if not self.note_coords: return
        
        # Calculate scale ratio between actual W_WIDTH and canvas display width
        c_w = self.warped_canvas.winfo_width()
        c_h = self.warped_canvas.winfo_height()
        if c_w < 10: return
        
        scale_x = self.W_WIDTH / c_w
        scale_y = self.W_HEIGHT / c_h
        
        # Real coordinates in the 1200x80 space
        real_x = event.x * scale_x
        real_y = event.y * scale_y
        
        # Find nearest note
        best_note = None
        best_dist = 9999
        
        for note, (nx, ny) in self.note_coords.items():
            dx = self.note_nudges.get(note, [0,0])[0]
            dy = self.note_nudges.get(note, [0,0])[1]
            
            dist = np.sqrt((real_x - (nx + dx))**2 + (real_y - (ny + dy))**2)
            if dist < best_dist and dist < 25: # Max click distance
                best_dist = dist
                best_note = note
                
        if best_note:
            self.selected_note = best_note
            self.lbl_selected_note.configure(text=f"Touche : {midi_to_note_name(best_note)} ({best_note})")
            self.scale_nudge_x.configure(state="normal")
            self.scale_nudge_y.configure(state="normal")
            
            curr_nudges = self.note_nudges.get(best_note, [0,0])
            self.nudge_x_val.set(curr_nudges[0])
            self.nudge_y_val.set(curr_nudges[1])
        else:
            self.selected_note = None
            self.lbl_selected_note.configure(text="Touche : Aucune")
            self.scale_nudge_x.configure(state="disabled")
            self.scale_nudge_y.configure(state="disabled")
            self.nudge_x_val.set(0)
            self.nudge_y_val.set(0)
            
        self.update_warped_preview()

    def on_nudge_change(self, val):
        if self.selected_note:
            self.note_nudges[self.selected_note] = [self.nudge_x_val.get(), self.nudge_y_val.get()]
            self.update_warped_preview()

    # --- Core Note Coordinate Calculation ---
    def update_keyboard_layout(self):
        start_str = self.combo_start.get()
        end_str = self.combo_end.get()
        try:
            start_note = int(start_str.split("(")[1].replace(")", ""))
            end_note = int(end_str.split("(")[1].replace(")", ""))
        except: return
            
        if start_note >= end_note:
            start_note, end_note = end_note, start_note
            self.combo_start.set(MIDI_NOTES_ALL[start_note])
            self.combo_end.set(MIDI_NOTES_ALL[end_note])
            
        self.start_note = start_note
        self.end_note = end_note
        
        self.white_keys = [n for n in range(self.start_note, self.end_note + 1) if is_midi_note_white(n)]
        num_whites = len(self.white_keys)
        if num_whites == 0: return
            
        # Clear/initialize coordinates (Keep nudges if possible)
        self.note_coords = {}
        
        w_y_offset = self.wy_val.get() / 100.0
        b_y_offset = self.by_val.get() / 100.0
        
        for n in range(self.start_note, self.end_note + 1):
            if is_midi_note_white(n):
                w_idx = self.white_keys.index(n)
                x = int((w_idx + 0.5) * (self.W_WIDTH / num_whites))
                y = int(self.W_HEIGHT * w_y_offset)
                self.note_coords[n] = (x, y)
                if n not in self.note_nudges:
                    self.note_nudges[n] = [0.0, 0.0]
            else:
                left_whites = [w for w in self.white_keys if w < n]
                if left_whites:
                    left_white = max(left_whites)
                    w_idx = self.white_keys.index(left_white)
                    x = int((w_idx + 1) * (self.W_WIDTH / num_whites))
                else:
                    x = int(0.5 * (self.W_WIDTH / num_whites))
                y = int(self.W_HEIGHT * b_y_offset)
                self.note_coords[n] = (x, y)
                if n not in self.note_nudges:
                    self.note_nudges[n] = [0.0, 0.0]
                
        if self.idle_warped_frame is not None:
            self.sample_idle_colors()

    def sample_idle_colors(self):
        if self.idle_warped_frame is None: return
        self.idle_colors = {}
        for note, pt in self.note_coords.items():
            nx = int(pt[0] + self.note_nudges[note][0])
            ny = int(pt[1] + self.note_nudges[note][1])
            self.idle_colors[note] = self.get_neighborhood_color(self.idle_warped_frame, nx, ny)

    def get_neighborhood_color(self, frame, x, y, size=5):
        half = size // 2
        y_min = max(0, y - half)
        y_max = min(frame.shape[0] - 1, y + half)
        x_min = max(0, x - half)
        x_max = min(frame.shape[1] - 1, x + half)
        block = frame[y_min:y_max+1, x_min:x_max+1]
        return cv2.mean(block)[:3] 

    def on_frame_scrub(self, val):
        if self.cap is None: return
        frame_idx = int(float(val))
        self.lbl_frame_idx.configure(text=f"{frame_idx} / {self.total_frames}")
        self.read_frame_at(frame_idx)
        self.update_frame_preview()

    def load_video_dialog(self):
        filepath = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm")])
        if filepath: self.load_video(filepath)

    def load_video(self, filepath):
        self.lbl_status.configure(text="Loading video...", text_color="gray")
        self.update_idletasks()
        
        if self.cap is not None: self.cap.release()
            
        self.video_path = filepath
        self.cap = cv2.VideoCapture(filepath)
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0: self.fps = 30.0
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        filename = os.path.basename(filepath)
        duration_sec = self.total_frames / self.fps
        duration_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
        
        self.lbl_video_info.configure(text=f"Fichier: {filename}\nRésolution: {self.video_width}x{self.video_height}\nFPS: {self.fps:.2f} | Durée: {duration_str}")
        
        self.scale_frame.configure(to=self.total_frames - 1)
        self.scale_frame.set(0)
        self.lbl_frame_idx.configure(text=f"0 / {self.total_frames}")
        
        max_w, max_h = 800, 450
        scale = min(max_w / self.video_width, max_h / self.video_height)
        self.display_scale = scale
        
        disp_w = int(self.video_width * scale)
        disp_h = int(self.video_height * scale)
        self.video_canvas.config(width=disp_w, height=disp_h)
        
        self.corners = {
            "TL": [int(disp_w * 0.08), int(disp_h * 0.70)],
            "TR": [int(disp_w * 0.92), int(disp_h * 0.70)],
            "BR": [int(disp_w * 0.95), int(disp_h * 0.88)],
            "BL": [int(disp_w * 0.05), int(disp_h * 0.88)]
        }
        
        self.lbl_view_title.configure(text="Étape 2 : Ajustez les coins pour encadrer le clavier")
        self.lbl_resolution_info.configure(text=f"Vidéo: {self.video_width}x{self.video_height} | Warped Preview: {self.W_WIDTH}x{self.W_HEIGHT}")
        
        self.idle_warped_frame = None
        self.idle_colors = {}
        
        self.read_frame_at(0)
        self.update_keyboard_layout()
        self.update_frame_preview()
        self.lbl_status.configure(text="Video loaded successfully.", text_color="#10B981")

    def read_frame_at(self, frame_idx):
        if self.cap is None: return
        self.current_frame_idx = frame_idx
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if ret:
            self.current_video_frame = frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            disp_w = int(self.video_width * self.display_scale)
            disp_h = int(self.video_height * self.display_scale)
            pil_img_resized = pil_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
            self.current_tk_image = ImageTk.PhotoImage(image=pil_img_resized)
        else:
            self.lbl_status.configure(text=f"Failed to read frame {frame_idx}", text_color="red")

    def update_frame_preview(self):
        if self.current_video_frame is None: return
        self.video_canvas.delete("all")
        self.video_canvas.create_image(0, 0, anchor="nw", image=self.current_tk_image)
        
        tl, tr, br, bl = self.corners["TL"], self.corners["TR"], self.corners["BR"], self.corners["BL"]
        
        self.video_canvas.create_line(tl[0], tl[1], tr[0], tr[1], fill="#FF79C6", width=2, tags="overlay")
        self.video_canvas.create_line(tr[0], tr[1], br[0], br[1], fill="#FF79C6", width=2, tags="overlay")
        self.video_canvas.create_line(br[0], br[1], bl[0], bl[1], fill="#FF79C6", width=2, tags="overlay")
        self.video_canvas.create_line(bl[0], bl[1], tl[0], tl[1], fill="#FF79C6", width=2, tags="overlay")
        
        for name, pt in self.corners.items():
            r = self.corner_radius
            color = "#F1FA8C" if self.active_corner == name else "#6366F1"
            self.video_canvas.create_oval(pt[0]-r, pt[1]-r, pt[0]+r, pt[1]+r, fill=color, outline="#FFFFFF", width=2, tags=("overlay", f"handle_{name}"))
            self.video_canvas.create_text(pt[0], pt[1]-r-8, text=name, fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags="overlay")
            
        self.update_warped_preview()

    def update_warped_preview(self):
        if self.current_video_frame is None: return
        pts_src = np.float32([self.corners["TL"], self.corners["TR"], self.corners["BR"], self.corners["BL"]]) / self.display_scale
        pts_dst = np.float32([[0, 0], [self.W_WIDTH, 0], [self.W_WIDTH, self.W_HEIGHT], [0, self.W_HEIGHT]])
        
        M = cv2.getPerspectiveTransform(pts_src, pts_dst)
        warped_frame = cv2.warpPerspective(self.current_video_frame, M, (self.W_WIDTH, self.W_HEIGHT))
        
        threshold = int(self.thresh_val.get())
        annotated_warped = warped_frame.copy()
        
        for note, pt in self.note_coords.items():
            cx = int(pt[0] + self.note_nudges[note][0])
            cy = int(pt[1] + self.note_nudges[note][1])
            
            is_pressed = False
            
            if self.idle_colors and note in self.idle_colors:
                curr_color = self.get_neighborhood_color(warped_frame, cx, cy)
                idle_color = self.idle_colors[note]
                dist = np.sqrt((curr_color[0] - idle_color[0])**2 + (curr_color[1] - idle_color[1])**2 + (curr_color[2] - idle_color[2])**2)
                if dist > threshold: is_pressed = True
            
            is_white = is_midi_note_white(note)
            
            # Highlight selected note
            is_selected = (note == self.selected_note)
            
            if is_pressed:
                color_bgr = (0, 230, 0) if is_white else (0, 0, 230)
                if is_selected: color_bgr = (0, 255, 255) # Cyan for selected
                cv2.circle(annotated_warped, (cx, cy), 5, color_bgr, -1)
                cv2.putText(annotated_warped, midi_to_note_name(note), (cx - 10, cy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
            else:
                color_bgr = (150, 150, 150)
                if is_selected: color_bgr = (0, 255, 255) # Cyan outline for selected
                thickness = 2 if is_selected else 1
                cv2.circle(annotated_warped, (cx, cy), 4 if is_selected else 3, color_bgr, thickness)
                
        rgb_warped = cv2.cvtColor(annotated_warped, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_warped)
        
        c_w = self.warped_canvas.winfo_width()
        if c_w < 10: c_w = 800
        c_h = int(c_w * (self.W_HEIGHT / self.W_WIDTH))
        self.warped_canvas.config(height=c_h)
        
        pil_img_resized = pil_img.resize((c_w, c_h), Image.Resampling.LANCZOS)
        self.warped_tk_image = ImageTk.PhotoImage(image=pil_img_resized)
        
        self.warped_canvas.delete("all")
        self.warped_canvas.create_image(0, 0, anchor="nw", image=self.warped_tk_image)

    def on_canvas_press(self, event):
        if self.current_video_frame is None: return
        mx, my = event.x, event.y
        r = self.corner_radius + 4 
        self.active_corner = None
        for name, pt in self.corners.items():
            dist = np.sqrt((mx - pt[0])**2 + (my - pt[1])**2)
            if dist <= r:
                self.active_corner = name
                self.update_frame_preview()
                break

    def on_canvas_drag(self, event):
        if self.active_corner is None or self.current_video_frame is None: return
        disp_w = int(self.video_width * self.display_scale)
        disp_h = int(self.video_height * self.display_scale)
        mx = max(0, min(event.x, disp_w))
        my = max(0, min(event.y, disp_h))
        self.corners[self.active_corner] = [mx, my]
        self.update_frame_preview()

    def on_canvas_release(self, event):
        if self.active_corner is not None:
            self.active_corner = None
            self.update_frame_preview()

    def capture_idle_state(self):
        if self.current_video_frame is None:
            messagebox.showwarning("Erreur", "Veuillez charger une vidéo et vous placer sur une image où le clavier est vide.")
            return
            
        pts_src = np.float32([self.corners["TL"], self.corners["TR"], self.corners["BR"], self.corners["BL"]]) / self.display_scale
        pts_dst = np.float32([[0, 0], [self.W_WIDTH, 0], [self.W_WIDTH, self.W_HEIGHT], [0, self.W_HEIGHT]])
        M = cv2.getPerspectiveTransform(pts_src, pts_dst)
        
        self.idle_warped_frame = cv2.warpPerspective(self.current_video_frame, M, (self.W_WIDTH, self.W_HEIGHT))
        self.sample_idle_colors()
        self.lbl_status.configure(text=f"État repos capturé. Prêt à transcrire.", text_color="#10B981")
        self.update_frame_preview()

    def start_transcription(self):
        if self.video_path is None: return
        if not self.idle_colors:
            messagebox.showwarning("Erreur", "Veuillez capturer l'état au repos d'abord.")
            return
            
        default_name = os.path.splitext(os.path.basename(self.video_path))[0] + "_touches.mid"
        out_path = filedialog.asksaveasfilename(initialfile=default_name, filetypes=[("MIDI Files", "*.mid")])
        if not out_path: return
            
        self.set_ui_state("disabled")
        self.btn_cancel.configure(state="normal")
        self.lbl_status.configure(text="Transcription en cours...", text_color="gray")
        self.progress_bar.set(0)
        
        pts_src = np.float32([self.corners["TL"], self.corners["TR"], self.corners["BR"], self.corners["BL"]]) / self.display_scale
        threshold = int(self.thresh_val.get())
        
        try:
            min_on_frames = int(self.spin_on.get())
            min_off_frames = int(self.spin_off.get())
        except:
            min_on_frames, min_off_frames = 1, 2
        
        self.cancel_event.clear()
        
        self.transcribe_thread = threading.Thread(
            target=self.transcribe_worker,
            args=(self.video_path, pts_src, self.note_coords.copy(), self.idle_colors.copy(), 
                  threshold, min_on_frames, min_off_frames, out_path)
        )
        self.transcribe_thread.daemon = True
        self.transcribe_thread.start()

    def set_ui_state(self, state):
        s = "disabled" if state == "disabled" else "normal"
        self.btn_load.configure(state=s)
        self.combo_preset.configure(state=s)
        self.combo_start.configure(state=s)
        self.combo_end.configure(state=s)
        self.scale_thresh.configure(state=s)
        self.scale_wy.configure(state=s)
        self.scale_by.configure(state=s)
        self.scale_frame.configure(state=s)
        self.btn_capture_idle.configure(state=s)
        self.btn_transcribe.configure(state=s)

    def cancel_transcription(self):
        self.cancel_event.set()
        self.btn_cancel.configure(state="disabled")
        self.lbl_status.configure(text="Annulation...", text_color="red")

    def transcribe_worker(self, video_path, pts_src, note_coords, idle_colors, threshold, min_on, min_off, out_path):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0: fps = 30.0
            
        pts_dst = np.float32([[0, 0], [self.W_WIDTH, 0], [self.W_WIDTH, self.W_HEIGHT], [0, self.W_HEIGHT]])
        M = cv2.getPerspectiveTransform(pts_src, pts_dst)
        
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(120), time=0))
        ticks_per_second = mid.ticks_per_beat * (120 / 60)
        
        note_states = {}
        for note in note_coords.keys():
            note_states[note] = {'active': False, 'history': []}
            
        events = [] 
        frame_idx = 0
        last_progress_update = time.time()
        
        while cap.isOpened() and not self.cancel_event.is_set():
            ret, frame = cap.read()
            if not ret: break
                
            warped = cv2.warpPerspective(frame, M, (self.W_WIDTH, self.W_HEIGHT))
            t_ticks = int((frame_idx / fps) * ticks_per_second)
            
            for note, pt in note_coords.items():
                cx = int(pt[0] + self.note_nudges[note][0])
                cy = int(pt[1] + self.note_nudges[note][1])
                
                curr_color = self.get_neighborhood_color(warped, cx, cy)
                idle_color = idle_colors[note]
                
                dist = np.sqrt((curr_color[0] - idle_color[0])**2 + (curr_color[1] - idle_color[1])**2 + (curr_color[2] - idle_color[2])**2)
                is_active_now = dist > threshold
                
                history = note_states[note]['history']
                history.append(is_active_now)
                max_history = max(min_on, min_off)
                if len(history) > max_history: history.pop(0)
                    
                current_state = note_states[note]['active']
                if not current_state:
                    if len(history) >= min_on and all(history[-min_on:]):
                        note_states[note]['active'] = True
                        events.append((t_ticks, 'note_on', note))
                else:
                    if len(history) >= min_off and not any(history[-min_off:]):
                        note_states[note]['active'] = False
                        events.append((t_ticks, 'note_off', note))
            
            frame_idx += 1
            curr_time = time.time()
            if curr_time - last_progress_update > 0.1:
                progress = frame_idx / total_frames
                self.progress_queue.put(('progress', progress, frame_idx))
                last_progress_update = curr_time
                
        cap.release()
        t_ticks_end = int((frame_idx / fps) * ticks_per_second)
        for note, state in note_states.items():
            if state['active']: events.append((t_ticks_end, 'note_off', note))
                
        if self.cancel_event.is_set():
            self.progress_queue.put(('cancelled',))
            return
            
        events.sort(key=lambda e: e[0])
        prev_tick = 0
        for t_ticks, ev_type, note in events:
            delta = t_ticks - prev_tick
            if ev_type == 'note_on': track.append(mido.Message('note_on', note=note, velocity=100, time=delta))
            else: track.append(mido.Message('note_off', note=note, velocity=0, time=delta))
            prev_tick = t_ticks
            
        try:
            mid.save(out_path)
            self.progress_queue.put(('success', out_path))
        except Exception as e:
            self.progress_queue.put(('error', str(e)))

    def check_progress_queue(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg[0] == 'progress':
                    pct = msg[1]
                    self.progress_bar.set(pct)
                    self.lbl_status.configure(text=f"Traitement frame {msg[2]} of {self.total_frames} ({int(pct * 100)}%)...")
                elif msg[0] == 'success':
                    self.progress_bar.set(1.0)
                    self.lbl_status.configure(text="Fichier MIDI sauvegardé !", text_color="#10B981")
                    if messagebox.askyesno("Succès", f"Fichier MIDI généré :\n{msg[1]}\n\nOuvrir le dossier ?"):
                        os.startfile(os.path.dirname(msg[1]))
                    self.finalize_transcription()
                elif msg[0] == 'cancelled':
                    self.progress_bar.set(0)
                    self.lbl_status.configure(text="Annulé par l'utilisateur.", text_color="red")
                    self.finalize_transcription()
                elif msg[0] == 'error':
                    self.progress_bar.set(0)
                    self.lbl_status.configure(text=f"Erreur: {msg[1]}", text_color="red")
                    messagebox.showerror("Erreur", f"Échec de l'enregistrement :\n{msg[1]}")
                    self.finalize_transcription()
        except queue.Empty: pass
        self.after(100, self.check_progress_queue)

    def finalize_transcription(self):
        self.set_ui_state("normal")
        self.btn_cancel.configure(state="disabled")
        self.transcribe_thread = None


# --- Original MIDIa implementation below ---

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
        self.sim_window = None
        self.sim_label = None
        self.sim_info = None
        self.calib_y = 0.8 
        self.calib_scale = 1.0 
        self.calib_offset = 0.0 
        self.black_key_width_ratio = 0.6 
        self.black_key_spread = 0.0
        self.visual_zoom = 1.0
        self.analysis_mode = ctk.StringVar(value="barres") 
        self.show_preview = ctk.BooleanVar(value=False)
        
        self.thresh_w_on = ctk.DoubleVar(value=0.80)
        self.thresh_w_off = ctk.DoubleVar(value=0.40)
        self.thresh_b_on = ctk.DoubleVar(value=0.75)
        self.thresh_b_off = ctk.DoubleVar(value=0.20)
        
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
        
        tab_new_video = self.tabview.add("🎥 Vidéo Pro (Warping)")
        tab_audio = self.tabview.add("🎵 Audio (IA)")
        tab_video = self.tabview.add("📹 Vidéo (Calque)")

        # Integrate the new engine
        self.new_engine = NewVideoEngine(tab_new_video, self.controller)
        self.new_engine.pack(fill="both", expand=True)

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

        self.preview_cb = ctk.CTkCheckBox(parent, text="Afficher la simulation en direct (ralentit l'analyse)", variable=self.show_preview, fg_color="#2E8B57", hover_color="#1F5F3A")
        self.preview_cb.pack(pady=5)

        self.video_btn = ctk.CTkButton(parent, text="👁️ Calibrer & Analyser", font=ctk.CTkFont(size=18, weight="bold"),
                                      height=50, fg_color="#2E8B57", hover_color="#1F5F3A", command=self._start_video_processing)
        self.video_btn.pack(pady=20)
        ctk.CTkLabel(parent, text="💡 Ce mode projette un clavier virtuel pour une précision parfaite.", font=ctk.CTkFont(size=12, slant="italic"), text_color="#aaaaaa").pack(pady=10)

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
        self.calib_window.geometry("1400x1000")
        self.calib_window.transient(self)
        
        top_frame = ctk.CTkFrame(self.calib_window, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(top_frame, text="Mode :", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        ctk.CTkRadioButton(top_frame, text="Barres", variable=self.analysis_mode, value="barres").pack(side="left", padx=10)
        ctk.CTkRadioButton(top_frame, text="Touches", variable=self.analysis_mode, value="touches").pack(side="left", padx=10)
        ctk.CTkLabel(top_frame, text=" | Zoom :").pack(side="left", padx=10)
        self.vzoom_slider = ctk.CTkSlider(top_frame, from_=1.0, to=4.0, number_of_steps=300, width=150)
        self.vzoom_slider.set(self.visual_zoom)
        self.vzoom_slider.pack(side="left", padx=10)
        self.selected_key_label = ctk.CTkLabel(top_frame, text="Touche : Aucune", text_color="#E07A5F")
        self.selected_key_label.pack(side="right", padx=20)
        
        self.calib_canvas = tk.Canvas(self.calib_window, bg="black", highlightthickness=0)
        self.calib_canvas.pack(fill="both", expand=True, padx=20, pady=5)
        
        h, w = frame.shape[:2]
        self.kb_tag = "keyboard_overlay"
        self.drag_data = {"x": 0, "y": 0, "active": False}

        def on_mouse_down(event):
            cw = self.calib_canvas.winfo_width()
            ch = self.calib_canvas.winfo_height()
            cx, cy = cw//2, ch//2
            img_left_x = cx - self.vid_w//2
            best_dist = 9999
            self.selected_key_idx = -1
            for i, rect in enumerate(self.key_rects):
                x_center = img_left_x + (rect[0] + (rect[1]-rect[0])/2) * self.vid_w
                dist = abs(event.x - x_center)
                if dist < 20 and dist < best_dist:
                    best_dist = dist
                    self.selected_key_idx = i
            if self.selected_key_idx != -1:
                n = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][(21+self.selected_key_idx)%12]
                self.selected_key_label.configure(text=f"Touche : {n}{(21+self.selected_key_idx)//12}")
                self.nudge_slider.set(self.key_nudges[self.selected_key_idx])
            else: self.selected_key_label.configure(text="Touche : Aucune")
            self.drag_data["x"] = event.x; self.drag_data["y"] = event.y; self.drag_data["active"] = True
            update_view()

        def on_mouse_drag(event):
            if not self.drag_data["active"]: return
            dx = event.x - self.drag_data["x"]; dy = event.y - self.drag_data["y"]
            self.drag_data["x"] = event.x; self.drag_data["y"] = event.y
            self.calib_offset += (dx / (self.vid_w * self.visual_zoom * 3.0))
            self.calib_y += (dy / (self.vid_h * self.visual_zoom * 2.0))
            self.calib_y = max(0.0, min(1.0, self.calib_y))
            self.y_slider.set(self.calib_y); self.pan_slider.set(self.calib_offset)
            update_view()

        def on_mouse_up(event): self.drag_data["active"] = False

        self.calib_canvas.bind("<ButtonPress-1>", on_mouse_down)
        self.calib_canvas.bind("<B1-Motion>", on_mouse_drag)
        self.calib_canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        def generate_keyboard_rects(total_width, black_ratio, black_spread):
            white_width = total_width / 52.0
            black_width = white_width * black_ratio
            is_black = [False, True, False]
            for _ in range(7): is_black.extend([False, True, False, True, False, False, True, False, True, False, True, False])
            is_black.append(False)
            rects = []; current_white_x = 0
            for i, black in enumerate(is_black):
                note_mod = (21 + i) % 12
                indiv_nudge = self.key_nudges[i] * white_width
                if not black:
                    rects.append([current_white_x + indiv_nudge, current_white_x + white_width + indiv_nudge, False, i])
                    current_white_x += white_width
                else:
                    dx = 0
                    if note_mod == 1: dx = -black_spread
                    elif note_mod == 3: dx = black_spread
                    elif note_mod == 6: dx = -black_spread
                    elif note_mod == 8: dx = 0
                    elif note_mod == 10: dx = black_spread
                    center_x = current_white_x + (dx * white_width) + indiv_nudge
                    rects.append([center_x - black_width/2, center_x + black_width/2, True, i])
            return rects

        def update_view(*args):
            self.visual_zoom = float(self.vzoom_slider.get())
            cw = self.calib_canvas.winfo_width(); ch = self.calib_canvas.winfo_height()
            if cw < 100: cw, ch = 1000, 500
            ratio = min(cw/w, ch/h) * self.visual_zoom
            self.vid_w, self.vid_h = int(w*ratio), int(h*ratio)
            prev = cv2.resize(frame, (self.vid_w, self.vid_h))
            prev = cv2.cvtColor(prev, cv2.COLOR_BGR2RGB)
            self.calib_img_orig = Image.fromarray(prev); self.calib_img_tk = ImageTk.PhotoImage(self.calib_img_orig)
            self.calib_canvas.delete("all")
            cx, cy = cw//2, ch//2; self.calib_canvas.create_image(cx, cy, image=self.calib_img_tk)
            self.calib_y = float(self.y_slider.get()); y_p = cy - self.vid_h//2 + int(self.vid_h * self.calib_y)
            self.calib_canvas.create_line(cx-self.vid_w//2, y_p, cx+self.vid_w//2, y_p, fill="red", width=2)
            scale = float(self.zoom_slider.get()); self.calib_offset = float(self.pan_slider.get())
            offset = self.calib_offset * self.vid_w; b_ratio = float(self.bw_slider.get()); b_spread = float(self.bs_slider.get())
            self.base_rects = generate_keyboard_rects(self.vid_w, b_ratio, b_spread)
            img_left_x = cx - self.vid_w//2; self.key_rects = []
            for i, r in enumerate(self.base_rects):
                x1 = img_left_x + (r[0] * scale) + offset; x2 = img_left_x + (r[1] * scale) + offset
                is_black = r[2]; self.key_rects.append([(r[0] * scale + offset)/self.vid_w, (r[1] * scale + offset)/self.vid_w, is_black, r[3]])
                if x2 > img_left_x and x1 < img_left_x + self.vid_w:
                    color = "magenta" if is_black else "cyan"; width = 2
                    if i == self.selected_key_idx: color = "yellow"; width = 3
                    if is_black: self.calib_canvas.create_rectangle(x1, y_p-30, x2, y_p+10, outline=color, width=width, tags=self.kb_tag, fill=color, stipple="gray25")
                    else: self.calib_canvas.create_rectangle(x1, y_p-20, x2, y_p+20, outline=color, width=width, tags=self.kb_tag)

        def update_nudge(val):
            if self.selected_key_idx != -1: self.key_nudges[self.selected_key_idx] = float(val); update_view()

        self.calib_window.update(); bot_ctrl = ctk.CTkFrame(self.calib_window); bot_ctrl.pack(fill="x", padx=20, pady=10)
        
        col_left = ctk.CTkFrame(bot_ctrl, fg_color="transparent")
        col_left.pack(side="left", fill="both", expand=True, padx=5)
        col_right = ctk.CTkFrame(bot_ctrl, fg_color="#2b2b2b", corner_radius=10)
        col_right.pack(side="right", fill="both", expand=False, padx=5, ipadx=10, ipady=10)

        # Left Column : Geometry
        r1 = ctk.CTkFrame(col_left, fg_color="transparent"); r1.pack(fill="x", pady=2)
        ctk.CTkLabel(r1, text="Y :").pack(side="left"); self.y_slider = ctk.CTkSlider(r1, from_=0, to=1, number_of_steps=1000, command=update_view)
        self.y_slider.set(self.calib_y); self.y_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        r2 = ctk.CTkFrame(col_left, fg_color="transparent"); r2.pack(fill="x", pady=5)
        ctk.CTkLabel(r2, text="Échelle X :").pack(side="left"); self.zoom_slider = ctk.CTkSlider(r2, from_=0.5, to=1.5, number_of_steps=3000, command=update_view)
        self.zoom_slider.set(1.0); self.zoom_slider.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(r2, text="Offset X :").pack(side="left"); self.pan_slider = ctk.CTkSlider(r2, from_=-0.5, to=0.5, number_of_steps=3000, command=update_view)
        self.pan_slider.set(0.0); self.pan_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        r3 = ctk.CTkFrame(col_left, fg_color="transparent"); r3.pack(fill="x", pady=5)
        ctk.CTkLabel(r3, text="Larg. Noires :").pack(side="left"); self.bw_slider = ctk.CTkSlider(r3, from_=0.2, to=1.0, command=update_view)
        self.bw_slider.set(0.6); self.bw_slider.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkLabel(r3, text="Écart. Noires :").pack(side="left"); self.bs_slider = ctk.CTkSlider(r3, from_=-0.3, to=0.3, command=update_view)
        self.bs_slider.set(0.0); self.bs_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        r4 = ctk.CTkFrame(col_left, fg_color="#333333"); r4.pack(fill="x", pady=5)
        ctk.CTkLabel(r4, text="NUDGE TOUCHE :", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=10)
        self.nudge_slider = ctk.CTkSlider(r4, from_=-1.0, to=1.0, number_of_steps=200, command=update_nudge)
        self.nudge_slider.set(0.0); self.nudge_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        # Right Column : Thresholds
        ctk.CTkLabel(col_right, text="Seuils de Couverture (%)", font=ctk.CTkFont(weight="bold")).pack(pady=(0, 5))
        
        tw1 = ctk.CTkFrame(col_right, fg_color="transparent"); tw1.pack(fill="x", pady=2)
        ctk.CTkLabel(tw1, text="Blanc ON:").pack(side="left"); s_won = ctk.CTkSlider(tw1, from_=0.1, to=1.0, variable=self.thresh_w_on, width=100); s_won.pack(side="right")
        tw2 = ctk.CTkFrame(col_right, fg_color="transparent"); tw2.pack(fill="x", pady=2)
        ctk.CTkLabel(tw2, text="Blanc OFF:").pack(side="left"); s_woff = ctk.CTkSlider(tw2, from_=0.0, to=0.9, variable=self.thresh_w_off, width=100); s_woff.pack(side="right")
        
        tb1 = ctk.CTkFrame(col_right, fg_color="transparent"); tb1.pack(fill="x", pady=2)
        ctk.CTkLabel(tb1, text="Noir ON:").pack(side="left"); s_bon = ctk.CTkSlider(tb1, from_=0.1, to=1.0, variable=self.thresh_b_on, width=100, button_color="gray"); s_bon.pack(side="right")
        tb2 = ctk.CTkFrame(col_right, fg_color="transparent"); tb2.pack(fill="x", pady=2)
        ctk.CTkLabel(tb2, text="Noir OFF:").pack(side="left"); s_boff = ctk.CTkSlider(tb2, from_=0.0, to=0.9, variable=self.thresh_b_off, width=100, button_color="gray"); s_boff.pack(side="right")

        self.vzoom_slider.configure(command=update_view); update_view()
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
            from PIL import Image, ImageTk
            
            self._update_status(f"Analyse ({self.analysis_mode.get()})...")
            v_path = self.video_file.get()
            mid_path = v_path.rsplit('.', 1)[0] + ".mid"
            
            cap = cv2.VideoCapture(v_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w, h = int(cap.get(3)), int(cap.get(4))
            
            target_y = int(h * self.calib_y)
            y_start, y_end = max(0, target_y-3), min(h, target_y+3)

            for _ in range(10): cap.read()
            ret, baseline_frame = cap.read()
            if not ret: baseline_frame = np.zeros((h, w, 3), np.uint8)
            baseline_band = baseline_frame[y_start:y_end, :, :]
            baseline_hsv = cv2.cvtColor(baseline_band, cv2.COLOR_BGR2HSV)
            
            keys = [False] * 88
            events = []
            ticks_per_second = 960.0
            
            # --- CUSTOM TKINTER SIMULATION WINDOW ---
            self.sim_state = {
                "paused": False,
                "play_delay": 0.001,
                "seek_frames": 0,
                "active": self.show_preview.get()
            }
            
            if self.sim_state["active"]:
                self.after(0, self._open_sim_window)

            f_idx = 11
            while True:
                if not self.is_processing: break
                    
                if self.sim_state["seek_frames"] != 0:
                    f_idx = max(11, min(total_f - 1, f_idx + self.sim_state["seek_frames"]))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                    current_ticks = int((f_idx / fps) * ticks_per_second)
                    events = [e for e in events if e[0] < current_ticks]
                    keys = [False] * 88
                    self.sim_state["seek_frames"] = 0
                    continue

                if self.sim_state["paused"]:
                    time.sleep(0.05)
                    continue

                ret, frame = cap.read()
                if not ret: break
                
                current_ticks = int((f_idx / fps) * ticks_per_second)
                band = frame[y_start:y_end, :, :]
                hsv_band = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
                diff = cv2.absdiff(hsv_band, baseline_hsv)
                
                if self.sim_state["active"]:
                    display_frame = frame.copy()
                    cv2.line(display_frame, (0, target_y), (w, target_y), (0, 0, 255), 2)

                for i in range(88):
                    rect = self.key_rects[i]
                    xs, xe = int(rect[0] * w), int(rect[1] * w)
                    if xe < 0 or xs > w or xs >= xe: continue
                    
                    is_black = rect[2]
                    zone_curr = hsv_band[:, max(0,xs):min(w,xe), :]
                    if zone_curr.size == 0: continue
                    
                    col_v = np.mean(zone_curr[:,:,2], axis=0)
                    col_s = np.mean(zone_curr[:,:,1], axis=0)
                    active_cols = ((col_v > 70) & (col_s > 60)) | (col_v > 185)
                    coverage = np.mean(active_cols)
                    
                    if is_black and self.analysis_mode.get() == "barres":
                        is_on = coverage >= self.thresh_b_on.get()
                        thresh_off = self.thresh_b_off.get()
                    else:
                        is_on = coverage >= self.thresh_w_on.get()
                        thresh_off = self.thresh_w_off.get()

                    if is_on and not keys[i]:
                        keys[i] = True
                        events.append((current_ticks, 'note_on', 21+i, 100))
                    elif not is_on and keys[i]:
                        if coverage < thresh_off:
                            keys[i] = False
                            events.append((current_ticks, 'note_off', 21+i, 0))
                            
                    if self.sim_state["active"] and keys[i]:
                        color = (255, 0, 255) if is_black else (255, 255, 0)
                        cv2.rectangle(display_frame, (xs, target_y-15), (xe, target_y+15), color, -1)
                        
                if self.sim_state["active"] and f_idx % 2 == 0:
                    frame_rgb = cv2.cvtColor(cv2.resize(display_frame, (800, 450)), cv2.COLOR_BGR2RGB)
                    img_tk = ImageTk.PhotoImage(Image.fromarray(frame_rgb))
                    info_text = f"Frame: {f_idx}/{total_f} | Delay: {int(self.sim_state['play_delay']*1000)}ms"
                    self.after(0, lambda im=img_tk, txt=info_text: self._update_sim_ui(im, txt))
                    time.sleep(self.sim_state["play_delay"])

                f_idx += 1
                if f_idx % 30 == 0: self.after(0, lambda p=f_idx/total_f: self.progress_bar.set(p))
            
            cap.release()
            self.sim_state["active"] = False
            if self.sim_window: self.after(0, self.sim_window.destroy)
            
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

    def _open_sim_window(self):
        if self.sim_window is not None: return
        self.sim_window = ctk.CTkToplevel(self)
        self.sim_window.title("Simulation MIDIa (Tkinter)")
        self.sim_window.geometry("840x550")
        self.sim_window.protocol("WM_DELETE_WINDOW", self._on_sim_close)
        
        self.sim_info = ctk.CTkLabel(self.sim_window, text="[ESPACE] Pause | [A] Reculer | [D] Avancer | [W/S] Vitesse", font=ctk.CTkFont(weight="bold"))
        self.sim_info.pack(pady=5)
        
        self.sim_label = ctk.CTkLabel(self.sim_window, text="Chargement...", fg_color="black")
        self.sim_label.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.sim_window.bind("<space>", lambda e: self._sim_toggle_pause())
        self.sim_window.bind("p", lambda e: self._sim_toggle_pause())
        self.sim_window.bind("w", lambda e: self._sim_change_speed(-0.01))
        self.sim_window.bind("s", lambda e: self._sim_change_speed(0.01))
        self.sim_window.bind("a", lambda e: self._sim_seek(-150))
        self.sim_window.bind("d", lambda e: self._sim_seek(150))

    def _update_sim_ui(self, img_tk, info_text):
        if self.sim_label and self.sim_label.winfo_exists():
            self.sim_label.configure(image=img_tk)
            self.sim_label._image = img_tk
            if self.sim_info: self.sim_info.configure(text=f"[ESPACE] Pause | [A] -5s | [D] +5s | [W/S] Vitesse  ---  {info_text}")

    def _sim_toggle_pause(self):
        self.sim_state["paused"] = not self.sim_state["paused"]

    def _sim_change_speed(self, delta):
        self.sim_state["play_delay"] = max(0.001, min(1.0, self.sim_state["play_delay"] + delta))

    def _sim_seek(self, frames):
        self.sim_state["seek_frames"] = frames

    def _on_sim_close(self):
        self.sim_state["active"] = False
        self._close_sim_window()

    def _close_sim_window(self):
        if self.sim_window:
            self.sim_window.destroy()
            self.sim_window = None
            self.sim_label = None

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
            cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "piano_transcription_inference", "mido", "librosa", "opencv-python", "numpy", "pillow"]
            subprocess.check_call(cmd)
            messagebox.showinfo("Succès", "Prêt !")
        except Exception as e: messagebox.showerror("Erreur", str(e))

    def _update_status(self, msg): self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_success(self, p):
        self._set_ui_processing(False); self.status_label.configure(text="Terminé !")
        if messagebox.askyesno("Succès", f"Généré :\n{p}\n\nOuvrir ?"): os.startfile(os.path.dirname(p))

    def _on_error(self, err): self._set_ui_processing(False); self.status_label.configure(text="Erreur."); messagebox.showerror("Erreur", err)
