import os
import sys
import shutil
import threading
import urllib.request
import zipfile
import io
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

import requests
import yt_dlp
from PIL import Image

# Config paths (we might want to move these to a shared config later)
APP_DIR = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'YT_Universal_Converter')
APP_BIN_DIR = os.path.join(APP_DIR, 'bin')
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings: dict):
    os.makedirs(APP_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

class YTDLPLogger:
    def __init__(self, log_callback):
        self.log_callback = log_callback
    def debug(self, msg): pass
    def warning(self, msg):
        if "JavaScript runtime" in msg or "ffmpeg not found" in msg: return
        self.log_callback(f"⚠️ AVERTISSEMENT: {msg}")
    def error(self, msg):
        self.log_callback(f"❌ ERREUR: {msg}")

def parse_time_to_seconds(t_str: str):
    if not t_str or not t_str.strip(): return None
    parts = t_str.strip().split(':')
    try:
        if len(parts) == 3: return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
        elif len(parts) == 2: return float(parts[0])*60 + float(parts[1])
        elif len(parts) == 1: return float(parts[0])
    except ValueError: pass
    return None

def format_seconds_to_time(seconds: float):
    if seconds is None: return ""
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0: return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def get_platform_subfolder(url: str) -> str:
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u: return 'YouTube'
    if 'tiktok.com' in u: return 'TikTok'
    if 'instagram.com' in u: return 'Instagram'
    if 'pinterest.com' in u or 'pin.it' in u: return 'Pinterest'
    return 'Autres'

class DownloaderApp(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        settings = load_settings()
        saved_dir = settings.get("output_dir", os.path.expanduser("~\\Downloads"))
        
        self.output_dir = ctk.StringVar(value=saved_dir)
        self.url_var = ctk.StringVar()
        self.ext_var = ctk.StringVar(value="mp3")
        self.crop_start_var = ctk.StringVar()
        self.crop_end_var = ctk.StringVar()
        self.batch_urls = []
        self.batch_file_var = ctk.StringVar()
        self.playlist_mode = ctk.BooleanVar(value=False)
        
        self.is_downloading = False
        self.is_ready = False
        self.ffmpeg_path = None
        self.video_metadata = None
        self.video_duration = 0 
        self.preview_image_ref = None 

        # Deezer state
        self.deezer_mode = ctk.BooleanVar(value=False)
        self.deezer_url = settings.get("deezer_url", "https://www.deezer.com/fr/profile/me/mp3")

        self._build_ui()

        self.crop_start_var.trace_add("write", self._on_text_crop_change)
        self.crop_end_var.trace_add("write", self._on_text_crop_change)

        # Lazy load dependencies after UI is shown
        threading.Thread(target=self._resolve_dependencies, daemon=True).start()

    def _build_ui(self):
        # Header with Back Button
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        self.back_btn = ctk.CTkButton(
            header_frame, text="🏠 Menu", width=80, 
            command=lambda: self.controller.show_menu()
        )
        self.back_btn.pack(side="left")

        # Deezer Link Config Button
        self.deezer_config_btn = ctk.CTkButton(
            header_frame, text="⚙️ Lien Deezer", width=100,
            fg_color="#33334d", hover_color="#4d4d70",
            command=self._configure_deezer_url
        )
        self.deezer_config_btn.pack(side="right")

        self.title_label = ctk.CTkLabel(
            header_frame, text="Downloader Universel", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.pack(side="left", expand=True, padx=(0, 20))

        self.tabview = ctk.CTkTabview(self, segmented_button_selected_color="#E07A5F", segmented_button_unselected_hover_color="#3a3a50")
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(5, 10))

        tab_yt = self.tabview.add("📥 Vidéos & Musique")
        self._build_yt_ui(tab_yt)

        env_frame = ctk.CTkFrame(self, fg_color="transparent")
        env_frame.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(env_frame, text="Dossier :", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkEntry(env_frame, textvariable=self.output_dir, state="disabled", width=250).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(env_frame, text="Modifier", command=self._select_directory, width=80).pack(side="left")

    def _configure_deezer_url(self):
        dialog = ctk.CTkInputDialog(
            text="Collez le lien de votre page 'Mes MP3' Deezer :\n(Ex: https://www.deezer.com/fr/profile/.../personal_song)", 
            title="Lien Deezer"
        )
        url = dialog.get_input()
        
        if url is not None:
            if url.strip() == "":
                self.deezer_url = "https://www.deezer.com/fr/profile/me/mp3"
                self.log_message("ℹ️ Lien Deezer réinitialisé par défaut.")
            else:
                self.deezer_url = url.strip()
                self.log_message("✅ Lien Deezer sauvegardé.")
                
            settings = load_settings()
            settings["deezer_url"] = self.deezer_url
            save_settings(settings)

    def _build_yt_ui(self, parent):
        self.main_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.main_container.grid_columnconfigure(0, weight=3)
        self.main_container.grid_columnconfigure(1, weight=2)
        self.main_container.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_panel = ctk.CTkFrame(self.main_container)
        self.right_panel.grid(row=0, column=1, sticky="nsew")

        url_row = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        url_row.pack(fill="x", pady=(0, 5))
        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self.url_var,
            placeholder_text="URL (YouTube, TikTok, Instagram...)"
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.import_txt_btn = ctk.CTkButton(
            url_row, text="📂 .txt", width=70,
            fg_color="#555568", hover_color="#3a3a50",
            command=self._import_batch_file
        )
        self.import_txt_btn.pack(side="left")

        self.batch_label = ctk.CTkLabel(
            self.left_panel, text="", text_color="#7EC8E3",
            font=ctk.CTkFont(size=11, slant="italic")
        )
        self.batch_label.pack(anchor="w", pady=(0, 2))

        playlist_row = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        playlist_row.pack(fill="x", pady=(0, 5))
        self.playlist_checkbox = ctk.CTkCheckBox(
            playlist_row, text="🎵 Playlist",
            variable=self.playlist_mode, command=self._on_playlist_toggle
        )
        self.playlist_checkbox.pack(side="left")

        # Adding Deezer Checkbox
        deezer_row = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        deezer_row.pack(fill="x", pady=(0, 5))
        self.deezer_checkbox = ctk.CTkCheckBox(
            deezer_row, text="🎵 Envoyer vers Deezer (Mes MP3)",
            variable=self.deezer_mode
        )
        self.deezer_checkbox.pack(side="left")

        self.load_btn = ctk.CTkButton(self.left_panel, text="🔍 Charger l'Aperçu", fg_color="#E07A5F", hover_color="#D16043", command=self._start_preview_thread)
        self.load_btn.pack(pady=5)

        self.format_menu = ctk.CTkOptionMenu(
            self.left_panel, values=["mp3", "wav", "m4a", "flac", "mp4", "mkv", "webm"], variable=self.ext_var, width=200
        )
        self.format_menu.pack(anchor="w", pady=(5, 10))

        self.progress_bar = ctk.CTkProgressBar(self.left_panel)
        self.progress_bar.pack(fill="x", pady=(10, 5))
        self.progress_bar.set(0.0)

        self.log_textbox = ctk.CTkTextbox(self.left_panel, state="disabled", height=150)
        self.log_textbox.pack(fill="both", expand=True)

        self.download_button = ctk.CTkButton(self.left_panel, text="🔄 Initialisation...", font=ctk.CTkFont(weight="bold", size=15), height=40, state="disabled", command=self._start_download_thread)
        self.download_button.pack(fill="x", pady=10)

        # Panneau de droite
        self.img_label = ctk.CTkLabel(self.right_panel, text="[Pas d'aperçu]", height=150, fg_color="gray20", corner_radius=8)
        self.img_label.pack(pady=5, padx=10, fill="x")

        self.play_btn = ctk.CTkButton(self.right_panel, text="▶ Voir en ligne", width=120, fg_color="#2E8B57", hover_color="#1F5F3A", state="disabled", command=self._play_video_preview)
        self.play_btn.pack(pady=(0, 5))

        self.info_title = ctk.CTkLabel(self.right_panel, text="Titre: N/A", wraplength=250)
        self.info_title.pack(padx=10)
        
        crop_frame = ctk.CTkFrame(self.right_panel)
        crop_frame.pack(fill="x", padx=10, pady=5)
        
        val_frame = ctk.CTkFrame(crop_frame, fg_color="transparent")
        val_frame.pack(fill="x", padx=5, pady=5)
        
        self.entry_start = ctk.CTkEntry(val_frame, textvariable=self.crop_start_var, width=60, justify="center")
        self.entry_start.pack(side="left")
        self.entry_end = ctk.CTkEntry(val_frame, textvariable=self.crop_end_var, width=60, justify="center")
        self.entry_end.pack(side="right")

        self.slider_start = ctk.CTkSlider(crop_frame, from_=0, to=1, command=self._on_start_slide, state="disabled", button_color="#E07A5F", progress_color="gray30", fg_color="#E07A5F")
        self.slider_start.pack(fill="x", padx=5, pady=5)
        self.slider_end = ctk.CTkSlider(crop_frame, from_=0, to=1, command=self._on_end_slide, state="disabled", button_color="#E07A5F", progress_color="#E07A5F", fg_color="gray30")
        self.slider_end.pack(fill="x", padx=5, pady=5)

    def _import_batch_file(self):
        filepath = filedialog.askopenfilename(title="Sélectionner un fichier .txt", filetypes=[("Fichier texte", "*.txt")])
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                urls = [ln.strip() for ln in f.readlines() if ln.strip().startswith('http')]
            if not urls: return
            self.batch_urls = urls
            self.batch_file_var.set(filepath)
            self.url_var.set("")
            self.batch_label.configure(text=f"📋 Batch : {len(urls)} lien(s)")
            if self.is_ready: self.download_button.configure(state="normal")
        except Exception as e: self.log_message(f"❌ Erreur : {str(e)}")

    def _select_directory(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get())
        if d: 
            self.output_dir.set(d)
            settings = load_settings(); settings["output_dir"] = d; save_settings(settings)

    def _on_start_slide(self, value):
        if value >= self.slider_end.get(): self.slider_start.set(self.slider_end.get() - 1); value = self.slider_start.get()
        self.crop_start_var.set(format_seconds_to_time(value))

    def _on_end_slide(self, value):
        if value <= self.slider_start.get(): self.slider_end.set(self.slider_start.get() + 1); value = self.slider_end.get()
        self.crop_end_var.set(format_seconds_to_time(value))

    def _on_text_crop_change(self, *args):
        if not self.video_duration: return
        try:
            s_val = parse_time_to_seconds(self.crop_start_var.get())
            if s_val is not None: self.slider_start.set(s_val)
            e_val = parse_time_to_seconds(self.crop_end_var.get())
            if e_val is not None: self.slider_end.set(e_val)
        except: pass

    def log_message(self, message: str):
        def update_ui():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        self.after(0, update_ui)

    def _resolve_dependencies(self):
        # Logic from main.py simplified for lazy loading
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            self.ffmpeg_path = os.path.dirname(sys_ffmpeg)
            self._finalize_init()
            return

        appdata_ffmpeg = os.path.join(APP_BIN_DIR, "ffmpeg.exe")
        if os.path.exists(appdata_ffmpeg):
            self.ffmpeg_path = APP_BIN_DIR
            self._finalize_init()
            return

        self.log_message("⚙️ Dépendance FFmpeg manquante. Installation...")
        try:
            os.makedirs(APP_BIN_DIR, exist_ok=True)
            zip_path = os.path.join(APP_BIN_DIR, "ffm_deps.zip")
            urllib.request.urlretrieve(FFMPEG_URL, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for f_info in zip_ref.infolist():
                    if f_info.filename.endswith(('ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe')):
                        xp = zip_ref.extract(f_info, APP_BIN_DIR)
                        shutil.move(xp, os.path.join(APP_BIN_DIR, os.path.basename(xp)))
            os.remove(zip_path)
            self.ffmpeg_path = APP_BIN_DIR
            self._finalize_init()
        except Exception as e:
            self.log_message(f"❌ Erreur FFmpeg : {str(e)}")

    def _finalize_init(self):
        self.is_ready = True
        self.after(0, lambda: self.download_button.configure(text="📥 Télécharger", state="normal" if self.video_duration > 0 or self.batch_urls else "disabled"))
        self.log_message("✅ Système prêt.")

    def _on_playlist_toggle(self):
        state = "disabled" if self.playlist_mode.get() else "normal"
        self.slider_start.configure(state=state); self.slider_end.configure(state=state)
        self.entry_start.configure(state=state); self.entry_end.configure(state=state)

    def _start_preview_thread(self):
        url = self.url_var.get().strip()
        if not url: return
        self.load_btn.configure(state="disabled")
        threading.Thread(target=self._fetch_preview_task, args=(url,), daemon=True).start()

    def _play_video_preview(self):
        import webbrowser; webbrowser.open(self.url_var.get().strip())

    def _fetch_preview_task(self, url):
        logger = YTDLPLogger(self.log_message)
        opts = {'skip_download': True, 'quiet': True, 'noplaylist': not self.playlist_mode.get(), 'logger': logger}
        if self.ffmpeg_path: opts['ffmpeg_location'] = self.ffmpeg_path
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: info = ydl.extract_info(url, download=False)
            if not info: return
            
            if self.playlist_mode.get() and info.get('_type') == 'playlist':
                count = len(list(info.get('entries', [])))
                self.after(0, self._update_playlist_preview, info.get('title'), count)
                return

            self.video_metadata = info
            self.video_duration = int(info.get('duration', 0))
            img = None
            if info.get('thumbnail'):
                try:
                    resp = requests.get(info['thumbnail'], timeout=5)
                    raw_img = Image.open(io.BytesIO(resp.content))
                    img = ctk.CTkImage(light_image=raw_img, size=(250, 140))
                except: pass
            self.after(0, self._update_preview_ui, info.get('title'), img)
        except Exception as e: self.log_message(f"❌ Erreur : {str(e)}")
        finally: self.after(0, lambda: self.load_btn.configure(state="normal"))

    def _update_playlist_preview(self, title, count):
        self.info_title.configure(text=f"📋 {title} ({count} vidéos)")
        self.img_label.configure(image=None, text="Playlist")
        self.download_button.configure(state="normal")

    def _update_preview_ui(self, title, img):
        self.info_title.configure(text=f"Titre: {title}")
        if img: self.preview_image_ref = img; self.img_label.configure(image=img, text="")
        if self.video_duration > 0:
            self.slider_start.configure(state="normal", from_=0, to=self.video_duration); self.slider_start.set(0)
            self.slider_end.configure(state="normal", from_=0, to=self.video_duration); self.slider_end.set(self.video_duration)
            self.crop_start_var.set("00:00"); self.crop_end_var.set(format_seconds_to_time(self.video_duration))
        self.download_button.configure(state="normal"); self.play_btn.configure(state="normal")

    def _start_download_thread(self):
        out = self.output_dir.get().strip(); ext = self.ext_var.get()
        if self.batch_urls:
            self.download_button.configure(state="disabled"); self.progress_bar.set(0.0)
            threading.Thread(target=self._download_batch_task, args=(list(self.batch_urls), out, ext), daemon=True).start()
        else:
            url = self.url_var.get().strip()
            if not url: return
            self.download_button.configure(state="disabled"); self.progress_bar.set(0.0)
            s = parse_time_to_seconds(self.crop_start_var.get()); e = parse_time_to_seconds(self.crop_end_var.get())
            threading.Thread(target=self._download_task, args=(url, out, ext, s, e), daemon=True).start()

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                import re
                p = float(re.sub(r'\x1b\[.*?m', '', d.get('_percent_str', '0%')).replace('%', '')) / 100.0
                self.after(0, lambda: self.progress_bar.set(p))
            except: pass

    def _get_ydl_opts(self, output, ext, logger, hook, is_playlist, s=None, e=None):
        is_audio = ext in ['mp3', 'wav', 'm4a', 'flac']
        opts = {
            'outtmpl': os.path.join(output, '%(title)s.%(ext)s'),
            'logger': logger, 'progress_hooks': [hook], 'noplaylist': not is_playlist,
            'writethumbnail': True, 'ignoreerrors': True
        }
        if self.ffmpeg_path: opts['ffmpeg_location'] = self.ffmpeg_path
        if not is_playlist and ((s and s > 0) or (e and self.video_duration and e < self.video_duration)):
            opts['download_ranges'] = lambda info, ydl: [{'start_time': s or 0, 'end_time': e or float('inf')}]
        if is_audio:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': ext, 'preferredquality': '0'}, {'key': 'EmbedThumbnail'}, {'key': 'FFmpegMetadata'}]
        else:
            opts['format'] = f'bestvideo[ext={ext}]+bestaudio/best/best'
            opts['merge_output_format'] = ext
            opts['postprocessors'] = [{'key': 'EmbedThumbnail'}, {'key': 'FFmpegMetadata'}]
        return opts

    def _download_batch_task(self, urls, out, ext):
        logger = YTDLPLogger(self.log_message)
        for i, url in enumerate(urls, 1):
            sub = get_platform_subfolder(url); final = os.path.join(out, sub); os.makedirs(final, exist_ok=True)
            self.log_message(f"⬇️ [{i}/{len(urls)}] {url[:50]}...")
            opts = self._get_ydl_opts(final, ext, logger, self._progress_hook, False)
            
            filepath = None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filepath = ydl.prepare_filename(info)
                    if ext in ['mp3', 'wav', 'm4a', 'flac']:
                        filepath = os.path.splitext(filepath)[0] + "." + ext
            except Exception as e: self.log_message(f"❌ Erreur: {str(e)}")
        self.after(0, self._on_complete)

    def _download_task(self, url, out, ext, s, e):
        logger = YTDLPLogger(self.log_message); is_p = self.playlist_mode.get()
        sub = get_platform_subfolder(url); final = os.path.join(out, sub); os.makedirs(final, exist_ok=True)
        opts = self._get_ydl_opts(final, ext, logger, self._progress_hook, is_p, s, e)
        
        filepath = None
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if '_type' not in info:
                    filepath = ydl.prepare_filename(info)
                    if ext in ['mp3', 'wav', 'm4a', 'flac']:
                        filepath = os.path.splitext(filepath)[0] + "." + ext
            self.log_message("🎉 Terminé !")
        except Exception as e: self.log_message(f"❌ Erreur: {str(e)}")
        finally: self.after(0, lambda: self._on_complete(filepath))

    def _on_complete(self, filepath=None):
        self.download_button.configure(state="normal"); self.progress_bar.set(1.0)
        
        # Semi-automatic Deezer workflow
        if self.deezer_mode.get() and filepath and filepath.lower().endswith(".mp3"):
            self.log_message("🎵 Ouverture de Deezer et du dossier pour glisser-déposer...")
            
            # 1. Open the folder containing the file
            folder_path = os.path.dirname(filepath)
            try:
                if os.name == 'nt':
                    # On Windows, we can select the file in Explorer
                    import subprocess
                    subprocess.run(f'explorer /select,"{os.path.normpath(filepath)}"')
                else:
                    import webbrowser
                    webbrowser.open(folder_path)
            except Exception as e:
                self.log_message(f"⚠️ Impossible d'ouvrir le dossier: {e}")
            
            # 2. Open Deezer My MP3s page
            try:
                import webbrowser
                webbrowser.open(self.deezer_url)
            except Exception as e:
                self.log_message(f"⚠️ Impossible d'ouvrir Deezer: {e}")
