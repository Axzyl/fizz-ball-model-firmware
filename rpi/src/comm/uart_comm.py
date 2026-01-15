"""Bidirectional UART communication handler."""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Optional

import sys
sys.path.append("..")
import config
from state import AppState, CommandState
from .protocol import Protocol

logger = logging.getLogger(__name__)


@dataclass
class LastSentState:
    """Tracks last sent values to detect changes."""

    light_command: int = -1
    rgb_mode: int = -1
    rgb_r: int = -1
    rgb_g: int = -1
    rgb_b: int = -1
    matrix_left: int = -1
    matrix_right: int = -1
    npm_mode: int = -1
    npm_letter: str = ""
    npm_r: int = -1
    npm_g: int = -1
    npm_b: int = -1
    npr_mode: int = -1
    npr_r: int = -1
    npr_g: int = -1
    npr_b: int = -1
    valve_open: bool = False
    estop_enable: bool = True
    flags: int = -1


class MockSerial:
    """
    Mock serial port for testing without hardware.

    Simulates ESP32 responses with realistic behavior.
    """

    def __init__(self) -> None:
        self.is_open = True
        self._rx_buffer = bytearray()
        self._servo_positions = [90.0, 90.0, 90.0]  # 3 servos
        self._light_state = 0
        self._limit = 0
        self._valve_open = 0
        self._valve_enabled = 1
        self._valve_ms = 0
        self._last_update = time.time()

    @property
    def in_waiting(self) -> int:
        """Return number of bytes available to read."""
        self._generate_status()
        return len(self._rx_buffer)

    def read(self, size: int) -> bytes:
        """Read bytes from mock buffer."""
        data = bytes(self._rx_buffer[:size])
        self._rx_buffer = self._rx_buffer[size:]
        return data

    def write(self, data: bytes) -> int:
        """Process written data and simulate ESP32 response."""
        # Parse command to update simulated state
        try:
            line = data.decode("ascii").strip()

            if line.startswith("$SRV,"):
                # Servo command: $SRV,<s1>,<s2>,<s3>
                parts = line[5:].split(",")
                if len(parts) >= 3:
                    targets = [float(parts[0]), float(parts[1]), float(parts[2])]
                    for i in range(3):
                        self._servo_positions[i] = self._move_toward(
                            self._servo_positions[i], targets[i], 5.0
                        )
                    # Simulate limit switch at extremes
                    if self._servo_positions[0] <= 5:
                        self._limit = 2  # CCW limit
                    elif self._servo_positions[0] >= 175:
                        self._limit = 1  # CW limit
                    else:
                        self._limit = 0

            elif line.startswith("$LGT,"):
                # Light command: $LGT,<cmd>
                parts = line[5:].split(",")
                if len(parts) >= 1:
                    light_cmd = int(parts[0])
                    if light_cmd == 0:
                        self._light_state = 0
                    elif light_cmd == 1:
                        self._light_state = 1

            elif line.startswith("$VLV,"):
                # Valve command: $VLV,<open>
                parts = line[5:].split(",")
                if len(parts) >= 1:
                    self._valve_open = int(parts[0])
                    if self._valve_open:
                        self._valve_ms = 0  # Reset timer on open

            elif line.startswith("$EST,"):
                # Emergency stop: $EST,<enable>
                parts = line[5:].split(",")
                if len(parts) >= 1:
                    self._valve_enabled = int(parts[0])
                    if not self._valve_enabled:
                        self._valve_open = 0  # Force valve closed

        except Exception:
            pass

        return len(data)

    def close(self) -> None:
        """Close mock port."""
        self.is_open = False

    def _move_toward(self, current: float, target: float, speed: float) -> float:
        """Simulate servo movement."""
        diff = target - current
        if abs(diff) <= speed:
            return target
        return current + (speed if diff > 0 else -speed)

    def _generate_status(self) -> None:
        """Generate periodic status packets."""
        now = time.time()
        if now - self._last_update >= 0.02:  # 50Hz
            # Update valve timer
            if self._valve_open and self._valve_enabled:
                self._valve_ms += int((now - self._last_update) * 1000)

            # Add some noise to simulate real hardware
            noise = [random.uniform(-0.5, 0.5) for _ in range(3)]

            status = (
                f"$STS,{self._limit},"
                f"{self._servo_positions[0] + noise[0]:.1f},"
                f"{self._servo_positions[1] + noise[1]:.1f},"
                f"{self._servo_positions[2] + noise[2]:.1f},"
                f"{self._light_state},0,0,"
                f"{self._valve_open},{self._valve_enabled},{self._valve_ms}\n"
            )
            self._rx_buffer.extend(status.encode("ascii"))
            self._last_update = now


