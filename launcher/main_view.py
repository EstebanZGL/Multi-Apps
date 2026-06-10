import os
import traceback
import tkinter.messagebox as messagebox
import customtkinter as ctk
from launcher.app_discovery import discover_apps, load_app_module
from launcher.ui_wheel import AppWheel
from launcher.ui_carousel import AppCarousel

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
        self.apps = discover_apps()
        self.current_app_frame = None
        self.view_mode = ctk.StringVar(value="wheel") # "wheel" or "carousel"
        
        # Container for views
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        
        # View Switcher (Bottom) - Initialize BEFORE show_menu
        self.switcher_btn = ctk.CTkButton(self, text="🔄 Changer de vue (Carrousel)", 
                                          command=self.toggle_view_mode,
                                          fg_color="#3a3a50", hover_color="#555568")
        self.switcher_btn.pack(pady=20)

        # Initial View
        self.show_menu()

    def register_cleanup(self, callback):
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)

    def _on_closing(self):
        print("Fermeture de l'application, exécution du nettoyage...")
        for cb in self.cleanup_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"Erreur de nettoyage: {e}")
        self.destroy()
        os._exit(0)

    def toggle_view_mode(self):
        if self.view_mode.get() == "wheel":
            self.view_mode.set("carousel")
            self.switcher_btn.configure(text="🔄 Changer de vue (Roue)")
        else:
            self.view_mode.set("wheel")
            self.switcher_btn.configure(text="🔄 Changer de vue (Carrousel)")
        
        if not self.current_app_frame:
            self.show_menu()

    def show_menu(self):
        # Clear container
        for child in self.container.winfo_children():
            child.destroy()
        
        self.current_app_frame = None
        self.switcher_btn.pack(pady=20) # Show switcher if hidden
        
        if self.view_mode.get() == "wheel":
            menu = AppWheel(self.container, self.apps, self.launch_app)
        else:
            menu = AppCarousel(self.container, self.apps, self.launch_app)
            
        menu.pack(fill="both", expand=True)

    def launch_app(self, app_manifest):
        is_installed = app_manifest.get("is_installed", True)
        
        if not is_installed:
            if messagebox.askyesno("Application non installée", 
                                  f"L'application '{app_manifest['name']}' n'est pas installée sur ce PC.\n\nVoulez-vous lancer l'assistant d'installation ?"):
                try:
                    # Look for installer in the same dir as the launcher
                    if os.path.exists("multivers_installer.py"):
                        import subprocess
                        subprocess.Popen([sys.executable, "multivers_installer.py"])
                    else:
                        messagebox.showinfo("Info", "Veuillez télécharger et lancer le 'Multivers_Installer.exe' pour ajouter ce module.")
                except: pass
            return

        print(f"Lancement de {app_manifest['name']}...")
