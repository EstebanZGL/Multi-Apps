# MIDIa - Documentation de Recherche & Développement 🎹

## 📋 Concept
Application de transcription musicale automatique (AMT) spécialisée dans le piano. Elle utilise des réseaux de neurones profonds pour analyser un fichier audio (.wav, .mp3) et générer un fichier .mid correspondant.

## 🧠 Technologies retenues
- **Moteur Principal** : `piano_transcription_inference` (par ByteDance/Qiuqiang Kong).
- **Pourquoi ce choix ?** Détection haute fidélité des notes, de la vélocité (pression) et des pédales (sustain).
- **Alternative** : `basic-pitch` (Spotify) si l'utilisateur souhaite plus de légèreté.

## 🛠️ Architecture Technique
- **Interface** : CustomTkinter (intégré au Multivers Launcher).
- **Gestion des dépendances** : Lazy loading de `torch` et `piano_transcription_inference` pour ne pas ralentir le Launcher au démarrage.
- **Workflow Utilisateur** :
  1. Sélection du fichier source.
  2. Analyse IA (local).
  3. Export MIDI.
  4. Lien vers un **DAW** (Digital Audio Workstation) pour la post-édition.

## 🎼 Qu'est-ce qu'un DAW ?
Un DAW est un logiciel de production musicale (ex: FL Studio, Ableton, Musescore). 
Il est **indispensable** après l'utilisation de MIDIa pour :
- **Recaler les notes** sur le rythme (Quantification).
- **Corriger les erreurs** de l'IA.
- **Changer d'instrument** (jouer le MIDI avec un son d'orchestre par exemple).

## 🚀 Évolutions possibles (V2)
- **Video-to-MIDI** : Utiliser la vision par ordinateur (OpenCV) pour transcrire des vidéos de type "Synthesia" (notes qui défilent). Beaucoup plus précis que l'audio.
