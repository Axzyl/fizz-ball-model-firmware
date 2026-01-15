"""Telemetry panel for displaying system state values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING

import cv2
import numpy as np

import sys
sys.path.append("..")
import config
from state import FaceState, EspState, CommandState, SystemState

if TYPE_CHECKING:
    from state_machine import StateMachine


@dataclass
class ButtonInfo:
    """Information about a clickable button."""
    x: int
    y: int
    width: int
    height: int
    name: str

    def contains(self, x: int, y: int) -> bool:
        """Check if a point is inside this button."""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)


class TelemetryPanel:
    """
    Telemetry panel that displays live system state values.

    Displays:
    - Face detection state (yaw, pitch, roll, facing)
    - ESP32 state (servo position, limit switch, lights)
    - Command state (servo target, light command)
    - System state (FPS, UART status, uptime)
    - Test buttons
    """

    # Panel layout
    SECTION_SPACING = 30
    LINE_HEIGHT = 20
    MARGIN = 15
    LABEL_WIDTH = 140

    # Button layout
    BUTTON_HEIGHT = 28
    BUTTON_WIDTH = 120
    BUTTON_COLOR = (80, 80, 80)
    BUTTON_HOVER_COLOR = (100, 100, 100)
    BUTTON_TEXT_COLOR = (255, 255, 255)

    # State colors (BGR format)
    STATE_COLORS = {
        "IDLE": (180, 100, 180),      # Purple
        "TRACKING": (200, 150, 50),   # Blue
        "COLLAPSE": (255, 255, 255),  # White
        "ALIVE": (100, 200, 100),     # Green
        "DEAD": (100, 100, 200),      # Red
        "RESET": (150, 150, 150),     # Gray
        "FAULT": (50, 100, 200),      # Orange
    }

    def __init__(
        self,
        width: int,
        height: int,
        state_machine: Optional["StateMachine"] = None,
    ) -> None:
        """
        Initialize telemetry panel.

        Args:
            width: Panel width in pixels
            height: Panel height in pixels
            state_machine: State machine instance for display and control
        """
        self.width = width
        self.height = height
        self.state_machine = state_machine
        self.buttons: list[ButtonInfo] = []
        self.hovered_button: Optional[str] = None

        # Scrolling support
        self.scroll_offset = 0
        self.content_height = 0  # Will be calculated during render
        self.scroll_speed = 30  # Pixels per scroll tick

    def scroll(self, direction: int) -> None:
        """
        Scroll the panel content.

        Args:
            direction: Positive to scroll down, negative to scroll up
        """
        self.scroll_offset += direction * self.scroll_speed
        # Clamp scroll offset
        max_scroll = max(0, self.content_height - self.height + 50)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def render(
        self,
        face: FaceState,
        esp: EspState,
        command: CommandState,
        system: SystemState,
        hover_pos: Optional[Tuple[int, int]] = None,
    ) -> np.ndarray:
        """
        Render telemetry panel with current state values.

        Args:
            face: Current face detection state
            esp: Current ESP32 state
            command: Current command state
            system: Current system state
            hover_pos: Mouse position relative to panel (x, y), or None

        Returns:
            Rendered panel as BGR image
        """
        # Adjust hover position for scroll offset
        adjusted_hover_pos = None
        if hover_pos:
            hx, hy = hover_pos
            adjusted_hover_pos = (hx, hy + self.scroll_offset)

        # Determine which button is hovered (using previous frame's buttons)
        self.hovered_button = None
        if adjusted_hover_pos:
            hx, hy = adjusted_hover_pos
            button_name = self.get_button_at(hx, hy)
            if button_name:
                self.hovered_button = button_name

        # Clear button list for this frame (after hover check)
        self.buttons = []

        # Create a larger buffer for content (will be cropped to viewport)
        buffer_height = max(self.height, 1200)  # Ensure enough space for all content
        panel = np.zeros((buffer_height, self.width, 3), dtype=np.uint8)
        panel[:] = config.COLOR_PANEL_BG

        y = self.MARGIN

        # State Machine section (at top, always visible)
        if self.state_machine:
            y = self._draw_state_machine_section(panel, y, esp)

        # Face section
        y = self._draw_section_header(panel, "FACE", y)
        y = self._draw_value(panel, "Detected", "YES" if face.detected else "NO", y,
                             config.COLOR_FACING_YES if face.detected else config.COLOR_FACING_NO)
        # Show multi-face info
        if face.num_faces > 0:
            faces_text = f"{face.num_faces} ({face.num_facing} facing)"
            y = self._draw_value(panel, "Faces", faces_text, y)
        y = self._draw_value(panel, "Yaw", f"{face.yaw:+.1f}°", y)
        y = self._draw_value(panel, "Pitch", f"{face.pitch:+.1f}°", y)
        y = self._draw_value(panel, "Roll", f"{face.roll:+.1f}°", y)
        y = self._draw_value(panel, "Facing", "YES" if face.is_facing else "NO", y,
                             config.COLOR_FACING_YES if face.is_facing else config.COLOR_FACING_NO)
        y = self._draw_value(panel, "Confidence", f"{face.confidence:.2f}", y)

        y += self.SECTION_SPACING // 2

        # Servo section
        y = self._draw_section_header(panel, "SERVOS", y)
        targets = command.servo_targets
        positions = esp.servo_positions
        y = self._draw_value(panel, "Targets", f"{targets[0]:.0f}° / {targets[1]:.0f}° / {targets[2]:.0f}°", y)
        y = self._draw_value(panel, "Actual", f"{positions[0]:.0f}° / {positions[1]:.0f}° / {positions[2]:.0f}°", y)

        # Limit switch
        limit_text = "CLEAR"
        limit_color = config.COLOR_FACING_YES
        if esp.limit_triggered:
            limit_text = "CW" if esp.limit_direction == 1 else "CCW"
            limit_color = config.COLOR_FACING_NO
        y = self._draw_value(panel, "Limit", limit_text, y, limit_color)

        y += self.SECTION_SPACING // 2

        # Lights section
        y = self._draw_section_header(panel, "LIGHTS", y)
        light_cmd_text = ["OFF", "ON", "AUTO"][command.light_command]
        y = self._draw_value(panel, "Command", light_cmd_text, y)
        y = self._draw_value(panel, "State", "ON" if esp.light_state else "OFF", y,
                             config.COLOR_FACING_YES if esp.light_state else (128, 128, 128))

        y += self.SECTION_SPACING // 2

        # RGB section with color buttons
        y = self._draw_section_header(panel, "RGB", y)
        y = self._draw_value(panel, "Current", f"R:{command.rgb_r} G:{command.rgb_g} B:{command.rgb_b}", y)
        y = self._draw_color_buttons(panel, y)

        y += self.SECTION_SPACING // 2

        # Matrix section with pattern buttons
        y = self._draw_section_header(panel, "MATRIX", y)
        left_pattern = ["OFF", "Circle", "X"][command.matrix_left] if command.matrix_left < 3 else "?"
        right_pattern = ["OFF", "Circle", "X"][command.matrix_right] if command.matrix_right < 3 else "?"
        y = self._draw_value(panel, "Patterns", f"L:{left_pattern} R:{right_pattern}", y)
        y = self._draw_matrix_buttons(panel, y)

        y += self.SECTION_SPACING // 2

        # System section
        y = self._draw_section_header(panel, "SYSTEM", y)
        y = self._draw_value(panel, "FPS", f"{system.fps:.1f}", y)
        y = self._draw_value(panel, "Tracker FPS", f"{system.face_tracker_fps:.1f}", y)
        y = self._draw_value(panel, "UART", "Connected" if esp.connected else "Disconnected", y,
                             config.COLOR_FACING_YES if esp.connected else config.COLOR_FACING_NO)
        y = self._draw_value(panel, "UART TX", str(system.uart_tx_count), y)
        y = self._draw_value(panel, "UART RX", str(system.uart_rx_count), y)

        # Uptime
        uptime_str = self._format_uptime(system.uptime)
        y = self._draw_value(panel, "Uptime", uptime_str, y)

        y += self.SECTION_SPACING // 2

        # UART Packets section (for debugging)
        y = self._draw_section_header(panel, "UART PACKETS", y)
        # Truncate packets if too long
        tx_display = system.last_tx_packet[:45] + "..." if len(system.last_tx_packet) > 45 else system.last_tx_packet
        rx_display = system.last_rx_packet[:45] + "..." if len(system.last_rx_packet) > 45 else system.last_rx_packet
        y = self._draw_value(panel, "Last TX", tx_display or "-", y)
        y = self._draw_value(panel, "Last RX", rx_display or "-", y)

        y += self.SECTION_SPACING // 2

        # Test section with buttons
        y = self._draw_section_header(panel, "TEST", y)
        y = self._draw_value(panel, "Response", "OK" if esp.test_active else "-", y,
                             config.COLOR_FACING_YES if esp.test_active else (128, 128, 128))
        y = self._draw_button(panel, "LED Test", "led_test", y)

        # Store content height for scrolling calculations
        self.content_height = y + 60  # Add padding for servo bar

        # Draw servo position indicator bar at fixed position (bottom of viewport)
        # This will be drawn on the final viewport, not the scrollable content

        # Create viewport by cropping the buffer based on scroll offset
        viewport = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        viewport[:] = config.COLOR_PANEL_BG

        # Calculate visible range
        start_y = self.scroll_offset
        end_y = min(start_y + self.height, panel.shape[0])
        visible_height = end_y - start_y

        # Copy visible portion to viewport
        if visible_height > 0:
            viewport[:visible_height] = panel[start_y:end_y]

        # Draw servo bar at fixed position (bottom of viewport)
        self._draw_servo_bar(viewport, command.servo_targets[0], esp.servo_positions[0])

        # Draw scroll indicator if content overflows
        if self.content_height > self.height:
            self._draw_scroll_indicator(viewport)

        return viewport

    def get_button_at(self, x: int, y: int) -> Optional[str]:
        """
        Check if a point is inside any button.

        Args:
            x: X coordinate (relative to panel)
            y: Y coordinate (relative to panel)

        Returns:
            Button name if clicked, None otherwise
        """
        for button in self.buttons:
            if (button.x <= x <= button.x + button.width and
                button.y <= y <= button.y + button.height):
                return button.name
        return None

    def _draw_section_header(
        self,
        panel: np.ndarray,
        title: str,
        y: int,
    ) -> int:
        """Draw section header and return new y position."""
        cv2.putText(
            panel,
            title,
            (self.MARGIN, y + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
        )

        # Draw underline
        cv2.line(
            panel,
            (self.MARGIN, y + 20),
            (self.width - self.MARGIN, y + 20),
            (100, 100, 100),
            1,
        )

        return y + self.SECTION_SPACING

    def _draw_value(
        self,
        panel: np.ndarray,
        label: str,
        value: str,
        y: int,
        value_color: tuple = config.COLOR_TEXT,
    ) -> int:
        """Draw a label-value pair and return new y position."""
        # Label
        cv2.putText(
            panel,
            label + ":",
            (self.MARGIN + 10, y + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (150, 150, 150),
            1,
        )

        # Value
        cv2.putText(
            panel,
            value,
            (self.MARGIN + self.LABEL_WIDTH, y + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            value_color,
            1,
        )

        return y + self.LINE_HEIGHT

    def _draw_button(
        self,
        panel: np.ndarray,
        label: str,
        name: str,
        y: int,
    ) -> int:
        """Draw a clickable button and return new y position."""
        button_x = self.MARGIN + 10
        button_y = y

        # Check if this button is hovered
        is_hovered = (self.hovered_button == name)

        # Choose colors based on hover state
        bg_color = self.BUTTON_HOVER_COLOR if is_hovered else self.BUTTON_COLOR
        border_color = (180, 180, 180) if is_hovered else (120, 120, 120)

        # Draw button background
        cv2.rectangle(
            panel,
            (button_x, button_y),
            (button_x + self.BUTTON_WIDTH, button_y + self.BUTTON_HEIGHT),
            bg_color,
            -1,
        )

        # Draw button border
        cv2.rectangle(
            panel,
            (button_x, button_y),
            (button_x + self.BUTTON_WIDTH, button_y + self.BUTTON_HEIGHT),
            border_color,
            2 if is_hovered else 1,
        )

        # Draw button text (centered)
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        text_x = button_x + (self.BUTTON_WIDTH - text_size[0]) // 2
        text_y = button_y + (self.BUTTON_HEIGHT + text_size[1]) // 2
        cv2.putText(
            panel,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            self.BUTTON_TEXT_COLOR,
            1,
        )

        # Store button info for click detection
        self.buttons.append(ButtonInfo(
            x=button_x,
            y=button_y,
            width=self.BUTTON_WIDTH,
            height=self.BUTTON_HEIGHT,
            name=name,
        ))

        return y + self.BUTTON_HEIGHT + 10

    def _draw_color_buttons(
        self,
        panel: np.ndarray,
        y: int,
    ) -> int:
        """Draw color wheel bar and Off button, return new y position."""
        start_x = self.MARGIN + 10
        bar_width = self.width - 2 * self.MARGIN - 50  # Leave room for Off button
        bar_height = 30

        # Draw color wheel bar (HSV gradient)
        for i in range(bar_width):
            # Convert position to hue (0-360)
            hue = int((i / bar_width) * 180)  # OpenCV uses 0-180 for hue
            # Create HSV color and convert to BGR
            hsv_color = np.uint8([[[hue, 255, 255]]])
            bgr_color = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0][0]
            cv2.line(
                panel,
                (start_x + i, y),
                (start_x + i, y + bar_height),
                tuple(int(c) for c in bgr_color),
                1,
            )

        # Draw border around color bar
        is_wheel_hovered = self.hovered_button == "color_wheel"
        border_color = (255, 255, 255) if is_wheel_hovered else (120, 120, 120)
        cv2.rectangle(
            panel,
            (start_x, y),
            (start_x + bar_width, y + bar_height),
            border_color,
            2 if is_wheel_hovered else 1,
        )

        # Store color wheel as clickable area
        self.buttons.append(ButtonInfo(
            x=start_x,
            y=y,
            width=bar_width,
            height=bar_height,
            name="color_wheel",
        ))

        # Draw Off button next to color wheel
        off_x = start_x + bar_width + 5
        off_width = 40
        is_off_hovered = self.hovered_button == "rgb_off"

        cv2.rectangle(
            panel,
            (off_x, y),
            (off_x + off_width, y + bar_height),
            (40, 40, 40),
            -1,
        )
        cv2.rectangle(
            panel,
            (off_x, y),
            (off_x + off_width, y + bar_height),
            (255, 255, 255) if is_off_hovered else (120, 120, 120),
            2 if is_off_hovered else 1,
        )
        cv2.putText(
            panel,
            "OFF",
            (off_x + 8, y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (200, 200, 200),
            1,
        )

        self.buttons.append(ButtonInfo(
            x=off_x,
            y=y,
            width=off_width,
            height=bar_height,
            name="rgb_off",
        ))

        # Store color wheel bounds for click handling
        self._color_wheel_x = start_x
        self._color_wheel_width = bar_width

        return y + bar_height + 10

    def get_color_from_wheel_click(self, x: int) -> tuple[int, int, int]:
        """Convert x position on color wheel to RGB values."""
        if not hasattr(self, '_color_wheel_x'):
            return (255, 255, 255)

        # Calculate relative position
        rel_x = x - self._color_wheel_x
        rel_x = max(0, min(rel_x, self._color_wheel_width - 1))

        # Convert to hue
        hue = int((rel_x / self._color_wheel_width) * 180)

        # Convert HSV to RGB (not BGR)
        hsv_color = np.uint8([[[hue, 255, 255]]])
        bgr_color = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0][0]

        # Return as RGB (for sending to ESP32)
        return (int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0]))

    def _draw_matrix_buttons(
        self,
        panel: np.ndarray,
        y: int,
    ) -> int:
        """Draw matrix pattern buttons and return new y position."""
        # Pattern options
        patterns = [
            ("L:Off", "matrix_left_off"),
            ("L:O", "matrix_left_circle"),
            ("L:X", "matrix_left_x"),
            ("R:Off", "matrix_right_off"),
            ("R:O", "matrix_right_circle"),
            ("R:X", "matrix_right_x"),
        ]

        button_width = 40
        button_height = 24
        spacing = 3
        start_x = self.MARGIN + 10

        for i, (label, name) in enumerate(patterns):
            # Start new row for right matrix buttons
            row = 0 if i < 3 else 1
            col = i if i < 3 else i - 3

            button_x = start_x + col * (button_width + spacing)
            button_y = y + row * (button_height + spacing)

            is_hovered = (self.hovered_button == name)

            # Draw button background
            bg_color = self.BUTTON_HOVER_COLOR if is_hovered else self.BUTTON_COLOR
            cv2.rectangle(
                panel,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                bg_color,
                -1,
            )

            # Draw border
            border_color = (180, 180, 180) if is_hovered else (100, 100, 100)
            cv2.rectangle(
                panel,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                border_color,
                1,
            )

            # Draw label (centered)
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
            text_x = button_x + (button_width - text_size[0]) // 2
            text_y = button_y + (button_height + text_size[1]) // 2
            cv2.putText(
                panel,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                self.BUTTON_TEXT_COLOR,
                1,
            )

            # Store button info
            self.buttons.append(ButtonInfo(
                x=button_x,
                y=button_y,
                width=button_width,
                height=button_height,
                name=name,
            ))

        return y + 2 * (button_height + spacing) + 5

    def _draw_servo_bar(
        self,
        panel: np.ndarray,
        target: float,
        actual: float,
    ) -> None:
        """Draw servo position indicator bar at bottom of panel."""
        bar_margin = 20
        bar_y = self.height - 40
        bar_height = 15
        bar_width = self.width - 2 * bar_margin

        # Draw bar background
        cv2.rectangle(
            panel,
            (bar_margin, bar_y),
            (bar_margin + bar_width, bar_y + bar_height),
            (60, 60, 60),
            -1,
        )

        # Draw border
        cv2.rectangle(
            panel,
            (bar_margin, bar_y),
            (bar_margin + bar_width, bar_y + bar_height),
            (100, 100, 100),
            1,
        )

        # Draw target position marker
        target_x = int(bar_margin + (target / 180.0) * bar_width)
        cv2.line(
            panel,
            (target_x, bar_y - 5),
            (target_x, bar_y + bar_height + 5),
            (0, 255, 255),  # Yellow
            2,
        )

        # Draw actual position marker
        actual_x = int(bar_margin + (actual / 180.0) * bar_width)
        cv2.rectangle(
            panel,
            (actual_x - 3, bar_y + 2),
            (actual_x + 3, bar_y + bar_height - 2),
            (0, 255, 0),  # Green
            -1,
        )

        # Draw scale labels
        cv2.putText(panel, "0", (bar_margin, bar_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        cv2.putText(panel, "90", (bar_margin + bar_width // 2 - 8, bar_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        cv2.putText(panel, "180", (bar_margin + bar_width - 20, bar_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)

        # Label
        cv2.putText(panel, "SERVO", (bar_margin, self.height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

    def _draw_scroll_indicator(self, panel: np.ndarray) -> None:
        """Draw scroll indicator on right edge of panel."""
        if self.content_height <= self.height:
            return

        # Scrollbar dimensions
        bar_width = 6
        bar_margin = 3
        bar_x = self.width - bar_width - bar_margin
        bar_top = 50  # Leave room at top
        bar_bottom = self.height - 60  # Leave room for servo bar
        bar_height = bar_bottom - bar_top

        # Draw scrollbar track
        cv2.rectangle(
            panel,
            (bar_x, bar_top),
            (bar_x + bar_width, bar_bottom),
            (60, 60, 60),
            -1,
        )

        # Calculate thumb position and size
        visible_ratio = self.height / self.content_height
        thumb_height = max(20, int(bar_height * visible_ratio))
        max_scroll = self.content_height - self.height
        scroll_ratio = self.scroll_offset / max_scroll if max_scroll > 0 else 0
        thumb_y = bar_top + int((bar_height - thumb_height) * scroll_ratio)

        # Draw scrollbar thumb
        cv2.rectangle(
            panel,
            (bar_x, thumb_y),
            (bar_x + bar_width, thumb_y + thumb_height),
            (150, 150, 150),
            -1,
        )

    def _draw_state_machine_section(
        self,
        panel: np.ndarray,
        y: int,
        esp: EspState,
    ) -> int:
        """Draw state machine status and control buttons."""
        if not self.state_machine:
            return y

        # Get current state info
        state_name = self.state_machine.get_state_name()
        time_in_state = self.state_machine.get_time_in_state()
        dispensing_enabled = self.state_machine.dispensing_enabled
        forced_outcome = self.state_machine.forced_outcome

        # Get sub-state for DEAD
        dead_sub = ""
        if state_name == "DEAD":
            dead_sub = self.state_machine.get_dead_sub_state_name()

        state_color = self.STATE_COLORS.get(state_name, (200, 200, 200))

        # Draw large state display with colored background
        y = self._draw_section_header(panel, "STATE MACHINE", y)

        # Draw state box
        box_x = self.MARGIN + 10
        box_width = self.width - 2 * self.MARGIN - 20
        box_height = 50

        cv2.rectangle(
            panel,
            (box_x, y),
            (box_x + box_width, y + box_height),
            state_color,
            -1,
        )
        cv2.rectangle(
            panel,
            (box_x, y),
            (box_x + box_width, y + box_height),
            (255, 255, 255),
            2,
        )

        # Draw state name (large, centered)
        display_text = state_name
        if dead_sub:
            display_text = f"{state_name}: {dead_sub}"

        text_size = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        text_x = box_x + (box_width - text_size[0]) // 2
        text_y = y + (box_height + text_size[1]) // 2
        # Text color: black for light backgrounds, white for dark
        text_color = (0, 0, 0) if state_name in ["COLLAPSE", "ALIVE"] else (255, 255, 255)
        cv2.putText(
            panel,
            display_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            text_color,
            2,
        )

        y += box_height + 8

        # Time in state
        y = self._draw_value(panel, "Time in State", f"{time_in_state:.1f}s", y)

        # Dispensing status
        status_text = "ENABLED" if dispensing_enabled else "DISABLED"
        status_color = config.COLOR_FACING_YES if dispensing_enabled else config.COLOR_FACING_NO
        y = self._draw_value(panel, "Dispensing", status_text, y, status_color)

        # Valve status
        valve_text = "OPEN" if esp.valve_open else "CLOSED"
        valve_color = config.COLOR_FACING_NO if esp.valve_open else config.COLOR_FACING_YES
        y = self._draw_value(panel, "Valve", valve_text, y, valve_color)

        if esp.valve_open:
            y = self._draw_value(panel, "Valve Time", f"{esp.valve_ms}ms", y)

        # Next outcome
        outcome_text = forced_outcome if forced_outcome else "RANDOM"
        y = self._draw_value(panel, "Next Outcome", outcome_text, y)

        y += 5

        # Control buttons - Emergency controls (always visible)
        if dispensing_enabled:
            y = self._draw_danger_button(panel, "EMERGENCY STOP", "emergency_stop", y)
        else:
            y = self._draw_button(panel, "Enable Dispensing", "enable_dispensing", y)

        y = self._draw_button(panel, "Close Valve", "close_valve", y)
        y = self._draw_button(panel, "Force Reset", "force_reset", y)

        # Context-sensitive buttons
        if state_name == "TRACKING":
            y = self._draw_button(panel, "Force Collapse", "force_collapse", y)

        if state_name in ["COLLAPSE", "ALIVE", "DEAD"]:
            y = self._draw_button(panel, "Skip Animation", "skip_animation", y)

        y += 5

        # Outcome buttons
        y = self._draw_small_label(panel, "Next Outcome:", y)
        y = self._draw_outcome_buttons(panel, y, forced_outcome)

        y += self.SECTION_SPACING // 2

        return y

    def _draw_danger_button(
        self,
        panel: np.ndarray,
        label: str,
        name: str,
        y: int,
    ) -> int:
        """Draw a red danger button."""
        button_x = self.MARGIN + 10
        button_y = y
        button_width = self.width - 2 * self.MARGIN - 20
        button_height = 35

        is_hovered = (self.hovered_button == name)

        # Red background
        bg_color = (80, 80, 180) if is_hovered else (60, 60, 150)
        border_color = (100, 100, 255) if is_hovered else (80, 80, 200)

        cv2.rectangle(
            panel,
            (button_x, button_y),
            (button_x + button_width, button_y + button_height),
            bg_color,
            -1,
        )
        cv2.rectangle(
            panel,
            (button_x, button_y),
            (button_x + button_width, button_y + button_height),
            border_color,
            2,
        )

        # Text centered
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)[0]
        text_x = button_x + (button_width - text_size[0]) // 2
        text_y = button_y + (button_height + text_size[1]) // 2
        cv2.putText(
            panel,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )

        self.buttons.append(ButtonInfo(
            x=button_x,
            y=button_y,
            width=button_width,
            height=button_height,
            name=name,
        ))

        return y + button_height + 8

    def _draw_small_label(
        self,
        panel: np.ndarray,
        text: str,
        y: int,
    ) -> int:
        """Draw a small label."""
        cv2.putText(
            panel,
            text,
            (self.MARGIN + 10, y + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 150, 150),
            1,
        )
        return y + 18

    def _draw_outcome_buttons(
        self,
        panel: np.ndarray,
        y: int,
        current_outcome: Optional[str],
    ) -> int:
        """Draw outcome selection buttons."""
        outcomes = [
            ("Random", None, "outcome_random"),
            ("Alive", "ALIVE", "outcome_alive"),
            ("Dead", "DEAD", "outcome_dead"),
        ]

        button_width = 70
        button_height = 26
        spacing = 5
        start_x = self.MARGIN + 10

        for i, (label, value, name) in enumerate(outcomes):
            button_x = start_x + i * (button_width + spacing)
            button_y = y

            is_selected = (current_outcome == value)
            is_hovered = (self.hovered_button == name)

            # Colors
            if is_selected:
                bg_color = (100, 150, 100)  # Green for selected
                border_color = (150, 200, 150)
            elif is_hovered:
                bg_color = self.BUTTON_HOVER_COLOR
                border_color = (180, 180, 180)
            else:
                bg_color = self.BUTTON_COLOR
                border_color = (100, 100, 100)

            cv2.rectangle(
                panel,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                bg_color,
                -1,
            )
            cv2.rectangle(
                panel,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                border_color,
                1,
            )

            # Text
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            text_x = button_x + (button_width - text_size[0]) // 2
            text_y = button_y + (button_height + text_size[1]) // 2
            cv2.putText(
                panel,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                self.BUTTON_TEXT_COLOR,
                1,
            )

            self.buttons.append(ButtonInfo(
                x=button_x,
                y=button_y,
                width=button_width,
                height=button_height,
                name=name,
            ))

        return y + button_height + 10

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
