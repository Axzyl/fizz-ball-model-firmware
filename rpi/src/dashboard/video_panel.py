"""Video panel for displaying camera feed with overlays."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

import sys
sys.path.append("..")
import config
from state import FaceState


class VideoPanel:
    """
    Video panel that displays camera feed with face detection overlays.

    Renders:
    - Live camera feed
    - Face bounding box (green if facing, red if not)
    - Facial landmarks
    - Head pose axes
    - Facing indicator
    """

    def __init__(self, width: int, height: int) -> None:
        """
        Initialize video panel.

        Args:
            width: Panel width in pixels
            height: Panel height in pixels
        """
        self.width = width
        self.height = height
        # Track actual source frame dimensions for correct scaling
        self._source_width = config.CAMERA_WIDTH
        self._source_height = config.CAMERA_HEIGHT

    def render(
        self,
        frame: Optional[np.ndarray],
        face: FaceState,
    ) -> np.ndarray:
        """
        Render video panel with overlays.

        Args:
            frame: Raw camera frame (BGR)
            face: Current face detection state

        Returns:
            Rendered panel as BGR image
        """
        # Create blank panel if no frame
        if frame is None:
            panel = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            panel[:] = config.COLOR_PANEL_BG
            cv2.putText(
                panel,
                "No Camera Feed",
                (self.width // 2 - 100, self.height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                config.COLOR_TEXT,
                2,
            )
            return panel

        # Get ACTUAL frame dimensions (this is critical for correct bbox scaling)
        # The camera may return a different resolution than config.CAMERA_WIDTH/HEIGHT
        self._source_height, self._source_width = frame.shape[:2]

        # Resize frame to fit panel
        panel = cv2.resize(frame, (self.width, self.height))

        # Draw overlays if face detected
        if face.detected:
            self._draw_bbox(panel, face)
            self._draw_landmarks(panel, face)
            self._draw_pose_axes(panel, face)
            self._draw_facing_indicator(panel, face)

        # Draw status overlay
        self._draw_status_overlay(panel, face)

        return panel

    def _draw_bbox(self, panel: np.ndarray, face: FaceState) -> None:
        """Draw bounding box around detected face."""
        if face.bbox is None:
            return

        # Scale bbox from source frame coordinates to panel coordinates
        # IMPORTANT: Use actual source frame dimensions, not config values!
        frame_scale_x = self.width / self._source_width
        frame_scale_y = self.height / self._source_height

        x, y, w, h = face.bbox
        x = int(x * frame_scale_x)
        y = int(y * frame_scale_y)
        w = int(w * frame_scale_x)
        h = int(h * frame_scale_y)

        # Color based on facing status
        color = config.COLOR_FACING_YES if face.is_facing else config.COLOR_FACING_NO

        cv2.rectangle(panel, (x, y), (x + w, y + h), color, 2)

    def _draw_landmarks(self, panel: np.ndarray, face: FaceState) -> None:
        """Draw facial landmarks."""
        if face.landmarks is None:
            return

        # Scale landmarks from source frame coordinates to panel coordinates
        frame_scale_x = self.width / self._source_width
        frame_scale_y = self.height / self._source_height

        # Draw subset of landmarks for performance
        # Draw every 5th landmark
        for i in range(0, len(face.landmarks), 5):
            x = int(face.landmarks[i, 0] * frame_scale_x)
            y = int(face.landmarks[i, 1] * frame_scale_y)
            cv2.circle(panel, (x, y), 1, config.COLOR_LANDMARKS, -1)

    def _draw_pose_axes(self, panel: np.ndarray, face: FaceState) -> None:
        """Draw head pose axes at nose tip."""
        if face.landmarks is None:
            return

        # Scale from source frame coordinates to panel coordinates
        frame_scale_x = self.width / self._source_width
        frame_scale_y = self.height / self._source_height

        # Get nose tip (landmark index 1)
        nose = face.landmarks[1]
        nose_x = int(nose[0] * frame_scale_x)
        nose_y = int(nose[1] * frame_scale_y)
        nose_point = (nose_x, nose_y)

        # Calculate axis endpoints based on rotation angles
        axis_length = 40
        yaw_rad = np.radians(face.yaw)
        pitch_rad = np.radians(face.pitch)

        # X axis (red) - points right, affected by yaw
        x_end = (
            int(nose_x + axis_length * np.cos(yaw_rad)),
            nose_y,
        )
        cv2.arrowedLine(panel, nose_point, x_end, config.COLOR_POSE_X, 2, tipLength=0.3)

        # Y axis (green) - points up, affected by pitch
        y_end = (
            nose_x,
            int(nose_y - axis_length * np.cos(pitch_rad)),
        )
        cv2.arrowedLine(panel, nose_point, y_end, config.COLOR_POSE_Y, 2, tipLength=0.3)

        # Z axis (blue) - points out of screen
        z_end = (
            int(nose_x - axis_length * np.sin(yaw_rad) * 0.5),
            int(nose_y + axis_length * np.sin(pitch_rad) * 0.5),
        )
        cv2.arrowedLine(panel, nose_point, z_end, config.COLOR_POSE_Z, 2, tipLength=0.3)

    def _draw_facing_indicator(self, panel: np.ndarray, face: FaceState) -> None:
        """Draw facing status indicator."""
        # Draw indicator in top-right corner
        indicator_size = 20
        margin = 10
        x = self.width - indicator_size - margin
        y = margin

        color = config.COLOR_FACING_YES if face.is_facing else config.COLOR_FACING_NO
        cv2.circle(panel, (x + indicator_size // 2, y + indicator_size // 2),
                   indicator_size // 2, color, -1)

        # Draw label
        label = "FACING" if face.is_facing else "NOT FACING"
        cv2.putText(
            panel,
            label,
            (x - 80, y + indicator_size // 2 + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )

    def _draw_status_overlay(self, panel: np.ndarray, face: FaceState) -> None:
        """Draw status information overlay."""
        # Semi-transparent background for text
        overlay_height = 60
        overlay = panel[:overlay_height, :].copy()
        cv2.rectangle(overlay, (0, 0), (self.width, overlay_height),
                      (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, panel[:overlay_height, :], 0.5, 0,
                        panel[:overlay_height, :])

        # Draw face info
        y_offset = 20
        if face.detected:
            text = f"Yaw: {face.yaw:+6.1f}  Pitch: {face.pitch:+6.1f}  Roll: {face.roll:+6.1f}"
        else:
            text = "No face detected"

        cv2.putText(
            panel,
            text,
            (10, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            config.COLOR_TEXT,
            1,
        )

        # Draw confidence
        if face.detected:
            conf_text = f"Confidence: {face.confidence:.2f}"
            cv2.putText(
                panel,
                conf_text,
                (10, y_offset + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                config.COLOR_TEXT,
                1,
            )
