import requests
import json

class LLMEngine:
    def __init__(self):
        self.current_model = None
        self.ollama_url = "http://localhost:11434/api/generate"

    def load_model(self, model_name: str):
        """Définit le modèle Ollama à utiliser."""
        print(f"LLMEngine: Modèle sélectionné -> {model_name}")
        self.current_model = model_name

    def generate_response(self, prompt: str, context_history: list = None, audio_path: str = None) -> str:
        """Génère une réponse textuelle complète (non streamée) pour le test vocal."""
        if not self.current_model or self.current_model in ["Aucun modèle", "Chargement..."]:
            return "Aucun modèle LLM n'est démarré."
            
        print(f"LLMEngine: Inférence sur '{prompt}' avec {self.current_model}")
        
        # On peut rajouter un contexte (system prompt) pour qu'il réponde brièvement
        full_prompt = f"Tu es le cerveau d'un robot appelé Bastet. Réponds toujours en français, de manière très courte et concise. Voici la phrase de l'utilisateur : {prompt}"
        if prompt == "[AUDIO]":
            full_prompt = "Tu es le cerveau d'un robot appelé Bastet. Écoute l'audio fourni et réponds brièvement en français."
        
        payload = {
            "model": self.current_model,
            "prompt": full_prompt,
            "stream": False
        }
        
        if audio_path:
            try:
                import base64
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                payload["images"] = [audio_b64]
                print(f"LLMEngine: Fichier audio {audio_path} encodé et ajouté à la requête.")
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
