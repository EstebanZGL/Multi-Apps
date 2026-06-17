import os
import shutil
import subprocess

def run_git(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Erreur Git: {' '.join(args)}\n{result.stderr}")
        return False
    return True

def deploy():
    print("🛰️ Préparation du déploiement vers GitHub (branche builds)...")
    
    # 1. Sauvegarder la branche actuelle
    current_branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    
    # 2. Vérifier si le dossier build existe
    build_data_dir = os.path.abspath("build_installer/data")
    if not os.path.exists(build_data_dir):
        print("❌ Dossier build_installer/data introuvable. Lancez pack_installer.py d'abord.")
        return

    # 3. Basculer sur la branche builds
    print(f"🌿 Passage sur la branche 'builds'...")
    if not run_git(["checkout", "builds"]): return

    # 4. Nettoyer et copier les nouveaux fichiers
    print("📂 Mise à jour des données...")
    target_data_dir = "data"
    if os.path.exists(target_data_dir):
        shutil.rmtree(target_data_dir)
    
    # Copie sélective : on ignore les fichiers > 100 Mo pour Git
    os.makedirs(target_data_dir, exist_ok=True)
    for root, dirs, files in os.walk(build_data_dir):
        rel_root = os.path.relpath(root, build_data_dir)
        dest_root = os.path.join(target_data_dir, rel_root)
        os.makedirs(dest_root, exist_ok=True)
        
        for f in files:
            src_file = os.path.join(root, f)
            if os.path.getsize(src_file) < 100 * 1024 * 1024: # 100 Mo
                shutil.copy2(src_file, os.path.join(dest_root, f))
            else:
                print(f"  ⚠️ Ignoré (trop lourd pour Git) : {f}")

    # 5. Commit et Push
    print("📤 Envoi vers GitHub...")
    # Utiliser -f pour forcer l'ajout des .zip qui sont dans le .gitignore
    run_git(["add", "-f", "data"])
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if status:
        run_git(["commit", "-m", "🚀 Mise à jour automatique des builds d'applications"])
        run_git(["push", "origin", "builds", "--force"])
    else:
        print("  ℹ️ Aucun changement à déployer.")

    # 6. Retourner sur la branche d'origine
    print(f"🔄 Retour sur la branche '{current_branch}'...")
    run_git(["checkout", current_branch])

    print("\n✅ Déploiement terminé ! Vos utilisateurs peuvent maintenant installer les dernières versions.")

if __name__ == "__main__":
    deploy()
