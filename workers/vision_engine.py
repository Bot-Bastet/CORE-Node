import threading
import time
import cv2
import requests
import json
import os
import face_recognition
import numpy as np
import unicodedata

def remove_accents(input_str):
    return unicodedata.normalize('NFKD', input_str).encode('ASCII', 'ignore').decode('utf-8')

class VisionEngine:
    def __init__(self, gateway_url="http://127.0.0.1:8001", rtsp_url="rtsp://127.0.0.1:8554/cam1"):
        self.gateway_url = gateway_url
        self.rtsp_url = rtsp_url
        
        self.yolo_enabled = False
        self.yolo_model = None
        self.current_yolo_model_name = ""
        
        self.face_rec_enabled = False
        self.known_face_encodings = []
        self.known_face_names = []
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def enable_yolo(self, state: bool, model_name="yolov8n.pt"):
        self.yolo_enabled = state
        print(f"VisionEngine: YOLOv8 {'activé' if state else 'désactivé'}")
        
        if state:
            # Charger le modèle uniquement si différent ou non chargé
            if self.current_yolo_model_name != model_name or self.yolo_model is None:
                print(f"VisionEngine: Chargement de {model_name}...")
                from ultralytics import YOLO
                import torch
                self.yolo_model = YOLO(model_name)
                
                # Forcer l'utilisation de CUDA si disponible
                if torch.cuda.is_available():
                    self.yolo_model.to("cuda")
                    print("VisionEngine: YOLO configuré sur GPU (CUDA).")
                else:
                    print("VisionEngine: YOLO configuré sur CPU.")
                
                self.current_yolo_model_name = model_name

    def enable_face_rec(self, state: bool):
        self.face_rec_enabled = state
        print(f"VisionEngine: Reconnaissance Faciale {'activée' if state else 'désactivée'}")
        
        if state:
            self._sync_faces()

    def _sync_faces(self):
        print("VisionEngine: Téléchargement des visages depuis la Gateway...")
        headers = {"X-API-Token": "your-api-token-here"}
        
        try:
            r = requests.get(f"{self.gateway_url}/faces", headers=headers, timeout=5)
            if r.status_code != 200:
                print(f"VisionEngine: Erreur de synchro ({r.status_code})")
                return
            
            faces = r.json().get("faces", [])
            print(f"VisionEngine: {len(faces)} photos trouvées sur la Gateway.")
            
            cache_dir = "data/faces"
            os.makedirs(cache_dir, exist_ok=True)
            
            self.known_face_encodings = []
            self.known_face_names = []
            
            for f in faces:
                face_id = f["id"]
                name = f["name"]
                img_path = os.path.join(cache_dir, f"{face_id}.jpg")
                
                # Télécharger l'image si elle n'est pas déjà dans le cache
                if not os.path.exists(img_path):
                    img_resp = requests.get(f"{self.gateway_url}/faces/{face_id}/image", headers=headers)
                    if img_resp.status_code == 200:
                        with open(img_path, "wb") as file:
                            file.write(img_resp.content)
                            
                # Encoder avec face_recognition
                if os.path.exists(img_path):
                    image = face_recognition.load_image_file(img_path)
                    encodings = face_recognition.face_encodings(image)
                    if len(encodings) > 0:
                        self.known_face_encodings.append(encodings[0])
                        self.known_face_names.append(name)
                        
            print(f"VisionEngine: {len(self.known_face_encodings)} encodages faciaux prêts.")
            
        except Exception as e:
            print(f"VisionEngine: Exception lors de la synchronisation: {e}")

    def _process_loop(self):
        cap = None
        window_name = "Vision CORE-Node"
        
        while self.running:
            # Si aucune fonctionnalité visuelle n'est activée, on dort et on libère la caméra
            if not self.yolo_enabled and not self.face_rec_enabled:
                if cap is not None:
                    cap.release()
                    cap = None
                    try: cv2.destroyWindow(window_name)
                    except: pass
                time.sleep(1)
                continue
                
            if cap is None or not cap.isOpened():
                print(f"VisionEngine: Connexion à la webcam locale...")
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    print("VisionEngine: Impossible d'ouvrir la webcam locale. Nouvelle tentative dans 2s...")
                    time.sleep(2)
                    continue
            
            ret, frame = cap.read()
            if not ret:
                print("VisionEngine: Perte du flux vidéo.")
                cap.release()
                cap = None
                time.sleep(1)
                continue
            
            # 1. Traitement YOLO (en premier pour ne pas écraser les dessins FaceRec)
            if self.yolo_enabled and self.yolo_model is not None:
                # YOLOv8 dessine les boîtes automatiquement avec results[0].plot()
                # On baisse la confiance à 0.2 pour détecter plus facilement les téléphones
                results = self.yolo_model.predict(frame, verbose=False, conf=0.2)
                frame = results[0].plot()

            # Redimensionner pour optimiser la reconnaissance faciale (plus rapide)
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # 2. Traitement Face Recognition
            if self.face_rec_enabled and len(self.known_face_encodings) > 0:
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
                
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.5)
                    name = "Inconnu"
                    
                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            name = self.known_face_names[best_match_index]
                    
                    name_clean = remove_accents(name)
                    
                    # Dessiner le rectangle visage (on multiplie par 2 car on avait fx=0.5)
                    cv2.rectangle(frame, (left*2, top*2), (right*2, bottom*2), (0, 255, 0), 2)
                    cv2.putText(frame, name_clean, (left*2 + 6, bottom*2 - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

            # Affichage de la fenêtre
            cv2.imshow(window_name, frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=2)
