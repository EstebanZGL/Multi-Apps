# CERviable

## Description
Outil d'automatisation pour la rédaction de rapports CER (Compte Rendu d'Expérimentation) à partir de documents "Prosit Aller".

## Fonctionnalités
- **Template Persistant** : Sélection et mémorisation du chemin vers le template CER (.docx).
- **Nom de Fichier Personnalisable** : Choix du nom de sortie par défaut (mémorisé).
- **Parsing Robuste** : Extraction automatique des sections clés du Prosit (Contexte, Problématique, etc.) avec gestion des fautes, pluriels et variantes.
- **Arrêt Intelligent** : Stopper l'extraction dès qu'une section exclue (Philosophie, Généralisation, Livrable) est détectée.
- **Remplissage par Titres** : Plus besoin de balises `{{TAG}}`. L'appli utilise les titres existants du template comme ancres pour insérer le texte.
- **Mise en Forme** : Force l'alignement à gauche pour le texte injecté tout en préservant le style des titres.

## Sections supportées (Document A & Template B)
- Contexte
- Problématique
- Mots-Clefs (et variantes : Mots clés, etc.)
- Contrainte
- Hypothèses
- Plan d’action
