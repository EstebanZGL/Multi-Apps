# CAHIER DES CHARGES - IA STUDIO
Dernière mise à jour : Version 5.1

## 1. MOTEUR & SYSTÈME
- [x] **Auto-Start Ollama** : Vérification et lancement automatique de `ollama serve` au démarrage du script.
- [x] **Compatibilité Modèles** : Support dynamique des modèles installés (Llama 3, Mistral, Qwen, etc.).
- [x] **Patch JSON Mistral** : Fonction de "sauvetage" (Regex) pour les modèles qui écrivent le JSON des outils en brut au lieu de l'exécuter.
- [x] **Gestion des Erreurs** : Bloc `try/except` autour de la génération pour capter les erreurs de contexte (Context Limit) sans crasher l'app.

## 2. INTERFACE (UI)
- [x] **Sidebar Complète** : Volet latéral pour tous les réglages et l'historique.
- [x] **CSS Personnalisé** : Arrondis des bulles de chat, masquage des éléments Streamlit inutiles.
- [x] **Notifications (Toasts)** : Feedback visuel lors de l'upload de fichiers ("Image ajoutée", "Fichier lu").

## 3. GESTION DES CONVERSATIONS
- [x] **Multi-Conversations** : Stockage des chats dans un dossier `/conversations` (format JSON).
- [x] **Création** : Bouton "➕ Nouveau Chat".
- [x] **Navigation** : Liste déroulante pour changer de conversation sans perdre l'actuelle.
- [x] **Persistance** : Sauvegarde automatique après chaque message.
- [x] **Renommage** : Champ texte pour renommer le fichier JSON de la conversation actuelle.
- [x] **Suppression** : Bouton pour effacer la conversation active.

## 4. FONCTIONNALITÉS DE CHAT
- [x] **Streaming** : Affichage du texte de l'IA caractère par caractère (effet machine à écrire).
- [x] **Rewind (Retour Arrière)** : Petit bouton "↩" à côté de chaque message utilisateur pour couper l'historique et repartir de là.
- [x] **Régénération (Retry)** : Bouton "🔄 Régénérer" (visible uniquement sous le dernier message IA) pour relancer la réponse.

## 5. CAPACITÉS MULTIMODALES & FICHIERS
- [x] **Upload Universel** : Zone de glisser-déposer acceptant plusieurs fichiers.
- [x] **Vision (Images)** : Envoi des images aux modèles compatibles (Llava, Llama 3.2 Vision).
- [x] **Extraction de Texte (RAG light)** :
    - PDF (`PyPDF2`) avec limite de sécurité (~25k caractères).
    - Word (`python-docx`).
    - Texte brut / Code (`.txt`, `.py`, `.js`, etc.).
- [x] **Système de "Flag" (One-Shot)** : Les fichiers sont consommés au moment de l'envoi (vidage automatique de l'uploader) et attachés uniquement au message en cours pour ne pas surcharger la boucle.

## 6. RECHERCHE WEB (AGENT)
- [x] **Moteur Serper** : Utilisation de l'API Serper.dev (résultats Google réels).
- [x] **Toggle ON/OFF** : Interrupteur "🌐 Internet" pour activer/désactiver l'accès web.
- [x] **Clé API Sécurisée** : Champ `st.text_input(type="password")` dans la sidebar pour entrer la clé Serper (pas besoin de toucher au code).
- [x] **Tool Calling** : L'IA décide seule quand chercher.
- [x] **Feedback UI** : Affichage d'un `st.status` ("Recherche en cours...") pendant l'appel API.

## 7. RÉGLAGES AVANCÉS
- [x] **System Prompt** : Zone de texte pour définir la personnalité de l'IA (ex: "Tu es un expert Python").
- [x] **Sélecteur de Modèle** : Liste déroulante auto-peuplée avec les modèles Ollama locaux.
- [x] **Température** : Slider (0.0 à 1.0) pour la créativité.
- [x] **Fenêtre de Contexte** : Slider (2k à 32k) pour gérer la mémoire RAM vs la longueur des documents.