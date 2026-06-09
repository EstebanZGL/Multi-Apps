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
    
    shutil.copytree(build_data_dir, target_data_dir)

    # 5. Commit et Push
    print("📤 Envoi vers GitHub...")
    run_git(["add", "data"])
    run_git(["commit", "-m", "🚀 Mise à jour automatique des builds d'applications"])
    run_git(["push", "origin", "builds"])

    # 6. Retourner sur la branche d'origine
    print(f"🔄 Retour sur la branche '{current_branch}'...")
    run_git(["checkout", current_branch])

    print("\n✅ Déploiement terminé ! Vos utilisateurs peuvent maintenant installer les dernières versions.")

if __name__ == "__main__":
    deploy()
