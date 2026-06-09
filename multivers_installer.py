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
        self.header = ctk.CTkLabel(self, text="Multivers Launcher", font=ctk.CTkFont(size=24, weight="bold"))
        self.header.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="Récupération des informations depuis GitHub...", font=ctk.CTkFont(slant="italic"))
        self.status_label.pack(pady=5)

        # Scrollable area for apps
        self.apps_frame = ctk.CTkScrollableFrame(self, label_text="Sélectionnez les applications à installer")
        self.apps_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        self.progress_bar.set(0)

        # Footer Buttons
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=20, pady=20)

        self.install_btn = ctk.CTkButton(self.footer, text="Démarrer l'installation", state="disabled", command=self._start_installation)
        self.install_btn.pack(side="right")

        self.ollama_btn = ctk.CTkButton(self.footer, text="🔍 Vérifier Ollama", fg_color="#555568", command=self._check_ollama)
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
        self.status_label.configure(text=f"Version de l'installateur : {self.manifest_data.get('version', 'Unknown')}")
        
        for app in self.manifest_data.get("apps", []):
            var = tk.BooleanVar(value=True)
            self.selected_apps[app['id']] = var
            
            cb = ctk.CTkCheckBox(self.apps_frame, text=f"{app['icon_text']} {app['name']} - {app['description']}", variable=var)
            cb.pack(anchor="w", padx=10, pady=5)

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
            
            total_steps = len(apps_to_install) + 1 # +1 for core/finalization
            current_step = 0

            for app in apps_to_install:
                self._log(f"Téléchargement de {app['name']}...")
                zip_url = f"{BASE_URL}/{app['zip_file']}"
                zip_path = os.path.join(INSTALL_DIR, f"{app['id']}.zip")
                
                # Download
                r = requests.get(zip_url, stream=True)
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract
                self._log(f"Extraction de {app['name']}...")
                app_dir = os.path.join(INSTALL_DIR, "apps", app['id'])
                if os.path.exists(app_dir): shutil.rmtree(app_dir)
                os.makedirs(app_dir, exist_ok=True)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(app_dir)
                
                os.remove(zip_path)
                current_step += 1
                self.after(0, lambda p=current_step/total_steps: self.progress_bar.set(p))

            self._log("Finalisation de l'installation...")
            # Here we would create shortcuts, etc.
            self._create_shortcuts()
            
            self.after(0, lambda: messagebox.showinfo("Succès", "Installation terminée avec succès !"))
            self.after(0, self.destroy)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur d'installation", str(e)))
            self.after(0, lambda: self.install_btn.configure(state="normal"))

    def _log(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _create_shortcuts(self):
        # Basic Windows Shortcut logic could go here
        # (Requires winshell or similar, or just a .bat/powershell command)
        pass

if __name__ == "__main__":
    app = WebInstaller()
    app.mainloop()
