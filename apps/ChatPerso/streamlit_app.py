import streamlit as st
import ollama
import requests
import json
import os
import glob
import time
import re
import subprocess
import datetime
from google import genai
from google.genai import types
from PIL import Image
import io
import PyPDF2
from docx import Document

st.set_page_config(page_title="Jarvis", layout="wide", page_icon="🤖")

# --- 0. AUTO-START OLLAMA ---
def ensure_ollama_running():
    try:
        ollama.list()
    except:
        if os.name == 'nt':
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

ensure_ollama_running()

# --- CSS ---
st.markdown("""
<style>
    .stChatMessage { border-radius: 12px; }
    div[data-testid="stVerticalBlock"] > div > button {
        border: none; background: transparent; color: #aaa; font-size: 0.8em;
    }
    div[data-testid="stVerticalBlock"] > div > button:hover {
        color: #ff4b4b; text-decoration: underline;
    }
    section[data-testid="stSidebar"] .stButton:first-of-type button {
        color: white; background-color: #ff4b4b; border: none; font-weight: bold;
    }
    section[data-testid="stSidebar"] .stButton:first-of-type button:hover {
        background-color: #ff0000; color: white;
    }
    @keyframes blink { 50% { opacity: 0; } }
    .typing-indicator { color: #888; animation: blink 1s linear infinite; }
    .google-source { font-size: 0.8em; background: #e8f0fe; color: #1a73e8; padding: 2px 6px; border-radius: 4px; text-decoration: none; margin-right: 5px; display: inline-block; margin-top: 5px;}
</style>
""", unsafe_allow_html=True)

# --- CONFIG ---
CONFIG_FILE = "config.json"

