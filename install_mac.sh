#!/bin/bash
# Script d'installation automatique des dépendances pour Mac ARM (Apple Silicon)

echo "Installation des dépendances système (Homebrew)..."
if ! command -v brew &> /dev/null
then
    echo "Homebrew n'est pas installé. Veuillez l'installer d'abord : https://brew.sh/"
    exit 1
fi

# Installer cmake, portaudio et dlib pour faciliter la compilation python
brew install cmake portaudio dlib
echo "Dépendances système installées avec succès !"

# Exporter les chemins de recherche Homebrew pour la compilation de dlib/face_recognition
export C_INCLUDE_PATH="/opt/homebrew/include:$C_INCLUDE_PATH"
export LIBRARY_PATH="/opt/homebrew/lib:$LIBRARY_PATH"

echo "Installation des dépendances Python..."
pip install -r requirements.txt
echo "Installation terminée ! Vous pouvez lancer le programme avec : python3 main.py"
