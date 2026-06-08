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
    def __init__(self):
        super().__init__()

        self.title("Bastet CORE-Node")
        self.geometry("800x750")

        self.gateway_url = "ws://127.0.0.1:8001/ws/node"
        self.gateway_token = "your-api-token-here"
        self.node_coordinates = "Node-Salon"
        self.model_running = False
        self.gateway_client = None

        # Layout configuration
        self.grid_columnconfigure(1, weight=1)
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
            command=lambda: self.on_feature_toggle("yolo", self.yolo_checkbox, "Activer YOLOv8 (Détection d'objets)", self.yolo_var))
        self.yolo_checkbox.grid(row=1, column=0, sticky="w", pady=5)
        
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
        self.stt_optionmenu = ctk.CTkOptionMenu(self.audio_models_frame, values=["Whisper Tiny (Vite)", "Whisper Base", "Whisper Small", "Whisper Medium (Précis)"])
        self.stt_optionmenu.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(self.audio_models_frame, text="Modèle TTS :").grid(row=1, column=0, sticky="w", padx=5)
        self.tts_optionmenu = ctk.CTkOptionMenu(self.audio_models_frame, values=["Voice 1 (Rapide)", "Voice 2 (Lourd/HD)", "Piper TTS (Moyen)", "Bark (Très Lourd)"])
        self.tts_optionmenu.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Section LLM (Ollama)
        self.llm_label = ctk.CTkLabel(self.main_frame, text="Modèle LLM (100% Local via Ollama)", font=ctk.CTkFont(size=16, weight="bold"))
        self.llm_label.grid(row=6, column=0, sticky="w", pady=(20, 10))
        
        self.llm_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.llm_frame.grid(row=7, column=0, sticky="ew")

        self.llm_optionmenu = ctk.CTkOptionMenu(self.llm_frame, values=["Chargement..."], width=200)
        self.llm_optionmenu.pack(side="left", padx=(0, 10))
        
        self.refresh_btn = ctk.CTkButton(self.llm_frame, text="🔄 Actualiser", width=80, command=self.fetch_ollama_models)
        self.refresh_btn.pack(side="left", padx=(0, 10))

        self.toggle_model_btn = ctk.CTkButton(self.llm_frame, text="▶ Lancer", fg_color="green", hover_color="darkgreen", command=self.toggle_model)
        self.toggle_model_btn.pack(side="left")

        self.model_status_label = ctk.CTkLabel(self.main_frame, text="Statut : Aucun modèle démarré", text_color="gray")
        self.model_status_label.grid(row=8, column=0, sticky="w", pady=(5, 15))

        # Installer un nouveau modèle
        self.install_label = ctk.CTkLabel(self.main_frame, text="Installer un nouveau modèle (ex: mistral:latest) :", font=ctk.CTkFont(size=12))
        self.install_label.grid(row=9, column=0, sticky="w")

        self.install_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.install_frame.grid(row=10, column=0, sticky="ew", pady=5)

        self.install_entry = ctk.CTkEntry(self.install_frame, placeholder_text="hermes:latest", width=250)
        self.install_entry.pack(side="left", padx=(0, 10))

        self.install_btn = ctk.CTkButton(self.install_frame, text="⬇ Installer", width=100, command=self.install_model)
        self.install_btn.pack(side="left")
        
        self.install_status = ctk.CTkLabel(self.install_frame, text="", text_color="yellow")
        self.install_status.pack(side="left", padx=10)

        self.fetch_ollama_models()

    def fetch_ollama_models(self):
        def _fetch():
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    if models:
                        self.llm_optionmenu.configure(values=models)
                        self.llm_optionmenu.set(models[0])
                    else:
                        self.llm_optionmenu.configure(values=["Aucun modèle"])
                        self.llm_optionmenu.set("Aucun modèle")
                else:
                    self.llm_optionmenu.configure(values=["Erreur API Ollama"])
            except Exception:
                self.llm_optionmenu.configure(values=["Ollama injoignable"])
        threading.Thread(target=_fetch).start()

    def install_model(self):
        model_name = self.install_entry.get().strip()
        if not model_name:
            return
        self.install_btn.configure(state="disabled", text="Installation...")
        self.install_status.configure(text=f"Téléchargement de {model_name}...")
        
        def _pull():
            try:
                requests.post("http://localhost:11434/api/pull", json={"name": model_name}, timeout=600)
                self.install_status.configure(text="✅ Terminé", text_color="green")
            except Exception as e:
                self.install_status.configure(text="❌ Erreur", text_color="red")
            finally:
                self.install_btn.configure(state="normal", text="⬇ Installer")
                self.install_entry.delete(0, 'end')
                self.fetch_ollama_models()

        threading.Thread(target=_pull).start()

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
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

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
                self.yolo_checkbox.configure(state="normal", text="Activer YOLOv8 (Détection d'objets)")
            elif feature == "face_rec":
                self.face_var.set(state)
                self.face_checkbox.configure(state="normal", text="Activer Reconnaissance Faciale")
            elif feature == "audio":
                self.audio_var.set(state)
                self.audio_checkbox.configure(state="normal", text="Prendre en charge STT / TTS")
