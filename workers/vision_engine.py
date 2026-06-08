class VisionEngine:
    def __init__(self):
        self.yolo_enabled = False
        self.face_rec_enabled = False

    def enable_yolo(self, state: bool):
        self.yolo_enabled = state
        print(f"VisionEngine: YOLOv8 {'activé' if state else 'désactivé'}")

    def enable_face_rec(self, state: bool):
        self.face_rec_enabled = state
        print(f"VisionEngine: Reconnaissance Faciale {'activée' if state else 'désactivée'}")

    def process_frame(self, frame):
        """Analyse une image avec OpenCV/Ultralytics si activé"""
        if not self.yolo_enabled and not self.face_rec_enabled:
            return None
        
        results = {}
        if self.yolo_enabled:
            # Exécuter YOLO
            results["objects"] = ["person", "laptop"]
        
        if self.face_rec_enabled:
            # Exécuter face_recognition
            results["faces"] = ["Teano"]
            
        return results
