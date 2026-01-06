"""Main entry point for the face tracking system."""

from __future__ import annotations

import logging
import queue
import signal
import sys
import threading
import time
from typing import Optional

import cv2
import numpy as np

import config
from state import AppState
from vision.face_tracker import FaceTracker
from comm.uart_comm import UartComm
from dashboard.dashboard import Dashboard


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CameraThread(threading.Thread):
    """Thread for capturing camera frames."""

    def __init__(
        self,
        state: AppState,
        frame_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="CameraThread", daemon=True)
        self.state = state
        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_id = 0

    def run(self) -> None:
        """Main camera capture loop."""
        logger.info("Camera thread starting...")

        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            self.state.add_error("Failed to open camera")
            return

        logger.info("Camera opened successfully")

        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to capture frame")
                time.sleep(0.01)
                continue

            self.frame_id += 1

            # Update state with raw frame
            self.state.update_frame(frame, self.frame_id)

            # Put frame in queue for face tracker (non-blocking)
            try:
                self.frame_queue.put_nowait((frame, self.frame_id))
            except queue.Full:
                # Drop frame if queue is full (face tracker is behind)
                pass

        self.cap.release()
        logger.info("Camera thread stopped")


class FaceTrackerThread(threading.Thread):
    """Thread for face detection and pose estimation."""

    def __init__(
        self,
        state: AppState,
        frame_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="FaceTrackerThread", daemon=True)
        self.state = state
        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self.tracker: Optional[FaceTracker] = None

        # FPS tracking
        self.fps_counter = 0
        self.fps_start_time = time.time()

    def run(self) -> None:
        """Main face tracking loop."""
        logger.info("Face tracker thread starting...")

        self.tracker = FaceTracker()

        while not self.stop_event.is_set():
            try:
                frame, frame_id = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Process frame
            result = self.tracker.process(frame)

            # Update state
            if result["detected"]:
                self.state.update_face(
                    detected=True,
                    bbox=result["bbox"],
                    landmarks=result["landmarks"],
                    yaw=result["yaw"],
                    pitch=result["pitch"],
                    roll=result["roll"],
                    is_facing=result["is_facing"],
                    confidence=result["confidence"],
                )
            else:
                self.state.clear_face()

            # Update servo target based on face detection and facing status
            self._update_servo_target(result)

            # Update FPS
            self.fps_counter += 1
            elapsed = time.time() - self.fps_start_time
            if elapsed >= 1.0:
                fps = self.fps_counter / elapsed
                self.state.update_fps(fps, fps)
                self.fps_counter = 0
                self.fps_start_time = time.time()

        logger.info("Face tracker thread stopped")

    def _update_servo_target(self, result: dict) -> None:
        """Update servo target based on face detection and facing status.

        Simple logic:
        - Face detected AND facing forward -> servo at 180°
        - Otherwise -> servo at 0°
        """
        if result["detected"] and result["is_facing"]:
            self.state.set_command(servo_target=180.0)
        else:
            self.state.set_command(servo_target=0.0)


class Application:
    """Main application controller."""

    def __init__(self) -> None:
        self.state = AppState()
        self.stop_event = threading.Event()
        self.frame_queue: queue.Queue = queue.Queue(maxsize=config.FRAME_QUEUE_SIZE)

        # Components
        self.camera_thread: Optional[CameraThread] = None
        self.face_tracker_thread: Optional[FaceTrackerThread] = None
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

        # Start camera thread
        self.camera_thread = CameraThread(
            self.state, self.frame_queue, self.stop_event
        )
        self.camera_thread.start()

        # Start face tracker thread
        self.face_tracker_thread = FaceTrackerThread(
            self.state, self.frame_queue, self.stop_event
        )
        self.face_tracker_thread.start()

        # Start UART communication
        self.uart_comm = UartComm(self.state, self.stop_event)
        self.uart_comm.start()

        # Run dashboard in main thread
        self.dashboard = Dashboard(self.state, self.stop_event)

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
        logger.info("Stopping application...")
        self.stop_event.set()

        # Wait for threads to finish
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=2.0)

        if self.face_tracker_thread and self.face_tracker_thread.is_alive():
            self.face_tracker_thread.join(timeout=2.0)

        if self.uart_comm and self.uart_comm.is_alive():
            self.uart_comm.join(timeout=2.0)

        logger.info("Application stopped")


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
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
