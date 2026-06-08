import os
import threading
import sounddevice as sd
from scipy.io.wavfile import write
import pyttsx3
import numpy as np

class AudioEngine:
    def __init__(self):
        self.stt_enabled = False
        self.tts_enabled = False
        self.whisper_model = None
        self.is_recording = False
        self.audio_data = []
        self.sample_rate = 16000

    def start_recording(self):
        """Démarre l'enregistrement audio depuis le microphone par défaut."""
        self.is_recording = True
        self.audio_data = []
        
        def callback(indata, frames, time, status):
            if self.is_recording:
                self.audio_data.append(indata.copy())

        self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
        self.stream.start()
        print("AudioEngine: Début de l'enregistrement.")

    def stop_recording(self) -> str:
        """Arrête l'enregistrement et sauvegarde en .wav, retourne le chemin du fichier."""
        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        
        if not self.audio_data:
            return ""
            
        audio_concat = np.concatenate(self.audio_data, axis=0)
        
        # Vérification du volume
        volume = np.max(np.abs(audio_concat))
        if volume < 0.005:
            print("AudioEngine: AVERTISSEMENT : Aucun son detecte (Volume tres faible). Verifiez que votre micro n'est pas muet.")
            
        wav_path = "temp_recording.wav"
        # Sauvegarde en int16 (standard pour Whisper)
        audio_int16 = (audio_concat * 32767).astype(np.int16)
        write(wav_path, self.sample_rate, audio_int16)
        print(f"AudioEngine: Enregistrement sauvegardé dans {wav_path} (Volume max: {volume:.4f}).")
        return wav_path

    def process_stt(self, wav_path: str) -> str:
        """Convertit le fichier wav en texte avec Whisper."""
        if not os.path.exists(wav_path):
            return ""
            
        # Chargement tardif pour éviter de geler l'app au démarrage
        if self.whisper_model is None:
            print("AudioEngine: Chargement de Faster-Whisper 'base'...")
            import torch
            from faster_whisper import WhisperModel
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            if device == "cpu":
                print("ATTENTION: CUDA non detecte. Le STT tournera sur le CPU (LENT).")
            
            self.whisper_model = WhisperModel("base", device=device, compute_type=compute_type)
            
        print("AudioEngine: Transcription en cours (GPU)...")
        segments, info = self.whisper_model.transcribe(wav_path, language="fr")
        
        texte = " ".join([segment.text for segment in segments]).strip()
        print("AudioEngine: STT termine.")
        return texte

    def process_tts(self, text: str):
        """Génère l'audio avec pyttsx3 de manière sécurisée pour les threads."""
        if not text:
            return
            
        # Initialisation COM pour Windows dans un thread secondaire
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass

        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'fr' in voice.languages or 'French' in voice.name:
                    engine.setProperty('voice', voice.id)
                    break
            
            print("AudioEngine: Lecture TTS en cours...")
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
