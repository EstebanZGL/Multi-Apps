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
- [ ] Déploiement dans `%APPDATA%/MultiversLauncher`.
- [ ] Création du raccourci bureau et menu démarrer.

### 3. Spécificités Jarvis (LLM)
- [x] Script de vérification d'Ollama (bouton de diagnostic intégré).
- [ ] Analyse des modèles locaux présents.
- [ ] Proposition d'installation d'un LLM recommandé (Deepseek, etc.).
- [ ] Option de téléchargement de **HackGPT** (depuis le NAS/Cloud).

### 4. Mise à jour du Launcher
- [ ] Détection des applications non installées localement.
- [ ] UI : Icônes grisées pour les apps manquantes.
- [ ] Bouton "Installer" dynamique ouvrant le module de téléchargement.

### 5. Système d'Auto-Update (GitHub)
- [x] Hébergement d'un fichier `latest_versions.json` sur GitHub (Automatisé via CI/CD).
- [x] Configuration GitHub Actions pour compiler l'EXE de l'installateur à chaque tag.
- [ ] Au lancement du Launcher : vérification silencieuse de la version distante.
- [ ] Si MAJ disponible : Notification utilisateur et téléchargement de l'archive.
- [ ] Remplacement automatique des fichiers.

---

## 📈 État d'avancement

### Phase 1 : Préparation & Infrastructure
- [x] Exportation du modèle HackGPT vers le dossier Nextcloud.
- [x] Création du script de packaging (`pack_installer.py`).
- [x] Mise en place de l'automatisation du déploiement GitHub (`deploy_builds.py`).
- [x] Initialisation propre du dépôt Git avec `.gitignore` strict (exclusion des bins et configs privées).

### Phase 2 : Développement de l'Installateur
- [x] Interface de sélection des apps (Design "Cards" validé et fonctionnel).
- [x] Logique de téléchargement asynchrone et décompression implémentée.
- [ ] Logique finale de copie vers AppData.
- [ ] Script de création de raccourcis Windows.

### Phase 3 : Intelligence & LLM
- [ ] Module de détection/installation Ollama.
- [ ] Système de téléchargement de HackGPT.

### Phase 4 : Intégration Launcher
- [ ] Refonte de la détection des apps dans le Launcher.
- [ ] Ajout de l'état "Grisé / À installer".

---

## 📝 Notes & Configuration
- **Location Nextcloud LLM :** `C:\Users\CESI\Documents (CESI)\Nextcloud\Documents\Autres\LLM`
- **Isolation :** Les fichiers `config.json` et le dossier `conversations/` sont protégés par le `.gitignore` et ignorés par le packager.
