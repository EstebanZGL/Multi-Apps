import os
import sys
import json
import requests
import zipfile
import shutil
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# --- Configuration ---
GITHUB_USER = "EstebanZGL"
GITHUB_REPO = "Multi-Apps"
GITHUB_BRANCH = "builds"
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data"
MANIFEST_URL = f"{BASE_URL}/install_manifest.json"

APP_NAME = "MultiversLauncher"
INSTALL_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
LOCAL_VERSION_FILE = os.path.join(INSTALL_DIR, "versions.json")

class WebInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Multivers - Web Installer")
        self.geometry("600x500")
        ctk.set_appearance_mode("dark")

        self.manifest_data = None
        self.selected_apps = {}
        self.install_progress = {}

        self._build_ui()
        self._load_remote_manifest()

    def _build_ui(self):
        # Header
        self.header = ctk.CTkLabel(
            self, text="🚀 Multivers - Assistant d'Installation", 
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#00BFFF"
        )
        self.header.pack(pady=(30, 10))

        self.status_label = ctk.CTkLabel(
            self, text="Connexion aux serveurs GitHub...", 
            font=ctk.CTkFont(slant="italic", size=14)
        )
        self.status_label.pack(pady=(0, 15))

        # Scrollable area for apps
        self.apps_frame = ctk.CTkScrollableFrame(
            self, label_text="Sélectionnez les modules à installer",
            label_font=ctk.CTkFont(weight="bold", size=16),
            border_width=2, border_color="#333333"
        )
        self.apps_frame.pack(fill="both", expand=True, padx=30, pady=10)

        # Progress bar
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=30, pady=(10, 0))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#00BFFF")
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        # Footer Buttons
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=30, pady=20)

        self.install_btn = ctk.CTkButton(
            self.footer, text="Démarrer l'installation", 
            state="disabled", command=self._start_installation,
            font=ctk.CTkFont(weight="bold", size=15),
            fg_color="#28a745", hover_color="#218838",
            height=40
        )
        self.install_btn.pack(side="right")

        self.ollama_btn = ctk.CTkButton(
            self.footer, text="🔍 Diagnostiquer Ollama", 
            fg_color="#555568", hover_color="#444455",
            command=self._check_ollama,
            height=40
        )
        self.ollama_btn.pack(side="left")

    def _load_remote_manifest(self):
        def task():
            try:
                response = requests.get(MANIFEST_URL, timeout=10)
                response.raise_for_status()
                self.manifest_data = response.json()
                self.after(0, self._populate_apps)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de charger le manifest : {e}"))
        
        threading.Thread(target=task, daemon=True).start()

    def _populate_apps(self):
        self.status_label.configure(text=f"Version du catalogue : {self.manifest_data.get('version', '1.0.0')}")
        
        for app in self.manifest_data.get("apps", []):
            var = tk.BooleanVar(value=True)
            self.selected_apps[app['id']] = var
            
            # Application Card
            app_card = ctk.CTkFrame(self.apps_frame, fg_color="#2b2b2b", corner_radius=8)
            app_card.pack(fill="x", pady=5, padx=5)
            
            cb = ctk.CTkCheckBox(
                app_card, 
                text=f"{app['icon_text']} {app['name']}", 
                font=ctk.CTkFont(weight="bold", size=15),
                variable=var,
                fg_color="#00BFFF"
            )
            cb.pack(anchor="w", padx=15, pady=(10, 0))
            
            desc = ctk.CTkLabel(
                app_card, text=app['description'], 
                font=ctk.CTkFont(size=12), text_color="#aaaaaa",
                justify="left", wraplength=450
            )
            desc.pack(anchor="w", padx=45, pady=(0, 10))

        self.install_btn.configure(state="normal")

    def _check_ollama(self):
        import subprocess
        try:
            # Try to run ollama --version
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=True)
            messagebox.showinfo("Ollama", f"Ollama est installé !\nVersion : {result.stdout.strip()}")
        except:
            if messagebox.askyesno("Ollama", "Ollama n'a pas été détecté. Souhaitez-vous ouvrir la page de téléchargement ?"):
                import webbrowser
                webbrowser.open("https://ollama.com/download")

    def _start_installation(self):
        self.install_btn.configure(state="disabled")
        threading.Thread(target=self._installation_task, daemon=True).start()

    def _installation_task(self):
        try:
            os.makedirs(INSTALL_DIR, exist_ok=True)
            apps_to_install = [app for app in self.manifest_data['apps'] if self.selected_apps[app['id']].get()]
            
            # Step calculation: Core + Apps + FFmpeg (optional) + Shortcut
            downloader_selected = any(app['id'] == 'downloader' for app in apps_to_install)
            has_ffmpeg = 'ffmpeg_zip' in self.manifest_data
            
            total_steps = (1 if 'core_zip' in self.manifest_data else 0) + \
                          len(apps_to_install) + \
                          (1 if (downloader_selected and has_ffmpeg) else 0) + 1
            current_step = 0

            # 1. Install Core if necessary
            if 'core_zip' in self.manifest_data:
                self._log("Téléchargement du moteur principal (Core)...")
                core_zip_url = f"{BASE_URL}/{self.manifest_data['core_zip']}"
                core_zip_path = os.path.join(INSTALL_DIR, "core.zip")
                self._download_file(core_zip_url, core_zip_path)
                
                self._log("Extraction du moteur principal...")
                with zipfile.ZipFile(core_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(INSTALL_DIR)
                os.remove(core_zip_path)
                current_step += 1
                self.after(0, lambda p=current_step/total_steps: self.progress_bar.set(p))

            # 2. Install Apps
            for app in apps_to_install:
                self._log(f"Téléchargement de {app['name']}...")
                zip_url = f"{BASE_URL}/{app['zip_file']}"
                zip_path = os.path.join(INSTALL_DIR, f"{app['id']}.zip")
                self._download_file(zip_url, zip_path)
                
                self._log(f"Extraction de {app['name']}...")
                app_dir = os.path.join(INSTALL_DIR, "apps", app['id'])
                if os.path.exists(app_dir): shutil.rmtree(app_dir)
                os.makedirs(app_dir, exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(app_dir)
                os.remove(zip_path)
                current_step += 1
                self.after(0, lambda p=current_step/total_steps: self.progress_bar.set(p))

            # 3. Install FFmpeg if needed
            if downloader_selected and has_ffmpeg:
                self._log("Téléchargement des outils multimédia (FFmpeg)...")
                ff_url = f"{BASE_URL}/{self.manifest_data['ffmpeg_zip']}"
                ff_zip_path = os.path.join(INSTALL_DIR, "ffmpeg.zip")
                self._download_file(ff_url, ff_zip_path)
                
                self._log("Extraction de FFmpeg...")
                bin_dir = os.path.join(INSTALL_DIR, "bin")
                os.makedirs(bin_dir, exist_ok=True)
                with zipfile.ZipFile(ff_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(bin_dir)
                os.remove(ff_zip_path)
                current_step += 1
                self.after(0, lambda p=current_step/total_steps: self.progress_bar.set(p))

            self._log("Création des raccourcis...")
            self._create_shortcuts()
            
            self.after(0, lambda: messagebox.showinfo("Succès", "Installation terminée avec succès !"))
            self.after(0, self.destroy)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur d'installation", str(e)))
            self.after(0, lambda: self.install_btn.configure(state="normal"))

    def _download_file(self, url, dest_path):
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    def _log(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _create_shortcuts(self):
        import subprocess
        exe_path = os.path.join(INSTALL_DIR, "Launcher_Universel.exe")
        if not os.path.exists(exe_path):
            return

        # Desktop Shortcut
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        shortcut_path = os.path.join(desktop, "Multivers Launcher.lnk")
        
        # Start Menu Shortcut
        start_menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
        start_shortcut = os.path.join(start_menu, "Multivers Launcher.lnk")

        powershell_cmd = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
        $Shortcut.TargetPath = '{exe_path}'
        $Shortcut.WorkingDirectory = '{INSTALL_DIR}'
        $Shortcut.IconLocation = '{exe_path},0'
        $Shortcut.Save()
        
        $ShortcutStart = $WshShell.CreateShortcut('{start_shortcut}')
        $ShortcutStart.TargetPath = '{exe_path}'
        $ShortcutStart.WorkingDirectory = '{INSTALL_DIR}'
        $ShortcutStart.IconLocation = '{exe_path},0'
        $ShortcutStart.Save()
        """
        
        subprocess.run(["powershell", "-Command", powershell_cmd], capture_output=True)

if __name__ == "__main__":
    app = WebInstaller()
    app.mainloop()
