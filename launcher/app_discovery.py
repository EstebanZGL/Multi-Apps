import os
import sys
import json
import importlib

def get_base_path():
    """Returns the base path of the application (where main.py or the EXE is)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_local_apps():
    """Returns only apps physically present in the apps/ folder."""
    base_path = get_base_path()
    apps_dir = os.path.join(base_path, "apps")
    apps = []
    
    if not os.path.exists(apps_dir):
        return apps

    for folder in os.listdir(apps_dir):
        if folder.startswith(('.', '__')): continue
        m_path = os.path.join(apps_dir, folder, "manifest.json")
        if os.path.exists(m_path):
            try:
                with open(m_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    manifest['folder'] = folder
                    manifest['is_installed'] = True
                    apps.append(manifest)
            except: pass
    return apps

def get_remote_apps(github_manifest_url):
    """Fetches the latest manifest from GitHub to see what's available."""
    try:
        import requests
        r = requests.get(github_manifest_url, timeout=5)
        r.raise_for_status()
        return r.json().get("apps", [])
    except:
        return []

def discover_apps():
    """Legacy wrapper for compatibility, returns local apps."""
    return get_local_apps()

def load_app_module(app_manifest):
    folder = app_manifest['folder']
    entry_point = app_manifest['entry_point']
    module_path = f"apps.{folder}.{entry_point}"
    # Let exceptions bubble up so the UI can display them
    if module_path in sys.modules:
        importlib.reload(sys.modules[module_path])
    module = importlib.import_module(module_path)
    app_class = getattr(module, app_manifest['class_name'])
    return app_class
