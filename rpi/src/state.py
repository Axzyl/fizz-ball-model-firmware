"""Thread-safe centralized state management."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class FrameData:
    """Raw camera frame data."""

    raw_frame: Optional[np.ndarray] = None
    frame_id: int = 0
    timestamp: float = 0.0

    def update(self, frame: np.ndarray, frame_id: int) -> None:
        """Update frame data."""
        self.raw_frame = frame
        self.frame_id = frame_id
        self.timestamp = time.time()


@dataclass
class FaceState:
    """Face detection and pose estimation results."""

    detected: bool = False
    bbox: Optional[tuple[int, int, int, int]] = None  # x, y, w, h
    landmarks: Optional[np.ndarray] = None  # 468 points (x, y, z)
    yaw: float = 0.0  # Horizontal rotation (left/right)
    pitch: float = 0.0  # Vertical rotation (up/down)
    roll: float = 0.0  # Tilt rotation
    is_facing: bool = False
    confidence: float = 0.0
    timestamp: float = 0.0

    def clear(self) -> None:
        """Clear face detection results."""
        self.detected = False
        self.bbox = None
        self.landmarks = None
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.is_facing = False
        self.confidence = 0.0


@dataclass
class EspState:
    """State received from ESP32."""

    connected: bool = False
    limit_triggered: bool = False
    limit_direction: int = 0  # 0=none, 1=CW, 2=CCW
    servo_position: float = 90.0
    light_state: bool = False
    flags: int = 0
    last_rx_time: float = 0.0

    def update_from_packet(
        self,
        limit: int,
        servo_pos: float,
        light_state: int,
        flags: int,
    ) -> None:
        """Update state from received packet."""
        self.connected = True
        self.limit_triggered = limit != 0
        self.limit_direction = limit
        self.servo_position = servo_pos
        self.light_state = light_state == 1
        self.flags = flags
        self.last_rx_time = time.time()

    def check_connection(self, timeout_ms: float) -> None:
        """Check if connection is still active."""
        if time.time() - self.last_rx_time > timeout_ms / 1000.0:
            self.connected = False


@dataclass
class CommandState:
    """Commands to send to ESP32."""

    servo_target: float = 90.0
    light_command: int = 2  # Default to AUTO
    flags: int = 0


@dataclass
class SystemState:
    """System-level state."""

    fps: float = 0.0
    face_tracker_fps: float = 0.0
    uart_tx_count: int = 0
    uart_rx_count: int = 0
    uptime: float = 0.0
    start_time: float = field(default_factory=time.time)
    errors: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add error to list, keeping last 10."""
        self.errors.append(f"{time.strftime('%H:%M:%S')} - {error}")
        if len(self.errors) > 10:
            self.errors.pop(0)

    def update_uptime(self) -> None:
        """Update uptime value."""
        self.uptime = time.time() - self.start_time