class UartComm(threading.Thread):
    """
    Bidirectional UART communication thread.

    Handles:
    - Sending servo commands at regular intervals (heartbeat)
    - Sending other commands on change
    - Receiving and parsing status packets from ESP32
    - Connection monitoring
    - Mock mode for testing without hardware
    """

    def __init__(self, state: AppState, stop_event: threading.Event) -> None:
        """
        Initialize UART communication.

        Args:
            state: Application state for reading commands and writing ESP state
            stop_event: Event to signal thread shutdown
        """
        super().__init__(name="UartCommThread", daemon=True)
        self.state = state
        self.stop_event = stop_event
        self.protocol = Protocol()
        self.mock_mode = config.UART_MOCK_ENABLED

        self.serial: Optional[object] = None  # serial.Serial or MockSerial
        self.tx_interval = 1.0 / config.UART_TX_RATE_HZ
        self.last_tx_time = 0.0

        # Track last sent values to detect changes
        self._last_sent = LastSentState()

    def run(self) -> None:
        """Main UART communication loop."""
        mode_str = "MOCK" if self.mock_mode else "HARDWARE"
        logger.info(f"UART communication thread starting ({mode_str} mode)...")
        logger.info(f"Platform: {config.PLATFORM_NAME}")

        # Retry initial connection with increasing delays
        max_retries = 10
        retry_delay = 1.0
        connected = False

        for attempt in range(max_retries):
            if self.stop_event.is_set():
                return

            if self._connect():
                connected = True
                break

            logger.warning(f"UART connection attempt {attempt + 1}/{max_retries} failed")
            self.state.add_error(f"UART connection attempt {attempt + 1} failed")

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay:.1f}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 5.0)  # Exponential backoff, max 5s

        if not connected:
            logger.error("Failed to connect to UART after all retries, thread exiting")
            self.state.add_error("UART connection failed - check port settings")
            return

        logger.info("UART connected successfully")

        while not self.stop_event.is_set():
            try:
                # Receive data
                self._receive()

                # Send commands at regular interval
                now = time.time()
                if now - self.last_tx_time >= self.tx_interval:
                    self._transmit()
                    self.last_tx_time = now

                # Check connection status
                self.state.check_esp_connection(config.UART_CONNECTION_TIMEOUT_MS)

                # Small sleep to prevent busy-waiting
                time.sleep(0.001)

            except Exception as e:
                logger.error(f"UART error: {e}")
                self.state.add_error(f"UART error: {e}")

                if not self.mock_mode:
                    # Try to reconnect (only for real hardware)
                    self._disconnect()
                    time.sleep(1.0)
                    if not self._connect():
                        logger.error("UART reconnection failed")
                        time.sleep(5.0)  # Wait longer before next attempt

        self._disconnect()
        logger.info("UART communication thread stopped")

    def _connect(self) -> bool:
        """
        Connect to UART port.

        Returns:
            True if connected successfully
        """
        if self.mock_mode:
            logger.info("Using mock UART (no hardware)")
            self.serial = MockSerial()
            self.protocol.reset()
            return True

        try:
            import serial as pyserial

            # Re-run port auto-detection on each attempt
            port = self._detect_port()
            if port is None:
                logger.warning("No serial ports detected")
                return False

            logger.info(f"Opening UART port: {port}")
            self.serial = pyserial.Serial(
                port=port,
                baudrate=config.UART_BAUDRATE,
                timeout=config.UART_TIMEOUT,
                write_timeout=config.UART_TIMEOUT,
            )
            # Disable DTR/RTS to prevent ESP32 reset on connection
            self.serial.dtr = False
            self.serial.rts = False
            self.protocol.reset()
            return True

        except ImportError:
            logger.error("pyserial not installed - falling back to mock mode")
            self.mock_mode = True
            self.serial = MockSerial()
            self.protocol.reset()
            return True

        except Exception as e:
            logger.error(f"Failed to open UART port: {e}")
            self.state.add_error(f"UART open failed: {e}")

            # Offer helpful suggestions
            if config.IS_WINDOWS:
                logger.info("Tip: Check Device Manager for correct COM port")
                logger.info("Tip: Set UART_PORT in local_config.py")
            else:
                logger.info("Tip: Check that user has permission to access serial port")
                logger.info("Tip: Try: sudo usermod -a -G dialout $USER")

            return False

    def _detect_port(self) -> Optional[str]:
        """
        Auto-detect ESP32 serial port.

        Returns:
            Detected port name, or None if not found
        """
        try:
            import serial.tools.list_ports

            # Keywords to identify ESP32/USB-serial adapters
            esp32_keywords = [
                "CP210",      # Silicon Labs CP210x
                "CH340",      # WCH CH340
                "CH341",      # WCH CH341
                "FTDI",       # FTDI chips
                "USB Serial", # Generic USB serial
                "USB-SERIAL", # Generic USB serial
                "ESP32",      # ESP32 native USB
                "USB JTAG",   # ESP32-S3/C3 native USB
            ]

            ports = list(serial.tools.list_ports.comports())

            if not ports:
                logger.info("No serial ports found")
                return None

            logger.info(f"Available serial ports ({len(ports)}):")
            for p in ports:
                logger.info(f"  - {p.device}: {p.description} (mfr: {p.manufacturer or 'unknown'})")

            # Look for ESP32 keywords
            for port in ports:
                port_info = f"{port.description} {port.manufacturer or ''} {port.product or ''}"
                port_info_upper = port_info.upper()

                for keyword in esp32_keywords:
                    if keyword.upper() in port_info_upper:
                        logger.info(f"Auto-detected ESP32 port: {port.device} ({port.description})")
                        return port.device

            # If no match found, try first available COM/ttyUSB port
            for port in ports:
                if config.IS_WINDOWS and port.device.startswith("COM"):
                    logger.info(f"Using first available COM port: {port.device}")
                    return port.device
                elif config.IS_LINUX and ("ttyUSB" in port.device or "ttyACM" in port.device):
                    logger.info(f"Using first available USB serial port: {port.device}")
                    return port.device

            logger.warning("No suitable serial port found")
            return None

        except ImportError:
            logger.warning("pyserial not installed, cannot auto-detect port")
            return config.UART_PORT  # Fall back to config value
        except Exception as e:
            logger.warning(f"Port auto-detection failed: {e}")
            return config.UART_PORT  # Fall back to config value

    def _disconnect(self) -> None:
        """Disconnect from UART port."""
        if self.serial:
            try:
                if hasattr(self.serial, 'is_open') and self.serial.is_open:
                    self.serial.close()
            except Exception as e:
                logger.warning(f"Error closing UART: {e}")
        self.serial = None

    def _receive(self) -> None:
        """Receive and process data from UART."""
        if not self.serial:
            return

        try:
            # Read available data
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)

                # Log raw received data for debugging
                logger.debug(f"Raw RX ({len(data)} bytes): {data}")

                # Feed to protocol parser
                packets = self.protocol.feed(data)

                # Process received packets
                for packet in packets:
                    self.state.update_esp_from_packet(
                        limit=packet.limit,
                        servo_positions=packet.servo_positions,
                        light_state=packet.light_state,
                        flags=packet.flags,
                        test_active=packet.test_active,
                        valve_open=packet.valve_open,
                        valve_enabled=packet.valve_enabled,
                        valve_ms=packet.valve_ms,
                    )
                    rx_str = (
                        f"$STS,{packet.limit},"
                        f"{packet.servo_positions[0]:.1f},"
                        f"{packet.servo_positions[1]:.1f},"
                        f"{packet.servo_positions[2]:.1f},"
                        f"{packet.light_state},{packet.flags},{packet.test_active},"
                        f"{packet.valve_open},{packet.valve_enabled},{packet.valve_ms}"
                    )
                    self.state.increment_uart_rx(rx_str)
                    logger.debug(
                        f"RX: limit={packet.limit}, servos={packet.servo_positions}, "
                        f"valve_open={packet.valve_open}, valve_ms={packet.valve_ms}"
                    )

        except Exception as e:
            logger.error(f"UART receive error: {e}")
            if not self.mock_mode:
                raise

    def _transmit(self) -> None:
        """Send command messages to ESP32."""
        if not self.serial:
            return

        try:
            # Get current command state
            command = self.state.get_command()

            # Always send servo command as heartbeat
            self._send_servo_message(command)

            # Send other messages only on change
            self._send_if_changed(command)

        except Exception as e:
            logger.error(f"UART transmit error: {e}")
            if not self.mock_mode:
                raise

    def _send_servo_message(self, command: CommandState) -> None:
        """Send servo target message (always sent as heartbeat)."""
        packet = self.protocol.create_servo_message(
            command.servo_targets[0],
            command.servo_targets[1],
            command.servo_targets[2],
        )
        self.serial.write(packet)
        self.state.increment_uart_tx(packet.decode("ascii"))
        logger.debug(f"TX SRV: {command.servo_targets}")

    def _send_if_changed(self, command: CommandState) -> None:
        """Send messages for values that have changed."""
        last = self._last_sent

        # Light command
        if command.light_command != last.light_command:
            packet = self.protocol.create_light_message(command.light_command)
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.light_command = command.light_command
            logger.debug(f"TX LGT: {command.light_command}")

        # RGB strip
        if (command.rgb_mode != last.rgb_mode or
            command.rgb_r != last.rgb_r or
            command.rgb_g != last.rgb_g or
            command.rgb_b != last.rgb_b):
            packet = self.protocol.create_rgb_message(
                command.rgb_mode, command.rgb_r, command.rgb_g, command.rgb_b
            )
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.rgb_mode = command.rgb_mode
            last.rgb_r = command.rgb_r
            last.rgb_g = command.rgb_g
            last.rgb_b = command.rgb_b
            logger.debug(f"TX RGB: mode={command.rgb_mode}, ({command.rgb_r},{command.rgb_g},{command.rgb_b})")

        # MAX7219 matrix
        if (command.matrix_left != last.matrix_left or
            command.matrix_right != last.matrix_right):
            packet = self.protocol.create_matrix_message(
                command.matrix_left, command.matrix_right
            )
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.matrix_left = command.matrix_left
            last.matrix_right = command.matrix_right
            logger.debug(f"TX MTX: ({command.matrix_left},{command.matrix_right})")

        # NeoPixel matrix
        if (command.npm_mode != last.npm_mode or
            command.npm_letter != last.npm_letter or
            command.npm_r != last.npm_r or
            command.npm_g != last.npm_g or
            command.npm_b != last.npm_b):
            packet = self.protocol.create_npm_message(
                command.npm_mode, command.npm_letter,
                command.npm_r, command.npm_g, command.npm_b
            )
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.npm_mode = command.npm_mode
            last.npm_letter = command.npm_letter
            last.npm_r = command.npm_r
            last.npm_g = command.npm_g
            last.npm_b = command.npm_b
            logger.debug(f"TX NPM: mode={command.npm_mode}, letter={command.npm_letter}")

        # NeoPixel ring
        if (command.npr_mode != last.npr_mode or
            command.npr_r != last.npr_r or
            command.npr_g != last.npr_g or
            command.npr_b != last.npr_b):
            packet = self.protocol.create_npr_message(
                command.npr_mode, command.npr_r, command.npr_g, command.npr_b
            )
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.npr_mode = command.npr_mode
            last.npr_r = command.npr_r
            last.npr_g = command.npr_g
            last.npr_b = command.npr_b
            logger.debug(f"TX NPR: mode={command.npr_mode}, ({command.npr_r},{command.npr_g},{command.npr_b})")

        # Valve
        if command.valve_open != last.valve_open:
            packet = self.protocol.create_valve_message(command.valve_open)
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.valve_open = command.valve_open
            logger.debug(f"TX VLV: {command.valve_open}")

        # Emergency stop
        if command.estop_enable != last.estop_enable:
            packet = self.protocol.create_estop_message(command.estop_enable)
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.estop_enable = command.estop_enable
            logger.debug(f"TX EST: {command.estop_enable}")

        # Flags (for LED test, etc.)
        if command.flags != last.flags:
            packet = self.protocol.create_flags_message(command.flags)
            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))
            last.flags = command.flags
            logger.debug(f"TX FLG: {command.flags}")
