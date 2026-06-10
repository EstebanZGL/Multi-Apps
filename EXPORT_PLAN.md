# Suivi du Projet : Multivers Installer 🚀

Ce document suit l'évolution du système d'installation universel pour la suite d'applications Multivers.

## 📋 Objectifs principaux
- Créer un **Web-Installer** ultra-léger (quelques Mo).
- Télécharger les applications à la demande depuis GitHub (archives `.zip`).
- Gérer l'installation sélective des applications.
- Isoler les configurations personnelles (ne pas exporter les `.env` ou `config.json` privés).
- Intégration Windows standard (AppData, Menu Démarrer, Raccourci Bureau).
- Gestion intelligente des versions (MAJ / Réinstallation).
- Automatisation du build de l'installateur via GitHub Actions.

---

## 🛠️ Fonctionnalités détaillées

### 1. Build de l'Exportateur (Scripts Python)
- [x] Scan automatique du dossier `apps/` pour détecter les nouveautés (`pack_installer.py`).
- [x] Compression sélective des fichiers (exclure les dossiers de config/logs).
- [x] Génération d'un manifest de build pour l'installateur.
- [x] Upload automatisé des `.zip` et du manifest vers GitHub (`deploy_builds.py`).

### 2. Le Web-Installer (.exe)
- [x] Interface CustomTkinter légère (Design sous forme de cartes, boutons modernes).
- [x] Récupération du `install_manifest.json` distant pour lister les apps.
- [x] Téléchargement asynchrone des `.zip` sélectionnés et extraction.
- [x] Mode Turbo (1Mo/chunk) : Débit de 6-8 Mo/s avec statistiques (%, Mo/s, ETA).
- [x] Bouton Annuler l'installation (arrêt des tâches et nettoyage).
- [x] Liens cliquables vers les dossiers d'installation et temporaires.
- [x] Déploiement dans `%APPDATA%/MultiversLauncher`.
- [x] Création du raccourci bureau et menu démarrer (via PowerShell).

### 3. Spécificités Jarvis (LLM)
- [x] Script de vérification d'Ollama (bouton de diagnostic intégré).
- [x] Démarrage automatique d'Ollama (`ollama serve`) s'il est détecté mais éteint.
- [x] Gestionnaire IA HackGPT : Fenêtre dédiée (non-topmost, transient).
- [x] Installation Automatique de HackGPT : Téléchargement (5 Go) + Création automatique du `Modelfile` + `ollama create`.
- [x] Désinstallation propre de HackGPT via le bouton dédié.

### 4. Mise à jour du Launcher
- [x] Détection dynamique des applications non installées localement.
- [x] UI : Icônes grisées pour les apps manquantes et bouton "Installer" dynamique.

### 5. Système d'Auto-Update (GitHub)
- [x] Hébergement d'un fichier `latest_versions.json` sur GitHub (Automatisé via CI/CD).
- [x] Configuration GitHub Actions pour compiler l'EXE de l'installateur à chaque tag (Permissions Contents: Write fixées).
- [ ] Au lancement du Launcher : vérification silencieuse de la version distante.
- [ ] Si MAJ disponible : Notification utilisateur et téléchargement de l'archive.

---

## 📈 État d'avancement

### Phase 1 : Préparation & Infrastructure (TERMINÉ ✅)
- [x] Exportation du modèle HackGPT vers le dossier Nextcloud.
- [x] Création du script de packaging (`pack_installer.py`).
- [x] Mise en place de l'automatisation du déploiement GitHub (`deploy_builds.py`).
- [x] Initialisation propre du dépôt Git avec `.gitignore` strict (exclusion des bins et configs privées).

### Phase 2 : Développement de l'Installateur (TERMINÉ ✅)
- [x] Interface de sélection des apps (Design "Cards" validé et fonctionnel).
- [x] Logique de téléchargement asynchrone et décompression implémentée.
- [x] Logique de copie vers AppData et gestion des modes MAJ/Désinstall.
- [x] Script de création de raccourcis Windows.

### Phase 3 : Intelligence & LLM (TERMINÉ ✅)
- [x] Module de détection/lancement Ollama.
- [x] Système complet de téléchargement et d'importation de HackGPT (Modelfile auto).

### Phase 4 : Intégration Launcher (TERMINÉ ✅)
- [x] Refonte de la détection des apps dans le Launcher.
- [x] Gestion visuelle des états "Non installé".

---

## 📝 Notes & Configuration
- **Release Actuelle :** v1.0.0
- **Location Nextcloud LLM :** `https://nxt.xavest-truenas.fr/s/xi7pwXsgiD3gM4F`
- **Isolation :** Sécurité garantie par `.gitignore` multiniveau et nettoyage systématique des dossiers temporaires après install.
