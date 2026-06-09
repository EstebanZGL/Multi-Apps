import os
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Config paths
APP_DIR = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'CER_Automator')
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings: dict):
    os.makedirs(APP_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

def replace_content_by_titles(doc, replacements):
    """
    Finds section titles (e.g., 'Contexte :') and replaces the content of the 
    paragraphs immediately following them. Preserves the title's style.
    Ensures alignment is left (not justified).
    """
    section_keywords = {
        "Contexte": ["contexte"],
        "Problématique": ["problématique", "problematique", "problematiques", "problématiques"],
        "Mots-Clefs": ["mots-clefs", "mots clefs", "mots-clés", "mots clés", "mot clef", "mot clé"],
        "Contrainte": ["contrainte", "contraintes"],
        "Hypothèses": ["hypothèses", "hypotheses", "hypothèse", "hypothese"],
        "Plan d’action": ["plan d’action", "plan d'action", "plan action", "étapes", "etapes"]
    }

    paragraphs = doc.paragraphs
    for i, para in enumerate(paragraphs):
        text = para.text.strip().lower()
        for section_name, keywords in section_keywords.items():
            if section_name in replacements:
                # Check if this paragraph is one of our titles
                is_title = False
                for kw in keywords:
                    # Match "Title :" or "Title" or "Title "
                    clean_text = text.replace(":", "").replace(" ", " ").strip()
                    if clean_text == kw:
                        is_title = True
                        break
                
                if is_title:
                    j = i + 1
                    while j < len(paragraphs):
                        next_text = paragraphs[j].text.strip().lower()
                        
                        # Stop if we hit another section title
                        is_next_title = False
                        for other_kws in section_keywords.values():
                            for okw in other_kws:
                                clean_next = next_text.replace(":", "").replace(" ", " ").strip()
                                if clean_next == okw:
                                    is_next_title = True
                                    break
                            if is_next_title: break
                        
                        if is_next_title: break
                        
                        # If it's a placeholder or content, replace it and force Left Alignment
                        if paragraphs[j].text.strip():
                            paragraphs[j].text = replacements[section_name]
                            paragraphs[j].alignment = WD_ALIGN_PARAGRAPH.LEFT
                            break
                        j += 1
                    break

class CERAutomatorApp(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        settings = load_settings()
        self.template_path = ctk.StringVar(value=settings.get("template_path", ""))
        self.default_filename = ctk.StringVar(value=settings.get("default_filename", "CER_Genere"))
        
        # Fields for the 6 sections (explicitly excluding Philosophy, Generalization, Deliverable)
        self.sections = {
            "Contexte": tk.StringVar(),
            "Problématique": tk.StringVar(),
            "Mots-Clefs": tk.StringVar(),
            "Contrainte": tk.StringVar(),
            "Hypothèses": tk.StringVar(),
            "Plan d’action": tk.StringVar()
        }
        
        # Text widgets references
        self.text_widgets = {}

        self._build_ui()

    def _build_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        self.back_btn = ctk.CTkButton(
            header_frame, text="🏠 Menu", width=80, 
            command=lambda: self.controller.show_menu()
        )
        self.back_btn.pack(side="left")

        self.title_label = ctk.CTkLabel(
            header_frame, text="CERviable", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.pack(side="left", expand=True, padx=(0, 20))

        # Config Selection (Template & Default Name)
        config_frame = ctk.CTkFrame(self)
        config_frame.pack(fill="x", padx=20, pady=10)
        
        # Row 1: Template
        template_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        template_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(template_row, text="Template :", font=ctk.CTkFont(weight="bold"), width=100).pack(side="left")
        self.template_entry = ctk.CTkEntry(template_row, textvariable=self.template_path, state="disabled")
        self.template_entry.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(template_row, text="Choisir", command=self._select_template, width=80).pack(side="left")

        # Row 2: Default Filename
        filename_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        filename_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(filename_row, text="Nom Sortie :", font=ctk.CTkFont(weight="bold"), width=100).pack(side="left")
        self.filename_entry = ctk.CTkEntry(filename_row, textvariable=self.default_filename, placeholder_text="Ex: CER_Genere")
        self.filename_entry.pack(side="left", padx=10, fill="x", expand=True)
        self.default_filename.trace_add("write", self._save_filename_setting)

        # Prosit Selection
        prosit_frame = ctk.CTkFrame(self, fg_color="transparent")
        prosit_frame.pack(fill="x", padx=20, pady=5)
        
        self.load_prosit_btn = ctk.CTkButton(
            prosit_frame, text="📂 Charger un Prosit Aller (.docx)", 
            font=ctk.CTkFont(weight="bold"),
            command=self._select_prosit,
            fg_color="#E07A5F", hover_color="#D16043"
        )
        self.load_prosit_btn.pack(fill="x")

        # Scrollable Area for Revision
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Révision des données")
        self.scrollable_frame.pack(fill="both", expand=True, padx=20, pady=10)

        for section_name in self.sections.keys():
            section_label = ctk.CTkLabel(self.scrollable_frame, text=section_name, font=ctk.CTkFont(weight="bold"))
            section_label.pack(anchor="w", padx=10, pady=(10, 2))
            
            text_area = ctk.CTkTextbox(self.scrollable_frame, height=100)
            text_area.pack(fill="x", padx=10, pady=(0, 5))
            self.text_widgets[section_name] = text_area

        # Generate Button
        self.generate_btn = ctk.CTkButton(
            self, text="📝 Générer le CER", 
            font=ctk.CTkFont(size=18, weight="bold"),
            height=50,
            command=self._generate_cer,
            fg_color="#2E8B57", hover_color="#1F5F3A"
        )
        self.generate_btn.pack(fill="x", padx=20, pady=20)

    def _save_filename_setting(self, *args):
        settings = load_settings()
        settings["default_filename"] = self.default_filename.get()
        save_settings(settings)

    def _select_template(self):
        f = filedialog.askopenfilename(title="Sélectionner le Template CER", filetypes=[("Word files", "*.docx")])
        if f:
            self.template_path.set(f)
            settings = load_settings()
            settings["template_path"] = f
            save_settings(settings)

    def _select_prosit(self):
        f = filedialog.askopenfilename(title="Sélectionner le Prosit Aller", filetypes=[("Word files", "*.docx")])
        if f:
            threading.Thread(target=self._parse_prosit, args=(f,), daemon=True).start()

    def _parse_prosit(self, file_path):
        try:
            doc = Document(file_path)
            content = {s: [] for s in self.sections.keys()}
            current_section = None
            
            # Expanded keywords for parsing Document A
            section_keywords = {
                "Contexte": ["contexte"],
                "Problématique": ["problematique", "problématique", "problematiques", "problématiques"],
                "Mots-Clefs": ["mots-clefs", "mots clefs", "mots-clés", "mots clés", "mot clef", "mot clé"],
                "Contrainte": ["contrainte", "contraintes"],
                "Hypothèses": ["hypothese", "hypothèse", "hypothèses", "hypotheses"],
                "Plan d’action": ["plan d'action", "plan d’action", "plan action", "etapes", "étapes"]
            }
            
            # Keywords that should STOP the current extraction (excluded sections)
            excluded_keywords = ["philosophie", "généralisation", "generalisation", "livrable", "livrables"]

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text: continue
                
                # Clean text to handle non-breaking spaces and colons
                lower_text = text.lower().replace(":", "").replace(" ", " ").strip()
                
                # 1. Check if this paragraph is an EXCLUDED section header
                is_excluded = False
                for ex_kw in excluded_keywords:
                    if (ex_kw == lower_text or lower_text.startswith(ex_kw + " ")) and len(text) < 60:
                        current_section = None # STOP extracting
                        is_excluded = True
                        break
                if is_excluded: continue

                # 2. Check if this paragraph is a VALID section header
                found_header = False
                for section, kws in section_keywords.items():
                    for kw in kws:
                        if (kw == lower_text or lower_text.startswith(kw + " ")) and len(text) < 60:
                            current_section = section
                            found_header = True
                            break
                    if found_header: break
                
                if not found_header and current_section:
                    content[current_section].append(text)

            # Update UI
            self.after(0, lambda: self._update_revision_fields(content))
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", f"Erreur lors de la lecture du Prosit : {str(e)}"))

    def _update_revision_fields(self, content):
        for section, lines in content.items():
            if section in self.text_widgets:
                self.text_widgets[section].delete("1.0", "end")
                self.text_widgets[section].insert("1.0", "\n".join(lines))
        messagebox.showinfo("Succès", "Données extraites avec succès. Veuillez vérifier avant de générer.")

    def _generate_cer(self):
        t_path = self.template_path.get()
        if not t_path or not os.path.exists(t_path):
            messagebox.showwarning("Attention", "Veuillez d'abord sélectionner un template CER.")
            return

        default_name = self.default_filename.get() if self.default_filename.get() else "CER_Genere"
        save_path = filedialog.asksaveasfilename(
            title="Enregistrer le CER", 
            defaultextension=".docx",
            filetypes=[("Word files", "*.docx")],
            initialfile=f"{default_name}.docx"
        )
        
        if not save_path:
            return

        try:
            doc = Document(t_path)
            
            # Prepare replacements dictionary
            replacements = {}
            for section_name, widget in self.text_widgets.items():
                val = widget.get("1.0", "end-1c").strip()
                replacements[section_name] = val

            replace_content_by_titles(doc, replacements)
            doc.save(save_path)
            
            messagebox.showinfo("Succès", f"CER généré avec succès !\n\nSauvegardé ici : {save_path}")
            
            # Open the file
            os.startfile(save_path) if os.name == 'nt' else None

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la génération du CER : {str(e)}")
