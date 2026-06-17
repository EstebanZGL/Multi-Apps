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

# Official FFmpeg (Gyan.dev)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

APP_NAME = "MultiversLauncher"
INSTALL_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
LOCAL_MANIFEST_FILE = os.path.join(INSTALL_DIR, "install_manifest.json")

class WebInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Multivers - Assistant d'Installation")
        self.geometry("700x700")
        ctk.set_appearance_mode("dark")

        # Global States
        self.ai_task_active = False
        self.ai_progress_val = 0
        self.ai_status_msg = "Prêt."
        self.ai_cancel_requested = threading.Event()
        self.main_cancel_requested = threading.Event()
        self.ollama_installed = False

        self.manifest_data = None
        self.local_manifest = self._load_local_manifest()
        self.selected_apps = {}
        self.installation_mode = "install"

        self._build_ui()
        self._load_remote_manifest()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_local_manifest(self):
        if os.path.exists(LOCAL_MANIFEST_FILE):
            try:
                with open(LOCAL_MANIFEST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return None

    def _on_closing(self):
        if self.ai_task_active or self.main_cancel_requested.is_set():
            if not messagebox.askyesno("Quitter", "Opération en cours. Quitter quand même ?"):
                return
        self.ai_cancel_requested.set()
        self.main_cancel_requested.set()
        self.destroy()
        os._exit(0)

    def _build_ui(self):
        # Header
        self.header = ctk.CTkLabel(self, text="🚀 Multivers Suite", font=ctk.CTkFont(size=28, weight="bold"), text_color="#00BFFF")
        self.header.pack(pady=(30, 5))

        self.version_label = ctk.CTkLabel(self, text="Chargement...", font=ctk.CTkFont(slant="italic"))
        self.version_label.pack(pady=(0, 10))

        # Clickable Link
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(pady=5)
        ctk.CTkLabel(path_frame, text="Dossier d'installation : ", font=ctk.CTkFont(size=10)).pack(side="left")
        self.path_link = ctk.CTkLabel(path_frame, text=INSTALL_DIR, font=ctk.CTkFont(size=10, underline=True), text_color="#00BFFF", cursor="hand2")
        self.path_link.pack(side="left")
        self.path_link.bind("<Button-1>", lambda e: os.startfile(INSTALL_DIR) if os.path.exists(INSTALL_DIR) else None)

        # Mode Selection
        self.mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.local_manifest:
            self.mode_frame.pack(fill="x", padx=30, pady=5)
            self.mode_var = tk.StringVar(value="install")
            ctk.CTkRadioButton(self.mode_frame, text="Mise à jour", variable=self.mode_var, value="install", command=lambda: self._set_mode("install")).pack(side="left", padx=20)
            ctk.CTkRadioButton(self.mode_frame, text="Désinstaller", variable=self.mode_var, value="uninstall", command=lambda: self._set_mode("uninstall")).pack(side="left", padx=20)

        # Apps
        self.apps_frame = ctk.CTkScrollableFrame(self, label_text="Composants", border_width=2, border_color="#333333")
        self.apps_frame.pack(fill="both", expand=True, padx=30, pady=10)

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self, progress_color="#00BFFF")
        self.progress_bar.pack(fill="x", padx=30, pady=(10, 0))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Prêt.", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=5)

        # Footer
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=30, pady=20)

        self.action_btn = ctk.CTkButton(self.footer, text="Démarrer l'installation", state="disabled", command=self._handle_action, fg_color="#28a745", height=45)
        self.action_btn.pack(side="right", padx=5)

        self.cancel_main_btn = ctk.CTkButton(self.footer, text="🛑 Annuler", state="disabled", command=lambda: self.main_cancel_requested.set(), fg_color="#555568", height=45)
        self.cancel_main_btn.pack(side="right", padx=5)

        self.ai_btn = ctk.CTkButton(self.footer, text="🧠 Gérer HackGPT", fg_color="#6f42c1", command=self._manage_ai, height=45)
        self.ai_btn.pack(side="left", padx=5)

    def _set_mode(self, mode):
        self.installation_mode = mode
        self.action_btn.configure(text="Désinstaller" if mode == "uninstall" else "Démarrer l'installation", fg_color="#dc3545" if mode == "uninstall" else "#28a745")

    def _load_remote_manifest(self):
        def task():
            try:
                r = requests.get(MANIFEST_URL, timeout=10)
                r.raise_for_status()
                self.manifest_data = r.json()
                self.after(0, self._populate_apps)
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(text=f"Erreur catalogue: {e}"))
        threading.Thread(target=task, daemon=True).start()

    def _populate_apps(self):
        if not self.manifest_data: return
        v_cloud = self.manifest_data.get('version', '1.0.0')
        v_local = self.local_manifest.get('version', 'Aucune') if self.local_manifest else "Aucune"
        self.version_label.configure(text=f"Version Cloud : v{v_cloud} | Installée : {v_local}")
        for app in self.manifest_data.get("apps", []):
            var = tk.BooleanVar(value=True)
            self.selected_apps[app['id']] = var
            card = ctk.CTkFrame(self.apps_frame, fg_color="#2b2b2b", corner_radius=8)
            card.pack(fill="x", pady=5, padx=5)
            ctk.CTkCheckBox(card, text=f"{app['icon_text']} {app['name']}", variable=var, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
            ctk.CTkLabel(card, text=app['description'], font=ctk.CTkFont(size=11), text_color="#aaaaaa", justify="left").pack(anchor="w", padx=45, pady=(0, 10))
        self.action_btn.configure(state="normal")

    def _download_file(self, url, dest_path, cancel_event, update_func):
        """High performance download logic."""
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024): # 1MB Chunks for speed
                if cancel_event.is_set(): f.close(); os.remove(dest_path); raise Exception("Annulé.")
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    speed = downloaded / (elapsed + 0.001) / (1024 * 1024)
                    perc = (downloaded / total) * 100 if total > 0 else 0
                    eta = (total - downloaded) / (speed * 1024 * 1024 + 1)
                    update_func(f"{perc:.1f}% ({speed:.1f} Mo/s) - ETA: {int(eta)}s", downloaded/total if total > 0 else 0.5)

    def _handle_action(self):
        if self.installation_mode == "uninstall":
            if messagebox.askyesno("Confirmation", "Supprimer Multivers ?"):
                threading.Thread(target=self._uninstall_task, daemon=True).start()
        else:
            threading.Thread(target=self._installation_task, daemon=True).start()

    def _installation_task(self):
        try:
            self.action_btn.configure(state="disabled")
            self.cancel_main_btn.configure(state="normal")
            self.main_cancel_requested.clear()
            os.makedirs(INSTALL_DIR, exist_ok=True)
            apps_to_dl = [a for a in self.manifest_data['apps'] if self.selected_apps[a['id']].get()]
            downloader_selected = any(app['id'] == 'downloader' for app in apps_to_dl)
            
            # Smart Core Install: Only if missing or update
            launcher_exe = os.path.join(INSTALL_DIR, "Launcher_Universel.exe")
            v_cloud = self.manifest_data.get('version', '1.0.0')
            v_local = self.local_manifest.get('version', '0.0.0') if self.local_manifest else "0.0.0"
            needs_core = not os.path.exists(launcher_exe) or (v_cloud != v_local)

            total_tasks = (1 if needs_core else 0) + len(apps_to_dl) + (1 if downloader_selected else 0)
            current_task = 0

            # 1. Core
            if needs_core and 'core_zip' in self.manifest_data:
                self._update_main_ui("Moteur : Connexion...", current_task/total_tasks)
                core_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest/download/core.zip"
                self._download_file(core_url, os.path.join(INSTALL_DIR, "core.zip"), 
                                        self.main_cancel_requested, lambda m, p: self.after(0, lambda: self._update_main_ui(f"Moteur : {m}", (current_task + p)/total_tasks)))
                with zipfile.ZipFile(os.path.join(INSTALL_DIR, "core.zip"), 'r') as z: z.extractall(INSTALL_DIR)
                os.remove(os.path.join(INSTALL_DIR, "core.zip"))
                current_task += 1

            # 2. Apps
            for a in apps_to_dl:
                app_path = os.path.join(INSTALL_DIR, "apps", a['id'])
                self._update_main_ui(f"{a['name']} : Connexion...", current_task/total_tasks)
                temp_app_zip = os.path.join(INSTALL_DIR, "temp_app.zip")
                self._download_file(f"{BASE_URL}/{a['zip_file']}", temp_app_zip, 
                                        self.main_cancel_requested, lambda m, p, n=a['name']: self.after(0, lambda: self._update_main_ui(f"{n} : {m}", (current_task + p)/total_tasks)))
                if os.path.exists(app_path): shutil.rmtree(app_path)
                os.makedirs(app_path, exist_ok=True)
                with zipfile.ZipFile(temp_app_zip, 'r') as z: z.extractall(app_path)
                os.remove(temp_app_zip)
                current_task += 1

            # 3. FFmpeg (Official Source)
            if downloader_selected:
                bin_dir = os.path.join(INSTALL_DIR, "bin")
                ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe")
                if not os.path.exists(ffmpeg_exe):
                    os.makedirs(bin_dir, exist_ok=True)
                    self._update_main_ui("FFmpeg : Téléchargement depuis source officielle...", current_task/total_tasks)
                    ffmpeg_zip = os.path.join(INSTALL_DIR, "ffmpeg_official.zip")
                    self._download_file(FFMPEG_URL, ffmpeg_zip, 
                                            self.main_cancel_requested, lambda m, p: self.after(0, lambda: self._update_main_ui(f"FFmpeg : {m}", (current_task + p)/total_tasks)))
                    
                    self._update_main_ui("FFmpeg : Extraction...", (current_task + 0.9)/total_tasks)
                    with zipfile.ZipFile(ffmpeg_zip, 'r') as z:
                        for member in z.namelist():
                            if member.endswith("ffmpeg.exe") or member.endswith("ffprobe.exe"):
                                filename = os.path.basename(member)
                                with z.open(member) as source, open(os.path.join(bin_dir, filename), "wb") as target:
                                    shutil.copyfileobj(source, target)
                    os.remove(ffmpeg_zip)
                current_task += 1

            self._create_shortcuts()
            with open(LOCAL_MANIFEST_FILE, 'w', encoding='utf-8') as f: json.dump(self.manifest_data, f, indent=4)
            self.after(0, lambda: self._update_main_ui("Terminé !", 1.0))
            messagebox.showinfo("Succès", "Multivers est installé.")
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Erreur: {e}"))
            if "Annulé" not in str(e): self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
        finally:
            self.after(0, lambda: self.action_btn.configure(state="normal"))
            self.after(0, lambda: self.cancel_main_btn.configure(state="disabled"))

    def _update_main_ui(self, m, p):
        self.status_label.configure(text=m)
        self.progress_bar.set(p)

    def _uninstall_task(self):
        try:
            if os.path.exists(INSTALL_DIR): shutil.rmtree(INSTALL_DIR)
            for p in [os.path.join(os.environ["USERPROFILE"], "Desktop", "Multivers Launcher.lnk"),
                      os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Multivers Launcher.lnk")]:
                if os.path.exists(p): os.remove(p)
            messagebox.showinfo("Info", "Désinstallé.")
            self.destroy()
        except Exception as e: messagebox.showerror("Erreur", str(e))

    def _manage_ai(self):
        if self.ai_win and self.ai_win.winfo_exists():
            self.ai_win.lift()
            return

        self.ai_win = ctk.CTkToplevel(self)
        self.ai_win.title("Gestionnaire HackGPT")
        self.ai_win.geometry("550x600")
        self.ai_win.transient(self) 

        ctk.CTkLabel(self.ai_win, text="Assistant IA HackGPT", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=20)
        
        temp_path = os.path.join(os.getenv('TEMP'), "HackGPT_Install")
        t_link = ctk.CTkLabel(self.ai_win, text=f"Dossier temporaire (cliquable) :\n{temp_path}", font=ctk.CTkFont(size=10, underline=True), text_color="#00BFFF", cursor="hand2")
        t_link.pack(pady=5)
        t_link.bind("<Button-1>", lambda e: os.startfile(temp_path) if os.path.exists(temp_path) else None)

        self.ollama_status = ctk.CTkLabel(self.ai_win, text="Vérification Ollama...")
        self.ollama_status.pack(pady=10)
        
        self.ai_status_label = ctk.CTkLabel(self.ai_win, text=self.ai_status_msg, wraplength=450)
        self.ai_status_label.pack(pady=10)

        self.ai_progress_bar = ctk.CTkProgressBar(self.ai_win, width=450, progress_color="#6f42c1")
        self.ai_progress_bar.pack(pady=10)
        self.ai_progress_bar.set(self.ai_progress_val)

        f = ctk.CTkFrame(self.ai_win, fg_color="transparent")
        f.pack(pady=10, fill="x", padx=40)
        self.dl_ai_btn = ctk.CTkButton(f, text="🚀 Installer", fg_color="#6f42c1", command=self._start_hackgpt_install)
        self.dl_ai_btn.pack(side="left", expand=True, padx=5)
        self.rm_ai_btn = ctk.CTkButton(f, text="🗑️ Supprimer", fg_color="#dc3545", command=self._uninstall_hackgpt)
        self.rm_ai_btn.pack(side="left", expand=True, padx=5)

        self.cancel_ai_btn = ctk.CTkButton(self.ai_win, text="🛑 Annuler", fg_color="#555568", command=lambda: self.ai_cancel_requested.set())
        self.cancel_ai_btn.pack(pady=20)
        
        self._refresh_ai_loop()
        threading.Thread(target=self._check_ollama, daemon=True).start()

    def _refresh_ai_loop(self):
        if self.ai_win and self.ai_win.winfo_exists():
            self.ai_status_label.configure(text=self.ai_status_msg)
            self.ai_progress_bar.set(self.ai_progress_val)
            self.after(400, self._refresh_ai_loop)

    def _check_ollama(self):
        try:
            requests.get("http://localhost:11434/api/tags", timeout=2)
            self.ollama_installed = True
            self.after(0, lambda: self.ollama_status.configure(text="✅ Ollama est actif.", text_color="#28a745"))
        except:
            try:
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW, shell=True)
                time.sleep(4)
                requests.get("http://localhost:11434/api/tags", timeout=5)
                self.ollama_installed = True
                self.after(0, lambda: self.ollama_status.configure(text="✅ Ollama démarré.", text_color="#28a745"))
            except:
                self.ollama_installed = False
                self.after(0, lambda: self.ollama_status.configure(text="❌ Ollama non trouvé.", text_color="#dc3545"))

    def _start_hackgpt_install(self):
        if self.ai_task_active or not self.ollama_installed: return
        self.ai_task_active = True
        self.ai_cancel_requested.clear()
        threading.Thread(target=self._install_hackgpt_task, daemon=True).start()

    def _uninstall_hackgpt(self):
        if messagebox.askyesno("IA", "Supprimer HackGPT ?"):
            subprocess.run(["ollama", "rm", "HackGPT"], shell=True)
            self._check_ollama()

    def _install_hackgpt_task(self):
        temp_dir = os.path.join(os.getenv('TEMP'), "HackGPT_Install")
        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            self._download_file(HACKGPT_LINK, os.path.join(temp_dir, "h.zip"), self.ai_cancel_requested, 
                                    lambda m, p: self._set_ai_state(m, p))
            self.ai_status_msg = "Extraction et Importation..."
            with zipfile.ZipFile(os.path.join(temp_dir, "h.zip"), 'r') as z: z.extractall(temp_dir)
            work_dir = temp_dir
            for root, _, files in os.walk(temp_dir):
                if "manifest.json" in files: work_dir = root; break
            blob = max([os.path.join(work_dir, f) for f in os.listdir(work_dir) if f != "manifest.json"], key=os.path.getsize)
            with open(os.path.join(work_dir, "Modelfile"), 'w') as f: f.write(f"FROM {blob}\nSYSTEM \"You are HackGPT.\"")
            subprocess.run(["ollama", "create", "HackGPT", "-f", os.path.join(work_dir, "Modelfile")], shell=True, check=True)
            self.ai_status_msg = "Installé !"
            self.ai_progress_val = 1.0
            self.after(0, lambda: messagebox.showinfo("IA", "HackGPT est prêt."))
        except Exception as e: self.ai_status_msg = f"Erreur: {e}"
        finally:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
            self.ai_task_active = False

    def _set_ai_state(self, m, p): self.ai_status_msg = m; self.ai_progress_val = p

    def _create_shortcuts(self):
        exe = os.path.join(INSTALL_DIR, "Launcher_Universel.exe")
        if not os.path.exists(exe): return
        d = os.path.join(os.environ["USERPROFILE"], "Desktop", "Multivers Launcher.lnk")
        s = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Multivers Launcher.lnk")
        cmd = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{d}');$s.TargetPath='{exe}';$s.WorkingDirectory='{INSTALL_DIR}';$s.Save();"
        cmd += f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{s}');$s.TargetPath='{exe}';$s.WorkingDirectory='{INSTALL_DIR}';$s.Save();"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)

if __name__ == "__main__": WebInstaller().mainloop()
