# MIDIa - Documentation Technique et Architecture 🎹

Cette documentation détaille le fonctionnement interne de l'application **MIDIa (Transcription Studio)**. L'application est conçue pour fonctionner en mode "Dual-Mode", offrant deux approches distinctes pour convertir de la musique en fichiers MIDI.

---

## 1. Mode Audio : Intelligence Artificielle (Deep Learning)

Ce mode est idéal pour les enregistrements réels (MP3, WAV) d'un piano solo.

### 1.1 Fonctionnement interne
L'application utilise le réseau de neurones convolutifs récurrents (CRNN) développé par ByteDance (`piano_transcription_inference`). 
1. **Chargement Audio :** L'audio est chargé via `librosa` et `soundfile` (fallback). FFmpeg est injecté dynamiquement dans le `PATH` système pour garantir le décodage des formats compressés comme le MP3.
2. **Infèrence :** L'audio est converti en spectrogramme, puis passé dans le modèle PyTorch (`note_F1=0.9677_pedal_F1=0.9186.pth`). Si un GPU NVIDIA avec CUDA est détecté, le calcul est massivement accéléré.
3. **Modèle :** Le fichier de poids (165 Mo) est téléchargé automatiquement depuis Zenodo dans `~/piano_transcription_inference_data/` lors du premier lancement.

### 1.2 Filtrage Post-Traitement (Sustain & Echo)
Le modèle IA a tendance à interpréter la réverbération acoustique comme de nouvelles notes à faible vélocité. 
MIDIa applique un script de filtrage a posteriori via la bibliothèque `mido`. En ajustant le slider **Sensibilité** :
- Le seuil de suppression varie de `0` (filtre agressif, `vélocité < 40`) à `100` (aucun filtre, `vélocité > 0`).
- Les notes en dessous du seuil sont supprimées, **mais leur delta temporel est accumulé** pour la note suivante. Cela garantit que le rythme général du morceau reste parfait malgré la suppression de notes.

---

## 2. Mode Vidéo : Vision par Ordinateur (Synthesia OpenCV)

Ce mode est conçu pour les vidéos YouTube (Piano Roll / Synthesia). Il offre une précision parfaite à 0ms de latence et est totalement immunisé contre le bruit ou la réverbération audio.

### 2.1 Modélisation Mathématique du Clavier (Le Calque)
L'interface de calibration dessine un "Clavier Fantôme" parfait de 88 touches :
- **Touches Blanches (52) :** `Largeur_Totale / 52`.
- **Touches Noires (36) :** Leur largeur est réglable via `black_key_width_ratio`. Leur position X n'est pas parfaitement centrée entre deux touches blanches. Le paramètre `black_key_spread` permet d'ajuster leur écartement (ex: Do# et Ré# s'écartent l'un de l'autre).

### 2.2 Calibration Interactive (Drag & Drop)
L'utilisateur superpose le calque virtuel au clavier de la vidéo via des curseurs ou la **souris** :
- **Zoom Visuel :** Redimensionne le canevas Tkinter pour une précision au pixel près sans ralentir l'image source.
- **Drag & Drop Adouci :** Le mouvement de la souris modifie directement les paramètres mathématiques (Pan X et Ligne Y) avec un diviseur de vélocité pour éviter les sauts brusques.

### 2.3 Détection de Couleur (Espace HSV)
Pour analyser si une note est "ON" ou "OFF", MIDIa utilise l'espace colorimétrique **HSV** (Hue, Saturation, Value) :
- Les vidéos compressées (YouTube) créent du bruit sur les pixels noirs. Pour pallier cela, le script calcule le **90ème centile** de la luminosité et de la saturation sur la zone de la touche, ignorant ainsi les bordures sombres.
- **Mode Barres Tombantes :** Recherche une forte saturation (couleur de la barre) ou une luminosité extrême (barre blanche).
- **Mode Touches Pressées :** Détecte le surlignage brillant (Value > 230) des touches du clavier modélisé.
- **Hystérésis :** Le seuil pour "Allumer" une note est très strict, mais le seuil pour l'"Éteindre" est très bas. Cela empêche les micro-coupures (flickering) dues aux reflets de la vidéo.

### 2.4 Ingénierie Temporelle (Absolute to Delta)
C'est le composant le plus critique du mode Vidéo. 
Le format MIDI (Type 1) utilise un temps **Delta** (le temps écoulé depuis le précédent événement).
- Si OpenCV calculait le Delta en temps réel à chaque image (ex: 3 accords tombent), la première note décalerait la deuxième, qui décalerait la troisième.
- **Solution MIDIa :** 
  1. Le moteur affecte un temps **Absolu** (en `Ticks`) à chaque `note_on` et `note_off` calculé via `fps` et `960 ticks/s` (standard 120 BPM).
  2. À la fin de l'analyse vidéo, toutes les notes sont stockées dans une liste.
  3. La liste est **triée chronologiquement**.
  4. Le moteur itère sur la liste et soustrait le temps absolu de la note précédente pour générer les véritables *Deltas*. Le fichier final est temporellement parfait.

---

## 3. Déploiement et Dépendances (Smart Install)

Le script de lancement est pensé pour s'exécuter dans l'environnement centralisé "Multivers Launcher" :
- Les dépendances lourdes (`torch`, `opencv-python`) sont chargées en "Lazy Loading".
- Si elles manquent, une fonction `_install_dependencies` est déclenchée. Elle exécute silencieusement les commandes `pip install` avec des vérifications spécifiques à l'OS (CUDA fallback).
- **Note de packaging :** Cette installation automatique n'est possible que si l'application est exécutée via Python. En version compilée (`.exe`), le système avertira l'utilisateur que l'environnement est scellé.