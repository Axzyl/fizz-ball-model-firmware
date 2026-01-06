"""UART protocol encoding and decoding."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CommandPacket:
    """Command packet to send to ESP32."""

    servo_target: float
    light_command: int
    flags: int = 0

    def encode(self) -> bytes:
        """Encode packet to bytes for transmission."""
        packet = f"$CMD,{self.servo_target:.1f},{self.light_command},{self.flags}\n"
        return packet.encode("ascii")


@dataclass
class StatusPacket:
    """Status packet received from ESP32."""

    limit: int
    servo_position: float
    light_state: int
    flags: int

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

            if len(fields) != 4:
                logger.debug(f"Invalid field count: {len(fields)}")
                return None

            return cls(
                limit=int(fields[0]),
                servo_position=float(fields[1]),
                light_state=int(fields[2]),
                flags=int(fields[3]),
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
        servo_target: float,
        light_command: int,
        flags: int = 0,
    ) -> bytes:
        """
        Create a command packet.

        Args:
            servo_target: Target servo angle (0-180)
            light_command: Light command (0=OFF, 1=ON, 2=AUTO)
            flags: Reserved flags

        Returns:
            Encoded packet bytes
        """
        # Clamp servo target
        servo_target = max(0.0, min(180.0, servo_target))

        packet = CommandPacket(servo_target, light_command, flags)
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
