import os
import sys
import json
import importlib

def get_base_path():
    """Returns the base path of the application (where main.py or the EXE is)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def discover_apps():
    base_path = get_base_path()
    apps_dir = os.path.join(base_path, "apps")
    apps = []
    
    print(f"DEBUG: Searching apps in {apps_dir}")
    
    if not os.path.exists(apps_dir):
        print(f"DEBUG: Apps directory not found: {apps_dir}")
        return apps

    for folder in os.listdir(apps_dir):
        # Skip __pycache__ and other hidden folders
        if folder.startswith(('.', '__')):
            continue
            
        manifest_path = os.path.join(apps_dir, folder, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    manifest['folder'] = folder
                    apps.append(manifest)
                    print(f"DEBUG: Found app: {manifest['name']} in {folder}")
            except Exception as e:
                print(f"DEBUG: Error loading manifest in {folder}: {e}")
    
    print(f"DEBUG: Total apps found: {len(apps)}")
    return apps

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
