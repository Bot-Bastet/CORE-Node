"""
AI Orchestrator — Cerveau central de node-core.

Relie la reconnaissance faciale, le LLM et le contexte utilisateur.
Gère :
  - L'identification faciale → chargement auto du profil MyGes
  - La persistence du contexte 5s après perte de visage
  - Le pipeline complet : face → contexte → LLM → action
"""

import time
import threading
import requests
import json


class UserContext:
    """Contexte persistant d'un utilisateur identifié."""

    def __init__(self, name: str, face_encoding=None):
        self.name = name
        self.face_encoding = face_encoding
        self.myges_username: str | None = None
        self.myges_schedule: str = ""
        self.last_seen: float = time.time()
        self.active: bool = True

    def touch(self):
        self.last_seen = time.time()
        self.active = True

    def is_stale(self, ttl: float = 5.0) -> bool:
        return (time.time() - self.last_seen) > ttl

    def build_context_prompt(self) -> str:
        parts = [
            f"Tu interagis avec {self.name}.",
            f"Tu connais son emploi du temps MyGES.",
        ]
        if self.myges_schedule:
            parts.append(
                f"\nEmploi du temps de {self.name} (filtré) :\n{self.myges_schedule}"
            )
        return "\n".join(parts)


class AIOrchestrator:
    """
    Orchestre le pipeline IA complet :
      Visage identifié → Contexte MyGes → LLM avec tools → Actions robot
    """

    CONTEXT_TTL = 5.0  # secondes avant purge du contexte après perte de visage

    def __init__(self, gateway_url: str, gateway_token: str, verify_ssl: bool = False):
        self.gateway_url = gateway_url
        self.gateway_token = gateway_token
        self.verify_ssl = verify_ssl

        self._current_user: UserContext | None = None
        self._lock = threading.Lock()

        self._faces_cache: dict[str, dict] = {}  # name → {username, password}
        self._faces_loaded = False

        # Callbacks
        self.on_user_identified = None   # (name: str) → None
        self.on_user_lost = None         # () → None
        self.on_log = None               # (msg: str) → None

    def _log(self, msg: str):
        print(f"[Orchestrator] {msg}")
        if self.on_log:
            self.on_log(msg)

    # ─── Face Recognition Callback ────────────────────────

    def on_face_detected(self, name: str, face_encoding=None):
        """Appelé par VisionEngine quand un visage connu est détecté."""
        if name == "Inconnu":
            return

        with self._lock:
            if self._current_user and self._current_user.name == name:
                self._current_user.touch()
                return

            self._log(f"👤 Visage identifié : {name}")
            self._current_user = UserContext(name, face_encoding)
            self._current_user.touch()

        # Charger le contexte MyGes en arrière-plan
        threading.Thread(
            target=self._load_myges_context,
            args=(name,),
            daemon=True,
        ).start()

        if self.on_user_identified:
            self.on_user_identified(name)

    def on_face_lost(self):
        """Appelé quand aucun visage connu n'est plus visible."""
        with self._lock:
            if self._current_user and self._current_user.active:
                self._log(f"👤 Visage perdu pour {self._current_user.name} — contexte conservé {self.CONTEXT_TTL}s")
                self._current_user.active = False

    def _check_stale_context(self):
        """Vérifie si le contexte a expiré (thread daemon)."""
        while True:
            time.sleep(1.0)
            with self._lock:
                if (
                    self._current_user
                    and not self._current_user.active
                    and self._current_user.is_stale(self.CONTEXT_TTL)
                ):
                    name = self._current_user.name
                    self._current_user = None
                    self._log(f"⏰ Contexte de {name} expiré après {self.CONTEXT_TTL}s")
                    if self.on_user_lost:
                        self.on_user_lost()

    def start_context_watchdog(self):
        t = threading.Thread(target=self._check_stale_context, daemon=True)
        t.start()

    # ─── MyGes Integration ────────────────────────────────

    def _ensure_faces_loaded(self):
        """Charge les identifiants MyGES depuis la Gateway (une seule fois)."""
        if self._faces_loaded:
            return
        try:
            r = requests.get(
                f"{self.gateway_url}/myges",
                headers={"X-API-Token": self.gateway_token},
                verify=self.verify_ssl,
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                for user_name, creds in data.items():
                    self._faces_cache[user_name] = {
                        "username": creds.get("username", ""),
                        "password": creds.get("password", ""),
                    }
                self._log(f"📋 {len(self._faces_cache)} identifiants MyGES chargés")
            else:
                self._log(f"⚠️ Pas d'identifiants MyGES (HTTP {r.status_code})")
        except Exception as e:
            self._log(f"⚠️ Erreur chargement MyGES : {e}")
        self._faces_loaded = True

    def _load_myges_context(self, user_name: str):
        """Charge l'agenda MyGES pour un utilisateur donné."""
        self._ensure_faces_loaded()

        # Chercher les credentials par nom (tolérance partielle)
        creds = None
        for cached_name, c in self._faces_cache.items():
            if cached_name.lower() in user_name.lower() or user_name.lower() in cached_name.lower():
                creds = c
                break

        if not creds:
            self._log(f"⚠️ Pas de credentials MyGES pour '{user_name}'")
            return

        try:
            r = requests.post(
                f"{self.gateway_url}/myges/test",
                json={"username": creds["username"], "password": creds["password"]},
                headers={"X-API-Token": self.gateway_token},
                verify=self.verify_ssl,
                timeout=15,
            )
            if r.status_code == 200:
                result = r.json()
                agenda_raw = result.get("agenda_preview", "")
                # Filtrer l'agenda
                agenda_filtered = self._filter_myges_agenda(agenda_raw)

                with self._lock:
                    if self._current_user and self._current_user.name == user_name:
                        self._current_user.myges_username = creds["username"]
                        self._current_user.myges_schedule = agenda_filtered

                self._log(f"📅 Agenda MyGES chargé pour {user_name} ({len(agenda_filtered)} chars filtrés)")
            else:
                self._log(f"⚠️ Échec connexion MyGES pour {user_name} (HTTP {r.status_code})")
        except Exception as e:
            self._log(f"⚠️ Erreur MyGES pour {user_name} : {e}")

    def _filter_myges_agenda(self, raw_agenda: str) -> str:
        """
        Filtre l'agenda MyGES brut pour ne garder que l'essentiel.
        Retire les métadonnées inutiles, les lignes vides, etc.
        """
        if not raw_agenda:
            return ""

        lines = raw_agenda.strip().split("\n")
        filtered = []
        skip_patterns = [
            "heure de début",
            "heure de fin",
            "salle",
            "professeur",
            "---",
            "==="
        ]

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if any(p in stripped.lower() for p in skip_patterns):
                continue
            # Garder les lignes qui ressemblent à des cours/horaires
            if any(c.isdigit() for c in stripped):
                filtered.append(stripped)
            elif stripped.startswith("-") or stripped.startswith("•"):
                filtered.append(stripped)

        return "\n".join(filtered) if filtered else raw_agenda[:500]

    # ─── Context Access ───────────────────────────────────

    def get_current_context(self) -> str:
        """Retourne le contexte du user actuel (ou chaîne vide)."""
        with self._lock:
            if self._current_user:
                self._current_user.touch()
                return self._current_user.build_context_prompt()
        return ""

    def get_current_user_name(self) -> str | None:
        with self._lock:
            if self._current_user and not self._current_user.is_stale(self.CONTEXT_TTL):
                return self._current_user.name
        return None

    def has_active_context(self) -> bool:
        with self._lock:
            return self._current_user is not None and (
                self._current_user.active or not self._current_user.is_stale(self.CONTEXT_TTL)
            )
