"""
LLM Engine — Interface Ollama avec Function Calling (Tools).

Utilise l'API /api/chat d'Ollama pour supporter les tool calls.
Le LLM peut appeler des fonctions pour contrôler le robot (mouvements, navigation).
"""

import requests
import json
import re


# ─── Définition des outils (tools) disponibles pour le LLM ───

ROBOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "robot_move",
            "description": "Déplace le robot dans une direction. Le robot est un quadrupède.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right", "stop"],
                        "description": "Direction du mouvement: up=avancer, down=reculer, left=gauche, right=droite, stop=stop",
                    }
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "robot_posture",
            "description": "Change la posture du robot (debout, assis).",
            "parameters": {
                "type": "object",
                "properties": {
                    "posture": {
                        "type": "string",
                        "enum": ["stand", "sit"],
                        "description": "Posture: stand=debout, sit=assis",
                    }
                },
                "required": ["posture"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "robot_navigate",
            "description": "Envoie le robot vers des coordonnées (x, y) sur la carte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "Coordonnée X (mètres)"},
                    "y": {"type": "number", "description": "Coordonnée Y (mètres)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "robot_look_at",
            "description": "Oriente la tête/caméra du robot dans une direction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["left", "right", "center", "up", "down"],
                        "description": "Direction du regard",
                    }
                },
                "required": ["direction"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Tu es Bastet, un robot quadrupède intelligent. Tu parles en français, "
    "de manière courte et concrète. Tu es bavard mais utile.\n\n"
    "Tu peux te déplacer, changer de posture, naviguer et regarder dans différentes directions. "
    "Utilise les outils (functions) qui te sont fournis pour exécuter des actions physiques "
    "lorsque l'utilisateur te le demande.\n\n"
    "IMPORTANT : Si tu n'as pas d'outils disponibles, ajoute des balises d'action dans ta réponse :\n"
    "- [ACTION: up] pour avancer\n"
    "- [ACTION: down] pour reculer\n"
    "- [ACTION: left] pour tourner à gauche\n"
    "- [ACTION: right] pour tourner à droite\n"
    "- [ACTION: stop] pour s'arrêter\n"
    "- [ACTION: stand] pour se lever\n"
    "- [ACTION: sit] pour s'asseoir\n"
    "- [NAV: x, y] pour naviguer vers des coordonnées\n\n"
    "Règles :\n"
    "- Tu ES le robot, parle à la première personne.\n"
    "- Si l'utilisateur te dit 'avance', bouge et réponds que tu avances.\n"
    "- Si l'utilisateur te dit 'assieds-toi', assieds-toi.\n"
    "- Si l'utilisateur mentionne une pièce, navigue vers les coordonnées.\n"
    "- Si l'utilisateur te dit 'regarde à gauche', regarde à gauche.\n"
    "- Réponds toujours en une ou deux phrases courtes.\n"
    "- Si tu as un contexte sur l'utilisateur (agenda, emploi du temps), "
    "utilise-le pour personnaliser tes réponses de manière naturelle.\n"
)


class LLMEngine:
    def __init__(self):
        self.current_model = None
        self.ollama_url = "http://localhost:11434/api/chat"
        self._tools_enabled = True
        self._pending_actions: list[dict] = []

    def load_model(self, model_name: str):
        print(f"LLMEngine: Modèle sélectionné -> {model_name}")
        self.current_model = model_name

    def _supports_tools(self) -> bool:
        """Vérifie si le modèle supporte les tool calls."""
        if not self.current_model:
            return False
        try:
            r = requests.post(
                "http://localhost:11434/api/show",
                json={"name": self.current_model},
                timeout=3,
            )
            if r.status_code == 200:
                info = r.json().get("details", {})
                # Gemma, Mistral, Qwen supportent les tools
                families = info.get("families", [])
                template = info.get("template", "")
                return "tools" in template.lower() or any(
                    f in self.current_model.lower()
                    for f in ["gemma", "mistral", "qwen", "llama3"]
                )
        except Exception:
            pass
        return False

    def generate_response(
        self,
        prompt: str,
        context: str = None,
        audio_path: str = None,
        system_context: str = None,
    ) -> tuple[str, list[dict]]:
        """
        Génère une réponse avec support tool calling.

        Returns:
            (response_text, actions) — le texte de réponse et la liste d'actions extraites
        """
        if not self.current_model or self.current_model in [
            "Aucun modèle",
            "Chargement...",
        ]:
            return "Aucun modèle LLM n'est démarré.", []

        print(f"LLMEngine: Inférence sur '{prompt}' avec {self.current_model}")

        # Construire le system prompt
        system_msg = SYSTEM_PROMPT
        if system_context:
            system_msg += f"\n\n{system_context}"
        elif context:
            system_msg += f"\n\nContexte utilisateur :\n{context}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

        # Essayer avec tools si supporté
        use_tools = self._tools_enabled and self._supports_tools()

        payload = {
            "model": self.current_model,
            "messages": messages,
            "stream": False,
        }

        if use_tools:
            payload["tools"] = ROBOT_TOOLS

        if audio_path:
            try:
                import base64
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                payload["images"] = [audio_b64]
            except Exception as e:
                print(f"LLMEngine: Erreur lecture audio: {e}")

        actions = []

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                message = result.get("message", {})
                response_text = message.get("content", "").strip()

                # Extraire les tool calls
                tool_calls = message.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    func_args = func.get("arguments", {})
                    actions.append({"name": func_name, "args": func_args})

                # Fallback : extraire les balises [ACTION: xxx] du texte brut
                if not actions:
                    actions = self._parse_legacy_action_tags(response_text)

                return response_text, actions
            else:
                return f"Erreur API Ollama: {response.status_code}", []
        except Exception as e:
            return f"Erreur de connexion à Ollama: {str(e)}", []

    def _parse_legacy_action_tags(self, text: str) -> list[dict]:
        """Parse les balises [ACTION: xxx] et [NAV: x, y] dans le texte brut."""
        actions = []
        action_pattern = re.compile(r'\[ACTION:\s*(\w+)\]')
        nav_pattern = re.compile(r'\[NAV:\s*([-\d.]+),\s*([-\d.]+)\]')

        for match in action_pattern.finditer(text):
            direction = match.group(1).lower()
            actions.append({"name": "robot_move", "args": {"direction": direction}})

        for match in nav_pattern.finditer(text):
            x, y = float(match.group(1)), float(match.group(2))
            actions.append({"name": "robot_navigate", "args": {"x": x, "y": y}})

        return actions

    def get_pending_actions(self) -> list[dict]:
        """Retourne et vide la liste d'actions en attente."""
        actions = self._pending_actions[:]
        self._pending_actions.clear()
        return actions

    def unload_model(self):
        if not self.current_model or self.current_model in [
            "Aucun modèle",
            "Chargement...",
        ]:
            return

        print(f"LLMEngine: Déchargement du modèle '{self.current_model}'")
        payload = {"model": self.current_model, "prompt": "", "keep_alive": 0}
        try:
            requests.post(
                "http://localhost:11434/api/generate", json=payload, timeout=5
            )
        except Exception as e:
            print(f"LLMEngine: Erreur déchargement: {e}")

        self.current_model = None
