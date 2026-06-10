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
import time

# --- Configuration ---
GITHUB_USER = "EstebanZGL"
GITHUB_REPO = "Multi-Apps"
GITHUB_BRANCH = "builds"
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data"
MANIFEST_URL = f"{BASE_URL}/install_manifest.json"

# HackGPT Nextcloud Link
HACKGPT_LINK = "https://nxt.xavest-truenas.fr/s/xi7pwXsgiD3gM4F/download"

APP_NAME = "MultiversLauncher"
INSTALL_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
LOCAL_MANIFEST_FILE = os.path.join(INSTALL_DIR, "install_manifest.json")

class WebInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Multivers - Assistant d'Installation")
        self.geometry("700x650")
        ctk.set_appearance_mode("dark")

        # Persistence for HackGPT Task
        self.ai_task_active = False
        self.ai_progress_val = 0
        self.ai_status_msg = "Prêt."
        self.ai_cancel_requested = threading.Event()
        self.ai_win = None

        # Main Installer State
        self.manifest_data = None
        self.local_manifest = self._load_local_manifest()
        self.selected_apps = {}
        self.installation_mode = "install" 
        self.main_cancel_requested = threading.Event()

        self._build_ui()
        self._load_remote_manifest()
        
        # Handle Close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_local_manifest(self):
        if os.path.exists(LOCAL_MANIFEST_FILE):
            try:
                with open(LOCAL_MANIFEST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return None

    def _on_closing(self):
        if self.ai_task_active or self.main_cancel_requested.is_set(): # Simplified check
            if not messagebox.askyesno("Quitter", "Une opération est en cours. Voulez-vous vraiment annuler et quitter ?"):
                return
        
        self.ai_cancel_requested.set()
        self.main_cancel_requested.set()
        self.destroy()
        os._exit(0)

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

        # Mode Selection
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.local_manifest:
            self.mode_frame.pack(fill="x", padx=30, pady=5)
            self.mode_var = tk.StringVar(value="install")
            self.install_radio = ctk.CTkRadioButton(self.mode_frame, text="Mettre à jour / Réinstaller", variable=self.mode_var, value="install", command=lambda: self._set_mode("install"))
            self.install_radio.pack(side="left", padx=20)
            
            self.uninstall_radio = ctk.CTkRadioButton(self.mode_frame, text="Désinstaller tout", variable=self.mode_var, value="uninstall", command=lambda: self._set_mode("uninstall"))
            self.uninstall_radio.pack(side="left", padx=20)

        # Apps Frame
        self.apps_frame = ctk.CTkScrollableFrame(
            self, label_text="Composants disponibles",
            label_font=ctk.CTkFont(weight="bold", size=16),
            border_width=2, border_color="#333333"
        )
        self.apps_frame.pack(fill="both", expand=True, padx=30, pady=10)

        # Progress
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=30, pady=(10, 0))
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#00BFFF")
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Chargement du catalogue...", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=5)

        # Footer
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
                self.after(0, lambda: self.status_label.configure(text=f"Erreur catalogue: {e}"))
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
            if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer Multivers ?"):
                threading.Thread(target=self._uninstall_task, daemon=True).start()
        else:
            threading.Thread(target=self._installation_task, daemon=True).start()

    def _update_status(self, msg, progress):
        self.after(0, lambda: self.status_label.configure(text=msg))
        self.after(0, lambda: self.progress_bar.set(progress))

    def _download_and_extract(self, url, dest_dir, cancel_event):
        os.makedirs(dest_dir, exist_ok=True)
        temp_zip = os.path.join(dest_dir, "temp.zip")
        
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()

        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if cancel_event.is_set():
                    f.close()
                    os.remove(temp_zip)
                    raise Exception("Opération annulée par l'utilisateur.")
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        perc = (downloaded / total_size) * 100
                        speed = downloaded / (time.time() - start_time) / 1024 / 1024 # MB/s
                        eta = (total_size - downloaded) / (speed * 1024 * 1024) if speed > 0 else 0
                        self._update_status(f"Téléchargement... {perc:.1f}% ({speed:.1f} Mo/s) - reste {int(eta)}s", (downloaded/total_size)*0.8)

        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        os.remove(temp_zip)

    def _installation_task(self):
        try:
            self.action_btn.configure(state="disabled")
            self.main_cancel_requested.clear()
            os.makedirs(INSTALL_DIR, exist_ok=True)
            
            apps_to_install = [app for app in self.manifest_data['apps'] if self.selected_apps[app['id']].get()]
            downloader_selected = any(app['id'] == 'downloader' for app in apps_to_install)
            
            # Simplified flow for installer
            if 'core_zip' in self.manifest_data:
                self._update_status("Installation du moteur...", 0.1)
                self._download_and_extract(f"{BASE_URL}/{self.manifest_data['core_zip']}", INSTALL_DIR, self.main_cancel_requested)

            for app in apps_to_install:
                self._update_status(f"Module : {app['name']}...", 0.5)
                self._download_and_extract(f"{BASE_URL}/{app['zip_file']}", os.path.join(INSTALL_DIR, "apps", app['id']), self.main_cancel_requested)

            if downloader_selected and 'ffmpeg_zip' in self.manifest_data:
                self._update_status("FFmpeg...", 0.8)
                self._download_and_extract(f"{BASE_URL}/{self.manifest_data['ffmpeg_zip']}", os.path.join(INSTALL_DIR, "bin"), self.main_cancel_requested)

            self._create_shortcuts()
            with open(LOCAL_MANIFEST_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.manifest_data, f, indent=4)

            self._update_status("Installation terminée !", 1.0)
            self.after(0, lambda: messagebox.showinfo("Succès", "Installation terminée !"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
        finally:
            self.after(0, lambda: self.action_btn.configure(state="normal"))

    def _uninstall_task(self):
        try:
            self.action_btn.configure(state="disabled")
            if os.path.exists(INSTALL_DIR): shutil.rmtree(INSTALL_DIR)
            # Remove shortcuts
            for path in [os.path.join(os.environ["USERPROFILE"], "Desktop", "Multivers Launcher.lnk"),
                        os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Multivers Launcher.lnk")]:
                if os.path.exists(path): os.remove(path)
            self.after(0, lambda: messagebox.showinfo("Désinstallé", "Multivers a été supprimé."))
            self.after(0, self.destroy)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
        finally:
            self.after(0, lambda: self.action_btn.configure(state="normal"))

    def _manage_ai(self):
        if self.ai_win and self.ai_win.winfo_exists():
            self.ai_win.lift()
            return

        self.ai_win = ctk.CTkToplevel(self)
        self.ai_win.title("Gestionnaire HackGPT")
        self.ai_win.geometry("550x650")
        self.ai_win.attributes("-topmost", True)

        ctk.CTkLabel(self.ai_win, text="Assistant IA HackGPT", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=20)
        
        # Paths info
        temp_path = os.path.join(os.getenv('TEMP'), "HackGPT_Install")
        path_info = ctk.CTkLabel(self.ai_win, text=f"Chemin temporaire :\n{temp_path}", font=ctk.CTkFont(size=10), text_color="#888888")
        path_info.pack(pady=5)

        self.ollama_status_label = ctk.CTkLabel(self.ai_win, text="Vérification d'Ollama...")
        self.ollama_status_label.pack(pady=10)
        
        self.ai_status_label = ctk.CTkLabel(self.ai_win, text=self.ai_status_msg, wraplength=450)
        self.ai_status_label.pack(pady=10)

        self.ai_progress_bar = ctk.CTkProgressBar(self.ai_win, width=450)
        self.ai_progress_bar.pack(pady=10)
        self.ai_progress_bar.set(self.ai_progress_val)

        # Action Buttons
        self.ai_actions_frame = ctk.CTkFrame(self.ai_win, fg_color="transparent")
        self.ai_actions_frame.pack(pady=10, fill="x", padx=40)

        self.dl_ai_btn = ctk.CTkButton(self.ai_actions_frame, text="🚀 Installer HackGPT", fg_color="#6f42c1", command=self._start_hackgpt_install)
        self.dl_ai_btn.pack(side="left", expand=True, padx=5)

        self.rm_ai_btn = ctk.CTkButton(self.ai_actions_frame, text="🗑️ Supprimer HackGPT", fg_color="#dc3545", command=self._uninstall_hackgpt)
        self.rm_ai_btn.pack(side="left", expand=True, padx=5)

        self.cancel_ai_btn = ctk.CTkButton(self.ai_win, text="🛑 Annuler le téléchargement", fg_color="#555568", state="disabled", command=self._cancel_hackgpt)
        self.cancel_ai_btn.pack(pady=20)
        
        if self.ai_task_active:
            self.dl_ai_btn.configure(state="disabled")
            self.rm_ai_btn.configure(state="disabled")
            self.cancel_ai_btn.configure(state="normal")
        
        self._refresh_ai_ui_loop()
        threading.Thread(target=self._check_and_start_ollama, daemon=True).start()

    def _uninstall_hackgpt(self):
        if not messagebox.askyesno("Désinstallation", "Voulez-vous vraiment supprimer HackGPT d'Ollama ?"):
            return
        try:
            subprocess.run(["ollama", "rm", "HackGPT"], shell=True, check=True)
            messagebox.showinfo("Succès", "HackGPT a été supprimé avec succès.")
            self._check_and_start_ollama()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de supprimer le modèle : {e}")

    def _install_hackgpt_task(self):
        temp_dir = os.path.join(os.getenv('TEMP'), "HackGPT_Install")
        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            self.after(0, lambda: self.cancel_ai_btn.configure(state="normal"))

            # Download with Correct Progression
            self.ai_status_msg = "Connexion au serveur Nextcloud..."
            zip_path = os.path.join(temp_dir, "hackgpt.zip")
            
            # Using session for better header handling
            with requests.get(HACKGPT_LINK, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                start_time = time.time()

                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if self.ai_cancel_requested.is_set():
                            f.close()
                            raise Exception("Téléchargement annulé par l'utilisateur.")
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Calculation Fix
                            if total_size > 0:
                                self.ai_progress_val = (downloaded / total_size)
                                speed = downloaded / (time.time() - start_time) / 1024 / 1024 # MB/s
                                eta = (total_size - downloaded) / (speed * 1024 * 1024) if speed > 0.01 else 0
                                self.ai_status_msg = f"Téléchargement : {self.ai_progress_val*100:.1f}% ({speed:.1f} Mo/s)\nTemps restant : {int(eta)}s"
                            else:
                                self.ai_status_msg = f"Téléchargement en cours... ({downloaded/1024/1024:.1f} Mo reçus)"

            self.ai_status_msg = "Extraction des fichiers (5 Go)..."
            self.ai_progress_val = 0.95
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find manifest and model
            manifest_file = None
            work_dir = temp_dir
            for root, _, files in os.walk(temp_dir):
                if "manifest.json" in files:
                    manifest_file = os.path.join(root, "manifest.json")
                    work_dir = root
                    break
            
            if not manifest_file: raise Exception("Manifeste non trouvé dans l'archive.")
            
            # Find the model blob (the largest file)
            all_files = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if os.path.isfile(os.path.join(work_dir, f)) and f != "manifest.json"]
            model_blob = max(all_files, key=os.path.getsize)
            
            # Import into Ollama
            self.ai_status_msg = "Finalisation : Importation dans Ollama..."
            modelfile_path = os.path.join(work_dir, "Modelfile")
            with open(modelfile_path, 'w') as f:
                f.write(f"FROM {model_blob}\n")
                f.write('SYSTEM "You are HackGPT, a specialized AI for cybersecurity and coding."\n')

            subprocess.run(["ollama", "create", "HackGPT", "-f", modelfile_path], shell=True, capture_output=True, check=True)
            
            self.ai_status_msg = "HackGPT est installé avec succès !"
            self.ai_progress_val = 1.0
            self.after(0, lambda: messagebox.showinfo("Succès", "HackGPT est prêt dans Ollama !"))
            
        except Exception as e:
            self.ai_status_msg = f"Erreur : {e}"
            if not self.ai_cancel_requested.is_set():
                self.after(0, lambda: messagebox.showerror("Erreur IA", str(e)))
        finally:
            # CLEANUP EVERYTHING
            self._update_ai_status("Nettoyage des fichiers temporaires...", 1.0)
            if os.path.exists(temp_dir):
                try: shutil.rmtree(temp_dir)
                except: pass
            
            self.ai_task_active = False
            self.after(0, lambda: self.dl_ai_btn.configure(state="normal") if self.ai_win and self.ai_win.winfo_exists() else None)
            self.after(0, lambda: self.cancel_ai_btn.configure(state="disabled") if self.ai_win and self.ai_win.winfo_exists() else None)
            self.after(0, self._check_and_start_ollama)

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