def load_config():
    default_config = {
        "serper_key": "",
        "gemini_key": "",
        # On insiste sur l'utilisation de l'outil dans le prompt
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

def save_config_callback():
    config = {
        "serper_key": st.session_state.setting_serper,
        "gemini_key": st.session_state.setting_gemini,
        "system_prompt": st.session_state.setting_prompt,
        "temperature": st.session_state.setting_temp,
        "ctx_size": st.session_state.setting_ctx,
        "enable_web": st.session_state.setting_web,
        "last_model": st.session_state.setting_model
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

app_config = load_config()

# --- STATE ---
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "trigger_regen" not in st.session_state: st.session_state.trigger_regen = False

# --- FILES & TOOLS ---
CHATS_DIR = "conversations"
if not os.path.exists(CHATS_DIR): os.makedirs(CHATS_DIR)

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
    filename = f"{CHATS_DIR}/chat_{timestamp}.json"
    save_chat(filename, [])
    return filename

def rename_chat(current_path, new_name):
    safe_name = "".join([c for c in new_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    if not safe_name: safe_name = "Conversation"
    new_path = f"{CHATS_DIR}/{safe_name}.json"
    if current_path != new_path:
        try: os.rename(current_path, new_path); return new_path
        except OSError: st.error("Nom invalide."); return current_path
    return current_path

def extract_text_from_file(uploaded_file):
    text = ""
    MAX_CHARS = 25000 
    try:
        if uploaded_file.type == "application/pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
                if len(text) > MAX_CHARS: text += "\n\n[... TRONQUÉ ...]"; break
        elif "word" in uploaded_file.type:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
                if len(text) > MAX_CHARS: break
        else:
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors='ignore'))
            text = stringio.read()
            if len(text) > MAX_CHARS: text = text[:MAX_CHARS]
        return text
    except Exception as e: return f"Erreur: {e}"

# Outil Serper (Pour Ollama)
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

def search_tool(query, **kwargs):
    return search_google_serper(query, st.session_state.setting_serper)

def extract_json_mistral(text):
    pattern = re.compile(r'\[\s*\{.*?\}\s*\]', re.DOTALL)
    match = pattern.search(text)
    if match:
        try: return json.loads(match.group(0))
        except: return None
    return None

# --- FONCTION SCANNER GOOGLE ---
@st.cache_data(ttl=3600)
def get_google_models(api_key):
    if not api_key: return []
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            if m.name.startswith('gemini') or m.name.startswith('models/gemini') or 'gemma' in m.name:
                models.append(m.name)
        models.sort()
        return models
    except Exception as e:
        return []

# --- SIDEBAR ---
with st.sidebar:
    col_logo, col_title = st.columns([0.2, 0.8])
    with col_title: st.title("Jarvis")
    
    if st.button("🔴 OFF (Tout éteindre)", use_container_width=True):
        st.toast("Arrêt du système...", icon="🛑")
        if os.name == 'nt':
            os.system("taskkill /F /IM ollama_app.exe >nul 2>&1")
            os.system("taskkill /F /IM ollama.exe >nul 2>&1")
        else: os.system("pkill ollama")
        st.components.v1.html("<script>window.close();</script>", height=0, width=0)
        time.sleep(0.5); os._exit(0)
    
    st.divider()

    with st.expander("🔑 Clés API", expanded=False):
        st.text_input("Serper Key (Ollama)", value=app_config["serper_key"], type="password", key="setting_serper", on_change=save_config_callback)
        st.text_input("Gemini Key (Google)", value=app_config["gemini_key"], type="password", key="setting_gemini", on_change=save_config_callback)

    if st.button("➕ Nouveau Chat", use_container_width=True):
        new_file = create_new_chat()
        st.session_state.current_chat = new_file; st.rerun()

    chat_files = get_chat_files()
    if not chat_files: create_new_chat(); chat_files = get_chat_files()
    if "current_chat" not in st.session_state or st.session_state.current_chat not in chat_files:
        st.session_state.current_chat = chat_files[0]

    selected_file = st.selectbox("Historique", options=chat_files, 
                                 format_func=lambda x: os.path.basename(x).replace(".json", ""),
                                 index=chat_files.index(st.session_state.current_chat))
    if selected_file != st.session_state.current_chat: st.session_state.current_chat = selected_file; st.rerun()

    current_name = os.path.basename(st.session_state.current_chat).replace(".json", "")
    new_name = st.text_input("Nom", value=current_name)
    if new_name != current_name: st.session_state.current_chat = rename_chat(st.session_state.current_chat, new_name); st.rerun()

    st.divider()
    
    # LISTE MODÈLES
    google_available = []
    if app_config["gemini_key"]:
        google_available = get_google_models(app_config["gemini_key"])
    
    ollama_available = []
    try:
        ollama_available = [m['model'] for m in ollama.list()['models']]
    except: pass
    
    # Ordre de priorité personnalisé: Gemma 3 27B, Gemma 3 1B, Gemini 2.5 Flash, Ollama, Autres Google
    priority_models = ["models/gemma-3-27b-it", "models/gemma-3-1b-it", "gemini-2.5-flash"]
    
    model_options = []
    
    # 1. Les 3 modèles de google en priorité (s'ils existent dans ce qu'on a récupéré, ou on les force)
    for p_model in priority_models:
        if p_model in google_available or app_config["gemini_key"]:
            model_options.append(p_model)
    
    # 2. Les Ollama
    model_options.extend(ollama_available)
    
    # 3. Les autres Google
    for g_model in google_available:
        if g_model not in model_options:
             model_options.append(g_model)
             
    if not model_options:
        model_options = ["gemini-1.5-flash"] + ollama_available
    
    current_selection = app_config["last_model"]
    if current_selection not in model_options: 
        if model_options: current_selection = model_options[0]
        else: current_selection = "gemini-1.5-flash"

    st.selectbox("Modèle", model_options, index=model_options.index(current_selection) if current_selection in model_options else 0, key="setting_model", on_change=save_config_callback)
    
    if google_available:
        st.caption(f"✅ {len(google_available)} modèles Google détectés.")
        st.markdown("[📊 Voir mes crédits Restants](https://aistudio.google.com/rate-limit?timeRange=this-month&project=gen-lang-client-0220948768)")
    elif app_config["gemini_key"]:
        st.caption("⚠️ Impossible de lister les modèles Google.")

    st.toggle("🌐 Internet", value=app_config["enable_web"], key="setting_web", on_change=save_config_callback)
    st.text_area("System Prompt", value=app_config["system_prompt"], key="setting_prompt", on_change=save_config_callback)
    st.slider("Temp", 0.0, 1.0, app_config["temperature"], key="setting_temp", on_change=save_config_callback)
    st.select_slider("Contexte", [4096, 8192, 16384, 32768], value=app_config["ctx_size"], key="setting_ctx", on_change=save_config_callback)

    st.divider()
    if st.button("🗑️ Supprimer Chat", type="primary"):
        os.remove(st.session_state.current_chat); del st.session_state.current_chat; st.rerun()

# --- MAIN CHAT ---
messages = load_chat(st.session_state.current_chat)
st.title(os.path.basename(st.session_state.current_chat).replace(".json", ""))

for i, msg in enumerate(messages):
    if isinstance(msg, dict): role, content = msg.get("role"), msg.get("content")
    else: role, content = getattr(msg, "role", ""), getattr(msg, "content", "")
    if role == "user":
        with st.chat_message("user"):
            c1, c2 = st.columns([0.95, 0.05])
            c1.markdown(content)
            if c2.button("↩", key=f"rw_{i}"): messages = messages[:i]; save_chat(st.session_state.current_chat, messages); st.rerun()
    elif role == "assistant":
        if content and not extract_json_mistral(content) and content.strip():
            with st.chat_message("assistant"): st.markdown(content, unsafe_allow_html=True)

with st.expander("📎 Fichiers / Photos", expanded=False):
    uploaded_files = st.file_uploader("Ajouter", accept_multiple_files=True, key=st.session_state.uploader_key)

if messages and messages[-1]['role'] == 'assistant':
    if st.button("🔄 Régénérer"): messages.pop(); save_chat(st.session_state.current_chat, messages); st.session_state.trigger_regen = True; st.rerun()

# --- LOGIQUE ---
user_input = st.chat_input("Message...")
should_generate = False

if user_input:
    file_context = ""
    images_pil = [] 
    images_bytes = [] 
    
    if uploaded_files:
        for file in uploaded_files:
            if file.type.startswith('image/'):
                img = Image.open(file)
                images_pil.append(img) 
                with io.BytesIO() as output: 
                    img.save(output, format=img.format)
                    images_bytes.append(output.getvalue()) 
            else:
                extracted = extract_text_from_file(file)
                file_context += f"\n\n--- FICHIER JOINT ({file.name}) ---\n{extracted}\n-------------------\n"
        st.session_state.uploader_key += 1
        
    final_prompt = user_input + file_context
    user_msg = {"role": "user", "content": final_prompt}
    if images_bytes: user_msg["images"] = images_bytes 
    messages.append(user_msg); save_chat(st.session_state.current_chat, messages)
    with st.chat_message("user"): st.markdown(user_input + (" 📎" if uploaded_files else ""))
    should_generate = True
    if "gemini" in st.session_state.setting_model or "models/" in st.session_state.setting_model: 
        st.session_state.current_pil_images = images_pil

elif st.session_state.trigger_regen:
    st.session_state.trigger_regen = False; should_generate = True

# --- GÉNÉRATION ---
if should_generate:
    current_model = st.session_state.setting_model
    is_gemini = "gemini" in current_model or "models/" in current_model
    
    # INJECTION DATE
    now_str = datetime.datetime.now().strftime("%d %B %Y à %H:%M")
    base_sys = st.session_state.setting_prompt or "Tu es un assistant utile."
    if "[DATE_DU_JOUR]" in base_sys:
        final_sys_prompt = base_sys.replace("[DATE_DU_JOUR]", now_str)
    else:
        final_sys_prompt = f"DATE ACTUELLE : {now_str}.\n\n{base_sys}"

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown('<p class="typing-indicator">...</p>', unsafe_allow_html=True)
        full_response = ""
        
        # --- BRANCHE GOOGLE ---
        if is_gemini:
            if not st.session_state.setting_gemini: st.error("Clé Gemini manquante !"); st.stop()
            try:
                client = genai.Client(api_key=st.session_state.setting_gemini)
                
                # PREP MESSAGE
                current_parts = []
                if messages[-1]["content"]:
                    current_parts.append(messages[-1]["content"])

                pil_imgs = st.session_state.get("current_pil_images", [])
                for img in pil_imgs: current_parts.append(img)
                if "current_pil_images" in st.session_state: del st.session_state.current_pil_images
                
                history_gemini = []
                for m in messages[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    history_gemini.append({'role': role, 'parts': [{'text': m["content"]}]})

                tools_config = None
                if st.session_state.setting_web:
                    tools_config = [{"google_search": {}}]

                config = types.GenerateContentConfig(
                    system_instruction=final_sys_prompt,
                    temperature=st.session_state.setting_temp,
                    tools=tools_config,
                )
                
                # APPEL
                chat = client.chats.create(model=current_model, config=config, history=history_gemini)
                
                try:
                    response = chat.send_message(current_parts)
                    
                    search_done = False
                    try:
                        if response.candidates and response.candidates[0].grounding_metadata:
                             if getattr(response.candidates[0].grounding_metadata, 'search_entry_point', None):
                                 search_done = True
                    except:
                        pass
                    
                    full_response = response.text
                    
                    # DETECTION SIMULATION
                    if "Search(" in full_response or "[Insérer" in full_response:
                        if not search_done:
                             st.warning("⚠️ L'IA simule la recherche (Problème de compte/modèle).")

                    if search_done:
                        try:
                            meta = response.candidates[0].grounding_metadata
                            html_src = meta.search_entry_point.rendered_content
                            placeholder.markdown(full_response + f"<br>{html_src}", unsafe_allow_html=True)
                        except:
                            placeholder.markdown(full_response)
                    else:
                        placeholder.markdown(full_response)
                        
                except Exception as e:
                    err_msg = str(e)
                    if "Unknown field" in err_msg or "AttributeError" in err_msg or "google_search" in err_msg:
                        try:
                            st.toast("Recherche Google indisponible sur ce compte (Mode Fallback texte seul).", icon="⚠️")
                            fallback_config = types.GenerateContentConfig(
                                system_instruction=final_sys_prompt,
                                temperature=st.session_state.setting_temp,
                            )
                            chat = client.chats.create(model=current_model, config=fallback_config, history=history_gemini)
                            response = chat.send_message(current_parts)
                            placeholder.markdown(response.text)
                        except Exception as e2:
                            st.error(f"Erreur Fallback API : {e2}")
                    elif "429" in err_msg:
                        st.error("⚠️ Quota dépassé. Attendez un peu.")
                    elif "404" in err_msg:
                        st.error(f"⚠️ Modèle {current_model} introuvable.")
                    else:
                        st.error(f"Erreur API : {e}")

            except Exception as e:
                st.error(f"Erreur Gemini : {e}")

        # --- BRANCHE OLLAMA ---
        else:
            messages_payload = []
            messages_payload.append({"role": "system", "content": final_sys_prompt + (" Utilise search_web si besoin." if st.session_state.setting_web else "")})
            for m in messages:
                if isinstance(m, dict): messages_payload.append(m)
                else: messages_payload.append(m.model_dump())
            
            options = {"temperature": st.session_state.setting_temp, "num_ctx": st.session_state.setting_ctx}
            tools_list = [search_tool] if st.session_state.setting_web else []

            try:
                response = ollama.chat(model=current_model, messages=messages_payload, tools=tools_list, options=options, stream=False)
                final_content = response['message']['content']
                tool_calls = []
                
                if response['message'].get('tool_calls'):
                    tool_calls = response['message'].get('tool_calls')
                elif st.session_state.setting_web:
                     json_data = extract_json_mistral(final_content)
                     if json_data:
                         for item in json_data:
                             if 'name' in item: tool_calls.append({'function': {'name': item['name'], 'arguments': item.get('arguments', {})}})
                
                if not tool_calls:
                    placeholder.markdown(final_content)
                    full_response = final_content
                
                if tool_calls and st.session_state.setting_web:
                    ia_req_msg = {"role": "assistant", "content": final_content}
                    messages_payload.append(ia_req_msg)
                    messages.append(ia_req_msg)
                    
                    for tool in tool_calls:
                        if isinstance(tool, dict): fn_args = tool['function']['arguments']
                        else: fn_args = tool.function.arguments
                        with st.status(f"🌐 Recherche : {fn_args.get('q') or fn_args.get('query')}", state="running") as status:
                            res = search_tool(fn_args.get('q') or fn_args.get('query'))
                            tool_msg = {"role": "tool", "content": res}
                            messages_payload.append(tool_msg)
                            messages.append(tool_msg)
                            status.update(label="Reçu", state="complete")
                    
                    placeholder.markdown('<p class="typing-indicator">...</p>', unsafe_allow_html=True)
                    stream = ollama.chat(model=current_model, messages=messages_payload, stream=True, options=options)
                    full_response = ""
                    for chunk in stream:
                        full_response += chunk['message']['content']
                        placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)

            except Exception as e: st.error(f"Erreur Ollama: {e}")

        if full_response:
            messages.append({"role": "assistant", "content": full_response})
            save_chat(st.session_state.current_chat, messages)
            st.rerun()
