"""Main entry point for the face tracking system."""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from typing import Optional

import cv2
import numpy as np

import config
from state import AppState
from state_machine import StateMachine, StateMachineConfig
from vision.face_tracker import FaceTracker
from comm.uart_comm import UartComm
from dashboard.dashboard import Dashboard


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class VisionThread(threading.Thread):
    """
    Combined camera capture and face tracking thread.

    This mirrors the approach in vision_servo_test.py:
    - Single thread handles both camera and face tracking
    - No frame queue or synchronization issues
    - Frame and detection results are always matched
    """

    # Dark frame detection settings - loaded from config
    # Uses percentile-based detection to be robust to internal LED light spots
    DARK_THRESHOLD = getattr(config, 'DARK_THRESHOLD', 25)
    DARK_PERCENTILE = getattr(config, 'DARK_PERCENTILE', 75)
    DARK_USE_VARIANCE = getattr(config, 'DARK_USE_VARIANCE', False)
    DARK_VARIANCE_THRESHOLD = getattr(config, 'DARK_VARIANCE_THRESHOLD', 20)

    # Camera connection tracking - use config value or default
    MAX_CONSECUTIVE_FAILURES = getattr(config, 'CAMERA_MAX_FAILURES', 30)

    def __init__(
        self,
        state: AppState,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="VisionThread", daemon=True)
        self.state = state
        self.stop_event = stop_event
        self.cap: Optional[cv2.VideoCapture] = None
        self.tracker: Optional[FaceTracker] = None

        # FPS tracking (same as vision_servo_test.py)
        self.fps_times: list[float] = []
        self.fps = 0.0

        # Camera connection tracking
        self.consecutive_failures = 0
        self.camera_connected = False

    def run(self) -> None:
        """Main vision loop - identical structure to vision_servo_test.py"""
        logger.info("Vision thread starting...")

        # Initialize camera (same as vision_servo_test.py)
        camera_index = getattr(config, 'CAMERA_INDEX', 0)
        logger.info(f"Opening camera {camera_index}...")

        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

        if not self.cap.isOpened():
            logger.error(f"Failed to open camera {camera_index}")
            self.state.add_error("Failed to open camera")
            self.state.set_camera_connected(False)
            return

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Camera opened: {actual_w}x{actual_h}")

        # Initialize face tracker (same as vision_servo_test.py)
        logger.info("Initializing face tracker...")
        self.tracker = FaceTracker()

        logger.info("Vision thread running")

        # Main loop - same structure as vision_servo_test.py
        while not self.stop_event.is_set():
            frame_start = time.time()

            # Capture frame (same as vision_servo_test.py)
            ret, frame = self.cap.read()
            if not ret:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    if self.camera_connected:
                        logger.error("Camera disconnected (too many consecutive failures)")
                        self.state.add_error("Camera disconnected")
                    self.camera_connected = False
                    self.state.set_camera_connected(False)
                logger.warning("Failed to capture frame")
                time.sleep(0.01)
                continue

            # Successful frame read - reset failure counter
            self.consecutive_failures = 0
            if not self.camera_connected:
                logger.info("Camera reconnected")
            self.camera_connected = True

            # Get actual frame dimensions (same as vision_servo_test.py)
            frame_h, frame_w = frame.shape[:2]

            # Check if frame is too dark (door closed) - skip CV to save CPU
            # Use percentile-based detection to be robust to small bright LED spots
            # Convert to grayscale for brightness calculation
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Use percentile instead of mean - more robust to LED hotspots
            # e.g., 75th percentile means 75% of pixels must be below threshold
            frame_brightness = np.percentile(gray, self.DARK_PERCENTILE)
            frame_variance = gray.std()  # Standard deviation for uniformity check

            # Determine if dark based on brightness
            is_bright_dark = frame_brightness < self.DARK_THRESHOLD

            # Optionally also check variance (uniform colors = door closed)
            if self.DARK_USE_VARIANCE:
                is_var_low = frame_variance < self.DARK_VARIANCE_THRESHOLD
                is_dark = is_bright_dark and is_var_low
            else:
                is_dark = is_bright_dark

            if is_dark:
                # Skip CV processing, just report dark frame
                self.state.update_face(
                    detected=False,
                    frame_width=frame_w,
                    frame_height=frame_h,
                    processed_frame=frame,
                    is_dark=True,
                    frame_brightness=frame_brightness,
                    frame_variance=frame_variance,
                    camera_connected=True,
                )
            else:
                # Process frame with face tracker (same as vision_servo_test.py)
                result = self.tracker.process(frame)

                # Update state with face detection results
                if result["detected"] and result["bbox"]:
                    x, y, w, h = result["bbox"]

                    # Get multi-face info if available
                    all_faces = result.get("all_faces", [])
                    num_faces = len(all_faces) if all_faces else 1
                    num_facing = sum(1 for f in all_faces if f.get("is_facing", False)) if all_faces else (1 if result.get("is_facing") else 0)

                    self.state.update_face(
                        detected=True,
                        bbox=result["bbox"],
                        landmarks=result["landmarks"],
                        yaw=result["yaw"],
                        pitch=result["pitch"],
                        roll=result["roll"],
                        is_facing=result["is_facing"],
                        confidence=result["confidence"],
                        num_faces=num_faces,
                        num_facing=num_facing,
                        frame_width=frame_w,
                        frame_height=frame_h,
                        processed_frame=frame,
                        is_dark=False,
                        frame_brightness=frame_brightness,
                        frame_variance=frame_variance,
                        camera_connected=True,
                    )
                else:
                    self.state.update_face(
                        detected=False,
                        frame_width=frame_w,
                        frame_height=frame_h,
                        processed_frame=frame,
                        is_dark=False,
                        frame_brightness=frame_brightness,
                        frame_variance=frame_variance,
                        camera_connected=True,
                    )

            # Update FPS (same as vision_servo_test.py)
            now = time.time()
            self.fps_times.append(now)
            self.fps_times = [t for t in self.fps_times if t > now - 1.0]
            if len(self.fps_times) > 1:
                self.fps = len(self.fps_times) / (self.fps_times[-1] - self.fps_times[0])
                self.state.update_fps(self.fps, self.fps)

        # Cleanup
        self.cap.release()
        logger.info("Vision thread stopped")