class AppState:
    """
    Thread-safe application state container.

    All state access should go through this class to ensure thread safety.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame = FrameData()
        self._face = FaceState()
        self._esp = EspState()
        self._command = CommandState()
        self._system = SystemState()

    @property
    def lock(self) -> threading.Lock:
        """Get the state lock for external synchronization."""
        return self._lock

    # -------------------------------------------------------------------------
    # Frame Data Access
    # -------------------------------------------------------------------------

    def update_frame(self, frame: np.ndarray, frame_id: int) -> None:
        """Thread-safe frame update."""
        with self._lock:
            self._frame.update(frame, frame_id)

    def get_frame(self) -> tuple[Optional[np.ndarray], int, float]:
        """Thread-safe frame retrieval. Returns (frame, frame_id, timestamp)."""
        with self._lock:
            if self._frame.raw_frame is not None:
                return (
                    self._frame.raw_frame.copy(),
                    self._frame.frame_id,
                    self._frame.timestamp,
                )
            return None, 0, 0.0

    # -------------------------------------------------------------------------
    # Face State Access
    # -------------------------------------------------------------------------

    def update_face(
        self,
        detected: bool,
        bbox: Optional[tuple[int, int, int, int]] = None,
        landmarks: Optional[np.ndarray] = None,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        is_facing: bool = False,
        confidence: float = 0.0,
    ) -> None:
        """Thread-safe face state update."""
        with self._lock:
            self._face.detected = detected
            self._face.bbox = bbox
            self._face.landmarks = landmarks.copy() if landmarks is not None else None
            self._face.yaw = yaw
            self._face.pitch = pitch
            self._face.roll = roll
            self._face.is_facing = is_facing
            self._face.confidence = confidence
            self._face.timestamp = time.time()

    def get_face(self) -> FaceState:
        """Thread-safe face state retrieval (returns copy)."""
        with self._lock:
            return FaceState(
                detected=self._face.detected,
                bbox=self._face.bbox,
                landmarks=self._face.landmarks.copy()
                if self._face.landmarks is not None
                else None,
                yaw=self._face.yaw,
                pitch=self._face.pitch,
                roll=self._face.roll,
                is_facing=self._face.is_facing,
                confidence=self._face.confidence,
                timestamp=self._face.timestamp,
            )

    def clear_face(self) -> None:
        """Thread-safe clear face detection."""
        with self._lock:
            self._face.clear()

    # -------------------------------------------------------------------------
    # ESP State Access
    # -------------------------------------------------------------------------

    def update_esp_from_packet(
        self,
        limit: int,
        servo_pos: float,
        light_state: int,
        flags: int,
    ) -> None:
        """Thread-safe ESP state update from received packet."""
        with self._lock:
            self._esp.update_from_packet(limit, servo_pos, light_state, flags)

    def get_esp(self) -> EspState:
        """Thread-safe ESP state retrieval (returns copy)."""
        with self._lock:
            return EspState(
                connected=self._esp.connected,
                limit_triggered=self._esp.limit_triggered,
                limit_direction=self._esp.limit_direction,
                servo_position=self._esp.servo_position,
                light_state=self._esp.light_state,
                flags=self._esp.flags,
                last_rx_time=self._esp.last_rx_time,
            )

    def check_esp_connection(self, timeout_ms: float) -> None:
        """Thread-safe ESP connection check."""
        with self._lock:
            self._esp.check_connection(timeout_ms)

    # -------------------------------------------------------------------------
    # Command State Access
    # -------------------------------------------------------------------------

    def set_command(
        self,
        servo_target: Optional[float] = None,
        light_command: Optional[int] = None,
        flags: Optional[int] = None,
    ) -> None:
        """Thread-safe command update."""
        with self._lock:
            if servo_target is not None:
                self._command.servo_target = servo_target
            if light_command is not None:
                self._command.light_command = light_command
            if flags is not None:
                self._command.flags = flags

    def get_command(self) -> CommandState:
        """Thread-safe command retrieval (returns copy)."""
        with self._lock:
            return CommandState(
                servo_target=self._command.servo_target,
                light_command=self._command.light_command,
                flags=self._command.flags,
            )

    # -------------------------------------------------------------------------
    # System State Access
    # -------------------------------------------------------------------------

    def update_fps(self, fps: float, face_tracker_fps: float = 0.0) -> None:
        """Thread-safe FPS update."""
        with self._lock:
            self._system.fps = fps
            if face_tracker_fps > 0:
                self._system.face_tracker_fps = face_tracker_fps
            self._system.update_uptime()

    def increment_uart_tx(self) -> None:
        """Thread-safe UART TX counter increment."""
        with self._lock:
            self._system.uart_tx_count += 1

    def increment_uart_rx(self) -> None:
        """Thread-safe UART RX counter increment."""
        with self._lock:
            self._system.uart_rx_count += 1

    def add_error(self, error: str) -> None:
        """Thread-safe error logging."""
        with self._lock:
            self._system.add_error(error)

    def get_system(self) -> SystemState:
        """Thread-safe system state retrieval (returns copy)."""
        with self._lock:
            self._system.update_uptime()
            return SystemState(
                fps=self._system.fps,
                face_tracker_fps=self._system.face_tracker_fps,
                uart_tx_count=self._system.uart_tx_count,
                uart_rx_count=self._system.uart_rx_count,
                uptime=self._system.uptime,
                start_time=self._system.start_time,
                errors=self._system.errors.copy(),
            )

    # -------------------------------------------------------------------------
    # Bulk Access (for dashboard)
    # -------------------------------------------------------------------------

    def get_all(
        self,
    ) -> tuple[
        Optional[np.ndarray], FaceState, EspState, CommandState, SystemState
    ]:
        """
        Thread-safe retrieval of all state for dashboard rendering.

        Returns tuple of (frame, face, esp, command, system).
        """
        with self._lock:
            frame = (
                self._frame.raw_frame.copy()
                if self._frame.raw_frame is not None
                else None
            )

            face = FaceState(
                detected=self._face.detected,
                bbox=self._face.bbox,
                landmarks=self._face.landmarks.copy()
                if self._face.landmarks is not None
                else None,
                yaw=self._face.yaw,
                pitch=self._face.pitch,
                roll=self._face.roll,
                is_facing=self._face.is_facing,
                confidence=self._face.confidence,
                timestamp=self._face.timestamp,
            )

            esp = EspState(
                connected=self._esp.connected,
                limit_triggered=self._esp.limit_triggered,
                limit_direction=self._esp.limit_direction,
                servo_position=self._esp.servo_position,
                light_state=self._esp.light_state,
                flags=self._esp.flags,
                last_rx_time=self._esp.last_rx_time,
            )

            command = CommandState(
                servo_target=self._command.servo_target,
                light_command=self._command.light_command,
                flags=self._command.flags,
            )

            self._system.update_uptime()
            system = SystemState(
                fps=self._system.fps,
                face_tracker_fps=self._system.face_tracker_fps,
                uart_tx_count=self._system.uart_tx_count,
                uart_rx_count=self._system.uart_rx_count,
                uptime=self._system.uptime,
                start_time=self._system.start_time,
                errors=self._system.errors.copy(),
            )

            return frame, face, esp, command, system
