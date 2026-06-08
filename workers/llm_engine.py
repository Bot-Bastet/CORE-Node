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

    def generate_response(self, prompt: str, context_history: list = None) -> str:
        """Génère une réponse textuelle complète (non streamée) pour le test vocal."""
        if not self.current_model or self.current_model in ["Aucun modèle", "Chargement..."]:
            return "Aucun modèle LLM n'est démarré."
            
        print(f"LLMEngine: Inférence sur '{prompt}' avec {self.current_model}")
        
        # On peut rajouter un contexte (system prompt) pour qu'il réponde brièvement
        full_prompt = f"Tu es le cerveau d'un robot appelé Bastet. Réponds toujours en français, de manière très courte et concise. Voici la phrase de l'utilisateur : {prompt}"
        
        payload = {
            "model": self.current_model,
            "prompt": full_prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                return f"Erreur API Ollama: {response.status_code}"
        except Exception as e:
            return f"Erreur de connexion à Ollama: {str(e)}"
