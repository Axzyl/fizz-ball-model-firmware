"""Face detection and pose estimation using YOLO + MediaPipe hybrid approach.

Uses YOLO-face for robust detection (especially at longer distances),
then MediaPipe FaceLandmarker for precise pose estimation on detected faces.
"""

from __future__ import annotations

import logging
import math
import os
import urllib.request
from typing import Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

import sys
sys.path.append("..")
import config

logger = logging.getLogger(__name__)


# Model URLs and paths
FACE_LANDMARKER_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
FACE_LANDMARKER_MODEL = "face_landmarker.task"
YOLO_FACE_URL = "https://github.com/lindevs/yolov8-face/releases/latest/download/yolov8n-face-lindevs.pt"
YOLO_FACE_MODEL = "yolov8n-face-lindevs.pt"


def get_models_dir() -> str:
    """Get the models directory path."""
    models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir


def download_model_if_needed(url: str, filename: str) -> str:
    """
    Download a model file if not present.

    Args:
        url: URL to download from
        filename: Local filename to save to

    Returns:
        Full path to model file
    """
    model_path = os.path.join(get_models_dir(), filename)

    if not os.path.exists(model_path):
        logger.info(f"Downloading model: {filename}...")
        try:
            urllib.request.urlretrieve(url, model_path)
            logger.info(f"Model downloaded to: {model_path}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    return model_path


class YOLOFaceDetector:
    """Face detector using YOLO-face (ultralytics).

    YOLO is better at detecting small/distant faces compared to MediaPipe.
    """

    def __init__(self):
        """Initialize the YOLO face detector."""
        logger.info("Initializing YOLO face detector...")

        try:
            from ultralytics import YOLO
            model_path = download_model_if_needed(YOLO_FACE_URL, YOLO_FACE_MODEL)
            self.model = YOLO(model_path)
            self.available = True
            logger.info("YOLO face detector initialized")
        except ImportError:
            logger.warning("ultralytics not installed - YOLO detector unavailable")
            self.model = None
            self.available = False
        except Exception as e:
            logger.warning(f"Failed to initialize YOLO detector: {e}")
            self.model = None
            self.available = False

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Detect faces in the frame.

        Args:
            frame: BGR image

        Returns:
            List of detections, each with 'bbox' (x, y, w, h) and 'confidence'
        """
        if not self.available or self.model is None:
            return []

        try:
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
        except Exception as e:
            logger.debug(f"YOLO detection error: {e}")
            return []


class FacePoseEstimator:
    """Estimates head pose using MediaPipe Face Mesh on cropped face images."""

    # 3D model points for pose estimation
    MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),          # Nose tip
        (0.0, -330.0, -65.0),     # Chin
        (-225.0, 170.0, -135.0),  # Left eye left corner
        (225.0, 170.0, -135.0),   # Right eye right corner
        (-150.0, -150.0, -125.0), # Left mouth corner
        (150.0, -150.0, -125.0)   # Right mouth corner
    ], dtype=np.float64)

    # Landmark indices for the 6 key points
    LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    def __init__(self):
        """Initialize the pose estimator."""
        logger.info("Initializing MediaPipe pose estimator...")

        self.face_mesh = None
        self.use_legacy = False

        try:
            # Try legacy API first (more compatible)
            from mediapipe.python.solutions import face_mesh as mp_mesh
            self.face_mesh = mp_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.use_legacy = True
            logger.info("Using MediaPipe legacy Face Mesh API")
        except (ImportError, AttributeError):
            # Fall back to Tasks API
            model_path = download_model_if_needed(FACE_LANDMARKER_URL, FACE_LANDMARKER_MODEL)
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
                num_faces=1
            )
            self.face_mesh = vision.FaceLandmarker.create_from_options(options)
            logger.info("Using MediaPipe Tasks FaceLandmarker API")

    def estimate_pose(self, face_image: np.ndarray) -> tuple[Optional[tuple[float, float, float]], Optional[np.ndarray]]:
        """
        Estimate head pose from a cropped face image.

        Args:
            face_image: BGR cropped face image

        Returns:
            Tuple of ((yaw, pitch, roll) in degrees, landmarks array) or (None, None) on failure
        """
        if face_image is None or face_image.size == 0:
            return None, None

        h, w = face_image.shape[:2]
        if h < 20 or w < 20:
            return None, None

        rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

        try:
            if self.use_legacy:
                results = self.face_mesh.process(rgb_image)
                if not results.multi_face_landmarks:
                    return None, None
                landmarks_list = results.multi_face_landmarks[0].landmark

                # Convert to numpy array
                landmarks = np.array([
                    (lm.x * w, lm.y * h, lm.z * w) for lm in landmarks_list
                ])

                image_points = np.array([
                    (landmarks_list[idx].x * w, landmarks_list[idx].y * h)
                    for idx in self.LANDMARK_INDICES
                ], dtype=np.float64)
            else:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                results = self.face_mesh.detect(mp_image)
                if not results.face_landmarks:
                    return None, None
                landmarks_list = results.face_landmarks[0]

                # Convert to numpy array
                landmarks = np.array([
                    (lm.x * w, lm.y * h, lm.z * w) for lm in landmarks_list
                ])

                image_points = np.array([
                    (landmarks_list[idx].x * w, landmarks_list[idx].y * h)
                    for idx in self.LANDMARK_INDICES
                ], dtype=np.float64)

            # Camera matrix
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
                return None, landmarks

            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            yaw, pitch, roll = self._rotation_matrix_to_euler(rotation_matrix)

            return (yaw, pitch, roll), landmarks

        except Exception as e:
            logger.debug(f"Pose estimation error: {e}")
            return None, None

    def _rotation_matrix_to_euler(self, R: np.ndarray) -> tuple[float, float, float]:
        """Convert rotation matrix to Euler angles."""
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
    """Validates if a detected face meets requirements."""

    def __init__(self):
        """Initialize validator with config values."""
        self.min_face_width_ratio = getattr(config, 'MIN_FACE_WIDTH_RATIO', 0.08)
        self.max_pitch_angle = getattr(config, 'FACING_YAW_THRESHOLD', 45.0)
        self.max_roll_angle = getattr(config, 'FACING_PITCH_THRESHOLD', 35.0)

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
        """
        Validate if a face detection is valid.

        Args:
            detection: Detection dict with bbox and pose
            frame_width: Width of the frame

        Returns:
            Tuple of (is_valid, list of rejection reasons)
        """
        reasons = []
        x, y, w, h = detection['bbox']
        pose = detection.get('pose')

        # Check face size
        face_width_ratio = w / frame_width
        if face_width_ratio < self.min_face_width_ratio:
            reasons.append(f"Too far ({face_width_ratio:.1%} < {self.min_face_width_ratio:.0%})")

        # Check pose angles
        if pose is not None:
            yaw, pitch, roll = pose
            normalized_roll = self.normalize_roll(roll)

            # Pitch = looking left/right
            if abs(pitch) > self.max_pitch_angle:
                direction = "left" if pitch < 0 else "right"
                reasons.append(f"Looking {direction} ({abs(pitch):.0f}°)")

            # Roll = looking up/down
            if abs(normalized_roll) > self.max_roll_angle:
                direction = "up" if normalized_roll < 0 else "down"
                reasons.append(f"Looking {direction} ({abs(normalized_roll):.0f}°)")
        else:
            reasons.append("No pose data")

        return len(reasons) == 0, reasons


class FaceTracker:
    """
    Hybrid face detection and pose estimation.

    Uses YOLO-face for robust detection (especially at longer distances),
    then MediaPipe for precise pose estimation on detected faces.
    Falls back to MediaPipe-only if YOLO is unavailable.
    """

    def __init__(self) -> None:
        """Initialize the face tracker."""
        logger.info("Initializing FaceTracker (Hybrid YOLO+MediaPipe)...")

        # Initialize YOLO detector
        self.yolo_detector = YOLOFaceDetector()

        # Initialize MediaPipe pose estimator
        self.pose_estimator = FacePoseEstimator()

        # Initialize validator
        self.validator = FaceValidator()

        # Fallback to pure MediaPipe if YOLO not available
        self.fallback_landmarker = None
        if not self.yolo_detector.available:
            logger.info("YOLO unavailable, using MediaPipe-only fallback")
            self._init_fallback_landmarker()

        logger.info("FaceTracker initialized")

    def _init_fallback_landmarker(self) -> None:
        """Initialize MediaPipe FaceLandmarker for fallback detection."""
        model_path = download_model_if_needed(FACE_LANDMARKER_URL, FACE_LANDMARKER_MODEL)
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
            num_faces=config.MAX_NUM_FACES,
            min_face_detection_confidence=config.FACE_DETECTION_CONFIDENCE,
            min_face_presence_confidence=config.FACE_TRACKING_CONFIDENCE,
            min_tracking_confidence=config.FACE_TRACKING_CONFIDENCE,
        )
        self.fallback_landmarker = vision.FaceLandmarker.create_from_options(options)

    def process(self, frame: np.ndarray) -> dict:
        """
        Process a frame for face detection and pose estimation.

        Args:
            frame: BGR image from camera

        Returns:
            Dictionary containing:
                - detected: bool
                - bbox: (x, y, w, h) or None
                - landmarks: np.ndarray of shape (478, 3) or None
                - yaw: float (degrees)
                - pitch: float (degrees)
                - roll: float (degrees)
                - is_facing: bool
                - confidence: float
                - valid: bool (passes all validation checks)
                - invalid_reasons: list of str
        """
        result = {
            "detected": False,
            "bbox": None,
            "landmarks": None,
            "yaw": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "is_facing": False,
            "confidence": 0.0,
            "valid": False,
            "invalid_reasons": [],
        }

        if frame is None:
            return result

        frame_height, frame_width = frame.shape[:2]

        # Use YOLO for detection if available
        if self.yolo_detector.available:
            detections = self.yolo_detector.detect(frame)

            if not detections:
                return result

            # Get the largest/most confident face
            best_detection = max(detections, key=lambda d: d['confidence'])
            x, y, w, h = best_detection['bbox']
            confidence = best_detection['confidence']

            # Crop face with padding for pose estimation
            padding = 0.2
            pad_x = int(w * padding)
            pad_y = int(h * padding)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(frame_width, x + w + pad_x)
            y2 = min(frame_height, y + h + pad_y)

            face_crop = frame[y1:y2, x1:x2]

            # Estimate pose on cropped face
            pose, landmarks = self.pose_estimator.estimate_pose(face_crop)

            # Adjust landmarks to frame coordinates
            if landmarks is not None:
                landmarks[:, 0] += x1
                landmarks[:, 1] += y1

            if pose is not None:
                yaw, pitch, roll = pose
            else:
                yaw, pitch, roll = 0.0, 0.0, 0.0

            # Create detection dict for validation
            detection_data = {
                'bbox': (x, y, w, h),
                'pose': pose,
            }
            is_valid, invalid_reasons = self.validator.validate(detection_data, frame_width)

            # Determine if facing (using config thresholds)
            is_facing = (
                is_valid and
                abs(pitch) < config.FACING_YAW_THRESHOLD and
                abs(self.validator.normalize_roll(roll)) < config.FACING_PITCH_THRESHOLD
            )

            result.update({
                "detected": True,
                "bbox": (x, y, w, h),
                "landmarks": landmarks,
                "yaw": yaw,
                "pitch": pitch,
                "roll": roll,
                "is_facing": is_facing,
                "confidence": confidence,
                "valid": is_valid,
                "invalid_reasons": invalid_reasons,
            })

        else:
            # Fallback to MediaPipe-only detection
            result = self._process_mediapipe_fallback(frame)

        return result

    def _process_mediapipe_fallback(self, frame: np.ndarray) -> dict:
        """Process using MediaPipe only (fallback when YOLO unavailable)."""
        result = {
            "detected": False,
            "bbox": None,
            "landmarks": None,
            "yaw": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "is_facing": False,
            "confidence": 0.0,
            "valid": False,
            "invalid_reasons": [],
        }

        if self.fallback_landmarker is None:
            return result

        frame_height, frame_width = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        detection_result = self.fallback_landmarker.detect(mp_image)

        if not detection_result.face_landmarks:
            return result

        face_landmarks = detection_result.face_landmarks[0]
        landmarks = np.array([
            [lm.x * frame_width, lm.y * frame_height, lm.z * frame_width]
            for lm in face_landmarks
        ])

        # Calculate bounding box
        x_coords = landmarks[:, 0]
        y_coords = landmarks[:, 1]
        x_min, x_max = int(x_coords.min()), int(x_coords.max())
        y_min, y_max = int(y_coords.min()), int(y_coords.max())
        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        # Get pose from transformation matrix
        yaw, pitch, roll = 0.0, 0.0, 0.0
        if detection_result.facial_transformation_matrixes:
            matrix = detection_result.facial_transformation_matrixes[0]
            yaw, pitch, roll = self._matrix_to_euler(matrix)

        is_facing = (
            abs(yaw) < config.FACING_YAW_THRESHOLD
            and abs(pitch) < config.FACING_PITCH_THRESHOLD
        )

        confidence = self._calculate_confidence(landmarks)

        result.update({
            "detected": True,
            "bbox": bbox,
            "landmarks": landmarks,
            "yaw": yaw,
            "pitch": pitch,
            "roll": roll,
            "is_facing": is_facing,
            "confidence": confidence,
            "valid": is_facing,
            "invalid_reasons": [] if is_facing else ["Not facing camera"],
        })

        return result

    def _matrix_to_euler(self, matrix) -> tuple[float, float, float]:
        """Extract Euler angles from facial transformation matrix."""
        try:
            m = np.array(matrix.data).reshape(4, 4)
            r = m[:3, :3]
            sy = np.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)

            if sy > 1e-6:
                pitch = np.arctan2(-r[2, 0], sy)
                yaw = np.arctan2(r[1, 0], r[0, 0])
                roll = np.arctan2(r[2, 1], r[2, 2])
            else:
                pitch = np.arctan2(-r[2, 0], sy)
                yaw = np.arctan2(-r[0, 1], r[1, 1])
                roll = 0

            return (
                float(np.degrees(yaw)),
                float(np.degrees(pitch)),
                float(np.degrees(roll)),
            )
        except Exception as e:
            logger.debug(f"Matrix to euler conversion failed: {e}")
            return 0.0, 0.0, 0.0

    def _calculate_confidence(self, landmarks: np.ndarray) -> float:
        """Calculate a confidence score based on landmark positions."""
        try:
            z_coords = landmarks[:, 2]
            z_variance = np.var(z_coords)
            confidence = 1.0 - min(z_variance / 1000.0, 1.0)
            return float(max(0.0, min(1.0, confidence)))
        except Exception:
            return 0.5

    def draw_annotations(
        self,
        frame: np.ndarray,
        result: dict,
        draw_landmarks: bool = True,
        draw_bbox: bool = True,
        draw_pose: bool = True,
    ) -> np.ndarray:
        """
        Draw detection results on frame.

        Args:
            frame: BGR image to draw on
            result: Detection result from process()
            draw_landmarks: Whether to draw facial landmarks
            draw_bbox: Whether to draw bounding box
            draw_pose: Whether to draw pose axes

        Returns:
            Annotated frame
        """
        if not result["detected"]:
            return frame

        annotated = frame.copy()

        # Draw bounding box
        if draw_bbox and result["bbox"]:
            x, y, w, h = result["bbox"]
            color = config.COLOR_FACING_YES if result["is_facing"] else config.COLOR_FACING_NO
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

            # Draw confidence
            conf_text = f"{result['confidence']:.2f}"
            cv2.putText(annotated, conf_text, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw landmarks (every 5th for performance)
        if draw_landmarks and result["landmarks"] is not None:
            for i in range(0, len(result["landmarks"]), 5):
                landmark = result["landmarks"][i]
                lx, ly = int(landmark[0]), int(landmark[1])
                cv2.circle(annotated, (lx, ly), 1, config.COLOR_LANDMARKS, -1)

        # Draw pose axes
        if draw_pose and result["landmarks"] is not None and len(result["landmarks"]) > 1:
            nose = result["landmarks"][1]
            nose_point = (int(nose[0]), int(nose[1]))

            axis_length = 50
            yaw_rad = np.radians(result["yaw"])
            pitch_rad = np.radians(result["pitch"])

            # X axis (red)
            x_end = (
                int(nose_point[0] + axis_length * np.cos(yaw_rad)),
                nose_point[1],
            )
            cv2.arrowedLine(annotated, nose_point, x_end, config.COLOR_POSE_X, 2, tipLength=0.3)

            # Y axis (green)
            y_end = (
                nose_point[0],
                int(nose_point[1] - axis_length * np.cos(pitch_rad)),
            )
            cv2.arrowedLine(annotated, nose_point, y_end, config.COLOR_POSE_Y, 2, tipLength=0.3)

            # Z axis (blue)
            z_end = (
                int(nose_point[0] - axis_length * np.sin(yaw_rad) * 0.5),
                int(nose_point[1] + axis_length * np.sin(pitch_rad) * 0.5),
            )
            cv2.arrowedLine(annotated, nose_point, z_end, config.COLOR_POSE_Z, 2, tipLength=0.3)

        return annotated

    def close(self) -> None:
        """Release resources."""
        if self.fallback_landmarker is not None:
            self.fallback_landmarker.close()
        logger.info("FaceTracker closed")
