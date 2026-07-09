import requests


class LLMEngine:
    def __init__(self):
        self.current_model = None
        self.ollama_url = "http://localhost:11434/api/generate"

    def load_model(self, model_name: str):
        """Définit le modèle Ollama à utiliser."""
        print(f"LLMEngine: Modèle sélectionné -> {model_name}")
        self.current_model = model_name

    def generate_response(
        self,
        prompt: str,
        context_history: list = None,
        audio_path: str = None,
        context: str = None,
    ) -> str:
        """Génère une réponse textuelle complète (non streamée) pour le test vocal."""
        if not self.current_model or self.current_model in [
            "Aucun modèle",
            "Chargement...",
        ]:
            return "Aucun modèle LLM n'est démarré."

        print(f"LLMEngine: Inférence sur '{prompt}' avec {self.current_model}")

        # Intégrer les directives de contrôle et navigation
        system_prompt = (
            "Tu es le cerveau d'un robot quadrupède appelé Bastet. Réponds toujours en français, de manière très courte et concise.\n"
            "Tu es capable de contrôler les mouvements et la navigation du robot en insérant des balises d'action spécifiques dans tes réponses :\n"
            "- Pour les mouvements de base, ajoute la balise appropriée :\n"
            "  * Avancer / marche : [ACTION: up]\n"
            "  * Reculer / arrière : [ACTION: down]\n"
            "  * Tourner/Aller à gauche : [ACTION: left]\n"
            "  * Tourner/Aller à droite : [ACTION: right]\n"
            "  * S'arrêter / Stop : [ACTION: stop]\n"
            "  * Se lever / Debout : [ACTION: stand]\n"
            "  * S'asseoir / Assis : [ACTION: sit]\n"
            "- Pour naviguer vers une pièce ou un lieu sur la carte, ajoute la balise [NAV: x, y] associée :\n"
            "  * Salon : [NAV: 0.0, 0.0]\n"
            "  * Cuisine : [NAV: 2.5, 1.5]\n"
            "  * Bureau : [NAV: -2.0, 3.0]\n"
            "  * Chambre : [NAV: 1.5, -3.5]\n"
            "  * Entrée / Hall : [NAV: -1.0, -1.0]\n"
            "Exemples de réponses :\n"
            '- "J\'avance tout de suite. [ACTION: up]"\n'
            '- "Je vais dans la cuisine. [NAV: 2.5, 1.5]"\n'
            '- "Je me lève debout. [ACTION: stand]"\n'
        )
        if context:
            system_prompt += f"\nVoici des informations de contexte d'agenda à jour de l'utilisateur pour répondre à ses questions :\n{context}"

        full_prompt = f"{system_prompt}\nVoici la phrase de l'utilisateur : {prompt}"
        if prompt == "[AUDIO]":
            full_prompt = (
                f"{system_prompt}\nÉcoute l'audio fourni et réponds brièvement."
            )

        payload = {"model": self.current_model, "prompt": full_prompt, "stream": False}

        if audio_path:
            try:
                import base64

                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                payload["images"] = [audio_b64]
                print(
                    f"LLMEngine: Fichier audio {audio_path} encodé et ajouté à la requête."
                )
            except Exception as e:
                print(f"LLMEngine: Erreur lors de la lecture de l'audio: {e}")

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                return f"Erreur API Ollama: {response.status_code}"
        except Exception as e:
            return f"Erreur de connexion à Ollama: {str(e)}"
