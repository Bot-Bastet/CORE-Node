#!/bin/bash
# Script d'installation automatique des dépendances pour Mac ARM (Apple Silicon)

echo "Installation des dépendances système (Homebrew)..."
if ! command -v brew &> /dev/null
then
    echo "Homebrew n'est pas installé. Veuillez l'installer d'abord : https://brew.sh/"
    exit 1
fi

brew install cmake portaudio
echo "Dépendances système installées avec succès !"

echo "Installation des dépendances Python..."
pip install -r requirements.txt
echo "Installation terminée ! Vous pouvez lancer le programme avec : python3 main.py"
