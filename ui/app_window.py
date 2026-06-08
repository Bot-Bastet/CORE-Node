import customtkinter as ctk
import requests
import threading

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Paramètres")
        self.geometry("400x400")
        self.attributes('-topmost', True)
        
        # Gateway IP
        self.ip_label = ctk.CTkLabel(self, text="Adresse API Gateway (WS):")
        self.ip_label.pack(pady=(20, 5), padx=20, anchor="w")
        self.ip_entry = ctk.CTkEntry(self, width=350)
        self.ip_entry.insert(0, parent.gateway_url)
        self.ip_entry.pack(pady=5, padx=20)

        # API Token
        self.token_label = ctk.CTkLabel(self, text="Token d'authentification:")
        self.token_label.pack(pady=(10, 5), padx=20, anchor="w")
        self.token_entry = ctk.CTkEntry(self, width=350, show="*")
        self.token_entry.insert(0, parent.gateway_token)
        self.token_entry.pack(pady=5, padx=20)

        # Coordonnées (Exemple)
        self.coord_label = ctk.CTkLabel(self, text="Coordonnées / Identifiant du Node:")
        self.coord_label.pack(pady=(10, 5), padx=20, anchor="w")
        self.coord_entry = ctk.CTkEntry(self, width=350)
        self.coord_entry.insert(0, parent.node_coordinates)
        self.coord_entry.pack(pady=5, padx=20)

        # Save Button
        self.save_btn = ctk.CTkButton(self, text="Enregistrer", command=self.save_settings)
        self.save_btn.pack(pady=20)
        
        self.parent_app = parent

    def save_settings(self):
        self.parent_app.gateway_url = self.ip_entry.get()
        self.parent_app.gateway_token = self.token_entry.get()
        self.parent_app.node_coordinates = self.coord_entry.get()
        self.destroy()

