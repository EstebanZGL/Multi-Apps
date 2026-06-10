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
    
    # Try to load the master list from install_manifest.json
    manifest_path = os.path.join(base_path, "install_manifest.json")
    all_apps_list = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_apps_list = data.get("apps", [])
        except: pass

    apps = []
    
    # If we have a master list, use it to detect what's installed
    if all_apps_list:
        for app_info in all_apps_list:
            app_id = app_info['id']
            app_folder = os.path.join(apps_dir, app_id)
            app_manifest_path = os.path.join(app_folder, "manifest.json")
            
            if os.path.exists(app_manifest_path):
                # Installed: Load the full manifest from disk
                try:
                    with open(app_manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                        manifest['folder'] = app_id
                        manifest['is_installed'] = True
                        apps.append(manifest)
                except: pass
            else:
                # Not installed: Use info from the catalog
                app_info['folder'] = app_id
                app_info['is_installed'] = False
                apps.append(app_info)
    else:
        # Fallback to legacy scanning if no manifest exists (Dev mode)
        if not os.path.exists(apps_dir): return []
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
