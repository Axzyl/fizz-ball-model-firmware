"""Main dashboard controller for operator interface."""

from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

import sys
sys.path.append("..")
import config
from state import AppState
from .video_panel import VideoPanel
from .telemetry_panel import TelemetryPanel

logger = logging.getLogger(__name__)


class Dashboard:
    """
    Main dashboard controller.

    Manages the OpenCV window and coordinates rendering of
    video and telemetry panels.
    """

    WINDOW_NAME = "Face Tracker Dashboard"

    def __init__(self, state: AppState, stop_event: threading.Event) -> None:
        """
        Initialize dashboard.

        Args:
            state: Application state to read for display
            stop_event: Event to signal shutdown
        """
        self.state = state
        self.stop_event = stop_event

        # Calculate panel sizes
        self.telemetry_width = config.DASHBOARD_WIDTH - config.VIDEO_PANEL_WIDTH
        self.telemetry_height = config.DASHBOARD_HEIGHT

        # Create panels
        self.video_panel = VideoPanel(
            config.VIDEO_PANEL_WIDTH,
            config.VIDEO_PANEL_HEIGHT,
        )
        self.telemetry_panel = TelemetryPanel(
            self.telemetry_width,
            self.telemetry_height,
        )

        # FPS tracking
        self.frame_times: list[float] = []
        self.fps = 0.0

        # Mouse tracking for hover effects
        self.mouse_x = 0
        self.mouse_y = 0

    def run(self) -> None:
        """
        Run the dashboard main loop.

        This should be called from the main thread as OpenCV requires it.
        """
        logger.info("Dashboard starting...")

        # Create window (WINDOW_AUTOSIZE prevents resize scaling issues)
        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

        # Set up mouse callback for clicks and hover
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse_event)

        target_frame_time = 1.0 / config.DASHBOARD_FPS
        last_frame_time = time.time()

        logger.info("Dashboard running")

        while not self.stop_event.is_set():
            frame_start = time.time()

            # Get current state
            frame, face, esp, command, system = self.state.get_all()

            # Calculate hover position relative to telemetry panel
            hover_x = self.mouse_x - config.VIDEO_PANEL_WIDTH
            hover_y = self.mouse_y

            # Render panels
            video_img = self.video_panel.render(frame, face)
            telemetry_img = self.telemetry_panel.render(
                face, esp, command, system,
                hover_pos=(hover_x, hover_y) if hover_x >= 0 else None
            )

            # Compose dashboard
            dashboard = self._compose(video_img, telemetry_img)

            # Display
            cv2.imshow(self.WINDOW_NAME, dashboard)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # 'q' or ESC
                logger.info("User requested exit")
                self.stop_event.set()
                break
            elif key == ord("r"):  # Reset servo to center
                self.state.set_command(servo_target=90.0)
                logger.info("Servo reset to center")
            elif key == ord("l"):  # Toggle light mode
                current = self.state.get_command().light_command
                new_mode = (current + 1) % 3
                self.state.set_command(light_command=new_mode)
                logger.info(f"Light mode changed to {['OFF', 'ON', 'AUTO'][new_mode]}")

            # Check if window was closed
            if cv2.getWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Window closed")
                self.stop_event.set()
                break

            # Update FPS
            self._update_fps(frame_start)

            # Frame rate limiting
            elapsed = time.time() - frame_start
            if elapsed < target_frame_time:
                time.sleep(target_frame_time - elapsed)

        cv2.destroyAllWindows()
        logger.info("Dashboard stopped")

    def _compose(
        self,
        video_img: np.ndarray,
        telemetry_img: np.ndarray,
    ) -> np.ndarray:
        """
        Compose video and telemetry panels into single dashboard image.

        Args:
            video_img: Rendered video panel
            telemetry_img: Rendered telemetry panel

        Returns:
            Composed dashboard image
        """
        # Create dashboard canvas
        dashboard = np.zeros(
            (config.DASHBOARD_HEIGHT, config.DASHBOARD_WIDTH, 3),
            dtype=np.uint8,
        )
        dashboard[:] = config.COLOR_PANEL_BG

        # Place video panel (left side, centered vertically)
        video_y = (config.DASHBOARD_HEIGHT - config.VIDEO_PANEL_HEIGHT) // 2
        dashboard[
            video_y : video_y + config.VIDEO_PANEL_HEIGHT,
            0 : config.VIDEO_PANEL_WIDTH,
        ] = video_img

        # Place telemetry panel (right side)
        dashboard[
            0 : self.telemetry_height,
            config.VIDEO_PANEL_WIDTH : config.DASHBOARD_WIDTH,
        ] = telemetry_img

        # Draw divider line
        cv2.line(
            dashboard,
            (config.VIDEO_PANEL_WIDTH, 0),
            (config.VIDEO_PANEL_WIDTH, config.DASHBOARD_HEIGHT),
            (80, 80, 80),
            1,
        )

        # Draw FPS overlay
        cv2.putText(
            dashboard,
            f"Dashboard FPS: {self.fps:.1f}",
            (10, config.DASHBOARD_HEIGHT - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (100, 100, 100),
            1,
        )

        # Draw keyboard shortcuts help
        help_text = "Q: Quit | R: Reset Servo | L: Cycle Light Mode"
        cv2.putText(
            dashboard,
            help_text,
            (config.VIDEO_PANEL_WIDTH + 10, config.DASHBOARD_HEIGHT - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (100, 100, 100),
            1,
        )

        return dashboard

    def _update_fps(self, frame_start: float) -> None:
        """Update FPS calculation."""
        self.frame_times.append(frame_start)

        # Keep only last second of frame times
        cutoff = frame_start - 1.0
        self.frame_times = [t for t in self.frame_times if t > cutoff]

        if len(self.frame_times) > 1:
            self.fps = len(self.frame_times) / (
                self.frame_times[-1] - self.frame_times[0]
            )

    def _on_mouse_event(self, event: int, x: int, y: int, flags: int, param) -> None:
        """
        Handle mouse events for button interaction and hover effects.

        Args:
            event: OpenCV mouse event type
            x: X coordinate
            y: Y coordinate
            flags: Additional flags
            param: User data (unused)
        """
        # Always track mouse position for hover effects
        self.mouse_x = x
        self.mouse_y = y

        # Handle clicks
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if click is in telemetry panel area
            if x >= config.VIDEO_PANEL_WIDTH:
                # Convert to telemetry panel coordinates
                panel_x = x - config.VIDEO_PANEL_WIDTH
                panel_y = y

                # Check if a button was clicked
                button_name = self.telemetry_panel.get_button_at(panel_x, panel_y)
                if button_name:
                    self._handle_button_click(button_name)

    def _handle_button_click(self, button_name: str) -> None:
        """
        Handle a button click action.

        Args:
            button_name: Name of the clicked button
        """
        if button_name == "led_test":
            logger.info("LED test triggered")
            self.state.trigger_led_test()
