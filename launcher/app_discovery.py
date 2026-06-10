import os
import sys
import json
import importlib

def get_base_path():
    """Returns the absolute path to the directory containing the main script or EXE."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # dev mode
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_local_apps():
    """Ultra-robust app discovery with verbose logging."""
    base_path = get_base_path()
    cwd = os.getcwd()
    
    potential_dirs = [
        os.path.join(base_path, "apps"),
        os.path.join(cwd, "apps")
    ]
    
    log_msg = f"Base Path: {base_path}\nCWD: {cwd}\n"
    
    apps_dir = None
    for d in potential_dirs:
        log_msg += f"Scanning: {d} ... "
        if os.path.exists(d) and os.path.isdir(d):
            apps_dir = d
            log_msg += "FOUND\n"
            break
        else:
            log_msg += "NOT FOUND\n"
            
    if not apps_dir:
        # Don't show messagebox here to not spam, but keep log
        print(log_msg)
        return []

    # Ensure apps_dir is a package
    init_file = os.path.join(apps_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f: f.write("")

    if apps_dir not in sys.path:
        sys.path.insert(0, apps_dir)

    apps = []
    try:
        folders = os.listdir(apps_dir)
        for folder in folders:
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
                except Exception as e:
                    print(f"Error loading manifest in {folder}: {e}")
    except Exception as e:
        print(f"Error listing apps_dir: {e}")
    
    return apps

def get_remote_apps(github_manifest_url):
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
    
    # Try all naming conventions to avoid ImportErrors
    paths_to_try = [
        f"apps.{folder}.{entry_point}",
        f"{folder}.{entry_point}"
    ]
    
    last_err = None
    for module_path in paths_to_try:
        try:
            if module_path in sys.modules:
                importlib.reload(sys.modules[module_path])
            module = importlib.import_module(module_path)
            app_class = getattr(module, app_manifest['class_name'])
            return app_class
        except Exception as e:
            last_err = e
            continue
            
    raise last_err if last_err else ImportError(f"Impossible de trouver le module pour {folder}")
