import os
import sys
import traceback
import threading
import tkinter.messagebox as messagebox
import customtkinter as ctk
from launcher.app_discovery import get_local_apps, get_remote_apps, load_app_module
from launcher.ui_wheel import AppWheel
from launcher.ui_carousel import AppCarousel

GITHUB_MANIFEST_URL = "https://raw.githubusercontent.com/EstebanZGL/Multi-Apps/builds/data/install_manifest.json"

class LauncherMainView(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Launcher Universel")
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

        # Initial Load
        self.refresh_apps()

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

        if self.view_mode.get() == "carousel":
            # Hybrid mode: Start remote fetch in background
            threading.Thread(target=self._fetch_remote_apps, daemon=True).start()
            # Immediately show local ones while waiting
            self.show_menu(self.local_apps)
        else:
            # Wheel mode: only local
            self.show_menu(self.local_apps)

    def _fetch_remote_apps(self):
        remotes = get_remote_apps(GITHUB_MANIFEST_URL)
        if not remotes: return
        
        # Merge: If a remote app is already local, use local version (with is_installed=True)
        local_ids = [a['id'] for a in self.local_apps]
        hybrid_list = list(self.local_apps)
        
        for r in remotes:
            if r['id'] not in local_ids:
                r['is_installed'] = False
                hybrid_list.append(r)
        
        # Update UI if we are still in carousel mode
        if self.view_mode.get() == "carousel":
            self.after(0, lambda: self.show_menu(hybrid_list))

    def show_menu(self, apps_list):
        if self.current_app_frame: return # Don't interrupt a running app

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
        
        if not is_installed:
            if messagebox.askyesno("Installer", f"Installer '{app_manifest['name']}' ?"):
                try:
                    import subprocess
                    if os.path.exists("multivers_installer.py"):
                        subprocess.Popen([sys.executable, "multivers_installer.py"])
                    else:
                        messagebox.showinfo("Info", "Lancer Multivers_Installer.exe pour ajouter ce module.")
                except: pass
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
