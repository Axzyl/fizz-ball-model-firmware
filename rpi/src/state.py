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
    servo_positions: tuple[float, float, float] = (90.0, 90.0, 90.0)  # 3 servos
    light_state: bool = False
    flags: int = 0
    test_active: bool = False  # True when test was triggered on ESP32
    last_rx_time: float = 0.0

    def update_from_packet(
        self,
        limit: int,
        servo_positions: tuple[float, float, float],
        light_state: int,
        flags: int,
        test_active: int = 0,
    ) -> None:
        """Update state from received packet."""
        self.connected = True
        self.limit_triggered = limit != 0
        self.limit_direction = limit
        self.servo_positions = servo_positions
        self.light_state = light_state == 1
        self.flags = flags
        self.test_active = test_active == 1
        self.last_rx_time = time.time()

    def check_connection(self, timeout_ms: float) -> None:
        """Check if connection is still active."""
        if time.time() - self.last_rx_time > timeout_ms / 1000.0:
            self.connected = False


@dataclass
class CommandState:
    """Commands to send to ESP32."""

    servo_targets: tuple[float, float, float] = (90.0, 90.0, 90.0)  # 3 servos
    light_command: int = 2  # Default to AUTO
    flags: int = 0
    rgb_r: int = 0
    rgb_g: int = 0
    rgb_b: int = 0
    matrix_left: int = 1   # Left matrix pattern (0=off, 1=circle, 2=X)
    matrix_right: int = 2  # Right matrix pattern (0=off, 1=circle, 2=X)


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
    last_tx_packet: str = ""  # Last command sent to ESP32
    last_rx_packet: str = ""  # Last status received from ESP32

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
        servo_positions: tuple[float, float, float],
        light_state: int,
        flags: int,
        test_active: int = 0,
    ) -> None:
        """Thread-safe ESP state update from received packet."""
        with self._lock:
            self._esp.update_from_packet(limit, servo_positions, light_state, flags, test_active)

    def get_esp(self) -> EspState:
        """Thread-safe ESP state retrieval (returns copy)."""
        with self._lock:
            return EspState(
                connected=self._esp.connected,
                limit_triggered=self._esp.limit_triggered,
                limit_direction=self._esp.limit_direction,
                servo_positions=self._esp.servo_positions,
                light_state=self._esp.light_state,
                flags=self._esp.flags,
                test_active=self._esp.test_active,
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
        servo_targets: Optional[tuple[float, float, float]] = None,
        servo_target_1: Optional[float] = None,
        servo_target_2: Optional[float] = None,
        servo_target_3: Optional[float] = None,
        light_command: Optional[int] = None,
        flags: Optional[int] = None,
        rgb_r: Optional[int] = None,
        rgb_g: Optional[int] = None,
        rgb_b: Optional[int] = None,
        matrix_left: Optional[int] = None,
        matrix_right: Optional[int] = None,
    ) -> None:
        """Thread-safe command update."""
        with self._lock:
            if servo_targets is not None:
                self._command.servo_targets = servo_targets
            else:
                # Allow individual servo updates
                targets = list(self._command.servo_targets)
                if servo_target_1 is not None:
                    targets[0] = servo_target_1
                if servo_target_2 is not None:
                    targets[1] = servo_target_2
                if servo_target_3 is not None:
                    targets[2] = servo_target_3
                self._command.servo_targets = tuple(targets)
            if light_command is not None:
                self._command.light_command = light_command
            if flags is not None:
                self._command.flags = flags
            if rgb_r is not None:
                self._command.rgb_r = rgb_r
            if rgb_g is not None:
                self._command.rgb_g = rgb_g
            if rgb_b is not None:
                self._command.rgb_b = rgb_b
            if matrix_left is not None:
                self._command.matrix_left = matrix_left
            if matrix_right is not None:
                self._command.matrix_right = matrix_right

    def get_command(self) -> CommandState:
        """Thread-safe command retrieval (returns copy)."""
        with self._lock:
            return CommandState(
                servo_targets=self._command.servo_targets,
                light_command=self._command.light_command,
                flags=self._command.flags,
                rgb_r=self._command.rgb_r,
                rgb_g=self._command.rgb_g,
                rgb_b=self._command.rgb_b,
                matrix_left=self._command.matrix_left,
                matrix_right=self._command.matrix_right,
            )

    def set_command_flag(self, flag: int) -> None:
        """Thread-safe set a command flag bit."""
        with self._lock:
            self._command.flags |= flag

    def clear_command_flag(self, flag: int) -> None:
        """Thread-safe clear a command flag bit."""
        with self._lock:
            self._command.flags &= ~flag

    def trigger_led_test(self) -> None:
        """Trigger the LED blink test on ESP32."""
        import config
        self.set_command_flag(config.CMD_FLAG_LED_TEST)

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

    def increment_uart_tx(self, packet: str = "") -> None:
        """Thread-safe UART TX counter increment."""
        with self._lock:
            self._system.uart_tx_count += 1
            if packet:
                self._system.last_tx_packet = packet.strip()

    def increment_uart_rx(self, packet: str = "") -> None:
        """Thread-safe UART RX counter increment."""
        with self._lock:
            self._system.uart_rx_count += 1
            if packet:
                self._system.last_rx_packet = packet.strip()

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
                last_tx_packet=self._system.last_tx_packet,
                last_rx_packet=self._system.last_rx_packet,
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
                servo_positions=self._esp.servo_positions,
                light_state=self._esp.light_state,
                flags=self._esp.flags,
                test_active=self._esp.test_active,
                last_rx_time=self._esp.last_rx_time,
            )

            command = CommandState(
                servo_targets=self._command.servo_targets,
                light_command=self._command.light_command,
                flags=self._command.flags,
                rgb_r=self._command.rgb_r,
                rgb_g=self._command.rgb_g,
                rgb_b=self._command.rgb_b,
                matrix_left=self._command.matrix_left,
                matrix_right=self._command.matrix_right,
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
                last_tx_packet=self._system.last_tx_packet,
                last_rx_packet=self._system.last_rx_packet,
            )

            return frame, face, esp, command, system
