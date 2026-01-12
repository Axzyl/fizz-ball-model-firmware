"""UART protocol encoding and decoding."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Number of servos
NUM_SERVOS = 3


@dataclass
class CommandPacket:
    """Command packet to send to ESP32."""

    servo_targets: tuple[float, float, float]  # Target angles for 3 servos
    light_command: int
    flags: int = 0
    rgb_r: int = 0
    rgb_g: int = 0
    rgb_b: int = 0
    matrix_left: int = 1   # Left matrix pattern (0=off, 1=circle, 2=X)
    matrix_right: int = 2  # Right matrix pattern (0=off, 1=circle, 2=X)

    def encode(self) -> bytes:
        """Encode packet to bytes for transmission."""
        packet = (
            f"$CMD,{self.servo_targets[0]:.1f},{self.servo_targets[1]:.1f},{self.servo_targets[2]:.1f},"
            f"{self.light_command},{self.flags},"
            f"{self.rgb_r},{self.rgb_g},{self.rgb_b},{self.matrix_left},{self.matrix_right}\n"
        )
        return packet.encode("ascii")


@dataclass
class StatusPacket:
    """Status packet received from ESP32."""

    limit: int
    servo_positions: tuple[float, float, float]  # Current angles for 3 servos
    light_state: int
    flags: int
    test_active: int = 0  # 1 when test was triggered, stays high for 1 second

    @classmethod
    def decode(cls, data: bytes) -> Optional["StatusPacket"]:
        """
        Decode bytes to StatusPacket.

        Args:
            data: Raw bytes received from UART

        Returns:
            StatusPacket if valid, None otherwise
        """
        try:
            # Convert to string and strip whitespace
            line = data.decode("ascii").strip()

            # Check start marker
            if not line.startswith("$STS,"):
                logger.debug(f"Invalid packet start: {line}")
                return None

            # Remove start marker and parse fields
            content = line[5:]  # Remove "$STS,"
            fields = content.split(",")

            # New format: limit, servo1, servo2, servo3, light_state, flags, test_active
            if len(fields) < 6 or len(fields) > 7:
                logger.debug(f"Invalid field count: {len(fields)}")
                return None

            # Parse test_active if present (backwards compatible)
            test_active = int(fields[6]) if len(fields) >= 7 else 0

            return cls(
                limit=int(fields[0]),
                servo_positions=(
                    float(fields[1]),
                    float(fields[2]),
                    float(fields[3]),
                ),
                light_state=int(fields[4]),
                flags=int(fields[5]),
                test_active=test_active,
            )

        except (ValueError, UnicodeDecodeError) as e:
            logger.debug(f"Packet decode error: {e}")
            return None


class Protocol:
    """
    UART protocol handler.

    Manages packet encoding/decoding and buffer handling.
    """

    START_MARKER = b"$"
    END_MARKER = b"\n"
    MAX_PACKET_SIZE = 128

    def __init__(self) -> None:
        """Initialize protocol handler."""
        self.rx_buffer = bytearray()

    def create_command(
        self,
        servo_targets: tuple[float, float, float],
        light_command: int,
        flags: int = 0,
        rgb_r: int = 0,
        rgb_g: int = 0,
        rgb_b: int = 0,
        matrix_left: int = 1,
        matrix_right: int = 2,
    ) -> bytes:
        """
        Create a command packet.

        Args:
            servo_targets: Target servo angles (0-180) for all 3 servos
            light_command: Light command (0=OFF, 1=ON, 2=AUTO)
            flags: Reserved flags
            rgb_r: RGB red value (0-255)
            rgb_g: RGB green value (0-255)
            rgb_b: RGB blue value (0-255)
            matrix_left: Left matrix pattern (0=off, 1=circle, 2=X)
            matrix_right: Right matrix pattern (0=off, 1=circle, 2=X)

        Returns:
            Encoded packet bytes
        """
        # Clamp servo targets
        clamped_targets = tuple(
            max(0.0, min(180.0, t)) for t in servo_targets
        )

        # Clamp RGB values
        rgb_r = max(0, min(255, rgb_r))
        rgb_g = max(0, min(255, rgb_g))
        rgb_b = max(0, min(255, rgb_b))

        packet = CommandPacket(
            clamped_targets, light_command, flags,
            rgb_r, rgb_g, rgb_b, matrix_left, matrix_right
        )
        return packet.encode()

    def feed(self, data: bytes) -> list[StatusPacket]:
        """
        Feed received data into the protocol buffer.

        Args:
            data: Raw bytes received from UART

        Returns:
            List of complete StatusPackets parsed from buffer
        """
        packets = []

        self.rx_buffer.extend(data)

        # Prevent buffer overflow
        if len(self.rx_buffer) > self.MAX_PACKET_SIZE * 2:
            # Find last start marker and discard everything before it
            last_start = self.rx_buffer.rfind(self.START_MARKER)
            if last_start > 0:
                self.rx_buffer = self.rx_buffer[last_start:]
            else:
                self.rx_buffer.clear()

        # Process complete packets
        while True:
            # Find start marker
            start_idx = self.rx_buffer.find(self.START_MARKER)
            if start_idx < 0:
                self.rx_buffer.clear()
                break

            # Discard data before start marker
            if start_idx > 0:
                self.rx_buffer = self.rx_buffer[start_idx:]

            # Find end marker
            end_idx = self.rx_buffer.find(self.END_MARKER)
            if end_idx < 0:
                # Incomplete packet, wait for more data
                break

            # Extract packet
            packet_data = bytes(self.rx_buffer[: end_idx + 1])
            self.rx_buffer = self.rx_buffer[end_idx + 1 :]

            # Decode packet
            status = StatusPacket.decode(packet_data)
            if status:
                packets.append(status)

        return packets

    def reset(self) -> None:
        """Reset the protocol buffer."""
        self.rx_buffer.clear()
