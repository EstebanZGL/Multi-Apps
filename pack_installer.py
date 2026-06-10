import os
import shutil
import zipfile
import json
import hashlib

# --- Configuration ---
SOURCE_DIR = os.getcwd()
APPS_DIR = os.path.join(SOURCE_DIR, "apps")
BUILD_DIR = os.path.join(SOURCE_DIR, "build_installer")
DATA_DIR = os.path.join(BUILD_DIR, "data")
MANIFEST_FILE = os.path.join(DATA_DIR, "install_manifest.json")

# Exclusions globales
GLOBAL_EXCLUDE_FILES = [".env", "config.json", ".gitignore", "GEMINI.md"]
GLOBAL_EXCLUDE_DIRS = ["__pycache__", ".git", ".pytest_cache", "conversations"]

def get_file_hash(filepath):
    hash_func = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def zip_directory(src_dir, zip_name, exclude_files=None, exclude_dirs=None):
    if exclude_files is None: exclude_files = []
    if exclude_dirs is None: exclude_dirs = []
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(src_dir):
            # Filtrage des dossiers
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files or file.endswith('.pyc'):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, src_dir)
                zipf.write(full_path, rel_path)

def prepare_packaging():
    print("🧹 Nettoyage du dossier build...")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)

    install_manifest = {
        "version": "1.0.0",
        "apps": [],
        "core_files": []
    }

    # 1. Packaging des Applications
    print("📦 Packaging des applications...")
    apps_output_dir = os.path.join(DATA_DIR, "apps")
    os.makedirs(apps_output_dir, exist_ok=True)

    for app_id in os.listdir(APPS_DIR):
        app_src = os.path.join(APPS_DIR, app_id)
        if os.path.isdir(app_src) and app_id != "__pycache__":
            print(f"  - {app_id}...")
            zip_path = os.path.join(apps_output_dir, f"{app_id}.zip")
            
            # Lire le manifest d'origine pour récupérer les infos
            orig_manifest_path = os.path.join(app_src, "manifest.json")
            app_info = {}
            if os.path.exists(orig_manifest_path):
                with open(orig_manifest_path, 'r', encoding='utf-8') as f:
                    app_info = json.load(f)

            # Zipper l'application
            zip_directory(app_src, zip_path, GLOBAL_EXCLUDE_FILES, GLOBAL_EXCLUDE_DIRS)
            
            # Ajouter au manifest d'installation
            install_manifest["apps"].append({
                "id": app_id,
                "name": app_info.get("name", app_id),
                "description": app_info.get("description", ""),
                "icon_text": app_info.get("icon_text", "📦"),
                "zip_file": f"apps/{app_id}.zip",
                "hash": get_file_hash(zip_path)
            })

    # 2. Packaging du Launcher Core
    print("🏠 Préparation du Core...")
    core_src = os.path.join(SOURCE_DIR, "dist", "Launcher_Universel")
    if os.path.exists(core_src):
        print("  - Compression du moteur principal...")
        core_zip_path = os.path.join(DATA_DIR, "core.zip")
        zip_directory(core_src, core_zip_path, GLOBAL_EXCLUDE_FILES, GLOBAL_EXCLUDE_DIRS)
        install_manifest["core_zip"] = "core.zip"
        install_manifest["core_hash"] = get_file_hash(core_zip_path)
    else:
        print("  ⚠️ Attention : dist/Launcher_Universel introuvable. Lancez 'build.py' d'abord !")

    # 3. Sauvegarde du manifest final
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(install_manifest, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Packaging terminé ! Les fichiers sont dans : {BUILD_DIR}")
    print(f"📄 Manifest généré avec {len(install_manifest['apps'])} applications.")

if __name__ == "__main__":
    prepare_packaging()
