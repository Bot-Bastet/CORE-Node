import os
import threading
import sounddevice as sd
from scipy.io.wavfile import write
import pyttsx3
import numpy as np

class AudioEngine:
    def __init__(self):
        self.sample_rate = 16000
        self.is_recording = False
        self.continuous_running = False
        self.stream = None
        self.audio_data = []
        self.whisper_model = None
        self.current_whisper_model = None
        self.piper_voice = None
        self.bark_model = None
        self.bark_processor = None
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
        
        audio_data = []
        def callback(indata, frames, time_info, status):
            audio_data.append(indata.copy())
            
        stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback, blocksize=int(self.sample_rate*0.1))
        stream.start()
        
        try:
            while self.continuous_running:
                is_speaking = False
                silence_chunks = 0
                
                while self.continuous_running:
                    time.sleep(0.05)
                    if not audio_data: continue
                    
                    latest_chunk = audio_data[-1]
                    volume = np.max(np.abs(latest_chunk))
                    
                    # On baisse le seuil à 0.02 pour bien capter les consonnes faibles
                    if volume > 0.02: 
                        if not is_speaking:
                            print(f"AudioEngine: Début de parole détecté (vol: {volume:.3f})")
                        is_speaking = True
                        silence_chunks = 0
                    elif is_speaking:
                        silence_chunks += 1
                        
                    if is_speaking and silence_chunks > 15: # 1.5s de silence
                        break
                        
                    # Pre-roll : si on ne parle pas, on garde quand même la dernière seconde d'audio
                    # Cela évite de couper le tout début du mot (ex: le son "sss" de "salut")
                    if not is_speaking and len(audio_data) > 15:
                        audio_data = audio_data[-15:]
                        
                if is_speaking and self.continuous_running:
                    audio_concat = np.concatenate(audio_data, axis=0)
                    audio_data.clear() # On vide le buffer
                    
                    if len(audio_concat) > self.sample_rate * 0.5:
                        print("AudioEngine: Fin de parole. Envoi au pipeline bloquant...")
                        
                        # Normalisation du volume pour aider Whisper (boost du son)
                        max_vol = np.max(np.abs(audio_concat))
                        if max_vol > 0:
                            # On booste le volume à 90% du max pour éviter toute saturation
                            audio_concat = (audio_concat / max_vol) * 0.9
                            
                        wav_path = "temp_continuous.wav"
                        audio_int16 = (audio_concat * 32767).astype(np.int16)
                        write(wav_path, self.sample_rate, audio_int16)
                        
                        # On coupe le micro pendant que le robot réfléchit et parle
                        stream.stop()
                        callback_pipeline(wav_path)
                        time.sleep(0.5) # Petite pause avant de rouvrir le micro
                        stream.start()
                        audio_data.clear()
        finally:
            stream.stop()
            stream.close()

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

    def preload_stt_model(self, model_name: str, callback_done=None):
        """Précharge le modèle Whisper en arrière-plan pour éviter les blocages."""
        if "Tiny" in model_name:
            actual_model = "tiny"
        elif "Small" in model_name:
            actual_model = "small"
        elif "Medium" in model_name:
            actual_model = "medium"
        else:
            actual_model = "base"
            
        if self.whisper_model is None or self.current_whisper_model != actual_model:
            print(f"AudioEngine: Pré-chargement de Faster-Whisper '{actual_model}'...")
            from faster_whisper import WhisperModel
            
            try:
                self.whisper_model = WhisperModel(actual_model, device="cuda", compute_type="float16")
                print("AudioEngine: Whisper charge sur GPU (CUDA) avec succes.")
            except Exception as e:
                print(f"AudioEngine: CUDA indisponible ou echec ({e}). Fallback sur CPU (LENT)...")
                self.whisper_model = WhisperModel(actual_model, device="cpu", compute_type="int8")
                
            self.current_whisper_model = actual_model
            if callback_done:
                callback_done(actual_model)

    def process_stt(self, wav_path: str, model_name: str = "base") -> str:
        """Convertit le fichier wav en texte avec Whisper."""
        if not os.path.exists(wav_path):
            return ""
            
        # On précharge le modèle même si l'utilisateur ne parle pas encore
        self.preload_stt_model(model_name)
            
        print("AudioEngine: Transcription en cours...")
        segments, info = self.whisper_model.transcribe(wav_path, language="fr")
        
        texte = " ".join([segment.text for segment in segments]).strip()
        print("AudioEngine: STT termine.")
        return texte

    def preload_piper_model(self, callback_done=None):
        import os
        import urllib.request
        from piper import PiperVoice
        
        model_path = "fr_FR-siwis-low.onnx"
        config_path = "fr_FR-siwis-low.onnx.json"
        if not os.path.exists(model_path):
            print("AudioEngine: Téléchargement de Piper TTS (15 Mo)...")
            urllib.request.urlretrieve("https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/low/fr_FR-siwis-low.onnx", model_path)  # nosemgrep
            urllib.request.urlretrieve("https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/low/fr_FR-siwis-low.onnx.json", config_path)  # nosemgrep
            
        if self.piper_voice is None:
            print("AudioEngine: Chargement en mémoire du modèle Piper...")
            self.piper_voice = PiperVoice.load(model_path)
            
        if callback_done:
            callback_done()

    def preload_bark_model(self, callback_done=None):
        if self.bark_model is None:
            print("AudioEngine: Téléchargement/Chargement de Bark en cours (Patientez, fichiers lourds)...")
            from transformers import AutoProcessor, BarkModel
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.bark_processor = AutoProcessor.from_pretrained("suno/bark-small")
            # En float16 sur CUDA pour économiser la VRAM (Bark est très lourd)
            dtype = torch.float16 if device == "cuda" else torch.float32
            self.bark_model = BarkModel.from_pretrained("suno/bark-small", torch_dtype=dtype).to(device)
            print("AudioEngine: Bark TTS est prêt !")
            
        if callback_done:
            callback_done()

    def process_tts(self, text: str, voice_pref: str = "Voice 1"):
        """Génère l'audio avec pyttsx3 de manière sécurisée pour les threads."""
        if not text:
            return
            
        if "Piper" in voice_pref:
            print("AudioEngine: Utilisation de Piper TTS...")
            try:
                import io
                import wave
                import numpy as np
                import urllib.request
                import numpy as np
                import os
                from scipy.io.wavfile import write
                
                print("AudioEngine: Synthèse Piper en cours...")
                wav_path_piper = os.path.abspath("piper_out.wav")
                
                audio_arrays = []
                for chunk in self.piper_voice.synthesize(text):
                    audio_arrays.append(chunk.audio_int16_array)
                    
                if audio_arrays:
                    audio_data = np.concatenate(audio_arrays)
                    write(wav_path_piper, self.piper_voice.config.sample_rate, audio_data)
                    print(f"AudioEngine: Fichier Piper généré ({len(audio_data)} samples).")
                    
                    print("AudioEngine: Lecture Piper en cours (via powershell)...")
                    os.system(f'powershell -c "(New-Object Media.SoundPlayer \'{wav_path_piper}\').PlaySync()"')
                return
            except Exception as e:
                print(f"AudioEngine: Erreur avec Piper TTS ({e}). Fallback sur Windows TTS.")

        if "Bark" in voice_pref:
            print("AudioEngine: Utilisation de Bark TTS...")
            try:
                import torch
                import numpy as np
                import sounddevice as sd
                
                self.preload_bark_model()
                
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print("AudioEngine: Synthèse Bark en cours...")
                inputs = self.bark_processor(text, voice_preset="v2/fr_speaker_1").to(device)
                
                with torch.no_grad():
                    audio_array = self.bark_model.generate(**inputs)
                    
                audio_array = audio_array.cpu().numpy().squeeze()
                sample_rate = self.bark_model.generation_config.sample_rate
                
                # Sauvegarde en WAV puis lecture avec powershell
                import os
                wav_path_bark = os.path.abspath("bark_out.wav")
                from scipy.io.wavfile import write
                audio_int16 = (audio_array * 32767).astype(np.int16)
                write(wav_path_bark, sample_rate, audio_int16)
                print(f"AudioEngine: Fichier Bark généré ({len(audio_int16)} samples).")
                
                print("AudioEngine: Lecture Bark en cours (via powershell)...")
                os.system(f'powershell -c "(New-Object Media.SoundPlayer \'{wav_path_bark}\').PlaySync()"')
                return
            except Exception as e:
                print(f"AudioEngine: Erreur avec Bark TTS ({e}). Fallback sur Windows TTS.")
            
        import pyttsx3
        engine = pyttsx3.init()
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
                voice_name = fr_voices[0].name
                if "Voice 2" in voice_pref and len(fr_voices) > 1:
                    selected_voice = fr_voices[1].id
                    voice_name = fr_voices[1].name
                engine.setProperty('voice', selected_voice)
            else:
                voice_name = "Voix système par défaut"
            
            print(f"AudioEngine: Lecture TTS en cours (Utilisation de la voix : {voice_name})...")
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
