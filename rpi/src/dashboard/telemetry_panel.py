"""Telemetry panel for displaying system state values."""

from __future__ import annotations

import cv2
import numpy as np

import sys
sys.path.append("..")
import config
from state import FaceState, EspState, CommandState, SystemState


class TelemetryPanel:
    """
    Telemetry panel that displays live system state values.

    Displays:
    - Face detection state (yaw, pitch, roll, facing)
    - ESP32 state (servo position, limit switch, lights)
    - Command state (servo target, light command)
    - System state (FPS, UART status, uptime)
    """

    # Panel layout
    SECTION_SPACING = 30
    LINE_HEIGHT = 20
    MARGIN = 15
    LABEL_WIDTH = 140

    def __init__(self, width: int, height: int) -> None:
        """
        Initialize telemetry panel.

        Args:
            width: Panel width in pixels
            height: Panel height in pixels
        """
        self.width = width
        self.height = height

    def render(
        self,
        face: FaceState,
        esp: EspState,
        command: CommandState,
        system: SystemState,
    ) -> np.ndarray:
        """
        Render telemetry panel with current state values.

        Args:
            face: Current face detection state
            esp: Current ESP32 state
            command: Current command state
            system: Current system state

        Returns:
            Rendered panel as BGR image
        """
        # Create panel with background
        panel = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        panel[:] = config.COLOR_PANEL_BG

        y = self.MARGIN

        # Face section
        y = self._draw_section_header(panel, "FACE", y)
        y = self._draw_value(panel, "Detected", "YES" if face.detected else "NO", y,
                             config.COLOR_FACING_YES if face.detected else config.COLOR_FACING_NO)
        y = self._draw_value(panel, "Yaw", f"{face.yaw:+.1f}°", y)
        y = self._draw_value(panel, "Pitch", f"{face.pitch:+.1f}°", y)
        y = self._draw_value(panel, "Roll", f"{face.roll:+.1f}°", y)
        y = self._draw_value(panel, "Facing", "YES" if face.is_facing else "NO", y,
                             config.COLOR_FACING_YES if face.is_facing else config.COLOR_FACING_NO)
        y = self._draw_value(panel, "Confidence", f"{face.confidence:.2f}", y)

        y += self.SECTION_SPACING // 2

        # Servo section
        y = self._draw_section_header(panel, "SERVO", y)
        y = self._draw_value(panel, "Target", f"{command.servo_target:.1f}°", y)
        y = self._draw_value(panel, "Actual", f"{esp.servo_position:.1f}°", y)

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

        # Draw servo position indicator bar
        self._draw_servo_bar(panel, command.servo_target, esp.servo_position)

        return panel

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
