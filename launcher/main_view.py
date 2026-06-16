import os
import sys
import traceback
import threading
import tkinter.messagebox as messagebox
import customtkinter as ctk
from launcher.app_discovery import get_local_apps, get_remote_manifest, load_app_module, get_local_versions
from launcher.ui_wheel import AppWheel
from launcher.ui_carousel import AppCarousel

GITHUB_MANIFEST_URL = "https://raw.githubusercontent.com/EstebanZGL/Multi-Apps/builds/data/install_manifest.json"

class LauncherMainView(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Launcher Universel [STABLE]")
        self.geometry("1000x700")
        self.configure(fg_color="#1a1a1a")
        
        # Cleanup registry
        self.cleanup_callbacks = []
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Data
        self.local_apps = []
        self.remote_apps = []
        self.current_app_frame = None
        self.view_mode = ctk.StringVar(value="wheel") # "wheel" or "carousel"
        
        # Container for views
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        
        # View Switcher (Bottom)
        self.switcher_btn = ctk.CTkButton(self, text="🔄 Voir tout le catalogue (Carrousel)", 
                                          command=self.toggle_view_mode,
                                          fg_color="#3a3a50", hover_color="#555568")
        self.switcher_btn.pack(pady=20)

        # Initial Load & Update Check
        self.refresh_apps()
        threading.Thread(target=self.check_for_launcher_updates, daemon=True).start()

    def register_cleanup(self, callback):
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)

    def _on_closing(self):
        for cb in self.cleanup_callbacks:
            try: cb()
            except: pass
        self.destroy()
        os._exit(0)

    def toggle_view_mode(self):
        if self.view_mode.get() == "wheel":
            self.view_mode.set("carousel")
            self.switcher_btn.configure(text="🔄 Retour à mes applications (Roue)")
        else:
            self.view_mode.set("wheel")
            self.switcher_btn.configure(text="🔄 Voir tout le catalogue (Carrousel)")
        
        self.refresh_apps()

    def refresh_apps(self):
        """Reloads the app lists (local and remote) and refreshes the current view."""
        self.local_apps = get_local_apps()
        
        if not self.local_apps and self.view_mode.get() == "wheel":
            base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
            messagebox.showinfo("Diagnostic", f"Aucune application installée trouvée.\n\nChemin scanné : {base}\\apps\n\nVérifiez que le dossier 'apps' existe à côté du Launcher.")

        # Hybrid mode: Start remote fetch in background
        threading.Thread(target=self._fetch_remote_apps, daemon=True).start()
        
        # Immediately show local ones while waiting
        self.show_menu(self.local_apps)

    def _fetch_remote_apps(self):
        manifest = get_remote_manifest(GITHUB_MANIFEST_URL)
        remotes = manifest.get("apps", [])
        if not remotes: return
        
        local_versions = get_local_versions()
        local_ids = [a['id'] for a in self.local_apps]
        hybrid_list = list(self.local_apps)
        
        needs_update_apps = []

        for r in remotes:
            # Check for updates on installed apps
            if r['id'] in local_ids:
                # Compare hash from manifest with our local versions.json
                local_app_info = local_versions.get("apps", {}).get(r['id'], {})
                local_hash = local_app_info.get("last_build_hash", "")
                
                if local_hash and r.get("hash") and local_hash != r["hash"]:
                    # Find the app in our list and mark it
                    for app in hybrid_list:
                        if app['id'] == r['id']:
                            app['needs_update'] = True
                            needs_update_apps.append(app['name'])
                            break
            else:
                # App not installed
                r['is_installed'] = False
                hybrid_list.append(r)
        
        # Update UI
        self.after(0, lambda: self.show_menu(hybrid_list))
        
        if needs_update_apps:
            self.after(0, lambda: self._notify_updates(needs_update_apps))

    def _notify_updates(self, app_names):
        msg = "Des mises à jour sont disponibles pour :\n" + "\n".join([f"• {n}" for n in app_names])
        msg += "\n\nVoulez-vous lancer l'installateur pour les mettre à jour ?"
        if messagebox.askyesno("Mises à jour disponibles", msg):
            self._launch_installer()

    def check_for_launcher_updates(self):
        manifest = get_remote_manifest(GITHUB_MANIFEST_URL)
        remote_hash = manifest.get("core_hash")
        if not remote_hash: return

        local_versions = get_local_versions()
        local_hash = local_versions.get("launcher", {}).get("last_build_hash", "")

        if local_hash and remote_hash and local_hash != remote_hash:
            msg = f"Une nouvelle version du Launcher est disponible !\n\nSouhaitez-vous lancer l'installateur pour mettre à jour le moteur principal ?"
            self.after(0, lambda: self._notify_launcher_update(msg))

    def _notify_launcher_update(self, msg):
        if messagebox.askyesno("Mise à jour du Launcher", msg):
            self._launch_installer()

    def _launch_installer(self):
        try:
            import subprocess
            if os.path.exists("multivers_installer.py"):
                subprocess.Popen([sys.executable, "multivers_installer.py"])
            else:
                # In frozen mode, assume exe is next to us
                base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
                exe = os.path.join(base, "Multivers_Installer.exe")
                if os.path.exists(exe):
                    subprocess.Popen([exe])
                else:
                    messagebox.showinfo("Info", "Lancer Multivers_Installer.exe pour effectuer les mises à jour.")
        except: pass

    def show_menu(self, apps_list=None):
        self.current_app_frame = None # Reset when returning to menu
        
        if apps_list is None:
            apps_list = self.local_apps

        # Clear container
        for child in self.container.winfo_children():
            child.destroy()
        
        self.switcher_btn.pack(pady=20) # Show switcher
        
        if self.view_mode.get() == "wheel":
            menu = AppWheel(self.container, apps_list, self.launch_app)
        else:
            menu = AppCarousel(self.container, apps_list, self.launch_app)
            
        menu.pack(fill="both", expand=True)

    def launch_app(self, app_manifest):
        is_installed = app_manifest.get("is_installed", True)
        needs_update = app_manifest.get("needs_update", False)
        
        if not is_installed or needs_update:
            action = "Mettre à jour" if needs_update else "Installer"
            if messagebox.askyesno(action, f"{action} '{app_manifest['name']}' ?"):
                self._launch_installer()
            return

        try:
            # Lazy Loading
            app_class = load_app_module(app_manifest)
            if app_class:
                self.switcher_btn.pack_forget()
                for child in self.container.winfo_children(): child.destroy()
                self.current_app_frame = app_class(self.container, self)
                self.current_app_frame.pack(fill="both", expand=True)
            else:
                messagebox.showerror("Erreur", f"Impossible de charger '{app_manifest['name']}'.")
        except Exception as e:
            print(traceback.format_exc())
            messagebox.showerror("Erreur", f"Erreur fatale :\n{e}")
            self.show_menu(self.local_apps)

