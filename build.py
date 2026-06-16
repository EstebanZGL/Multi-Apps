import os
import sys
import shutil
import hashlib
import json
import PyInstaller.__main__
import customtkinter

# --- Configuration ---
DIST_NAME = "Launcher_Universel"
LOCAL_DIST = os.path.abspath("dist")
TARGET_PATH = os.path.join(LOCAL_DIST, DIST_NAME)
VERSIONS_FILE = "versions.json"
APPS_DIR = "apps"
LAUNCHER_DIRS = ["launcher", "core", "assets"]
MAIN_FILE = "main.py"
REQUIREMENTS_FILE = "requirements.txt"

def get_dir_hash(directory):
    """Calculates a hash for a directory's contents."""
    hash_func = hashlib.md5()
    for root, _, files in os.walk(directory):
        for names in sorted(files):
            if names.endswith(('.py', '.json', '.png', '.ico', '.txt')):
                filepath = os.path.join(root, names)
                with open(filepath, 'rb') as f:
                    while chunk := f.read(8192):
                        hash_func.update(chunk)
    return hash_func.hexdigest()

def get_file_hash(filepath):
    """Calculates a hash for a single file."""
    if not os.path.exists(filepath): return ""
    hash_func = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def load_versions():
    if os.path.exists(VERSIONS_FILE):
        with open(VERSIONS_FILE, 'r') as f:
            return json.load(f)
    return {"launcher": {"version": "1.0.0", "last_build_hash": ""}, "apps": {}}

def save_versions(versions):
    with open(VERSIONS_FILE, 'w') as f:
        json.dump(versions, f, indent=4)

def increment_version(version_str):
    parts = version_str.split('.')
    parts[-1] = str(int(parts[-1]) + 1)
    return '.'.join(parts)

def sync_apps_to_dist():
    """Copy apps files directly to the dist folder (Fast Sync)."""
    dist_apps_path = os.path.join(TARGET_PATH, "apps")
    if os.path.exists(dist_apps_path):
        # We don't rmtree to be fast, just copy2 which overwrites
        for app_id in os.listdir(APPS_DIR):
            src = os.path.join(APPS_DIR, app_id)
            if os.path.isdir(src) and app_id != "__pycache__":
                dst = os.path.join(dist_apps_path, app_id)
                shutil.copytree(src, dst, dirs_exist_ok=True)
        print("✅ Apps synchronisées dans le dossier dist (Mode Rapide).")

def run_full_build():
    """Runs the full PyInstaller build."""
    print("🚀 Lancement d'un build complet PyInstaller...")
    customtkinter_path = os.path.dirname(customtkinter.__file__)
    icon_path = os.path.abspath("assets/app_icon.ico")
    apps_dir_path = os.path.abspath("apps")

    # Temporary build paths
    import tempfile
    temp_dir = os.path.join(tempfile.gettempdir(), "pyinstaller_build_launcher")
    build_dir = os.path.join(temp_dir, "build")
    spec_dir = os.path.join(temp_dir, "spec")
    dist_temp_dir = os.path.join(temp_dir, "dist")

    for d in [build_dir, spec_dir, dist_temp_dir]:
        if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)

    PyInstaller.__main__.run([
        MAIN_FILE,
        f'--name={DIST_NAME}',
        '--onedir', '--windowed', '--noconfirm', '--clean',
        f'--icon={icon_path}',
        f'--add-data={customtkinter_path};customtkinter/', 
        f'--add-data={apps_dir_path};apps/',
        f'--workpath={build_dir}', f'--specpath={spec_dir}', f'--distpath={dist_temp_dir}',
        '--hidden-import=apps.downloader.app',
        '--hidden-import=apps.ChatPerso.app',
        '--hidden-import=apps.CERviable.app',
    ])

    os.makedirs(LOCAL_DIST, exist_ok=True)
    if os.path.exists(TARGET_PATH): shutil.rmtree(TARGET_PATH, ignore_errors=True)
    shutil.move(os.path.join(dist_temp_dir, DIST_NAME), TARGET_PATH)
    print(f"✨ Build complet terminé : {TARGET_PATH}")

def main():
    versions = load_versions()
    
    # Check Launcher Core
    launcher_hash_combined = get_file_hash(MAIN_FILE) + get_file_hash(REQUIREMENTS_FILE)
    for d in LAUNCHER_DIRS:
        if os.path.exists(d): launcher_hash_combined += get_dir_hash(d)
    
    launcher_changed = launcher_hash_combined != versions["launcher"].get("last_build_hash")
    
    # Check Apps
    apps_changed = []
    for app_id in os.listdir(APPS_DIR):
        app_path = os.path.join(APPS_DIR, app_id)
        if os.path.isdir(app_path) and app_id != "__pycache__":
            app_hash = get_dir_hash(app_path)
            if app_id not in versions["apps"] or versions["apps"][app_id]["last_build_hash"] != app_hash:
                apps_changed.append(app_id)
                if app_id not in versions["apps"]:
                    versions["apps"][app_id] = {"version": "1.0.0", "last_build_hash": app_hash}
                else:
                    versions["apps"][app_id]["version"] = increment_version(versions["apps"][app_id]["version"])
                    versions["apps"][app_id]["last_build_hash"] = app_hash

    if not os.path.exists(TARGET_PATH) or launcher_changed:
        print("🛠️ Changement détecté dans le Launcher ou build manquant.")
        versions["launcher"]["version"] = increment_version(versions["launcher"]["version"])
        versions["launcher"]["last_build_hash"] = launcher_hash_combined
        run_full_build()
        save_versions(versions)
    elif apps_changed:
        print(f"💡 Changements détectés dans les apps : {', '.join(apps_changed)}")
        # If the dist folder exists, we can just sync the files
        if os.path.exists(TARGET_PATH):
            sync_apps_to_dist()
            save_versions(versions)
            print("🚀 Mise à jour rapide effectuée (pas de re-compilation nécessaire).")
        else:
            run_full_build()
            save_versions(versions)
    else:
        print("✅ Tout est à jour. Aucun build nécessaire.")

if __name__ == "__main__":
    main()
