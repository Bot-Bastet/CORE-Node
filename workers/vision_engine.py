import threading
import time
import uuid
import cv2
import requests
import os

try:
    import face_recognition

    FACE_REC_AVAILABLE = True
except ImportError:
    face_recognition = None
    FACE_REC_AVAILABLE = False
import numpy as np
import unicodedata


def remove_accents(input_str):
    return (
        unicodedata.normalize("NFKD", input_str)
        .encode("ASCII", "ignore")
        .decode("utf-8")
    )


class VisionEngine:
    def __init__(
        self, gateway_url="http://127.0.0.1:44888", rtsp_url="rtsp://127.0.0.1:48554/robot/cam1"
    ):
        self.gateway_url = gateway_url
        self.rtsp_url = rtsp_url
        self.token = ""
        self._client_id = f"node-{uuid.uuid4().hex[:12]}"
        self._stream_joined = False

        self.yolo_enabled = False
        self.yolo_model = None
        self.current_yolo_model_name = ""
        self.yolo_model_name_to_load = ""

        self.face_rec_enabled = False
        self.known_face_encodings = []
        self.known_face_names = []

        # Callbacks pour l'orchestrateur
        self.on_face_identified = None  # (name: str, encoding) → None
        self.on_face_lost = None        # () → None
        self._last_identified_name: str | None = None

        # Tracking des détections YOLO (pour le contexte LLM)
        self.last_yolo_detections: str = ""

        # Mode simulation : utilise la webcam locale au lieu du stream robot
        self.simulation_mode = False

        self.show_window = False
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def _join_stream(self, cam_id: int = 1):
        if self._stream_joined:
            return
        headers = {"X-API-Token": self.token}
        try:
            r = requests.post(  # nosemgrep
                f"{self.gateway_url}/api/streams/{cam_id}/join",
                json={"client_id": self._client_id},
                headers=headers,
                timeout=5,
                verify=False,  # nosemgrep
            )
            if r.status_code < 300:
                self._stream_joined = True
                print(f"VisionEngine: Flux cam{cam_id} rejoint via REST (client={self._client_id})")
            else:
                print(f"VisionEngine: Join REST échoué ({r.status_code}): {r.text[:100]}")
        except Exception as e:
            print(f"VisionEngine: Erreur join REST: {e}")

    def _leave_stream(self, cam_id: int = 1):
        if not self._stream_joined:
            return
        headers = {"X-API-Token": self.token}
        try:
            r = requests.delete(  # nosemgrep
                f"{self.gateway_url}/api/streams/{cam_id}/leave",
                json={"client_id": self._client_id},
                headers=headers,
                timeout=5,
                verify=False,  # nosemgrep
            )
            if r.status_code < 300:
                self._stream_joined = False
                print(f"VisionEngine: Flux cam{cam_id} quitté via REST")
            else:
                print(f"VisionEngine: Leave REST échoué ({r.status_code})")
        except Exception as e:
            print(f"VisionEngine: Erreur leave REST: {e}")

    def enable_yolo(self, state: bool, model_name="yolov8n.pt"):
        self.yolo_enabled = state
        print(f"VisionEngine: YOLOv8 {'activé' if state else 'désactivé'}")
        if state:
            self.yolo_model_name_to_load = model_name

    def enable_face_rec(self, state: bool):
        if state and not FACE_REC_AVAILABLE:
            print("VisionEngine: face_recognition n'est pas disponible (manquant).")
            self.face_rec_enabled = False
            return

        self.face_rec_enabled = state
        print(
            f"VisionEngine: Reconnaissance Faciale {'activée' if state else 'désactivée'}"
        )

        if state:
            self._sync_faces()

    def _sync_faces(self):
        print("VisionEngine: Téléchargement des visages depuis la Gateway...")
        headers = {"X-API-Token": self.token}

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
                    img_resp = requests.get(
                        f"{self.gateway_url}/faces/{face_id}/image", headers=headers
                    )
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

            print(
                f"VisionEngine: {len(self.known_face_encodings)} encodages faciaux prêts."
            )

        except Exception as e:
            print(f"VisionEngine: Exception lors de la synchronisation: {e}")

    def _process_loop(self):
        cap = None
        window_name = "Vision CORE-Node"

        while self.running:
            # Charger YOLO dans le thread de traitement si demandé
            if self.yolo_enabled and (
                self.yolo_model is None
                or self.current_yolo_model_name != self.yolo_model_name_to_load
            ):
                model_name = self.yolo_model_name_to_load
                print(
                    f"VisionEngine: Chargement de {model_name} dans le thread de traitement..."
                )
                from ultralytics import YOLO
                import torch

                try:
                    self.yolo_model = YOLO(model_name)
                    if torch.cuda.is_available():
                        self.yolo_model.to("cuda")
                        print("VisionEngine: YOLO configuré sur GPU (CUDA).")
                    else:
                        print("VisionEngine: YOLO configuré sur CPU.")
                    self.current_yolo_model_name = model_name
                except Exception as e:
                    print(f"VisionEngine: Erreur lors du chargement de YOLO: {e}")

            # Décharger YOLO de la mémoire s'il est désactivé mais toujours présent
            if not self.yolo_enabled and self.yolo_model is not None:
                print("VisionEngine: Déchargement du modèle YOLO de la mémoire...")
                self.yolo_model = None
                self.current_yolo_model_name = ""
                import gc
                import sys

                gc.collect()
                if "torch" in sys.modules:
                    try:
                        import torch

                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        if hasattr(torch, "mps") and torch.mps.is_available():
                            torch.mps.empty_cache()
                    except Exception:
                        pass

            # Si aucune fonctionnalité visuelle n'est activée (sauf simulation), on dort
            if not self.yolo_enabled and not self.face_rec_enabled and not self.simulation_mode:
                self._leave_stream()
                if cap is not None:
                    cap.release()
                    cap = None
                    try:
                        cv2.destroyWindow(window_name)
                    except Exception:
                        pass
                time.sleep(1)
                continue

            if cap is None or not cap.isOpened():
                if self.simulation_mode:
                    # Mode simulation : webcam locale directe
                    source = 0
                    print(f"VisionEngine: [SIMULATION] Ouverture webcam locale...")
                    cap = cv2.VideoCapture(source)
                else:
                    source = self.rtsp_url
                    is_rtsp = source.startswith("rtsp://")
                    if is_rtsp:
                        self._join_stream()
                    print(f"VisionEngine: Connexion à la source vidéo ({source})...")
                    cap = cv2.VideoCapture(source)
                    if not cap.isOpened() and is_rtsp:
                        print("VisionEngine: Échec RTSP, repli sur la webcam locale (0)...")
                        cap = cv2.VideoCapture(0)

                if not cap.isOpened():
                    print(
                        "VisionEngine: Impossible d'ouvrir la source vidéo. Nouvelle tentative dans 2s..."
                    )
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
                results = self.yolo_model.predict(frame, verbose=False, conf=0.2)
                frame = results[0].plot()

                # Tracker les objets détectés pour le contexte LLM
                detected = []
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        cls_name = r.names.get(cls_id, str(cls_id))
                        conf = float(box.conf[0])
                        if conf > 0.3:
                            detected.append(cls_name)
                if detected:
                    unique = list(dict.fromkeys(detected))  # dédoublonner en gardant l'ordre
                    self.last_yolo_detections = ", ".join(unique)
                else:
                    self.last_yolo_detections = ""

            # Redimensionner pour optimiser la reconnaissance faciale (plus rapide)
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # 2. Traitement Face Recognition
            identified_name = None
            if self.face_rec_enabled and len(self.known_face_encodings) > 0:
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(
                    rgb_small_frame, face_locations
                )

                for (top, right, bottom, left), face_encoding in zip(
                    face_locations, face_encodings
                ):
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings, face_encoding, tolerance=0.5
                    )
                    name = "Inconnu"

                    face_distances = face_recognition.face_distance(
                        self.known_face_encodings, face_encoding
                    )
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            name = self.known_face_names[best_match_index]

                    identified_name = name if name != "Inconnu" else identified_name

                    name_clean = remove_accents(name)
                    is_known = name != "Inconnu"

                    # Couleur : vert pour connu, rouge pour inconnu
                    color = (0, 255, 0) if is_known else (0, 0, 255)
                    label = f"[CONNU] {name_clean}" if is_known else "[INCONNU]"

                    # Fond semi-transparent pour le label
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                    cv2.rectangle(frame, (left * 2, bottom * 2 + 5), (left * 2 + tw + 10, bottom * 2 + 5 + th + 10), color, -1)
                    cv2.putText(frame, label, (left * 2 + 5, bottom * 2 + 5 + th + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

                    # Rectangle autour du visage
                    cv2.rectangle(frame, (left * 2, top * 2), (right * 2, bottom * 2), color, 2)

                # Notifier l'orchestrateur
                if identified_name and identified_name != self._last_identified_name:
                    self._last_identified_name = identified_name
                    if self.on_face_identified:
                        self.on_face_identified(identified_name, None)
                elif not identified_name and self._last_identified_name:
                    self._last_identified_name = None
                    if self.on_face_lost:
                        self.on_face_lost()

            # Affichage conditionnel de la fenêtre (ou mode simulation)
            if self.show_window or self.simulation_mode:
                # Overlay simulation : afficher les infos en temps réel
                if self.simulation_mode:
                    h, w = frame.shape[:2]
                    # Bandeau haut
                    cv2.rectangle(frame, (0, 0), (w, 36), (20, 20, 20), -1)
                    status_parts = ["[SIMULATION]"]
                    if self.yolo_enabled:
                        status_parts.append("YOLO:ON")
                    if self.face_rec_enabled:
                        status_parts.append("FaceRec:ON")
                    if self.last_yolo_detections:
                        status_parts.append(f"Objets: {self.last_yolo_detections}")
                    status_text = " | ".join(status_parts)
                    cv2.putText(frame, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)

                    # Bandeau bas : contexte utilisateur
                    if self._last_identified_name:
                        ctx_text = f"Contexte: {self._last_identified_name}"
                        cv2.rectangle(frame, (0, h - 30), (w, h), (20, 20, 20), -1)
                        cv2.putText(frame, ctx_text, (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                try:
                    cv2.destroyWindow(window_name)
                except Exception:
                    pass
                time.sleep(0.03)  # limiter la conso CPU si pas affiché

    def stop(self):
        self.running = False
        self._leave_stream()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
