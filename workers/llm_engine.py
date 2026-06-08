class LLMEngine:
    def __init__(self):
        self.current_model = None

    def load_model(self, model_name: str):
        """Charge le modèle local via llama-cpp-python ou initialise l'API (OpenAI/Anthropic)"""
        print(f"LLMEngine: Chargement du modèle {model_name}...")
        self.current_model = model_name

    def generate_response_stream(self, prompt: str, context: dict):
        """Génère une réponse textuelle en streaming"""
        print(f"LLMEngine: Inférence sur '{prompt}'")
        # Yield tokens pour pouvoir les envoyer au Gateway en temps-réel
        yield "Ceci est "
        yield "une "
        yield "réponse "
        yield "simulée."
