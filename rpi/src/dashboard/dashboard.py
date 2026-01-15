"""Main dashboard controller for operator interface."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

import sys
sys.path.append("..")
import config
from state import AppState
from state_machine import StateMachine
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

    def __init__(
        self,
        state: AppState,
        stop_event: threading.Event,
        state_machine: Optional[StateMachine] = None,
    ) -> None:
        """
        Initialize dashboard.

        Args:
            state: Application state to read for display
            stop_event: Event to signal shutdown
            state_machine: State machine instance for control and display
        """
        self.state = state
        self.stop_event = stop_event
        self.state_machine = state_machine

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
            state_machine=state_machine,
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
            elif key == ord("r"):  # Reset all servos to center
                self.state.set_command(servo_target_1=90.0, servo_target_2=90.0, servo_target_3=90.0)
                logger.info("All servos reset to center")
            elif key == ord("l"):  # Toggle light mode
                current = self.state.get_command().light_command
                new_mode = (current + 1) % 3
                self.state.set_command(light_command=new_mode)
                logger.info(f"Light mode changed to {['OFF', 'ON', 'AUTO'][new_mode]}")
            # Valve controls
            elif key == ord("v"):  # Open valve
                if self.state_machine:
                    self.state_machine.open_valve()
                    logger.info("Valve opened (manual override)")
            elif key == ord("c"):  # Close valve
                if self.state_machine:
                    self.state_machine.close_valve()
                    logger.info("Valve closed (manual override cleared)")
            # State machine controls
            elif key == ord("e"):  # Emergency stop
                if self.state_machine:
                    self.state_machine.emergency_stop()
                    self.state.set_command(valve_open=False)
                    logger.warning("EMERGENCY STOP triggered")
            elif key == ord("d"):  # Enable dispensing
                if self.state_machine:
                    self.state_machine.enable_dispensing()
                    logger.info("Dispensing re-enabled")
            elif key == ord("i"):  # Force inactive
                if self.state_machine:
                    self.state_machine.force_inactive()
                    logger.info("Force inactive triggered")
            elif key == ord("f"):  # Force collapse
                if self.state_machine:
                    self.state_machine.force_collapse()
                    logger.info("Force collapse triggered")
            elif key == ord("s"):  # Skip animation
                if self.state_machine:
                    self.state_machine.skip_animation()
                    logger.info("Skip animation triggered")
            # Outcome controls
            elif key == ord("1"):  # Random outcome
                if self.state_machine:
                    self.state_machine.set_forced_outcome(None)
                    logger.info("Next outcome: RANDOM")
            elif key == ord("2"):  # Force alive
                if self.state_machine:
                    self.state_machine.set_forced_outcome("ALIVE")
                    logger.info("Next outcome: FORCE ALIVE")
            elif key == ord("3"):  # Force dead
                if self.state_machine:
                    self.state_machine.set_forced_outcome("DEAD")
                    logger.info("Next outcome: FORCE DEAD")
            # Test
            elif key == ord("t"):  # LED test
                self.state.trigger_led_test()
                logger.info("LED test triggered")

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

        # Draw keyboard shortcuts help (two lines)
        help_line1 = "Q:Quit E:Stop D:Enable V:Valve C:Close I:Inactive F:Collapse S:Skip"
        help_line2 = "1:Random 2:Alive 3:Dead T:Test R:Reset L:Light"
        cv2.putText(
            dashboard,
            help_line1,
            (config.VIDEO_PANEL_WIDTH + 10, config.DASHBOARD_HEIGHT - 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.32,
            (100, 100, 100),
            1,
        )
        cv2.putText(
            dashboard,
            help_line2,
            (config.VIDEO_PANEL_WIDTH + 10, config.DASHBOARD_HEIGHT - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.32,
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

        # Handle mouse wheel scrolling
        if event == cv2.EVENT_MOUSEWHEEL:
            # Check if mouse is over telemetry panel
            if x >= config.VIDEO_PANEL_WIDTH:
                # Scroll direction: positive flags = scroll up, negative = scroll down
                # We want scroll up to show content above (decrease offset)
                # and scroll down to show content below (increase offset)
                direction = -1 if flags > 0 else 1
                self.telemetry_panel.scroll(direction)

        # Handle clicks
        elif event == cv2.EVENT_LBUTTONDOWN:
            # Check if click is in telemetry panel area
            if x >= config.VIDEO_PANEL_WIDTH:
                # Convert to telemetry panel coordinates (with scroll offset)
                panel_x = x - config.VIDEO_PANEL_WIDTH
                panel_y = y + self.telemetry_panel.scroll_offset

                # Store click position for color wheel
                self._last_click_x = panel_x

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

        # RGB color controls
        elif button_name == "rgb_off":
            self.state.set_command(light_command=0, rgb_r=0, rgb_g=0, rgb_b=0)
            logger.info("RGB set to OFF")
        elif button_name == "color_wheel":
            # Get click position and convert to color
            # The click_x is stored when handling the click
            if hasattr(self, '_last_click_x'):
                r, g, b = self.telemetry_panel.get_color_from_wheel_click(self._last_click_x)
                self.state.set_command(light_command=1, rgb_r=r, rgb_g=g, rgb_b=b)
                logger.info(f"RGB set to R:{r} G:{g} B:{b}")

        # Matrix left buttons
        elif button_name == "matrix_left_off":
            self.state.set_command(matrix_left=0)
            logger.info("Left matrix set to OFF")
        elif button_name == "matrix_left_circle":
            self.state.set_command(matrix_left=1)
            logger.info("Left matrix set to CIRCLE")
        elif button_name == "matrix_left_x":
            self.state.set_command(matrix_left=2)
            logger.info("Left matrix set to X")

        # Matrix right buttons
        elif button_name == "matrix_right_off":
            self.state.set_command(matrix_right=0)
            logger.info("Right matrix set to OFF")
        elif button_name == "matrix_right_circle":
            self.state.set_command(matrix_right=1)
            logger.info("Right matrix set to CIRCLE")
        elif button_name == "matrix_right_x":
            self.state.set_command(matrix_right=2)
            logger.info("Right matrix set to X")

        # State machine controls
        elif button_name == "emergency_stop" and self.state_machine:
            self.state_machine.emergency_stop()
            self.state.set_command(valve_open=False)
            logger.warning("EMERGENCY STOP triggered")
        elif button_name == "enable_dispensing" and self.state_machine:
            self.state_machine.enable_dispensing()
            logger.info("Dispensing re-enabled")
        elif button_name == "force_inactive" and self.state_machine:
            self.state_machine.force_inactive()
            logger.info("Force inactive triggered")
        elif button_name == "force_collapse" and self.state_machine:
            self.state_machine.force_collapse()
            logger.info("Force collapse triggered")
        elif button_name == "skip_animation" and self.state_machine:
            self.state_machine.skip_animation()
            logger.info("Skip animation triggered")
        elif button_name == "open_valve" and self.state_machine:
            self.state_machine.open_valve()
            logger.info("Valve opened (manual override)")
        elif button_name == "close_valve" and self.state_machine:
            self.state_machine.close_valve()
            logger.info("Valve closed (manual override cleared)")
        elif button_name == "outcome_random" and self.state_machine:
            self.state_machine.set_forced_outcome(None)
            logger.info("Next outcome: RANDOM")
        elif button_name == "outcome_alive" and self.state_machine:
            self.state_machine.set_forced_outcome("ALIVE")
            logger.info("Next outcome: FORCE ALIVE")
        elif button_name == "outcome_dead" and self.state_machine:
            self.state_machine.set_forced_outcome("DEAD")
            logger.info("Next outcome: FORCE DEAD")
