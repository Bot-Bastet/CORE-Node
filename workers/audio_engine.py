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
        self.current_whisper_model = None
        self.is_recording = False
        self.continuous_running = False
        self.audio_data = []
        self.sample_rate = 16000

    def enable_continuous_listening(self, state: bool, callback_pipeline=None):
        self.continuous_running = state
        if state and callback_pipeline:
            import threading
            threading.Thread(target=self._continuous_listen_worker, args=(callback_pipeline,), daemon=True).start()

    def _continuous_listen_worker(self, callback_pipeline):
        import time
        import sounddevice as sd
        import numpy as np
        from scipy.io.wavfile import write
        
        print("AudioEngine: Écoute continue automatique (VAD) activée.")
        while self.continuous_running:
            audio_data = []
            
            def callback(indata, frames, time_info, status):
                audio_data.append(indata.copy())
                
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
            stream.start()
            
            is_speaking = False
            silence_chunks = 0
            
            while self.continuous_running:
                time.sleep(0.1)
                if not audio_data: continue
                
                latest_chunk = audio_data[-1]
                volume = np.max(np.abs(latest_chunk))
                
                if volume > 0.03: # Seuil de détection vocale
                    if not is_speaking:
                        print(f"AudioEngine: Début de parole détecté (vol: {volume:.3f})")
                    is_speaking = True
                    silence_chunks = 0
                elif is_speaking:
                    silence_chunks += 1
                    
                if is_speaking and silence_chunks > 15: # 1.5s de silence
                    break
                    
            stream.stop()
            stream.close()
            
            if is_speaking and self.continuous_running:
                audio_concat = np.concatenate(audio_data, axis=0)
                if len(audio_concat) > self.sample_rate * 0.5: # Au moins 0.5s d'audio
                    print("AudioEngine: Fin de parole. Envoi au pipeline bloquant...")
                    wav_path = "temp_continuous.wav"
                    audio_int16 = (audio_concat * 32767).astype(np.int16)
                    write(wav_path, self.sample_rate, audio_int16)
                    
                    # Bloque l'écoute pendant la réflexion et la réponse TTS !
                    callback_pipeline(wav_path)
                    
                    # Petite pause après avoir parlé avant de réécouter
                    time.sleep(0.5)

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

    def process_stt(self, wav_path: str, model_name: str = "base") -> str:
        """Convertit le fichier wav en texte avec Whisper."""
        if not os.path.exists(wav_path):
            return ""
            
        if "Tiny" in model_name:
            actual_model = "tiny"
        elif "Small" in model_name:
            actual_model = "small"
        elif "Medium" in model_name:
            actual_model = "medium"
        else:
            actual_model = "base"
            
        # Chargement tardif ou rechargement si le modèle change
        if self.whisper_model is None or self.current_whisper_model != actual_model:
            print(f"AudioEngine: Chargement de Faster-Whisper '{actual_model}'...")
            import torch
            from faster_whisper import WhisperModel
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            if device == "cpu":
                print("ATTENTION: CUDA non detecte. Le STT tournera sur le CPU (LENT).")
            
            self.whisper_model = WhisperModel(actual_model, device=device, compute_type=compute_type)
            self.current_whisper_model = actual_model
            
        print("AudioEngine: Transcription en cours (GPU)...")
        segments, info = self.whisper_model.transcribe(wav_path, language="fr")
        
        texte = " ".join([segment.text for segment in segments]).strip()
        print("AudioEngine: STT termine.")
        return texte

    def process_tts(self, text: str, voice_pref: str = "Voice 1"):
        """Génère l'audio avec pyttsx3 de manière sécurisée pour les threads."""
        if not text:
            return
            
        if "Piper" in voice_pref or "Bark" in voice_pref:
            print(f"AudioEngine: {voice_pref} non encore intégré. Fallback sur la voix Windows standard.")
            
        # Initialisation COM pour Windows dans un thread secondaire
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass

        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            fr_voices = [v for v in voices if 'fr' in v.languages or 'French' in v.name]
            
            if fr_voices:
                selected_voice = fr_voices[0].id
                if "Voice 2" in voice_pref and len(fr_voices) > 1:
                    selected_voice = fr_voices[1].id
                engine.setProperty('voice', selected_voice)
            
            print(f"AudioEngine: Lecture TTS en cours ({voice_pref})...")
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
