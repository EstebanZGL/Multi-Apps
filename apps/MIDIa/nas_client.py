import os
import json
import requests

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "nas_config.json")

def load_nas_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "url": "https://nxt.xavest-truenas.fr/remote.php/dav/files/esteban/",
        "username": "esteban",
        "password": "",
        "folder": "Piano/MIDI"
    }

def save_nas_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def test_nas_connection(config):
    url = config.get("url", "").rstrip('/')
    username = config.get("username", "")
    password = config.get("password", "")
    if not url or not username or not password:
        return False, "Champs obligatoires manquants."
    try:
        # Check Nextcloud connection using PROPFIND on the base URL
        r = requests.request('PROPFIND', url, auth=(username, password), headers={'Depth': '0'}, timeout=10)
        if r.status_code in [200, 207]:
            return True, "Connexion réussie !"
        else:
            return False, f"Erreur de connexion (HTTP {r.status_code})."
    except Exception as e:
        return False, f"Erreur réseau : {str(e)}"

def ensure_nas_folder(base_url, folder_path, username, password):
    segments = [s for s in folder_path.replace('\\', '/').split('/') if s]
    current_url = base_url.rstrip('/')
    for segment in segments:
        current_url += '/' + segment
        # Check if this folder already exists
        r = requests.request('PROPFIND', current_url, auth=(username, password), headers={'Depth': '0'}, timeout=10)
        if r.status_code not in [200, 207]:
            # Try to create it
            r_mkcol = requests.request('MKCOL', current_url, auth=(username, password), timeout=10)
            if r_mkcol.status_code not in [201, 405]: # 201 Created, 405 Method Not Allowed (already exists)
                raise Exception(f"Impossible de créer le dossier '{segment}' (HTTP {r_mkcol.status_code})")
    return current_url

def upload_midi_to_nas(midi_filepath, config):
    url = config.get("url", "").rstrip('/')
    username = config.get("username", "")
    password = config.get("password", "")
    folder = config.get("folder", "")
    
    if not url or not username or not password:
        raise Exception("Configuration NAS incomplète.")
        
    dest_folder_url = ensure_nas_folder(url, folder, username, password)
    
    filename = os.path.basename(midi_filepath)
    dest_file_url = dest_folder_url.rstrip('/') + '/' + filename
    
    with open(midi_filepath, 'rb') as f:
        r = requests.put(dest_file_url, data=f, auth=(username, password), timeout=30)
        
    if r.status_code not in [200, 201, 204]:
        raise Exception(f"Échec de l'envoi du fichier (HTTP {r.status_code})")
    return dest_file_url
