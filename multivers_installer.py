import os
import sys
import json
import requests
import zipfile
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import webbrowser

# --- Configuration ---
GITHUB_USER = "EstebanZGL"
GITHUB_REPO = "Multi-Apps"
GITHUB_BRANCH = "builds"
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data"
MANIFEST_URL = f"{BASE_URL}/install_manifest.json"

# HackGPT Nextcloud Link (Direct ZIP download if possible)
HACKGPT_LINK = "https://nxt.xavest-truenas.fr/s/xi7pwXsgiD3gM4F/download"

APP_NAME = "MultiversLauncher"
INSTALL_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
LOCAL_MANIFEST_FILE = os.path.join(INSTALL_DIR, "install_manifest.json")

class WebInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Multivers - Assistant d'Installation")
        self.geometry("700x600")
        ctk.set_appearance_mode("dark")

        self.manifest_data = None
        self.local_manifest = self._load_local_manifest()
        self.selected_apps = {}
        self.installation_mode = "install" # install, update, uninstall

        self._build_ui()
        self._load_remote_manifest()

    def _load_local_manifest(self):
        if os.path.exists(LOCAL_MANIFEST_FILE):
            try:
                with open(LOCAL_MANIFEST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return None

    def _build_ui(self):
        # Header
        self.header = ctk.CTkLabel(
            self, text="🚀 Multivers Suite", 
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00BFFF"
        )
        self.header.pack(pady=(30, 5))

        self.version_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(slant="italic"))
        self.version_label.pack(pady=(0, 10))

        # Mode Selection (if already installed)
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.local_manifest:
            self.mode_frame.pack(fill="x", padx=30, pady=5)
            self.install_radio = ctk.CTkRadioButton(self.mode_frame, text="Mettre à jour / Réinstaller", variable=tk.StringVar(value="install"), value="install", command=lambda: self._set_mode("install"))
            self.install_radio.pack(side="left", padx=20)
            self.install_radio.select()
            
            self.uninstall_radio = ctk.CTkRadioButton(self.mode_frame, text="Désinstaller tout", variable=tk.StringVar(value="install"), value="uninstall", command=lambda: self._set_mode("uninstall"))
            self.uninstall_radio.pack(side="left", padx=20)

        # Scrollable area for apps
        self.apps_frame = ctk.CTkScrollableFrame(
            self, label_text="Composants disponibles",
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

        self.status_label = ctk.CTkLabel(self, text="Chargement...", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=5)

        # Footer Buttons
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=30, pady=20)

        self.action_btn = ctk.CTkButton(
            self.footer, text="Démarrer l'installation", 
            state="disabled", command=self._handle_action,
            font=ctk.CTkFont(weight="bold", size=15),
            fg_color="#28a745", hover_color="#218838", height=45
        )
        self.action_btn.pack(side="right", padx=5)

        self.ai_btn = ctk.CTkButton(
            self.footer, text="🧠 Gérer HackGPT", 
            fg_color="#6f42c1", hover_color="#59359a",
            command=self._manage_ai, height=45
        )
        self.ai_btn.pack(side="left", padx=5)

    def _set_mode(self, mode):
        self.installation_mode = mode
        if mode == "uninstall":
            self.action_btn.configure(text="Désinstaller Multivers", fg_color="#dc3545", hover_color="#a71d2a")
        else:
            self.action_btn.configure(text="Démarrer l'installation", fg_color="#28a745", hover_color="#218838")

    def _load_remote_manifest(self):
        def task():
            try:
                response = requests.get(MANIFEST_URL, timeout=10)
                response.raise_for_status()
                self.manifest_data = response.json()
                self.after(0, self._populate_apps)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erreur", f"Erreur de connexion : {e}"))
        threading.Thread(target=task, daemon=True).start()

    def _populate_apps(self):
        v_remote = self.manifest_data.get('version', '1.0.0')
        v_local = self.local_manifest.get('version', 'Aucune') if self.local_manifest else "Aucune"
        self.version_label.configure(text=f"Version Cloud : v{v_remote} | Installée : {v_local}")
        
        for app in self.manifest_data.get("apps", []):
            var = tk.BooleanVar(value=True)
            self.selected_apps[app['id']] = var
            
            card = ctk.CTkFrame(self.apps_frame, fg_color="#2b2b2b", corner_radius=8)
            card.pack(fill="x", pady=5, padx=5)
            
            cb = ctk.CTkCheckBox(card, text=f"{app['icon_text']} {app['name']}", variable=var, font=ctk.CTkFont(weight="bold"))
            cb.pack(anchor="w", padx=15, pady=(10, 0))
            
            desc = ctk.CTkLabel(card, text=app['description'], font=ctk.CTkFont(size=11), text_color="#aaaaaa", justify="left")
            desc.pack(anchor="w", padx=45, pady=(0, 10))

        self.action_btn.configure(state="normal")
        self.status_label.configure(text="Prêt.")

    def _handle_action(self):
        if self.installation_mode == "uninstall":
            if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer Multivers et toutes ses applications ?"):
                threading.Thread(target=self._uninstall_task, daemon=True).start()
        else:
            threading.Thread(target=self._installation_task, daemon=True).start()

    def _installation_task(self):
        try:
            self.action_btn.configure(state="disabled")
            os.makedirs(INSTALL_DIR, exist_ok=True)
            
            apps_to_install = [app for app in self.manifest_data['apps'] if self.selected_apps[app['id']].get()]
            downloader_selected = any(app['id'] == 'downloader' for app in apps_to_install)
            
            total = (1 if 'core_zip' in self.manifest_data else 0) + len(apps_to_install) + (1 if downloader_selected else 0) + 1
            current = 0

            # 1. Core
            if 'core_zip' in self.manifest_data:
                self._update_status("Installation du moteur principal...", current/total)
                self._download_and_extract(f"{BASE_URL}/{self.manifest_data['core_zip']}", INSTALL_DIR)
                current += 1

            # 2. Apps
            for app in apps_to_install:
                self._update_status(f"Module : {app['name']}...", current/total)
                app_path = os.path.join(INSTALL_DIR, "apps", app['id'])
                self._download_and_extract(f"{BASE_URL}/{app['zip_file']}", app_path)
                current += 1

            # 3. FFmpeg
            if downloader_selected and 'ffmpeg_zip' in self.manifest_data:
                self._update_status("Outils Multimédia (FFmpeg)...", current/total)
                self._download_and_extract(f"{BASE_URL}/{self.manifest_data['ffmpeg_zip']}", os.path.join(INSTALL_DIR, "bin"))
                current += 1

            # 4. Finalize
            self._update_status("Raccourcis Windows...", current/total)
            self._create_shortcuts()
            
            # Save manifest locally
            with open(LOCAL_MANIFEST_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.manifest_data, f, indent=4)

            self.after(0, lambda: messagebox.showinfo("Succès", "Multivers est prêt !"))
            self.after(0, self.destroy)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
        finally:
            self.after(0, lambda: self.action_btn.configure(state="normal"))

    def _uninstall_task(self):
        try:
            self.action_btn.configure(state="disabled")
            self._update_status("Suppression des fichiers...", 0.5)
            if os.path.exists(INSTALL_DIR):
                shutil.rmtree(INSTALL_DIR)
            # Remove shortcuts
            for path in [os.path.join(os.environ["USERPROFILE"], "Desktop", "Multivers Launcher.lnk"),
                        os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Multivers Launcher.lnk")]:
                if os.path.exists(path): os.remove(path)
            
            self.after(0, lambda: messagebox.showinfo("Désinstallé", "Multivers a été retiré de votre ordinateur."))
            self.after(0, self.destroy)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
        finally:
            self.after(0, lambda: self.action_btn.configure(state="normal"))

    def _manage_ai(self):
        # AI Management Window
        ai_win = ctk.CTkToplevel(self)
        ai_win.title("Gestionnaire IA - HackGPT")
        ai_win.geometry("500x400")
        ai_win.attributes("-topmost", True)

        ctk.CTkLabel(ai_win, text="Assistant IA HackGPT", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        
        # Check Ollama
        try:
            res = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
            status = f"Ollama détecté : {res.stdout.strip()}"
            color = "#28a745"
        except:
            status = "Ollama n'est pas installé sur ce PC."
            color = "#dc3545"
        
        ctk.CTkLabel(ai_win, text=status, text_color=color).pack(pady=10)

        ctk.CTkButton(ai_win, text="Télécharger Ollama", command=lambda: webbrowser.open("https://ollama.com")).pack(pady=5)
        
        ctk.CTkLabel(ai_win, text="HackGPT est un modèle optimisé pour la cybersécurité.", font=ctk.CTkFont(size=12), wraplength=400).pack(pady=20)
        
        dl_btn = ctk.CTkButton(ai_win, text="🚀 Télécharger HackGPT (5 Go)", fg_color="#6f42c1", 
                               command=lambda: self._download_hackgpt())
        dl_btn.pack(pady=10)

    def _download_hackgpt(self):
        if messagebox.askyesno("Téléchargement", "Le modèle HackGPT pèse environ 5 Go. Voulez-vous lancer le téléchargement dans votre navigateur ?"):
            webbrowser.open(HACKGPT_LINK)
            messagebox.showinfo("Info", "Une fois le fichier téléchargé, placez-le dans votre dossier Ollama ou utilisez 'ollama create' avec le Modelfile fourni.")

    def _download_and_extract(self, url, dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
        temp_zip = os.path.join(dest_dir, "temp.zip")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(temp_zip, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        os.remove(temp_zip)

    def _update_status(self, msg, progress):
        self.after(0, lambda: self.status_label.configure(text=msg))
        self.after(0, lambda: self.progress_bar.set(progress))

    def _create_shortcuts(self):
        exe_path = os.path.join(INSTALL_DIR, "Launcher_Universel.exe")
        if not os.path.exists(exe_path): return
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop", "Multivers Launcher.lnk")
        start = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Multivers Launcher.lnk")
        
        cmd = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{desktop}');$s.TargetPath='{exe_path}';$s.WorkingDirectory='{INSTALL_DIR}';$s.Save();"
        cmd += f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{start}');$s.TargetPath='{exe_path}';$s.WorkingDirectory='{INSTALL_DIR}';$s.Save();"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)

if __name__ == "__main__":
    WebInstaller().mainloop()
