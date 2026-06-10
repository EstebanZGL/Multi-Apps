import tkinter as tk
import customtkinter as ctk
import math

class AppWheel(ctk.CTkFrame):
    def __init__(self, parent, apps, on_select):
        super().__init__(parent, fg_color="transparent")
        self.apps = apps
        self.on_select = on_select
        self.angle = -math.pi/2 # Current angle
        self.target_angle = -math.pi/2 # Angle we want to reach
        
        self.canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        
        self.items = []
        self._animate()

    def _animate(self):
        # Smooth transition: Move current angle towards target angle (lerp)
        diff = self.target_angle - self.angle
        if abs(diff) > 0.001:
            self.angle += diff * 0.15 # Lerp factor
            self.draw()
        
        if self.winfo_exists():
            self.after(16, self._animate)

    def _on_mousewheel(self, event):
        delta = event.delta / 120
        # Rotate by one "slot" per scroll step roughly
        num_apps = len(self.apps)
        if num_apps > 0:
            step = (2 * math.pi) / num_apps
            self.target_angle += delta * step
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10: 
            self.after(100, self.draw)
            return
            
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.35
        
        num_apps = len(self.apps)
        if num_apps == 0:
            self.canvas.create_text(cx, cy, text="Aucune application installée", fill="white", font=("Arial", 16))
            return

        # Special Case: Only 1 app -> Center it
        if num_apps == 1:
            app = self.apps[0]
            size = 100
            tag = "app_0"
            self.canvas.create_oval(cx-size+4, cy-size+4, cx+size+4, cy+size+4, fill="#000000", outline="", stipple="gray50")
            self.canvas.create_oval(cx-size, cy-size, cx+size, cy+size, fill="#E07A5F", outline="#555568", width=3, tags=tag)
            self.canvas.create_text(cx, cy-15, text=app.get("icon_text", "📦"), font=("Arial", 50), fill="white", tags=tag, state="disabled")
            self.canvas.create_text(cx, cy+35, text=app["name"], font=("Arial", 14, "bold"), fill="white", tags=tag, state="disabled")
            self.canvas.tag_bind(tag, "<Button-1>", lambda e: self.on_select(app))
            return

        # Regular Wheel logic for 2+ apps
        norm_angle = self.angle % (2 * math.pi)

        for i, app in enumerate(self.apps):
            # Calculate absolute angle for this app
            app_angle = (self.angle + (i * 2 * math.pi / num_apps))
            
            # Position
            x = cx + radius * math.cos(app_angle)
            y = cy + radius * math.sin(app_angle)
            
            # Selection logic (is it at the top?)
            # Normalized angle of the app
            norm_app_angle = app_angle % (2 * math.pi)
            target_angle = (1.5 * math.pi) % (2 * math.pi) # Top is 270 degrees or 1.5 pi
            
            diff = abs(norm_app_angle - target_angle)
            if diff > math.pi: diff = 2 * math.pi - diff
            
            is_selected = diff < (math.pi / num_apps)
            is_installed = app.get("is_installed", True)
            
            size = 70 if is_selected else 50
            
            # Color logic: Gray out if not installed
            if not is_installed:
                color = "#4a4a4a"
                border_color = "#555555"
                text_color = "#888888"
            else:
                color = "#E07A5F" if is_selected else "#3a3a50"
                border_color = "#555568"
                text_color = "white"
            
            # Draw circle shadow
            self.canvas.create_oval(x-size+4, y-size+4, x+size+4, y+size+4, fill="#000000", outline="", stipple="gray50")
            
            # Draw circle
            tag = f"app_{i}"
            self.canvas.create_oval(x-size, y-size, x+size, y+size, fill=color, outline=border_color, width=2, tags=tag)
            
            # Draw icon text
            self.canvas.create_text(x, y-10, text=app.get("icon_text", "📦"), font=("Arial", 35), fill=text_color, tags=tag, state="disabled")
            
            app_name = app["name"]
            if not is_installed: app_name += "\n(Non installé)"
            
            self.canvas.create_text(x, y+25, text=app_name, font=("Arial", 10, "bold" if is_selected else "normal"), fill=text_color, tags=tag, state="disabled", justify="center")
            
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, a=app: self.on_select(a))
            self.canvas.tag_bind(tag, "<Enter>", lambda e, t=tag: self.canvas.itemconfig(t, outline="white"))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, t=tag: self.canvas.itemconfig(t, outline="#555568"))

    def rotate_to_app(self, index):
        # Target angle for app i to be at top (-pi/2)
        target = -math.pi/2 - (index * 2 * math.pi / len(self.apps))
        # Simple animation could be added here
        self.angle = target
        self.draw()