class CoreNodeApp(ctk.CTk):
    def __init__(self, audio_engine=None, llm_engine=None, vision_engine=None):
        super().__init__()
        self.audio_engine = audio_engine
        self.llm_engine = llm_engine
        self.vision_engine = vision_engine

        self.title("Bastet CORE-Node")
        self.geometry("1100x750")

        self.gateway_url = "ws://127.0.0.1:8001/ws/node"
        self.gateway_token = "your-api-token-here"
        self.node_coordinates = "Node-Salon"
        self.model_running = False
        self.gateway_client = None

        # Layout configuration
        self.grid_columnconfigure(1, weight=1) # Main frame s'étend
        self.grid_columnconfigure(2, weight=0) # Right sidebar (taille fixe)
        self.grid_rowconfigure(0, weight=1)

        # ─── Sidebar (Menu) ───
        self.sidebar_frame = ctk.CTkFrame(self, width=160, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="CORE-Node", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="🔴 Déconnecté", text_color="red")
        self.status_label.grid(row=1, column=0, padx=20, pady=10)

        self.reconnect_btn = ctk.CTkButton(self.sidebar_frame, text="🔄 Reconnecter", command=self.reconnect)
        self.reconnect_btn.grid(row=2, column=0, padx=20, pady=5)

        self.logs_label = ctk.CTkLabel(self.sidebar_frame, text="Logs Réseau :", font=ctk.CTkFont(size=12))
        self.logs_label.grid(row=3, column=0, padx=20, pady=(15, 0), sticky="w")
        
        self.log_box = ctk.CTkTextbox(self.sidebar_frame, width=160, height=200, font=ctk.CTkFont(size=10))
        self.log_box.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.log_box.configure(state="disabled")

        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="⚙️ Paramètres", command=self.open_settings)
        self.settings_btn.grid(row=5, column=0, padx=20, pady=20)

        # ─── Main Content ───
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=0, sticky="nsew")
        
        # Section Vision
        self.vision_label = ctk.CTkLabel(self.main_frame, text="Module de Vision", font=ctk.CTkFont(size=16, weight="bold"))
        self.vision_label.grid(row=0, column=0, sticky="w", pady=(10, 10))
        
        self.yolo_var = ctk.BooleanVar(value=False)
        self.yolo_checkbox = ctk.CTkCheckBox(self.main_frame, text="Activer YOLOv8 (Détection d'objets)", variable=self.yolo_var, 
            command=lambda: self.on_feature_toggle("yolo", self.yolo_checkbox, "Activer YOLOv8", self.yolo_var))
        self.yolo_checkbox.grid(row=1, column=0, sticky="w", pady=5)
        
        self.yolo_optionmenu = ctk.CTkOptionMenu(self.main_frame, values=["yolov8n.pt", "yolov8s.pt", "yolov8m.pt"])
        self.yolo_optionmenu.grid(row=1, column=0, sticky="w", padx=(250, 0))
        
        self.face_var = ctk.BooleanVar(value=False)
        self.face_checkbox = ctk.CTkCheckBox(self.main_frame, text="Activer Reconnaissance Faciale", variable=self.face_var,
            command=lambda: self.on_feature_toggle("face_rec", self.face_checkbox, "Activer Reconnaissance Faciale", self.face_var))
        self.face_checkbox.grid(row=2, column=0, sticky="w", pady=5)

        # Section Audio
        self.audio_label = ctk.CTkLabel(self.main_frame, text="Module Audio (Offloading)", font=ctk.CTkFont(size=16, weight="bold"))
        self.audio_label.grid(row=3, column=0, sticky="w", pady=(20, 10))
        
        self.audio_var = ctk.BooleanVar(value=False)
        self.audio_checkbox = ctk.CTkCheckBox(self.main_frame, text="Prendre en charge STT / TTS", variable=self.audio_var,
            command=lambda: self.on_feature_toggle("audio", self.audio_checkbox, "Prendre en charge STT / TTS", self.audio_var))
        self.audio_checkbox.grid(row=4, column=0, sticky="w", pady=5)
        
        self.audio_models_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.audio_models_frame.grid(row=5, column=0, sticky="w", pady=5, padx=20)

        ctk.CTkLabel(self.audio_models_frame, text="Modèle STT :").grid(row=0, column=0, sticky="w", padx=5)
        self.stt_optionmenu = ctk.CTkOptionMenu(self.audio_models_frame, values=["Whisper Tiny (Vite)", "Whisper Base", "Whisper Small", "Whisper Medium (Précis)"], command=self.on_stt_changed)
        self.stt_optionmenu.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.tts_label = ctk.CTkLabel(self.audio_models_frame, text="Modèle TTS :")
        self.tts_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.tts_optionmenu = ctk.CTkOptionMenu(self.audio_models_frame, values=["Voice 1 (Rapide)", "Voice 2 (Lourd/HD)", "[À VENIR] Piper TTS", "[À VENIR] Bark"], command=self.on_tts_changed)
        self.tts_optionmenu.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        self.llm_native_audio_var = ctk.BooleanVar(value=False)
        self.llm_native_audio_checkbox = ctk.CTkCheckBox(self.audio_models_frame, text="✨ Le LLM gère le STT (Audio Natif)", variable=self.llm_native_audio_var, text_color="yellow")
        # Masqué par défaut, s'affichera si le LLM le supporte
        self.llm_native_audio_checkbox.grid_forget()

        # Sous-section Test Vocal Local
        self.test_audio_frame = ctk.CTkFrame(self.main_frame, border_width=1, border_color="#2d2d3d")
        self.test_audio_frame.grid(row=6, column=0, sticky="ew", pady=(15, 5))
        
        self.test_title = ctk.CTkLabel(self.test_audio_frame, text="🧪 Test Pipeline Vocale Locale", font=ctk.CTkFont(weight="bold"))
        self.test_title.pack(pady=(10, 5))

        self.record_btn = ctk.CTkButton(self.test_audio_frame, text="🎙️ Lancer l'Enregistrement", command=self.toggle_recording, fg_color="#3b82f6", hover_color="#2563eb")
        self.record_btn.pack(pady=5)

        self.transcript_label = ctk.CTkLabel(self.test_audio_frame, text="Vous : ...", text_color="#94a3b8")
        self.transcript_label.pack(pady=(5, 0))
        
        self.response_label = ctk.CTkLabel(self.test_audio_frame, text="Robot : ...", text_color="#4ade80", wraplength=400)
        self.response_label.pack(pady=(5, 10), padx=10)

        # Section LLM (Ollama)
        self.llm_label = ctk.CTkLabel(self.main_frame, text="Modèle LLM (100% Local via Ollama)", font=ctk.CTkFont(size=16, weight="bold"))
        self.llm_label.grid(row=7, column=0, sticky="w", pady=(20, 10))
        
        self.llm_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.llm_frame.grid(row=8, column=0, sticky="ew")

        self.llm_optionmenu = ctk.CTkOptionMenu(self.llm_frame, values=["Chargement..."], width=200, command=self.on_llm_selected)
        self.llm_optionmenu.pack(side="left", padx=(0, 10))
        
        self.refresh_btn = ctk.CTkButton(self.llm_frame, text="🔄 Actualiser", width=80, command=self.fetch_ollama_models)
        self.refresh_btn.pack(side="left", padx=(0, 10))

        self.toggle_model_btn = ctk.CTkButton(self.llm_frame, text="▶ Lancer", fg_color="green", hover_color="darkgreen", command=self.toggle_model)
        self.toggle_model_btn.pack(side="left")

        self.model_status_label = ctk.CTkLabel(self.main_frame, text="Statut : Aucun modèle démarré", text_color="gray")
        self.model_status_label.grid(row=9, column=0, sticky="w", pady=(5, 15))

        # Installer un nouveau modèle
        self.install_label = ctk.CTkLabel(self.main_frame, text="Installer un nouveau modèle (ex: mistral:latest) :", font=ctk.CTkFont(size=12))
        self.install_label.grid(row=10, column=0, sticky="w")

        self.install_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.install_frame.grid(row=11, column=0, sticky="ew", pady=5)

        self.install_entry = ctk.CTkEntry(self.install_frame, placeholder_text="hermes:latest", width=250)
        self.install_entry.pack(side="left", padx=(0, 10))

        self.install_btn = ctk.CTkButton(self.install_frame, text="⬇ Installer", width=100, command=self.install_model)
        self.install_btn.pack(side="left")
        
        self.install_progressbar = ctk.CTkProgressBar(self.install_frame, width=150)
        self.install_progressbar.pack(side="left", padx=10)
        self.install_progressbar.set(0)
        self.install_progressbar.pack_forget() # Masqué par défaut
        
        self.install_status = ctk.CTkLabel(self.install_frame, text="", text_color="yellow")
        self.install_status.pack(side="left", padx=5)

        # ─── Right Sidebar (Gateway Logs & Chat) ───
        self.right_sidebar = ctk.CTkFrame(self, width=350, corner_radius=0)
        self.right_sidebar.grid(row=0, column=2, sticky="nsew")
        self.right_sidebar.grid_rowconfigure(1, weight=1)
        self.right_sidebar.grid_columnconfigure(0, weight=1)
        
        self.gateway_logs_title = ctk.CTkLabel(self.right_sidebar, text="🌐 Gateway & Contexte", font=ctk.CTkFont(size=14, weight="bold"))
        self.gateway_logs_title.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.gateway_log_box = ctk.CTkTextbox(self.right_sidebar, font=ctk.CTkFont(size=11), fg_color="#12121a", text_color="#e2e8f0")
        self.gateway_log_box.grid(row=1, column=0, padx=10, pady=(0, 20), sticky="nsew")
        self.gateway_log_box.configure(state="disabled")

        self.after(100, self.fetch_ollama_models)
        self.check_cuda()

    def check_cuda(self):
        import torch
        if torch.cuda.is_available():
            self.add_log("⚡ Accélération matérielle NVIDIA (CUDA) détectée et active !")
        else:
            self.add_log("❌ CUDA non détecté. L'IA tournera sur le CPU (Lent). Vérifiez votre installation PyTorch.")

    def fetch_ollama_models(self):
        def _fetch():
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    self.after(0, lambda: self._update_ollama_ui(models))
                else:
                    self.after(0, lambda: self._update_ollama_ui(None, "Erreur API Ollama"))
            except Exception:
                self.after(0, lambda: self._update_ollama_ui(None, "Ollama injoignable"))
        threading.Thread(target=_fetch, daemon=True).start()

    def _update_ollama_ui(self, models, error=None):
        if error:
            self.llm_optionmenu.configure(values=[error])
            return
        if models:
            self.llm_optionmenu.configure(values=models)
            current_selection = self.llm_optionmenu.get()
            if current_selection not in models:
                self.llm_optionmenu.set(models[0])
                self.on_llm_selected(models[0])
            else:
                self.on_llm_selected(current_selection)
        else:
            self.llm_optionmenu.configure(values=["Aucun modèle"])
            self.llm_optionmenu.set("Aucun modèle")

    def on_stt_changed(self, choice):
        self.add_log(f"📥 Téléchargement/Chargement du modèle STT : {choice} en cours...")
        def _done(actual_model):
            self.add_log(f"✅ Modèle STT '{actual_model}' installé et prêt à l'emploi !")
        if self.audio_engine:
            threading.Thread(target=self.audio_engine.preload_stt_model, args=(choice, _done), daemon=True).start()

    def on_tts_changed(self, choice):
        if "À VENIR" in choice or "Piper" in choice or "Bark" in choice:
            self.add_log(f"⚠️ {choice} n'est pas encore programmé ! La voix de secours Windows sera utilisée.")
        else:
            self.add_log(f"⚙️ Voix TTS changée pour : {choice} (Instantané via Windows)")

    def on_llm_selected(self, choice):
        if choice in ["Aucun modèle", "Chargement...", "Ollama injoignable", "Erreur API Ollama"]:
            return
        def _check():
            try:
                r = requests.post("http://localhost:11434/api/show", json={"name": choice}, timeout=2)
                if r.status_code == 200:
                    info = r.json().get("details", {})
                    families = info.get("families", []) or []
                    # On cherche "audio" ou des modèles connus (ex: gemma4)
                    is_audio_model = "audio" in choice.lower() or "gemma4" in choice.lower()
                    if not is_audio_model and families:
                        is_audio_model = any("audio" in f.lower() for f in families)
                        
                    if is_audio_model:
                        self.after(0, lambda: self.llm_native_audio_checkbox.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5))
                    else:
                        self.after(0, self.llm_native_audio_checkbox.grid_forget)
                        self.after(0, lambda: self.llm_native_audio_var.set(False))
            except Exception:
                self.after(0, self.llm_native_audio_checkbox.grid_forget)
                self.after(0, lambda: self.llm_native_audio_var.set(False))
        threading.Thread(target=_check, daemon=True).start()

    def update_install_progress(self, pct, status):
        if pct is not None:
            self.install_progressbar.set(pct / 100.0)
            self.install_status.configure(text=f"{status} ({pct}%)")
        else:
            self.install_status.configure(text=status)

    def install_model(self):
        model_name = self.install_entry.get().strip()
        if not model_name:
            return
        self.install_btn.configure(state="disabled", text="Installation...")
        self.install_status.configure(text=f"Connexion...")
        self.install_progressbar.pack(side="left", padx=10, before=self.install_status)
        self.install_progressbar.set(0)
        
        def _pull():
            import json
            try:
                r = requests.post("http://localhost:11434/api/pull", json={"name": model_name}, stream=True, timeout=600)
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        status = data.get("status", "")
                        if "total" in data and "completed" in data and data["total"] > 0:
                            pct = int(data["completed"] / data["total"] * 100)
                            self.after(0, lambda p=pct, s=status: self.update_install_progress(p, s))
                        else:
                            self.after(0, lambda s=status: self.update_install_progress(None, s))
                self.after(0, lambda: self.install_status.configure(text="✅ Terminé", text_color="green"))
            except Exception as e:
                self.after(0, lambda err=e: self.install_status.configure(text=f"❌ Erreur: {err}", text_color="red"))
            finally:
                self.after(0, lambda: self.install_progressbar.pack_forget())
                self.after(0, lambda: self.install_btn.configure(state="normal", text="⬇ Installer"))
                self.after(0, lambda: self.install_entry.delete(0, 'end'))
                self.after(0, self.fetch_ollama_models)

        threading.Thread(target=_pull, daemon=True).start()

    def toggle_model(self):
        if self.model_running:
            self.model_running = False
            self.toggle_model_btn.configure(text="▶ Lancer", fg_color="green", hover_color="darkgreen")
            self.model_status_label.configure(text="Statut : Stoppé", text_color="gray")
        else:
            model = self.llm_optionmenu.get()
            if model and model not in ["Aucun modèle", "Chargement...", "Ollama injoignable", "Erreur API Ollama"]:
                self.model_running = True
                self.toggle_model_btn.configure(text="⏹ Stopper", fg_color="red", hover_color="darkred")
                self.model_status_label.configure(text=f"Statut : Modèle {model} en cours d'exécution", text_color="green")

    def open_settings(self):
        SettingsWindow(self)

    def add_log(self, message: str):
        def _add():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _add)

    def add_gateway_log(self, message: str):
        def _add_gw():
            self.gateway_log_box.configure(state="normal")
            self.gateway_log_box.insert("end", message + "\n\n")
            self.gateway_log_box.see("end")
            self.gateway_log_box.configure(state="disabled")
        self.after(0, _add_gw)

    def reconnect(self):
        self.add_log("🔄 Demande de reconnexion...")
        if self.gateway_client:
            self.gateway_client.force_reconnect()

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_label.configure(text="🟢 Connecté", text_color="green")
        else:
            self.status_label.configure(text="🔴 Déconnecté", text_color="red")

    def on_feature_toggle(self, feature: str, checkbox: ctk.CTkCheckBox, base_text: str, var: ctk.BooleanVar):
        target_state = var.get()
        # On bloque la case visuellement sans changer l'état réel pour l'instant
        var.set(not target_state)
        
        checkbox.configure(state="disabled", text=f"⏳ {base_text} (En attente...)")
        self.add_log(f"📤 Ordre {feature}={target_state} envoyé au robot.")
        
        if not hasattr(self, 'pending_requests'):
            self.pending_requests = {}
        
        req_id = f"{feature}_{target_state}"
        self.pending_requests[req_id] = True
        
        if hasattr(self, 'gateway_client') and self.gateway_client:
            self.gateway_client.send_feature_request(feature, target_state)
            self.after(5000, lambda: self.handle_timeout(feature, target_state, checkbox, base_text, req_id))
        else:
            self.add_log("⚠️ Déconnecté, impossible d'envoyer l'ordre.")
            checkbox.configure(state="normal", text=base_text)
            self.pending_requests.pop(req_id, None)

    def handle_timeout(self, feature: str, target_state: bool, checkbox: ctk.CTkCheckBox, base_text: str, req_id: str):
        if self.pending_requests.pop(req_id, False):
            self.add_log(f"⏱️ Délai dépassé pour {feature}. Robot injoignable.")
            checkbox.configure(state="normal", text=base_text)

    def handle_feature_ack(self, feature: str, state: bool, status: str):
        if hasattr(self, 'pending_requests'):
            req_id = f"{feature}_{state}"
            self.pending_requests.pop(req_id, None)

        if status == "ok":
            action = "activé" if state else "désactivé"
            self.add_log(f"✅ Robot a confirmé : {feature} {action}.")
            
            if feature == "yolo":
                self.yolo_var.set(state)
                self.yolo_checkbox.configure(state="normal", text="Activer YOLOv8")
                if self.vision_engine:
                    self.vision_engine.enable_yolo(state, model_name=self.yolo_optionmenu.get())
            elif feature == "face_rec":
                self.face_var.set(state)
                self.face_checkbox.configure(state="normal", text="Activer Reconnaissance Faciale")
                if self.vision_engine:
                    # On lance dans un thread pour éviter de bloquer l'UI lors du DL des visages
                    threading.Thread(target=self.vision_engine.enable_face_rec, args=(state,), daemon=True).start()
            elif feature == "audio":
                self.audio_var.set(state)
                self.audio_checkbox.configure(state="normal", text="Prendre en charge STT / TTS")
                if self.audio_engine:
                    self.audio_engine.enable_continuous_listening(state, self.process_audio_pipeline)

    def toggle_recording(self):
        if not self.audio_engine:
            self.add_log("Erreur: Moteur audio non initialisé.")
            return
            
        if not self.audio_engine.is_recording:
            self.audio_engine.start_recording()
            self.record_btn.configure(text="⏹️ Stopper l'Enregistrement", fg_color="#ef4444", hover_color="#b91c1c")
            self.transcript_label.configure(text="Vous : (Enregistrement en cours...)")
            self.response_label.configure(text="Robot : ...")
        else:
            self.record_btn.configure(state="disabled", text="⏳ Traitement STT...")
            wav_path = self.audio_engine.stop_recording()
            threading.Thread(target=self.process_audio_pipeline, args=(wav_path,), daemon=True).start()

    def process_audio_pipeline(self, wav_path):
        try:
            # 1. STT
            if self.llm_native_audio_var.get():
                self.after(0, lambda: self.transcript_label.configure(text=f"Vous : (Audio envoyé au LLM multimodal)"))
                self.add_gateway_log(f"👤 Humain :\n[Fichier Audio Brut]")
                texte_transcrit = "[AUDIO]" # Marqueur pour le LLM
            else:
                stt_choice = self.stt_optionmenu.get()
                texte_transcrit = self.audio_engine.process_stt(wav_path, stt_choice)
                self.after(0, lambda t=texte_transcrit: self.transcript_label.configure(text=f"Vous : {t}"))
                self.add_gateway_log(f"👤 Humain :\n\"{texte_transcrit}\"")
                
                if not texte_transcrit:
                    self.add_log("⚠️ Aucun texte reconnu par Whisper. Avez-vous parlé ?")
                    return

            # 2. LLM
            self.after(0, lambda: self.record_btn.configure(text="⏳ Réflexion LLM..."))
            model = self.llm_optionmenu.get()
            if not self.model_running or not self.llm_engine:
                reponse = "Je suis désolé, mon cerveau LLM n'est pas démarré."
            else:
                self.llm_engine.load_model(model)
                self.add_gateway_log("🧠 LLM : Génération de la réponse en cours avec le contexte visuel/MyGES...")
                if self.llm_native_audio_var.get():
                    reponse = self.llm_engine.generate_response(texte_transcrit, audio_path=wav_path)
                else:
                    reponse = self.llm_engine.generate_response(texte_transcrit)
            
            self.after(0, lambda r=reponse: self.response_label.configure(text=f"Robot : {r}"))
            self.add_gateway_log(f"🤖 Bastet :\n\"{reponse}\"")

            # 3. TTS
            self.after(0, lambda: self.record_btn.configure(text="🔊 Lecture Audio..."))
            tts_choice = self.tts_optionmenu.get()
            self.audio_engine.process_tts(reponse, tts_choice)
            self.add_gateway_log("🔊 Audio TTS généré et transmis au haut-parleur.")
            
        except Exception as e:
            self.after(0, lambda err=e: self.response_label.configure(text=f"Erreur : {err}"))
            self.add_log(f"Erreur pipeline audio : {e}")
            self.add_gateway_log(f"❌ Erreur critique : {e}")
        finally:
            self.after(0, lambda: self.record_btn.configure(state="normal", text="🎙️ Lancer l'Enregistrement", fg_color="#3b82f6", hover_color="#2563eb"))
