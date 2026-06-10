# Workflow Technique : Multivers Web-Installer 🛠️

Ce document détaille la logique critique du système de distribution, de la préparation sur le PC développeur à l'installation finale chez l'utilisateur.

---

## 🏗️ 1. Phase de Packaging (`pack_installer.py`)
Le but est de créer un catalogue d'applications "vierges" (sans données privées).

1. **Scan Dynamique** : Le script parcourt le dossier `apps/` et identifie chaque dossier ayant un `manifest.json`.
2. **Exclusion Sélective (Sécurité)** :
   - Ignore systématiquement : `config.json`, `.env`, `**/conversations/`, `__pycache__`.
   - Garantit qu'aucune donnée de chat ou clé API n'est exportée.
3. **Dual-Core Logic (Optimisation GitHub)** :
   - Crée `core.zip` (Moteur principal) en **excluant** les binaires lourds (>100Mo comme FFmpeg) pour respecter les limites de Git.
   - Crée `ffmpeg.zip` à part pour un téléchargement optionnel.
4. **Manifest de Distribution** : Génère `install_manifest.json` contenant les ID, noms, descriptions, hashes MD5 et noms des fichiers ZIP.

---

## 🛰️ 2. Phase de Déploiement (`deploy_builds.py`)
Le pont entre le PC local et le serveur de téléchargement (GitHub).

1. **Isolation de Branche** : Bascule sur la branche orpheline `builds`.
2. **Nettoyage Automatique** : Supprime l'ancien dossier `data/` pour éviter d'accumuler des fichiers obsolètes.
3. **Synchronisation "Light"** : Copie uniquement les fichiers < 100 Mo vers la branche (ignore les zips trop lourds qui devront être gérés via les Releases).
4. **Push Forcé** : Utilise `git push --force` pour maintenir un historique de builds ultra-léger et rapide à charger pour l'installateur.

---

## 🚀 3. Phase d'Installation (`multivers_installer.py`)
Le client final utilisé par les utilisateurs.

### A. Initialisation & Découverte
- Requête `GET` vers GitHub Raw pour charger le `install_manifest.json`.
- Comparaison avec le `install_manifest.json` local (dans `%APPDATA%`) pour détecter les mises à jour.

### B. Cycle d'Installation (Séquentiel)
1. **Moteur Principal (Core)** : Téléchargé et extrait à la racine de `%APPDATA%/MultiversLauncher`.
2. **Modules (Apps)** : Chaque application cochée est téléchargée et extraite dans son propre sous-dossier `apps/`.
3. **Dépendances Binaires** : Si l'app `downloader` est choisie, l'installateur récupère `ffmpeg.zip` et l'extrait dans `bin/`.
4. **Intégration Windows** :
   - Utilisation de **PowerShell** (via `WScript.Shell`) pour créer les fichiers `.lnk` sur le Bureau et dans le Menu Démarrer.
   - Pointage du `WorkingDirectory` vers `%APPDATA%` pour que l'app trouve ses bibliothèques.

---

## 🧠 4. Cas Spécifique : HackGPT (IA)
Logique d'importation automatique dans Ollama.

1. **Lien Externe** : Téléchargement depuis un dossier Nextcloud (évite de saturer GitHub).
2. **Persistence** : La tâche de téléchargement tourne en tâche de fond, permettant de fermer/rouvrir la fenêtre de gestion sans couper le flux.
3. **Importation "Zero-Config"** :
   - Extraction des Blobs et du Manifeste.
   - Identification automatique du fichier de modèle le plus lourd.
   - Génération d'un `Modelfile` temporaire sur la machine cible.
   - Exécution de `ollama create HackGPT -f Modelfile`.
4. **Nettoyage** : Suppression immédiate des 5 Go de fichiers temporaires après l'importation (ou en cas d'annulation).

---

## 🛑 Gestion des Erreurs & Sécurité
- **Signal d'Annulation** : Utilisation de `threading.Event()` pour stopper net les flux `requests` sans bloquer l'UI.
- **Auto-Start Ollama** : Lancement de `ollama serve` en arrière-plan avec un délai de courtoisie de 4s avant toute opération API.
- **Confirmation de Fermeture** : Dialogue préventif si une opération est active pour éviter les fichiers ZIP corrompus.
