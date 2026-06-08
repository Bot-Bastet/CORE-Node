class AudioEngine:
    def __init__(self):
        self.stt_enabled = False
        self.tts_enabled = False

    def enable_offloading(self, state: bool):
        self.stt_enabled = state
        self.tts_enabled = state
        print(f"AudioEngine: STT/TTS Offloading {'activé' if state else 'désactivé'}")

    def process_stt(self, audio_data: bytes) -> str:
        """Appel API ou modèle local Whisper pour convertir la voix en texte"""
        if not self.stt_enabled:
            return ""
        print("AudioEngine: Traitement STT...")
        return "Texte retranscrit simulé"

    def process_tts(self, text: str) -> bytes:
        """Appel API (ex: ElevenLabs) ou modèle local pour générer l'audio"""
        if not self.tts_enabled:
            return b""
        print(f"AudioEngine: Génération TTS pour '{text}'...")
        return b"fake_audio_bytes"