class StateMachineThread(threading.Thread):
    """Thread for running the state machine."""

    def __init__(
        self,
        state: AppState,
        stop_event: threading.Event,
        sm_config: Optional[StateMachineConfig] = None,
    ) -> None:
        super().__init__(name="StateMachineThread", daemon=True)
        self.state = state
        self.stop_event = stop_event
        self.state_machine = StateMachine(sm_config)
        self.tick_rate = 30  # Hz

    def run(self) -> None:
        """Main state machine loop."""
        logger.info("State machine thread starting...")

        tick_interval = 1.0 / self.tick_rate
        last_tick = time.time()

        while not self.stop_event.is_set():
            now = time.time()
            if now - last_tick >= tick_interval:
                last_tick = now

                # Get current face and ESP state
                face_state = self.state.get_face()
                esp_state = self.state.get_esp()

                # Run state machine tick
                commands = self.state_machine.tick(face_state, esp_state)

                # Apply commands to state
                self._apply_commands(commands)

            # Small sleep to prevent busy-waiting
            time.sleep(0.001)

        logger.info("State machine thread stopped")

    def _apply_commands(self, commands: dict) -> None:
        """Apply state machine commands to the app state."""
        self.state.set_command(
            servo_target_1=commands.get("servo_target_1", 90.0),
            servo_target_2=commands.get("servo_target_2", 90.0),
            valve_open=commands.get("valve_open", False),
            rgb_mode=commands.get("rgb_mode", 0),
            rgb_r=commands.get("rgb_r", 0),
            rgb_g=commands.get("rgb_g", 0),
            rgb_b=commands.get("rgb_b", 0),
            npm_mode=commands.get("npm_mode", 0),
            npm_letter=commands.get("npm_letter", "A"),
            npm_r=commands.get("npm_r", 255),
            npm_g=commands.get("npm_g", 255),
            npm_b=commands.get("npm_b", 255),
            npr_mode=commands.get("npr_mode", 0),
            npr_r=commands.get("npr_r", 255),
            npr_g=commands.get("npr_g", 255),
            npr_b=commands.get("npr_b", 255),
            matrix_left=commands.get("matrix_left", 1),
            matrix_right=commands.get("matrix_right", 2),
        )

    def get_state_machine(self) -> StateMachine:
        """Get the state machine instance for external control."""
        return self.state_machine


