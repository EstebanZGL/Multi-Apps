import os
import json
import glob
import time
import re
import subprocess
import datetime
import threading
import io
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

import requests
import ollama
from google import genai
from google.genai import types
from PIL import Image
import PyPDF2
from docx import Document

import markdown2
from tkhtmlview import HTMLLabel

# --- CONFIG & DIRS ---
APP_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
CHATS_DIR = os.path.join(APP_DIR, "conversations")

if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

def load_config():
    default_config = {
        "serper_key": "",
        "gemini_key": "",
        "system_prompt": "Tu es Jarvis. NOUS SOMMES LE [DATE_DU_JOUR].\nUtilise l'outil 'google_search' pour répondre aux questions d'actualité.\nNe simule pas la recherche, exécute-la.",
        "temperature": 0.4,
        "ctx_size": 8192,
        "enable_web": True,
        "last_model": "gemini-1.5-flash"
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        return default_config
    except: return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except: pass

def get_chat_files():
    files = glob.glob(f"{CHATS_DIR}/*.json")
    files.sort(key=os.path.getmtime, reverse=True)
    return files

def load_chat(filename):
    try: 
        with open(filename, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_chat(filename, messages):
    clean_msgs = []
    for m in messages:
        if isinstance(m, dict): clean_msgs.append(m)
        else:
            try: clean_msgs.append(m.model_dump())
            except: clean_msgs.append({"role": getattr(m, "role", "assistant"), "content": getattr(m, "content", "")})
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(clean_msgs, f, indent=4, ensure_ascii=False)

def create_new_chat():
    timestamp = int(time.time())
    filename = os.path.join(CHATS_DIR, f"chat_{timestamp}.json")
    save_chat(filename, [])
    return filename

def extract_text_from_file(filepath):
    text = ""
    MAX_CHARS = 25000 
    ext = filepath.lower().split('.')[-1]
    try:
        if ext == 'pdf':
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                    if len(text) > MAX_CHARS: text += "\n\n[... TRONQUÉ ...]"; break
        elif ext in ['doc', 'docx']:
            doc = Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
                if len(text) > MAX_CHARS: break
        else:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read(MAX_CHARS)
        return text
    except Exception as e: return f"Erreur de lecture: {e}"

def search_google_serper(query, api_key):
    if not api_key: return "Erreur : Clé Serper manquante."
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": "fr", "hl": "fr"})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        data = response.json()
        results = ""
        if "organic" in data:
            for item in data["organic"][:4]:
                results += f"- {item.get('title')} ({item.get('link')}): {item.get('snippet')}\n"
        else: return "Aucun résultat."
        return results
    except Exception as e: return f"Erreur API: {e}"

def extract_json_mistral(text):
    pattern = re.compile(r'\[\s*\{.*?\}\s*\]', re.DOTALL)
    match = pattern.search(text)
    if match:
        try: return json.loads(match.group(0))
        except: return None
    return None

class JarvisAppWrapper(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.config = load_config()
        self.current_chat_file = None
        self.messages = []
        self.attached_files = []
        self.streamlit_process = None
        self.is_generating = False
        self._current_assistant_bubble = None
        
        # Ensure Ollama runs in background
        threading.Thread(target=self._ensure_ollama_running, daemon=True).start()
        
        if hasattr(self.controller, 'register_cleanup'):
            self.controller.register_cleanup(self._cleanup)
        
        self._build_ui()
        self._load_models_async()
        
        # Load initial chat
        files = get_chat_files()
        if not files: self.current_chat_file = create_new_chat()
        else: self.current_chat_file = files[0]
        self._refresh_chat_history_list()
        self._load_current_chat()

    def _ensure_ollama_running(self):
        try:
            ollama.list()
        except:
            if os.name == 'nt': subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            else: subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR (Left) ---
        self.sidebar = ctk.CTkScrollableFrame(self, width=300, corner_radius=0, fg_color="#2b2b2b")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="🤖 Jarvis Native", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 10))
        
        self.btn_off = ctk.CTkButton(self.sidebar, text="🔴 OFF (Tout éteindre)", fg_color="#ff4b4b", hover_color="#cc0000", command=self.controller._on_closing)
        self.btn_off.pack(fill="x", padx=20, pady=5)
        
        self.btn_web = ctk.CTkButton(self.sidebar, text="🌐 Version Web (Streamlit)", fg_color="#1a73e8", hover_color="#1557b0", command=self._start_streamlit_fallback)
        self.btn_web.pack(fill="x", padx=20, pady=5)
        
        self.btn_menu = ctk.CTkButton(self.sidebar, text="🏠 Menu Principal", fg_color="#E07A5F", hover_color="#D16043", command=self._return_menu)
        self.btn_menu.pack(fill="x", padx=20, pady=(5, 20))

        # Settings
        ctk.CTkLabel(self.sidebar, text="🔑 Clés API", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20)
        self.serper_var = ctk.StringVar(value=self.config["serper_key"])
        ctk.CTkEntry(self.sidebar, textvariable=self.serper_var, placeholder_text="Serper Key", show="*").pack(fill="x", padx=20, pady=5)
        self.gemini_var = ctk.StringVar(value=self.config["gemini_key"])
        ctk.CTkEntry(self.sidebar, textvariable=self.gemini_var, placeholder_text="Gemini Key", show="*").pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(self.sidebar, text="💾 Sauver Clés", command=self._save_settings_ui).pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(self.sidebar, text="📁 Historique", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(15,0))
        ctk.CTkButton(self.sidebar, text="➕ Nouveau Chat", command=self._new_chat).pack(fill="x", padx=20, pady=5)
        self.chat_combo_var = ctk.StringVar()
        self.chat_combo = ctk.CTkComboBox(self.sidebar, variable=self.chat_combo_var, command=self._on_chat_selected)
        self.chat_combo.pack(fill="x", padx=20, pady=5)
        self.chat_name_var = ctk.StringVar()
        ctk.CTkEntry(self.sidebar, textvariable=self.chat_name_var, placeholder_text="Nommer").pack(fill="x", padx=20, pady=5)
        
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(btn_frame, text="✏️", width=40, command=self._rename_chat).pack(side="left", padx=(0,5))
        ctk.CTkButton(btn_frame, text="🗑️", width=40, fg_color="#ff4b4b", hover_color="#cc0000", command=self._delete_chat).pack(side="right")

        ctk.CTkLabel(self.sidebar, text="⚙️ Paramètres IA", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(15,0))
        self.model_combo_var = ctk.StringVar(value=self.config["last_model"])
        self.model_combo = ctk.CTkComboBox(self.sidebar, variable=self.model_combo_var, values=["Chargement..."], command=self._save_settings_ui)
        self.model_combo.pack(fill="x", padx=20, pady=5)
        
        self.web_toggle_var = ctk.BooleanVar(value=self.config["enable_web"])
        ctk.CTkSwitch(self.sidebar, text="🌐 Internet", variable=self.web_toggle_var, command=self._save_settings_ui).pack(anchor="w", padx=20, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="System Prompt:").pack(anchor="w", padx=20)
        self.prompt_box = ctk.CTkTextbox(self.sidebar, height=80)
        self.prompt_box.pack(fill="x", padx=20, pady=5)
        self.prompt_box.insert("1.0", self.config["system_prompt"])
        
        ctk.CTkLabel(self.sidebar, text="Température:").pack(anchor="w", padx=20)
        self.temp_slider = ctk.CTkSlider(self.sidebar, from_=0, to=1, number_of_steps=10, command=self._save_settings_ui)
        self.temp_slider.set(self.config["temperature"])
        self.temp_slider.pack(fill="x", padx=20, pady=5)

        # --- MAIN CHAT AREA (Right) ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        self.chat_scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="#1e1e1e", corner_radius=10)
        self.chat_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Input Area
        self.input_frame = ctk.CTkFrame(self.main_area, fg_color="transparent", height=60)
        self.input_frame.grid(row=1, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)
        
        self.attach_btn = ctk.CTkButton(self.input_frame, text="📎", width=40, font=("Arial", 18), command=self._attach_file, fg_color="#3a3a50", hover_color="#555568")
        self.attach_btn.grid(row=0, column=0, padx=(0, 10), sticky="ns")
        
        self.msg_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Envoyer un message à Jarvis...", font=("Arial", 14))
        self.msg_entry.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.msg_entry.bind("<Return>", lambda e: self._send_message())
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="➤", width=60, font=("Arial", 18), command=self._send_message, fg_color="#E07A5F", hover_color="#D16043")
        self.send_btn.grid(row=0, column=2, sticky="ns")
        
        self.attachment_label = ctk.CTkLabel(self.main_area, text="", text_color="#7EC8E3", font=("Arial", 12))
        self.attachment_label.grid(row=2, column=0, sticky="w", padx=5)

    def _save_settings_ui(self, *args):
        self.config["serper_key"] = self.serper_var.get()
        self.config["gemini_key"] = self.gemini_var.get()
        self.config["enable_web"] = self.web_toggle_var.get()
        self.config["last_model"] = self.model_combo_var.get()
        self.config["temperature"] = self.temp_slider.get()
        self.config["system_prompt"] = self.prompt_box.get("1.0", "end-1c")
        save_config(self.config)

    def _load_models_async(self):
        def task():
            google_models = []
            if self.config["gemini_key"]:
                try:
                    client = genai.Client(api_key=self.config["gemini_key"])
                    for m in client.models.list():
                        if m.name.startswith('gemini') or m.name.startswith('models/gemini') or 'gemma' in m.name:
                            google_models.append(m.name)
                except: pass
            
            ollama_models = []
            try:
                ollama_models = [m['model'] for m in ollama.list()['models']]
            except: pass
            
            priority = ["models/gemma-3-27b-it", "models/gemma-3-1b-it", "gemini-2.5-flash"]
            options = []
            for p in priority:
                if p in google_models or self.config["gemini_key"]: options.append(p)
            options.extend(ollama_models)
            for g in google_models:
                if g not in options: options.append(g)
            
            if not options: options = ["gemini-1.5-flash"] + ollama_models
            
            self.after(0, lambda: self._update_model_combo(options))
        threading.Thread(target=task, daemon=True).start()

    def _update_model_combo(self, options):
        self.model_combo.configure(values=options)
        if self.config["last_model"] in options:
            self.model_combo.set(self.config["last_model"])
        elif options:
            self.model_combo.set(options[0])

    def _refresh_chat_history_list(self):
        files = get_chat_files()
        names = [os.path.basename(f).replace(".json", "") for f in files]
        self.chat_combo.configure(values=names)
        if self.current_chat_file in files:
            idx = files.index(self.current_chat_file)
            self.chat_combo.set(names[idx])
            self.chat_name_var.set(names[idx])

    def _new_chat(self):
        self.current_chat_file = create_new_chat()
        self._refresh_chat_history_list()
        self._load_current_chat()

    def _on_chat_selected(self, name):
        files = get_chat_files()
        for f in files:
            if os.path.basename(f).replace(".json", "") == name:
                self.current_chat_file = f
                self.chat_name_var.set(name)
                self._load_current_chat()
                break

    def _rename_chat(self):
        new_name = self.chat_name_var.get().strip()
        if not new_name: return
        safe_name = "".join([c for c in new_name if c.isalnum() or c in (' ', '-', '_')])
        if not safe_name: return
        new_path = os.path.join(CHATS_DIR, f"{safe_name}.json")
        if new_path != self.current_chat_file:
            try:
                os.rename(self.current_chat_file, new_path)
                self.current_chat_file = new_path
                self._refresh_chat_history_list()
            except: pass

    def _delete_chat(self):
        if self.current_chat_file and os.path.exists(self.current_chat_file):
            try: os.remove(self.current_chat_file)
            except: pass
            self._new_chat()

    def _load_current_chat(self):
        for widget in self.chat_scroll.winfo_children():
            widget.destroy()
        self.messages = load_chat(self.current_chat_file)
        for msg in self.messages:
            self._add_bubble(msg.get("role", "user"), msg.get("content", ""))
        
        # Force UI update so the canvas shrinks if the new chat is smaller
        self.chat_scroll.update_idletasks()
        self._scroll_to_bottom()

    def _add_bubble(self, role, text):
        if not text: return None
        text = text.strip()
        
        bg_color = "#33334d" if role == "user" else "#1e1e1e"
        text_color = "#ffffff" if role == "user" else "#cccccc"
        
        frame = ctk.CTkFrame(self.chat_scroll, fg_color=bg_color, corner_radius=10)
        frame.pack(fill="x", padx=10, pady=5)
        
        icon = "👤" if role == "user" else "🤖"
        
        # We put the icon directly in the text to avoid rendering layout shifts
        markdown_text = f"**{icon}** &nbsp; {text}"
        html_content = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "tables"])
        
        # Zero margins and padding on the wrapper div
        full_html = f"<div style='color: {text_color}; font-family: Arial, sans-serif; font-size: 14px; margin: 0; padding: 0;'>{html_content}</div>"
        
        tb = HTMLLabel(frame, html=full_html, background=bg_color, foreground=text_color, borderwidth=0, pady=0, padx=5)
        tb.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Better heuristic for height based on content length and line breaks
        # We also use a more generous base height
        lines_count = text.count('\n')
        wrapped_lines = sum(len(line) // 50 for line in text.split('\n')) 
        total_lines = lines_count + wrapped_lines + 3 # +3 for margins/padding and icon
        
        tb.configure(height=total_lines)
        
        # Ask tkhtmlview to calculate its own exact height after drawing
        self.after(100, lambda: self._fit_html_label(tb))
        
        return tb

    def _fit_html_label(self, tb):
        try:
            tb.update_idletasks()
            tb.fit_height()
            current_height = int(float(tb.cget("height")))
            if current_height < 3:
                tb.configure(height=3)
            else:
                tb.configure(height=current_height + 2) # Add generous padding to prevent cutoffs
            self._scroll_to_bottom()
        except Exception as e:
            print(f"Error in fit_height: {e}")

    def _scroll_to_bottom(self):
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _attach_file(self):
        paths = filedialog.askopenfilenames(title="Joindre des fichiers")
        if paths:
            self.attached_files.extend(paths)
            self.attachment_label.configure(text=f"📎 {len(self.attached_files)} fichier(s) joint(s)")

    def _send_message(self):
        if self.is_generating: return
        
        text = self.msg_entry.get().strip()
        if not text and not self.attached_files: return
        
        self.msg_entry.delete(0, "end")
        self._save_settings_ui() # Save config before generation
        
        file_context = ""
        images_pil = []
        images_bytes = []
        
        for filepath in self.attached_files:
            if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                try:
                    img = Image.open(filepath)
                    images_pil.append(img)
                    with io.BytesIO() as output: 
                        img.save(output, format=img.format)
                        images_bytes.append(output.getvalue())
                except: pass
            else:
                extracted = extract_text_from_file(filepath)
                file_context += f"\n\n--- FICHIER JOINT ({os.path.basename(filepath)}) ---\n{extracted}\n-------------------\n"
        
        self.attached_files = []
        self.attachment_label.configure(text="")
        
        final_prompt = text + file_context
        user_msg = {"role": "user", "content": final_prompt}
        if images_bytes: user_msg["images"] = images_bytes
        
        self.messages.append(user_msg)
        save_chat(self.current_chat_file, self.messages)
        
        display_text = text + (" 📎 (Fichiers joints)" if file_context or images_pil else "")
        self._add_bubble("user", display_text)
        
        # Prepare for assistant response
        self._current_assistant_bubble = self._add_bubble("assistant", "...")
        self.is_generating = True
        self.send_btn.configure(state="disabled")
        
        threading.Thread(target=self._generate_task, args=(final_prompt, images_pil), daemon=True).start()

    def _update_assistant_bubble(self, text, finalize=False):
        if not self._current_assistant_bubble: return
        text = text.strip()
        
        icon = "🤖"
        markdown_text = f"**{icon}** &nbsp; {text}"
        html_content = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "tables"])
        full_html = f"<div style='color: #cccccc; font-family: Arial, sans-serif; font-size: 14px; margin: 0; padding: 0;'>{html_content}</div>"
        
        self._current_assistant_bubble.set_html(full_html)
        
        lines_count = text.count('\n')
        wrapped_lines = sum(len(line) // 40 for line in text.split('\n'))
        total_lines = lines_count + wrapped_lines + 4
        
        self._current_assistant_bubble.configure(height=total_lines)
        self._scroll_to_bottom()
        
        if finalize:
            self.after(200, lambda tb=self._current_assistant_bubble: self._fit_html_label(tb, True))
            self.messages.append({"role": "assistant", "content": text})
            save_chat(self.current_chat_file, self.messages)
            self.is_generating = False
            self.send_btn.configure(state="normal")
            self._current_assistant_bubble = None

    def _fit_html_label(self, tb, finalize=False):
        try:
            tb.update_idletasks()
            tb.fit_height()
            current_height = int(float(tb.cget("height")))
            if current_height < 3:
                tb.configure(height=3)
            else:
                tb.configure(height=current_height + (3 if finalize else 1)) 
            self._scroll_to_bottom()
        except Exception as e:
            pass

    def _generate_task(self, prompt, images_pil):
# ... existing generate code ...
        current_model = self.config["last_model"]
        is_gemini = "gemini" in current_model or "models/" in current_model
        now_str = datetime.datetime.now().strftime("%d %B %Y à %H:%M")
        base_sys = self.config["system_prompt"]
        if "[DATE_DU_JOUR]" in base_sys: final_sys_prompt = base_sys.replace("[DATE_DU_JOUR]", now_str)
        else: final_sys_prompt = f"DATE ACTUELLE : {now_str}.\n\n{base_sys}"
        
        full_response = ""
        
        if is_gemini:
            if not self.config["gemini_key"]:
                self.after(0, lambda: self._update_assistant_bubble("❌ Clé Gemini manquante dans la configuration.", True))
                return
            try:
                client = genai.Client(api_key=self.config["gemini_key"])
                current_parts = [prompt] if prompt else []
                for img in images_pil: current_parts.append(img)
                
                history_gemini = []
                for m in self.messages[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    history_gemini.append({'role': role, 'parts': [{'text': m["content"]}]})

                tools_config = [{"google_search": {}}] if self.config["enable_web"] else None
                config = types.GenerateContentConfig(
                    system_instruction=final_sys_prompt,
                    temperature=self.config["temperature"],
                    tools=tools_config,
                )
                
                chat = client.chats.create(model=current_model, config=config, history=history_gemini)
                response = chat.send_message(current_parts)
                
                search_done = False
                try:
                    if response.candidates and response.candidates[0].grounding_metadata:
                         if getattr(response.candidates[0].grounding_metadata, 'search_entry_point', None):
                             search_done = True
                except: pass
                
                full_response = response.text
                if search_done:
                    try:
                        meta = response.candidates[0].grounding_metadata
                        html_src = meta.search_entry_point.rendered_content
                        # CTk cannot render HTML easily, we just append a note
                        full_response += f"\n\n[Recherche Google effectuée]"
                    except: pass
                
                self.after(0, lambda: self._update_assistant_bubble(full_response, True))
            except Exception as e:
                # Handle Fallback for Gemini without tools
                if "google_search" in str(e):
                    try:
                        self.after(0, lambda: self._update_assistant_bubble("⚠️ Recherche indisponible, tentative de réponse classique...", False))
                        fallback_config = types.GenerateContentConfig(system_instruction=final_sys_prompt, temperature=self.config["temperature"])
                        chat = client.chats.create(model=current_model, config=fallback_config, history=history_gemini)
                        response = chat.send_message(current_parts)
                        self.after(0, lambda: self._update_assistant_bubble(response.text, True))
                    except Exception as e2:
                        self.after(0, lambda: self._update_assistant_bubble(f"❌ Erreur API Fallback: {e2}", True))
                else:
                    self.after(0, lambda: self._update_assistant_bubble(f"❌ Erreur Gemini: {e}", True))
        
        else:
            # Ollama branch
            messages_payload = [{"role": "system", "content": final_sys_prompt + (" Utilise search_web si besoin." if self.config["enable_web"] else "")}]
            for m in self.messages:
                if isinstance(m, dict): messages_payload.append(m)
                else: messages_payload.append({"role": m.role, "content": m.content})
            
            options = {"temperature": self.config["temperature"], "num_ctx": self.config["ctx_size"]}
            
            def search_tool_wrapper(query):
                return search_google_serper(query, self.config["serper_key"])
                
            tools_list = [search_tool_wrapper] if self.config["enable_web"] else []
            
            try:
                # Initial call to check for tools
                response = ollama.chat(model=current_model, messages=messages_payload, tools=tools_list, options=options, stream=False)
                final_content = response['message'].get('content', '')
                tool_calls = response['message'].get('tool_calls', [])
                
                if not tool_calls and self.config["enable_web"] and final_content:
                     json_data = extract_json_mistral(final_content)
                     if json_data:
                         for item in json_data:
                             if 'name' in item: tool_calls.append({'function': {'name': item['name'], 'arguments': item.get('arguments', {})}})
                
                if not tool_calls:
                    self.after(0, lambda: self._update_assistant_bubble(final_content, True))
                    return
                
                # Handling Tool Calls
                if tool_calls and self.config["enable_web"]:
                    self.after(0, lambda: self._update_assistant_bubble(f"🌐 Recherche en cours...", False))
                    ia_req_msg = {"role": "assistant", "content": final_content}
                    messages_payload.append(ia_req_msg)
                    self.messages.append(ia_req_msg) # We technically should save this state but for brevity we keep it in memory
                    
                    for tool in tool_calls:
                        if isinstance(tool, dict): fn_args = tool['function']['arguments']
                        else: fn_args = tool.function.arguments
                        query = fn_args.get('q') or fn_args.get('query')
                        if query:
                            res = search_tool_wrapper(query)
                            tool_msg = {"role": "tool", "content": res}
                            messages_payload.append(tool_msg)
                            self.messages.append(tool_msg)
                    
                    # Stream the final response
                    self.after(0, lambda: self._update_assistant_bubble(f"🧠 Analyse des résultats...", False))
                    stream = ollama.chat(model=current_model, messages=messages_payload, stream=True, options=options)
                    full_response = ""
                    
                    # Streaming loop
                    last_update = time.time()
                    for chunk in stream:
                        full_response += chunk['message']['content']
                        # Limit UI updates to not freeze the thread (60 fps roughly)
                        if time.time() - last_update > 0.05:
                            text_copy = full_response + "▌"
                            self.after(0, lambda t=text_copy: self._update_assistant_bubble(t, False))
                            last_update = time.time()
                    
                    self.after(0, lambda: self._update_assistant_bubble(full_response, True))

            except Exception as e:
                self.after(0, lambda: self._update_assistant_bubble(f"❌ Erreur Ollama: {e}", True))

    def _start_streamlit_fallback(self):
        try:
            import sys
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "streamlit_app.py"))
            # Crucial: set cwd to APP_DIR so Streamlit finds config.json and conversations/
            self.streamlit_process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", script_path],
                cwd=APP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            messagebox.showinfo("Version Web", "La version Streamlit s'ouvrira dans votre navigateur web.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lancer Streamlit : {e}")

    def _cleanup(self):
        if os.name == 'nt':
            os.system("taskkill /F /IM ollama_app.exe >nul 2>&1")
            os.system("taskkill /F /IM ollama.exe >nul 2>&1")
        else: os.system("pkill ollama")
        if self.streamlit_process:
            try: self.streamlit_process.terminate()
            except: pass

    def _return_menu(self):
        if self.streamlit_process:
            try: self.streamlit_process.terminate()
            except: pass
        self.controller.show_menu()
