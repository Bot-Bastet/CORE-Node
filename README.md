# CORE-Node (La Station de Calcul)

**Emplacement** : Tourne sur un PC Windows (n'importe quelle machine disposant d'une bonne carte graphique et de RAM, modifiable à la dernière minute).

**Fonction principale** : Héberger l'intelligence artificielle lourde. C'est une application de bureau qui fait tourner les LLM locaux (avec prise en charge multimodale), prend le relais sur la vision par ordinateur (YOLO et Reconnaissance Faciale) et gère l'audio lourd (STT/TTS) lorsque les cases sont cochées.

**Utilité** : Agir comme le "muscle" du projet. Il permet d'utiliser des modèles très performants (comme Gemma 12B ou Mistral) et d'analyser des flux vidéo en temps réel pour soulager totalement le Raspberry Pi du robot, garantissant ainsi une réactivité maximale.

## 💻 ROADMAP : CORE-Node (L'Application Windows / PC Puissant)

C'est ici que l'intelligence de ton interface prend tout son sens pour gérer la flexibilité des modèles IA.

### Étape 1 : Interface, Sécurité et Connectivité
- [x] Créer l'UI et les onglets (LLM, Vision, Audio, Paramètres).
- [x] Sauvegarde locale des identifiants (IP Gateway, Token) via modale Paramètres.
- [x] Connexion silencieuse au Gateway au lancement (client asynchrone WebSocket).

### Étape 2 : Le Module de Vision Déportée
- [x] Cases à cocher YOLO et Reconnaissance Faciale avec protocole d'état asynchrone.
- [ ] Récupération du flux RTSP, inférence via OpenCV/modèles locaux, et renvoi des résultats au Gateway.

### Étape 3 : Le Module LLM et Analyse des Modèles
- [x] Système de téléchargement et d'exécution à la volée de modèles LLM locaux via l'API Ollama.
- [ ] Nouveau : Mettre en place un analyseur de métadonnées du modèle sélectionné pour détecter s'il est "Multimodal" (capable de gérer l'audio nativement) ou "Texte uniquement".

### Étape 4 : Le Module Audio Déporté (L'Interface Dynamique)
- [x] Ajouter la case à cocher principale : "Prendre en charge STT / TTS" avec protocole asynchrone.
- [ ] Logique de l'UI selon le modèle LLM choisi :
  - **Scénario A (Modèle Multimodal sélectionné)** :
    Afficher/Dégriser la sous-case : "Je préfère utiliser STT et TTS classiques".
    - Si cette sous-case est décochée : Le flux audio brut du micro du robot part directement dans le LLM, et l'audio généré repart au robot. Les menus de choix des modèles STT et TTS classiques sont grisés.
    - Si cette sous-case est cochée : Le flux audio passe par le modèle STT classique, donne du texte au LLM, qui donne du texte au modèle TTS classique. Les menus STT et TTS redeviennent accessibles.
  - **Scénario B (Modèle Texte uniquement sélectionné)** :
    La sous-case "Je préfère utiliser STT et TTS classiques" est grisée/désactivée. L'utilisation du STT/TTS classique est forcée. Les menus de choix des modèles STT et TTS classiques sont obligatoirement accessibles.

### Étape 5 : Exécution et Inférence
- [x] Câbler la réception du flux audio (ou l'enregistrement local) et l'inférence locale.
- [x] Faire tourner la pipeline (Audio->STT Whisper->Texte->LLM Ollama->Texte->TTS pyttsx3->Audio) en test local.
- [ ] Câbler tout ça sur les messages entrants du Gateway.
- [ ] Renvoyer le flux audio final généré vers le Gateway pour qu'il le transmette au haut-parleur du robot.