class Application:
    """Main application controller."""

    def __init__(self) -> None:
        self.state = AppState()
        self.stop_event = threading.Event()
        self._shutdown_in_progress = False

        # Components
        self.vision_thread: Optional[VisionThread] = None
        self.state_machine_thread: Optional[StateMachineThread] = None
        self.uart_comm: Optional[UartComm] = None
        self.dashboard: Optional[Dashboard] = None

        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def start(self) -> None:
        """Start all components."""
        logger.info("Starting application...")

        # Start combined vision thread (camera + face tracking)
        self.vision_thread = VisionThread(self.state, self.stop_event)
        self.vision_thread.start()

        # Start state machine thread
        self.state_machine_thread = StateMachineThread(
            self.state, self.stop_event
        )
        self.state_machine_thread.start()

        # Start UART communication
        self.uart_comm = UartComm(self.state, self.stop_event)
        self.uart_comm.start()

        # Run dashboard in main thread (pass state machine for control)
        state_machine = self.state_machine_thread.get_state_machine()
        self.dashboard = Dashboard(self.state, self.stop_event, state_machine)

        logger.info("All components started")

        # Dashboard runs in main thread (blocking)
        try:
            self.dashboard.run()
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self.state.add_error(f"Dashboard error: {e}")

        # When dashboard exits, stop everything
        self.stop()

    def stop(self) -> None:
        """Stop all components."""
        # Prevent multiple shutdown calls
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True

        logger.info("Stopping application...")

        # Send shutdown commands to ESP32 before stopping threads
        self._send_shutdown_commands()

        # Now signal threads to stop
        self.stop_event.set()

        # Wait for threads to finish
        if self.vision_thread and self.vision_thread.is_alive():
            self.vision_thread.join(timeout=2.0)

        if self.state_machine_thread and self.state_machine_thread.is_alive():
            self.state_machine_thread.join(timeout=2.0)

        if self.uart_comm and self.uart_comm.is_alive():
            self.uart_comm.join(timeout=2.0)

        logger.info("Application stopped")

    def _send_shutdown_commands(self) -> None:
        """Send shutdown commands to turn off all LEDs and reset servos."""
        if not self.uart_comm:
            return

        logger.info("Sending shutdown commands to ESP32...")

        # Force UART to send all values even if they haven't changed
        self.uart_comm.force_send_all()

        # Set all outputs to off/default state
        self.state.set_command(
            # Servos to center
            servo_target_1=90.0,
            servo_target_2=90.0,
            # Valve closed
            valve_open=False,
            # RGB strip off
            rgb_mode=0,
            rgb_r=0,
            rgb_g=0,
            rgb_b=0,
            # NeoPixel matrix off
            npm_mode=0,  # NPM_OFF
            npm_letter="A",
            npm_r=0,
            npm_g=0,
            npm_b=0,
            # NeoPixel ring off
            npr_mode=0,  # NPR_OFF
            npr_r=0,
            npr_g=0,
            npr_b=0,
            # MAX7219 matrix off
            matrix_left=0,
            matrix_right=0,
            # Light off
            light_command=0,
        )

        # Give UART thread time to send the commands
        # The UART thread sends at UART_TX_RATE_HZ (default 30Hz = 33ms)
        # Wait long enough for at least 2-3 transmit cycles
        time.sleep(0.15)

        logger.info("Shutdown commands sent")


def main() -> int:
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Face Tracking System Starting")
    logger.info("=" * 50)
    logger.info(f"Platform: {config.PLATFORM_NAME}")
    logger.info(f"UART Port: {config.UART_PORT}")
    logger.info(f"UART Mock: {'Enabled' if config.UART_MOCK_ENABLED else 'Disabled'}")
    logger.info(f"Camera Index: {config.CAMERA_INDEX}")
    logger.info("=" * 50)

    app = Application()

    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1
    finally:
        # Ensure cleanup happens even on exceptions
        app.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
