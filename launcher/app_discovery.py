import os
import sys
import json
import importlib

def get_base_path():
    """Returns the absolute path to the directory containing the main script or EXE."""
    if getattr(sys, 'frozen', False):
        # When frozen, we want the directory where the EXE is located, NOT _MEIPASS
        return os.path.dirname(sys.executable)
    # When running as script
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_local_apps():
    """Returns only apps physically present in the apps/ folder."""
    base_path = get_base_path()
    apps_dir = os.path.join(base_path, "apps")
    
    # Crucial: Add apps_dir to sys.path so we can import them dynamically
    if apps_dir not in sys.path:
        sys.path.insert(0, apps_dir)
        # Also add base_path for absolute imports
        if base_path not in sys.path:
            sys.path.insert(0, base_path)

    apps = []
    if not os.path.exists(apps_dir):
        return apps

    for folder in os.listdir(apps_dir):
        if folder.startswith(('.', '__')): continue
        app_folder = os.path.join(apps_dir, folder)
        if not os.path.isdir(app_folder): continue
        
        m_path = os.path.join(app_folder, "manifest.json")
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

def load_app_module(app_manifest):
    folder = app_manifest['folder']
    entry_point = app_manifest['entry_point']
    
    # We try both apps.folder.entry_point AND folder.entry_point
    # depending on how the sys.path was set.
    try:
        module_path = f"apps.{folder}.{entry_point}"
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
        module = importlib.import_module(module_path)
    except ImportError:
        module_path = f"{folder}.{entry_point}"
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
        module = importlib.import_module(module_path)
        
    app_class = getattr(module, app_manifest['class_name'])
    return app_class
