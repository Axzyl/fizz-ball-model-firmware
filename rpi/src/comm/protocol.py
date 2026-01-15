"""UART protocol encoding and decoding.

Multi-message protocol format:
- $SRV,<s1>,<s2>,<s3>                         - Servo targets (sent at 50Hz)
- $LGT,<cmd>                                   - Light command (sent on change)
- $RGB,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>] - RGB strip (extended for gradient)
- $MTX,<left>,<right>                          - MAX7219 patterns (sent on change)
- $NPM,<mode>,<letter>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>] - NeoPixel matrix
- $NPR,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]          - NeoPixel ring
- $FLG,<flags>                                 - Command flags (sent on change)
- $VLV,<open>                                  - Valve command: 0=close, 1=open

RGB/NPM/NPR extended fields (optional, for gradient mode):
- r2, g2, b2: Second color (0-255)
- speed: Animation speed (1-50)

Status from ESP32:
- $STS,<limit>,<s1>,<s2>,<s3>,<light>,<flags>,<test>,<valve_open>,<valve_enabled>,<valve_ms>

Note: Valve auto-closes after 5 seconds. Extended fields are backwards compatible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Number of servos
NUM_SERVOS = 3


# NeoPixel Matrix modes
NPM_MODE_OFF = 0        # All LEDs off
NPM_MODE_LETTER = 1     # Display a single letter
NPM_MODE_SCROLL = 2     # Scroll text (NOT USED per spec - no text on matrix)
NPM_MODE_RAINBOW = 3    # Rainbow animation
NPM_MODE_SOLID = 4      # Solid color fill
NPM_MODE_EYE_CLOSED = 5 # Closed eye pattern (for IDLE)
NPM_MODE_EYE_OPEN = 6   # Open eye pattern (for TRACKING)
NPM_MODE_CIRCLE = 7     # Circle/filled icon (for ALIVE)
NPM_MODE_X = 8          # X icon (for DEAD)

# Scroll text IDs (for NPM_MODE_SCROLL)
# Pass as letter field: '0' for SCHRODINGER, '1' for ALIVE, etc.
SCROLL_TEXT_SCHRODINGER = '0'   # "SCHRODINGER"
SCROLL_TEXT_ALIVE = '1'         # "ALIVE"
SCROLL_TEXT_DEAD = '2'          # "DEAD"
SCROLL_TEXT_HELLO = '3'         # "HELLO"
SCROLL_TEXT_MEOW = '4'          # "MEOW"
SCROLL_TEXT_CAT = '5'           # "CAT"
SCROLL_TEXT_QUANTUM = '6'       # "QUANTUM"
SCROLL_TEXT_BOX = '7'           # "BOX"
SCROLL_TEXT_CHEERS = '8'        # "CHEERS"
SCROLL_TEXT_DRINK = '9'         # "DRINK"

# NeoPixel Matrix gradient mode
NPM_MODE_GRADIENT = 9  # Ping-pong gradient between 2 colors

# NeoPixel Ring modes
NPR_MODE_OFF = 0      # All LEDs off
NPR_MODE_SOLID = 1    # Solid color fill
NPR_MODE_RAINBOW = 2  # Rainbow wave animation
NPR_MODE_CHASE = 3    # Single LED chase animation
NPR_MODE_BREATHE = 4  # Breathing/pulse effect
NPR_MODE_SPINNER = 5  # Spinning dot animation
NPR_MODE_GRADIENT = 6 # Ping-pong gradient between 2 colors

# RGB Strip modes (matches ESP32 protocol)
RGB_MODE_SOLID = 0    # Static solid color
RGB_MODE_RAINBOW = 1  # Rainbow animation
RGB_MODE_GRADIENT = 2 # Ping-pong gradient between 2 colors


@dataclass
class StatusPacket:
    """Status packet received from ESP32."""

    limit: int
    servo_positions: tuple[float, float, float]  # Current angles for 3 servos
    light_state: int
    flags: int
    test_active: int = 0  # 1 when test was triggered, stays high for 1 second
    valve_open: int = 0  # 1 when valve is open
    valve_enabled: int = 1  # 0 when emergency stop active
    valve_ms: int = 0  # How long valve has been open (ms)

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

            # Format: limit, servo1, servo2, servo3, light_state, flags, test_active, valve_open, valve_enabled, valve_ms
            # Minimum 6 fields, maximum 10 (backwards compatible)
            if len(fields) < 6:
                logger.debug(f"Invalid field count: {len(fields)}")
                return None

            # Parse optional fields with defaults for backwards compatibility
            test_active = int(fields[6]) if len(fields) >= 7 else 0
            valve_open = int(fields[7]) if len(fields) >= 8 else 0
            valve_enabled = int(fields[8]) if len(fields) >= 9 else 1
            valve_ms = int(fields[9]) if len(fields) >= 10 else 0

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
                valve_open=valve_open,
                valve_enabled=valve_enabled,
                valve_ms=valve_ms,
            )

        except (ValueError, UnicodeDecodeError) as e:
            logger.debug(f"Packet decode error: {e}")
            return None


class Protocol:
    """
    UART protocol handler.

    Manages packet encoding/decoding and buffer handling.
    Uses multi-message format for flexible control.
    """

    START_MARKER = b"$"
    END_MARKER = b"\n"
    MAX_PACKET_SIZE = 128

    def __init__(self) -> None:
        """Initialize protocol handler."""
        self.rx_buffer = bytearray()

    # =========================================================================
    # Message Creation Functions
    # =========================================================================

    def create_servo_message(
        self,
        s1: float,
        s2: float,
        s3: float,
    ) -> bytes:
        """
        Create servo target message.

        Args:
            s1: Servo 1 target angle (0-180)
            s2: Servo 2 target angle (0-180)
            s3: Servo 3 target angle (0-180)

        Returns:
            Encoded message bytes: $SRV,<s1>,<s2>,<s3>\n
        """
        s1 = max(0.0, min(180.0, s1))
        s2 = max(0.0, min(180.0, s2))
        s3 = max(0.0, min(180.0, s3))
        return f"$SRV,{s1:.1f},{s2:.1f},{s3:.1f}\n".encode("ascii")

    def create_light_message(self, cmd: int) -> bytes:
        """
        Create light command message.

        Args:
            cmd: Light command (0=OFF, 1=ON, 2=AUTO)

        Returns:
            Encoded message bytes: $LGT,<cmd>\n
        """
        cmd = max(0, min(2, cmd))
        return f"$LGT,{cmd}\n".encode("ascii")

    def create_rgb_message(
        self,
        mode: int,
        r: int,
        g: int,
        b: int,
        r2: int = 0,
        g2: int = 0,
        b2: int = 0,
        speed: int = 10,
    ) -> bytes:
        """
        Create RGB strip message.

        Args:
            mode: RGB mode (RGB_MODE_OFF=0, RGB_MODE_SOLID=1, RGB_MODE_GRADIENT=2)
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            r2: Second color red (0-255, for gradient mode)
            g2: Second color green (0-255, for gradient mode)
            b2: Second color blue (0-255, for gradient mode)
            speed: Animation speed (1-50, for gradient mode)

        Returns:
            Encoded message bytes: $RGB,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]\n
        """
        mode = max(0, min(2, mode))
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        r2 = max(0, min(255, r2))
        g2 = max(0, min(255, g2))
        b2 = max(0, min(255, b2))
        speed = max(1, min(50, speed))

        if mode == RGB_MODE_GRADIENT:
            return f"$RGB,{mode},{r},{g},{b},{r2},{g2},{b2},{speed}\n".encode("ascii")
        return f"$RGB,{mode},{r},{g},{b}\n".encode("ascii")

    def create_matrix_message(self, left: int, right: int) -> bytes:
        """
        Create MAX7219 matrix pattern message.

        Args:
            left: Left matrix pattern ID
            right: Right matrix pattern ID

        Returns:
            Encoded message bytes: $MTX,<left>,<right>\n
        """
        return f"$MTX,{left},{right}\n".encode("ascii")

    def create_npm_message(
        self,
        mode: int,
        letter: str,
        r: int,
        g: int,
        b: int,
        r2: int = 0,
        g2: int = 0,
        b2: int = 0,
        speed: int = 10,
    ) -> bytes:
        """
        Create NeoPixel matrix message.

        Args:
            mode: NeoPixel matrix mode (NPM_MODE_*)
            letter: Letter to display (A-Z)
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            r2: Second color red (0-255, for gradient mode)
            g2: Second color green (0-255, for gradient mode)
            b2: Second color blue (0-255, for gradient mode)
            speed: Animation speed (1-50, for gradient mode)

        Returns:
            Encoded message bytes: $NPM,<mode>,<letter>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]\n
        """
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        r2 = max(0, min(255, r2))
        g2 = max(0, min(255, g2))
        b2 = max(0, min(255, b2))
        speed = max(1, min(50, speed))
        # Ensure single character
        letter = letter[0] if letter else "A"

        if mode == NPM_MODE_GRADIENT:
            return f"$NPM,{mode},{letter},{r},{g},{b},{r2},{g2},{b2},{speed}\n".encode("ascii")
        return f"$NPM,{mode},{letter},{r},{g},{b}\n".encode("ascii")

    def create_npr_message(
        self,
        mode: int,
        r: int,
        g: int,
        b: int,
        r2: int = 0,
        g2: int = 0,
        b2: int = 0,
        speed: int = 10,
    ) -> bytes:
        """
        Create NeoPixel ring message.

        Args:
            mode: NeoPixel ring mode (NPR_MODE_*)
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            r2: Second color red (0-255, for gradient mode)
            g2: Second color green (0-255, for gradient mode)
            b2: Second color blue (0-255, for gradient mode)
            speed: Animation speed (1-50, for gradient mode)

        Returns:
            Encoded message bytes: $NPR,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]\n
        """
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        r2 = max(0, min(255, r2))
        g2 = max(0, min(255, g2))
        b2 = max(0, min(255, b2))
        speed = max(1, min(50, speed))

        if mode == NPR_MODE_GRADIENT:
            return f"$NPR,{mode},{r},{g},{b},{r2},{g2},{b2},{speed}\n".encode("ascii")
        return f"$NPR,{mode},{r},{g},{b}\n".encode("ascii")

    def create_flags_message(self, flags: int) -> bytes:
        """
        Create command flags message.

        Args:
            flags: Command flags byte

        Returns:
            Encoded message bytes: $FLG,<flags>\n
        """
        return f"$FLG,{flags}\n".encode("ascii")

    def create_valve_message(self, open: bool) -> bytes:
        """
        Create valve command message.

        Args:
            open: True to open valve, False to close

        Returns:
            Encoded message bytes: $VLV,<open>\n
        """
        return f"$VLV,{1 if open else 0}\n".encode("ascii")

    def create_estop_message(self, enable: bool) -> bytes:
        """
        Create emergency stop message.

        DEPRECATED: This command is ignored by ESP32. Valve is always enabled.
        Kept for API compatibility only.

        Args:
            enable: True to enable valve operation, False to disable (emergency stop)

        Returns:
            Encoded message bytes: $EST,<enable>\n
        """
        return f"$EST,{1 if enable else 0}\n".encode("ascii")

    # =========================================================================
    # Receive Buffer Handling
    # =========================================================================

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
