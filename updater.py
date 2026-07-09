"""
Auto-updater pour CORE-Node (Windows .exe).
Vérifie GitHub Releases et propose la mise à jour au démarrage.
"""

import sys
import threading
import subprocess
import requests
import tkinter as tk
import tkinter.messagebox as messagebox
from pathlib import Path

GITHUB_REPO = "Bot-Bastet/CORE-Node"


def get_version_file_path() -> Path:
    """Récupérer le chemin de version.txt."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "version.txt"
    return Path(__file__).parent / "version.txt"


def get_current_version() -> str:
    """Lire la version locale depuis version.txt."""
    version_file = get_version_file_path()
    if version_file.exists():
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "v0.0.0"


def get_latest_release() -> dict | None:
    """Interroger l'API GitHub Releases."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        resp = requests.get(
            url, timeout=5, headers={"Accept": "application/vnd.github+json"}
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _version_tuple(v: str) -> tuple:
    v = v.lstrip("v")
    # Ignorer le suffixe -beta, -rc etc.
    v = v.split("-")[0]
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0, 0, 0)


def check_and_update(on_update_done=None):
    """
    Vérifie si une nouvelle version est disponible.
    Si oui, propose à l'utilisateur de télécharger et relancer.
    Doit être appelée dans un thread séparé pour ne pas bloquer l'UI.
    """
    current = get_current_version()
    release = get_latest_release()

    if not release:
        return

    latest_tag = release.get("tag_name", "v0.0.0")

    if _version_tuple(latest_tag) <= _version_tuple(current):
        return  # Déjà à jour

    # Trouver l'asset .exe
    exe_asset = None
    for asset in release.get("assets", []):
        if asset["name"].endswith(".exe"):
            exe_asset = asset
            break

    if not exe_asset:
        return

    # Afficher la boîte de dialogue dans le thread principal (Tkinter n'est pas thread-safe)
    def ask_user():
        answer = messagebox.askyesno(
            "Mise à jour disponible",
            f"Une nouvelle version de CORE-Node est disponible !\n\n"
            f"Version actuelle : {current}\n"
            f"Nouvelle version : {latest_tag}\n\n"
            f"Télécharger et redémarrer maintenant ?",
            icon="info",
        )
        if answer:
            _download_and_restart(exe_asset["browser_download_url"], latest_tag)

    # Programmer l'affichage dans le thread Tk
    try:
        root = tk._default_root
        if root:
            root.after(
                2000, ask_user
            )  # 2s après le lancement pour laisser l'UI s'initialiser
    except Exception:
        pass


def _download_and_restart(download_url: str, new_version: str):
    """Télécharge le nouvel .exe et lance un script batch de remplacement."""
    try:
        exe_path = Path(sys.executable)
        new_exe_path = exe_path.parent / "CORE-Node_new.exe"

        # Télécharger la nouvelle version
        resp = requests.get(download_url, stream=True, timeout=60)
        downloaded = 0

        with open(new_exe_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)

        # Créer un script .bat qui remplace l'exe après la fermeture et relance
        bat_path = exe_path.parent / "_update_bastet.bat"

        # En mode gelé, la version est packagée dans le nouvel exe, pas besoin de version.txt externe
        if getattr(sys, "frozen", False):
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
move /Y "{new_exe_path}" "{exe_path}"
start "" "{exe_path}"
del "%~f0"
"""
        else:
            version_file = get_version_file_path()
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
move /Y "{new_exe_path}" "{exe_path}"
echo {new_version} > "{version_file}"
start "" "{exe_path}"
del "%~f0"
"""
        bat_path.write_text(bat_content, encoding="utf-8")
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)], creationflags=subprocess.CREATE_NO_WINDOW
        )
        sys.exit(0)

    except Exception as e:
        messagebox.showerror("Erreur de mise à jour", f"La mise à jour a échoué :\n{e}")


def start_update_check_thread():
    """Lance la vérification de mise à jour en arrière-plan (Windows uniquement)."""
    if sys.platform.startswith("win"):
        t = threading.Thread(target=check_and_update, daemon=True)
        t.start()
