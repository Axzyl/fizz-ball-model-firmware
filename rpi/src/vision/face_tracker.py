"""Face detection and pose estimation using MediaPipe Tasks API."""

from __future__ import annotations

import logging
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


def download_model_if_needed(url: str, path: str) -> str:
    """
    Download a model file if not present.

    Args:
        url: URL to download from
        path: Local filename to save to

    Returns:
        Full path to model file
    """
    # Check in models directory first, then current directory
    models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    os.makedirs(models_dir, exist_ok=True)

    model_path = os.path.join(models_dir, path)

    if not os.path.exists(model_path):
        logger.info(f"Downloading model: {path}...")
        try:
            urllib.request.urlretrieve(url, model_path)
            logger.info(f"Model downloaded to: {model_path}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    return model_path


class FaceTracker:
    """
    Face detection and pose estimation using MediaPipe Tasks API.

    Uses FaceLandmarker for detection, landmark extraction, and pose estimation.
    """

    # Landmark indices for pose estimation (using FaceLandmarker indices)
    # These map to similar points as the old Face Mesh
    POSE_LANDMARKS = [
        1,    # Nose tip
        33,   # Left eye left corner
        263,  # Right eye right corner
        61,   # Left mouth corner
        291,  # Right mouth corner
        199,  # Chin
    ]

    # 3D model points for pose estimation (generic face model)
    MODEL_POINTS = np.array([
        [0.0, 0.0, 0.0],           # Nose tip
        [-30.0, -30.0, -30.0],     # Left eye left corner
        [30.0, -30.0, -30.0],      # Right eye right corner
        [-25.0, 40.0, -20.0],      # Left mouth corner
        [25.0, 40.0, -20.0],       # Right mouth corner
        [0.0, 70.0, -10.0],        # Chin
    ], dtype=np.float64)

    def __init__(self) -> None:
        """Initialize the face tracker."""
        logger.info("Initializing FaceTracker (MediaPipe Tasks API)...")

        # Download model if needed
        model_path = download_model_if_needed(FACE_LANDMARKER_URL, FACE_LANDMARKER_MODEL)

        # Create FaceLandmarker
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
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

        # Camera matrix (will be set based on frame size)
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        logger.info("FaceTracker initialized")

    def _get_camera_matrix(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Get or create camera matrix based on frame size."""
        if self.camera_matrix is None:
            focal_length = frame_width
            center = (frame_width / 2, frame_height / 2)
            self.camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ], dtype=np.float64)
        return self.camera_matrix

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
        }

        if frame is None:
            return result

        frame_height, frame_width = frame.shape[:2]

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Detect face landmarks
        detection_result = self.landmarker.detect(mp_image)

        if not detection_result.face_landmarks:
            return result

        # Get first face landmarks
        face_landmarks = detection_result.face_landmarks[0]

        # Convert landmarks to numpy array with pixel coordinates
        landmarks = np.array([
            [lm.x * frame_width, lm.y * frame_height, lm.z * frame_width]
            for lm in face_landmarks
        ])

        # Calculate bounding box from landmarks
        x_coords = landmarks[:, 0]
        y_coords = landmarks[:, 1]
        x_min, x_max = int(x_coords.min()), int(x_coords.max())
        y_min, y_max = int(y_coords.min()), int(y_coords.max())
        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        # Calculate head pose
        yaw, pitch, roll = self._estimate_pose(landmarks, frame_width, frame_height)

        # If transformation matrix is available, use it for more accurate pose
        if detection_result.facial_transformation_matrixes:
            matrix = detection_result.facial_transformation_matrixes[0]
            # Extract rotation from transformation matrix
            yaw_m, pitch_m, roll_m = self._matrix_to_euler(matrix)
            # Use matrix-based angles (often more stable)
            yaw, pitch, roll = yaw_m, pitch_m, roll_m

        # Determine if facing camera
        is_facing = (
            abs(yaw) < config.FACING_YAW_THRESHOLD
            and abs(pitch) < config.FACING_PITCH_THRESHOLD
        )

        # Calculate confidence
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
        })

        return result

    def _matrix_to_euler(self, matrix) -> tuple[float, float, float]:
        """
        Extract Euler angles from facial transformation matrix.

        Args:
            matrix: 4x4 transformation matrix from FaceLandmarker

        Returns:
            Tuple of (yaw, pitch, roll) in degrees
        """
        try:
            # Matrix is a FlattenedMatrix, convert to numpy
            m = np.array(matrix.data).reshape(4, 4)

            # Extract rotation matrix (upper-left 3x3)
            r = m[:3, :3]

            # Calculate Euler angles
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

    def _estimate_pose(
        self,
        landmarks: np.ndarray,
        frame_width: int,
        frame_height: int,
    ) -> tuple[float, float, float]:
        """
        Estimate head pose using solvePnP.

        Returns:
            Tuple of (yaw, pitch, roll) in degrees
        """
        try:
            # Get 2D image points for pose estimation
            image_points = np.array([
                landmarks[idx][:2] for idx in self.POSE_LANDMARKS
            ], dtype=np.float64)

            camera_matrix = self._get_camera_matrix(frame_width, frame_height)

            # Solve PnP
            success, rotation_vector, translation_vector = cv2.solvePnP(
                self.MODEL_POINTS,
                image_points,
                camera_matrix,
                self.dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            if not success:
                return 0.0, 0.0, 0.0

            # Convert rotation vector to rotation matrix
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

            # Get Euler angles from rotation matrix
            proj_matrix = np.hstack((rotation_matrix, translation_vector))
            _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)

            pitch = euler_angles[0, 0]
            yaw = euler_angles[1, 0]
            roll = euler_angles[2, 0]

            return float(yaw), float(pitch), float(roll)

        except Exception as e:
            logger.debug(f"Pose estimation failed: {e}")
            return 0.0, 0.0, 0.0

    def _calculate_confidence(self, landmarks: np.ndarray) -> float:
        """
        Calculate a confidence score based on landmark positions.
        """
        try:
            # Use the z-coordinate variance as a proxy for confidence
            z_coords = landmarks[:, 2]
            z_variance = np.var(z_coords)

            # Normalize to 0-1 range
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

        # Draw landmarks (every 5th for performance)
        if draw_landmarks and result["landmarks"] is not None:
            for i in range(0, len(result["landmarks"]), 5):
                landmark = result["landmarks"][i]
                x, y = int(landmark[0]), int(landmark[1])
                cv2.circle(annotated, (x, y), 1, config.COLOR_LANDMARKS, -1)

        # Draw pose axes
        if draw_pose and result["landmarks"] is not None:
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
        self.landmarker.close()
        logger.info("FaceTracker closed")
