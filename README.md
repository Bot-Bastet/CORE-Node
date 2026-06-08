# CORE-Node (La Station de Calcul)

**Emplacement** : Tourne sur un PC Windows (n'importe quelle machine disposant d'une bonne carte graphique et de RAM, modifiable à la dernière minute).

**Fonction principale** : Héberger l'intelligence artificielle lourde. C'est une application de bureau qui fait tourner les LLM locaux (avec prise en charge multimodale), prend le relais sur la vision par ordinateur (YOLO et Reconnaissance Faciale) et gère l'audio lourd (STT/TTS) lorsque les cases sont cochées.

**Utilité** : Agir comme le "muscle" du projet. Il permet d'utiliser des modèles très performants (comme Gemma 12B ou Mistral) et d'analyser des flux vidéo en temps réel pour soulager totalement le Raspberry Pi du robot, garantissant ainsi une réactivité maximale.

## 💻 ROADMAP : CORE-Node (L'Application Windows / PC Puissant)

C'est ici que l'intelligence de ton interface prend tout son sens pour gérer la flexibilité des modèles IA.

### Étape 1 : Interface, Sécurité et Connectivité
- [ ] Créer l'UI et les onglets (LLM, Vision, Audio, Paramètres).
- [ ] Sauvegarde sécurisée des identifiants (IP Gateway, API Key) dans le gestionnaire de mots de passe de Windows.
- [ ] Connexion silencieuse au Gateway au lancement (aucun port ouvert localement).

### Étape 2 : Le Module de Vision Déportée
- [ ] Cases à cocher YOLO et Reconnaissance Faciale.
- [ ] Récupération du flux RTSP, inférence via OpenCV/modèles locaux, et renvoi des résultats au Gateway.

### Étape 3 : Le Module LLM et Analyse des Modèles
- [ ] Système de téléchargement à la volée (via lien HuggingFace) et liste de modèles pré-téléchargés.
- [ ] Nouveau : Mettre en place un analyseur de métadonnées du modèle sélectionné pour détecter s'il est "Multimodal" (capable de gérer l'audio nativement) ou "Texte uniquement".

### Étape 4 : Le Module Audio Déporté (L'Interface Dynamique)
- [ ] Ajouter la case à cocher principale : "Prendre en charge STT / TTS". (Si cochée, le Raspberry Pi arrête de calculer l'audio).
- [ ] Logique de l'UI selon le modèle LLM choisi :
  - **Scénario A (Modèle Multimodal sélectionné)** :
    Afficher/Dégriser la sous-case : "Je préfère utiliser STT et TTS classiques".
    - Si cette sous-case est décochée : Le flux audio brut du micro du robot part directement dans le LLM, et l'audio généré repart au robot. Les menus de choix des modèles STT et TTS classiques sont grisés.
    - Si cette sous-case est cochée : Le flux audio passe par le modèle STT classique, donne du texte au LLM, qui donne du texte au modèle TTS classique. Les menus STT et TTS redeviennent accessibles.
  - **Scénario B (Modèle Texte uniquement sélectionné)** :
    La sous-case "Je préfère utiliser STT et TTS classiques" est grisée/désactivée. L'utilisation du STT/TTS classique est forcée. Les menus de choix des modèles STT et TTS classiques sont obligatoirement accessibles.

### Étape 5 : Exécution et Inférence
- [ ] Câbler la réception du flux audio brut depuis le Gateway.
- [ ] Faire tourner la pipeline choisie (Audio->LLM->Audio OU Audio->STT->Texte->LLM->Texte->TTS->Audio) en injectant le "Super-Prompt" du Gateway.
- [ ] Renvoyer le flux audio final généré vers le Gateway pour qu'il le transmette au haut-parleur du robot.
