import tkinter as tk
import customtkinter as ctk

class AppCarousel(ctk.CTkFrame):
    def __init__(self, parent, apps, on_select):
        super().__init__(parent, fg_color="transparent")
        self.apps = apps
        self.on_select = on_select
        
        self.scroll_frame = ctk.CTkScrollableFrame(self, orientation="horizontal", fg_color="transparent", height=300)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=50)
        
        self._build_carousel()

    def _build_carousel(self):
        for app in self.apps:
            is_installed = app.get("is_installed", True)
            bg_color = "#3a3a50" if is_installed else "#2a2a35"
            
            card = ctk.CTkFrame(self.scroll_frame, width=200, height=250, fg_color=bg_color, corner_radius=15)
            card.pack(side="left", padx=15, pady=10)
            card.pack_propagate(False)
            
            # Icon and labels with dimmed colors if not installed
            text_color = "white" if is_installed else "#777777"
            sub_text_color = "#aaa" if is_installed else "#555555"

            ctk.CTkLabel(card, text=app.get("icon_text", "📦"), font=("Arial", 60), text_color=text_color).pack(pady=(30, 10))
            ctk.CTkLabel(card, text=app["name"], font=("Arial", 18, "bold"), text_color=text_color).pack(pady=5)
            ctk.CTkLabel(card, text=app.get("description", ""), font=("Arial", 11), wraplength=180, text_color=sub_text_color).pack(pady=5, padx=10)
            
            btn_text = "Lancer" if is_installed else "Installer"
            btn_color = "#E07A5F" if is_installed else "#555568"
            btn_hover = "#D16043" if is_installed else "#444455"

            btn = ctk.CTkButton(card, text=btn_text, fg_color=btn_color, hover_color=btn_hover, 
                                command=lambda a=app: self.on_select(a))
            btn.pack(side="bottom", pady=20)
            
            # Make card clickable too
            for child in card.winfo_children():
                if not isinstance(child, ctk.CTkButton):
                    child.bind("<Button-1>", lambda e, a=app: self.on_select(a))
            card.bind("<Button-1>", lambda e, a=app: self.on_select(a))
