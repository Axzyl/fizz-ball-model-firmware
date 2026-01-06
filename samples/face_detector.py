import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import urllib.request
import os


MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
MODEL_PATH = "blaze_face_short_range.tflite"


def download_model_if_needed():
    """Download the face detection model if not present."""
    if not os.path.exists(MODEL_PATH):
        print("Downloading face detection model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model downloaded.")


class FaceDetector:
    def __init__(self, min_confidence=0.5):
        download_model_if_needed()

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=min_confidence
        )
        self.detector = vision.FaceDetector.create_from_options(options)

    def detect(self, frame, scale=1.0):
        """
        Detect a face in the frame.

        Args:
            frame: BGR image from camera
            scale: Downsample factor (e.g., 0.25 = 1/4 resolution)

        Returns:
            dict with 'found' (bool) and 'bbox' (x, y, w, h) if found,
            or None for bbox if not found. Bbox is in original frame coordinates.
        """
        # Downsample for detection
        if scale != 1.0:
            small_frame = cv2.resize(frame, None, fx=scale, fy=scale)
        else:
            small_frame = frame

        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        results = self.detector.detect(mp_image)

        if not results.detections:
            return {"found": False, "bbox": None}

        # Use the first detected face
        detection = results.detections[0]
        bbox = detection.bounding_box

        # Scale bbox back to original frame coordinates
        inv_scale = 1.0 / scale
        x = int(bbox.origin_x * inv_scale)
        y = int(bbox.origin_y * inv_scale)
        w = int(bbox.width * inv_scale)
        h = int(bbox.height * inv_scale)

        return {
            "found": True,
            "bbox": (x, y, w, h)
        }

    def draw_bbox(self, frame, bbox, color=(0, 255, 0)):
        """Draw bounding box on frame."""
        x, y, w, h = bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        return frame

    def close(self):
        self.detector.close()
