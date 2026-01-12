import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import time
import os
import json
import urllib.request
from abc import ABC, abstractmethod
import math


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    default_config = {
        "face_detection": {
            "min_face_width_ratio": 0.08,
            "max_pitch_angle": 45,
            "max_roll_angle": 35,
            "pose_required": True
        },
        "display": {
            "valid_color": [0, 255, 0],
            "invalid_color": [0, 0, 255],
            "pose_arrow_color": [255, 0, 255],
            "show_pose_text": True,
            "show_validity_reason": True
        },
        "camera": {
            "default_width": 640,
            "default_height": 480
        }
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                loaded = json.load(f)
                for key in default_config:
                    if key in loaded:
                        default_config[key].update(loaded[key])
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")

    return default_config


CONFIG = load_config()


class FaceDetector(ABC):
    """Abstract base class for face detectors."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[dict]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class MediaPipeDetector(FaceDetector):
    """Face detector using MediaPipe."""

    def __init__(self):
        self.use_legacy = False
        self.detector = None

        try:
            from mediapipe.python.solutions import face_detection as mp_face
            self.detector = mp_face.FaceDetection(
                model_selection=1,
                min_detection_confidence=0.5
            )
            self.use_legacy = True
        except (ImportError, AttributeError):
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = self._get_model_path()
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=0.5
            )
            self.detector = vision.FaceDetector.create_from_options(options)

    def _get_model_path(self) -> str:
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "blaze_face_short_range.tflite")

        if not os.path.exists(model_path):
            print("Downloading MediaPipe face detection model...")
            url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
            urllib.request.urlretrieve(url, model_path)
            print("MediaPipe model downloaded.")

        return model_path

    def detect(self, frame: np.ndarray) -> list[dict]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        detections = []
        h, w = frame.shape[:2]

        if self.use_legacy:
            results = self.detector.process(rgb_frame)
            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    width = int(bbox.width * w)
                    height = int(bbox.height * h)
                    confidence = detection.score[0]
                    detections.append({
                        'bbox': (x, y, width, height),
                        'confidence': confidence
                    })
        else:
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.detector.detect(mp_image)
            for detection in results.detections:
                bbox = detection.bounding_box
                x, y = bbox.origin_x, bbox.origin_y
                width, height = bbox.width, bbox.height
                confidence = detection.categories[0].score
                detections.append({
                    'bbox': (x, y, width, height),
                    'confidence': confidence
                })

        return detections

    def get_name(self) -> str:
        return "MediaPipe"


class YOLOFaceDetector(FaceDetector):
    """Face detector using YOLO-face (ultralytics)."""

    MODEL_URL = "https://github.com/lindevs/yolov8-face/releases/latest/download/yolov8n-face-lindevs.pt"

    def __init__(self):
        from ultralytics import YOLO
        model_path = self._get_model_path()
        self.model = YOLO(model_path)

    def _get_model_path(self) -> str:
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "yolov8n-face-lindevs.pt")

        if not os.path.exists(model_path):
            print("Downloading YOLOv8n-face model...")
            urllib.request.urlretrieve(self.MODEL_URL, model_path)
            print("YOLO-face model downloaded.")

        return model_path

    def detect(self, frame: np.ndarray) -> list[dict]:
        results = self.model(frame, verbose=False)

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    x, y = int(x1), int(y1)
                    w, h = int(x2 - x1), int(y2 - y1)
                    detections.append({
                        'bbox': (x, y, w, h),
                        'confidence': confidence
                    })

        return detections

    def get_name(self) -> str:
        return "YOLO-face"


class FacePoseEstimator:
    """Estimates head pose using MediaPipe Face Mesh."""

    MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0)
    ], dtype=np.float64)

    LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    def __init__(self):
        self.face_mesh = None
        self.use_legacy = False

        try:
            from mediapipe.python.solutions import face_mesh as mp_mesh
            self.face_mesh = mp_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.use_legacy = True
        except (ImportError, AttributeError):
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = self._get_model_path()
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
                num_faces=1
            )
            self.face_mesh = vision.FaceLandmarker.create_from_options(options)

    def _get_model_path(self) -> str:
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "face_landmarker.task")

        if not os.path.exists(model_path):
            print("Downloading MediaPipe Face Landmarker model...")
            url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
            print("Face Landmarker model downloaded.")

        return model_path

    def estimate_pose(self, face_image: np.ndarray) -> tuple[float, float, float] | None:
        if face_image is None or face_image.size == 0:
            return None

        h, w = face_image.shape[:2]
        if h < 20 or w < 20:
            return None

        rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

        try:
            if self.use_legacy:
                results = self.face_mesh.process(rgb_image)
                if not results.multi_face_landmarks:
                    return None
                landmarks = results.multi_face_landmarks[0].landmark
                image_points = np.array([
                    (landmarks[idx].x * w, landmarks[idx].y * h)
                    for idx in self.LANDMARK_INDICES
                ], dtype=np.float64)
            else:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                results = self.face_mesh.detect(mp_image)
                if not results.face_landmarks:
                    return None
                landmarks = results.face_landmarks[0]
                image_points = np.array([
                    (landmarks[idx].x * w, landmarks[idx].y * h)
                    for idx in self.LANDMARK_INDICES
                ], dtype=np.float64)

            focal_length = w
            center = (w / 2, h / 2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)

            dist_coeffs = np.zeros((4, 1))

            success, rotation_vector, _ = cv2.solvePnP(
                self.MODEL_POINTS,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

            if not success:
                return None

            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            yaw, pitch, roll = self._rotation_matrix_to_euler(rotation_matrix)

            return (yaw, pitch, roll)

        except Exception:
            return None

    def _rotation_matrix_to_euler(self, R: np.ndarray) -> tuple[float, float, float]:
        sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

        if sy > 1e-6:
            roll = math.atan2(R[2, 1], R[2, 2])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = math.atan2(R[1, 0], R[0, 0])
        else:
            roll = math.atan2(-R[1, 2], R[1, 1])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = 0

        return (
            math.degrees(yaw),
            math.degrees(pitch),
            math.degrees(roll)
        )


class FaceValidator:
    """Validates if a detected face meets requirements based on config."""

    def __init__(self, config: dict):
        self.config = config["face_detection"]

    @staticmethod
    def normalize_roll(roll: float) -> float:
        """Normalize roll so that 0 = looking straight at camera."""
        if abs(roll) > 90:
            if roll > 0:
                return 180 - roll
            else:
                return -180 - roll
        return roll

    def validate(self, detection: dict, frame_width: int) -> tuple[bool, list[str]]:
        reasons = []
        x, y, w, h = detection['bbox']
        pose = detection.get('pose')

        min_width_ratio = self.config["min_face_width_ratio"]
        face_width_ratio = w / frame_width

        if face_width_ratio < min_width_ratio:
            reasons.append(f"Too far ({face_width_ratio:.1%} < {min_width_ratio:.0%})")

        if self.config["pose_required"] and pose is None:
            reasons.append("No pose data")
        elif pose is not None:
            yaw, pitch, roll = pose
            normalized_roll = self.normalize_roll(roll)

            max_pitch = self.config["max_pitch_angle"]
            if abs(pitch) > max_pitch:
                direction = "left" if pitch < 0 else "right"
                reasons.append(f"Looking {direction} ({abs(pitch):.0f}° > {max_pitch}°)")

            max_roll = self.config["max_roll_angle"]
            if abs(normalized_roll) > max_roll:
                direction = "up" if normalized_roll < 0 else "down"
                reasons.append(f"Looking {direction} ({abs(normalized_roll):.0f}° > {max_roll}°)")

        return len(reasons) == 0, reasons


class HybridDetector(FaceDetector):
    """Hybrid detector: YOLO-face for detection + MediaPipe for pose estimation."""

    def __init__(self):
        print("Initializing Hybrid detector (YOLO + MediaPipe)...")
        self.yolo_detector = YOLOFaceDetector()
        self.pose_estimator = FacePoseEstimator()
        self.validator = FaceValidator(CONFIG)
        print("Hybrid detector ready.")

    def detect(self, frame: np.ndarray) -> list[dict]:
        detections = self.yolo_detector.detect(frame)
        h, w = frame.shape[:2]

        for det in detections:
            x, y, bw, bh = det['bbox']

            padding = 0.2
            pad_x = int(bw * padding)
            pad_y = int(bh * padding)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)

            face_crop = frame[y1:y2, x1:x2]
            pose = self.pose_estimator.estimate_pose(face_crop)
            det['pose'] = pose

            is_valid, reasons = self.validator.validate(det, w)
            det['valid'] = is_valid
            det['invalid_reasons'] = reasons

        return detections

    def get_name(self) -> str:
        return "Hybrid (YOLO+MP)"


class CameraManager:
    """Manages camera devices and capture."""

    def __init__(self):
        self.cap = None
        self.current_device = 0
        self.available_devices = self._find_cameras()

    def _find_cameras(self, max_devices: int = 5) -> list[int]:
        available = []
        for i in range(max_devices):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available if available else [0]

    def open(self, device_id: int = 0) -> bool:
        if self.cap is not None:
            self.cap.release()

        self.cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
        if self.cap.isOpened():
            self.current_device = device_id
            cam_config = CONFIG["camera"]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_config["default_width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_config["default_height"])
            return True
        return False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.cap is None or not self.cap.isOpened():
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class FaceDetectionApp:
    """Main application with UI."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Face Detection with Pose Estimation")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = CONFIG
        self.camera = CameraManager()
        self.detectors = {}
        self.current_detector = None
        self.running = False
        self.frame_times = []
        self.is_observed = False  # True if any person is looking at the camera

        self._init_detectors()
        self._create_ui()
        self._start_camera()

    def _init_detectors(self):
        try:
            self.detectors['Hybrid (YOLO+MP)'] = HybridDetector()
        except Exception as e:
            print(f"Failed to load Hybrid detector: {e}")

        try:
            self.detectors['YOLO-face'] = YOLOFaceDetector()
        except Exception as e:
            print(f"Failed to load YOLO-face: {e}")

        try:
            self.detectors['MediaPipe'] = MediaPipeDetector()
        except Exception as e:
            print(f"Failed to load MediaPipe: {e}")

        if self.detectors:
            if 'Hybrid (YOLO+MP)' in self.detectors:
                self.current_detector = self.detectors['Hybrid (YOLO+MP)']
            else:
                self.current_detector = list(self.detectors.values())[0]

    def _create_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.video_label = ttk.Label(main_frame)
        self.video_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Observed state frame - prominent display at top
        observed_frame = ttk.LabelFrame(main_frame, text="Observed State", padding="10")
        observed_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.observed_label = ttk.Label(
            observed_frame, text="NOT OBSERVED", font=("Helvetica", 16, "bold"),
            foreground="red", width=20, anchor="center"
        )
        self.observed_label.grid(row=0, column=0, padx=10)

        ttk.Label(observed_frame, text="(True if any person is looking at camera)").grid(row=0, column=1)

        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        controls_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(controls_frame, text="Camera:").grid(row=0, column=0, padx=(0, 5))
        self.camera_var = tk.StringVar()
        camera_options = [f"Camera {i}" for i in self.camera.available_devices]
        self.camera_combo = ttk.Combobox(
            controls_frame, textvariable=self.camera_var,
            values=camera_options, state="readonly", width=15
        )
        self.camera_combo.grid(row=0, column=1, padx=(0, 20))
        self.camera_combo.set(camera_options[0] if camera_options else "No camera")
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_change)

        ttk.Label(controls_frame, text="Model:").grid(row=0, column=2, padx=(0, 5))
        self.model_var = tk.StringVar()
        model_options = list(self.detectors.keys())
        self.model_combo = ttk.Combobox(
            controls_frame, textvariable=self.model_var,
            values=model_options, state="readonly", width=18
        )
        self.model_combo.grid(row=0, column=3, padx=(0, 20))
        if 'Hybrid (YOLO+MP)' in model_options:
            self.model_combo.set('Hybrid (YOLO+MP)')
        elif model_options:
            self.model_combo.set(model_options[0])
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="10")
        stats_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(stats_frame, text="FPS:").grid(row=0, column=0, padx=(0, 5))
        self.fps_label = ttk.Label(stats_frame, text="0.0")
        self.fps_label.grid(row=0, column=1, padx=(0, 20))

        ttk.Label(stats_frame, text="Faces:").grid(row=0, column=2, padx=(0, 5))
        self.faces_label = ttk.Label(stats_frame, text="0")
        self.faces_label.grid(row=0, column=3, padx=(0, 20))

        ttk.Label(stats_frame, text="Valid:").grid(row=0, column=4, padx=(0, 5))
        self.valid_faces_label = ttk.Label(stats_frame, text="0")
        self.valid_faces_label.grid(row=0, column=5, padx=(0, 20))

        ttk.Label(stats_frame, text="Active:").grid(row=0, column=6, padx=(0, 5))
        self.model_label = ttk.Label(stats_frame, text="-")
        self.model_label.grid(row=0, column=7)

        pose_frame = ttk.LabelFrame(main_frame, text="Head Pose (First Face)", padding="10")
        pose_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(pose_frame, text="L/R (Pitch):").grid(row=0, column=0, padx=(0, 5))
        self.pitch_label = ttk.Label(pose_frame, text="-", width=8)
        self.pitch_label.grid(row=0, column=1, padx=(0, 15))

        ttk.Label(pose_frame, text="U/D (Roll):").grid(row=0, column=2, padx=(0, 5))
        self.roll_label = ttk.Label(pose_frame, text="-", width=8)
        self.roll_label.grid(row=0, column=3, padx=(0, 15))

        ttk.Label(pose_frame, text="Direction:").grid(row=0, column=4, padx=(0, 5))
        self.direction_label = ttk.Label(pose_frame, text="-", width=12)
        self.direction_label.grid(row=0, column=5)

        validity_frame = ttk.LabelFrame(main_frame, text="Validity Status (First Face)", padding="10")
        validity_frame.grid(row=5, column=0, columnspan=2, sticky="ew")

        ttk.Label(validity_frame, text="Status:").grid(row=0, column=0, padx=(0, 5))
        self.status_label = ttk.Label(validity_frame, text="-", width=10)
        self.status_label.grid(row=0, column=1, padx=(0, 15))

        ttk.Label(validity_frame, text="Issues:").grid(row=0, column=2, padx=(0, 5))
        self.issues_label = ttk.Label(validity_frame, text="-", width=50, anchor="w")
        self.issues_label.grid(row=0, column=3, sticky="w")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def _start_camera(self):
        device_id = self.camera.available_devices[0] if self.camera.available_devices else 0
        if self.camera.open(device_id):
            self.running = True
            self._update_frame()
        else:
            self.video_label.config(text="Failed to open camera")

    def _on_camera_change(self, event):
        selection = self.camera_combo.current()
        if 0 <= selection < len(self.camera.available_devices):
            self.camera.open(self.camera.available_devices[selection])

    def _on_model_change(self, event):
        model_name = self.model_var.get()
        if model_name in self.detectors:
            self.current_detector = self.detectors[model_name]

    def _get_direction_text(self, pitch: float, roll: float) -> str:
        normalized_roll = FaceValidator.normalize_roll(roll)
        directions = []

        if normalized_roll < -15:
            directions.append("Up")
        elif normalized_roll > 15:
            directions.append("Down")

        if pitch < -15:
            directions.append("Left")
        elif pitch > 15:
            directions.append("Right")

        return " + ".join(directions) if directions else "Forward"

    def _draw_detections(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        display_config = self.config["display"]
        valid_color = tuple(display_config["valid_color"])
        invalid_color = tuple(display_config["invalid_color"])
        pose_color = tuple(display_config["pose_arrow_color"])
        show_pose_text = display_config["show_pose_text"]
        show_validity_reason = display_config["show_validity_reason"]

        for det in detections:
            x, y, w, h = det['bbox']
            confidence = det['confidence']
            pose = det.get('pose')
            is_valid = det.get('valid', True)
            invalid_reasons = det.get('invalid_reasons', [])

            box_color = valid_color if is_valid else invalid_color
            cv2.rectangle(frame, (x, y), (x + w, y + h), box_color, 2)

            label = f"{confidence:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(frame, (x, y - label_size[1] - 6), (x + label_size[0] + 4, y), box_color, -1)
            cv2.putText(frame, label, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

            if not is_valid and show_validity_reason and invalid_reasons:
                reason_text = "; ".join(invalid_reasons[:2])
                cv2.putText(frame, reason_text, (x, y + h + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, invalid_color, 1)

            if pose is not None:
                yaw, pitch, roll = pose
                normalized_roll = FaceValidator.normalize_roll(roll)
                center_x = x + w // 2
                center_y = y + h // 2

                arrow_length = min(w, h) // 2
                end_x = int(center_x + arrow_length * math.sin(math.radians(pitch)))
                end_y = int(center_y + arrow_length * math.sin(math.radians(normalized_roll)))

                cv2.arrowedLine(frame, (center_x, center_y), (end_x, end_y), pose_color, 3, tipLength=0.3)
                cv2.circle(frame, (center_x, center_y), 5, pose_color, -1)

                if show_pose_text:
                    pose_text = f"P:{pitch:.0f} R:{normalized_roll:.0f}"
                    cv2.putText(frame, pose_text, (x, y + h + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, pose_color, 2)

        return frame

    def _update_frame(self):
        if not self.running:
            return

        start_time = time.time()

        ret, frame = self.camera.read()
        if ret and frame is not None:
            detections = []
            if self.current_detector is not None:
                try:
                    detections = self.current_detector.detect(frame)
                except Exception as e:
                    print(f"Detection error: {e}")

            frame = self._draw_detections(frame, detections)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(image=img)

            self.video_label.config(image=photo)
            self.video_label.image = photo

            elapsed = time.time() - start_time
            self.frame_times.append(elapsed)
            if len(self.frame_times) > 30:
                self.frame_times.pop(0)

            avg_time = sum(self.frame_times) / len(self.frame_times)
            fps = 1.0 / avg_time if avg_time > 0 else 0

            valid_count = sum(1 for d in detections if d.get('valid', True))
            self.is_observed = valid_count > 0

            self.fps_label.config(text=f"{fps:.1f}")
            self.faces_label.config(text=str(len(detections)))
            self.valid_faces_label.config(text=str(valid_count))
            if self.current_detector:
                self.model_label.config(text=self.current_detector.get_name())

            # Update observed state
            if self.is_observed:
                self.observed_label.config(text="OBSERVED", foreground="green")
            else:
                self.observed_label.config(text="NOT OBSERVED", foreground="red")

            if detections:
                first_det = detections[0]
                pose = first_det.get('pose')
                is_valid = first_det.get('valid', True)
                invalid_reasons = first_det.get('invalid_reasons', [])

                if pose:
                    yaw, pitch, roll = pose
                    normalized_roll = FaceValidator.normalize_roll(roll)
                    self.pitch_label.config(text=f"{pitch:.1f}")
                    self.roll_label.config(text=f"{normalized_roll:.1f}")
                    self.direction_label.config(text=self._get_direction_text(pitch, roll))
                else:
                    self.pitch_label.config(text="-")
                    self.roll_label.config(text="-")
                    self.direction_label.config(text="-")

                self.status_label.config(
                    text="VALID" if is_valid else "INVALID",
                    foreground="green" if is_valid else "red"
                )
                self.issues_label.config(text="; ".join(invalid_reasons) if invalid_reasons else "None")
            else:
                self.pitch_label.config(text="-")
                self.roll_label.config(text="-")
                self.direction_label.config(text="-")
                self.status_label.config(text="-", foreground="black")
                self.issues_label.config(text="-")

        self.root.after(10, self._update_frame)

    def on_close(self):
        self.running = False
        self.camera.release()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FaceDetectionApp()
    app.run()
