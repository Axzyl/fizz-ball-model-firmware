"""Bidirectional UART communication handler."""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Optional

import sys
sys.path.append("..")
import config
from state import AppState
from .protocol import Protocol

logger = logging.getLogger(__name__)


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
            if line.startswith("$CMD,"):
                parts = line[5:].split(",")
                if len(parts) >= 5:
                    # Parse 3 servo targets
                    targets = [float(parts[0]), float(parts[1]), float(parts[2])]
                    light_cmd = int(parts[3])

                    # Simulate servo movements
                    for i in range(3):
                        self._servo_positions[i] = self._move_toward(
                            self._servo_positions[i], targets[i], 5.0
                        )

                    # Simulate light response
                    if light_cmd == 0:
                        self._light_state = 0
                    elif light_cmd == 1:
                        self._light_state = 1
                    # AUTO mode keeps current state

                    # Simulate limit switch at extremes (servo 1 only)
                    if self._servo_positions[0] <= 5:
                        self._limit = 2  # CCW limit
                    elif self._servo_positions[0] >= 175:
                        self._limit = 1  # CW limit
                    else:
                        self._limit = 0

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
            # Add some noise to simulate real hardware
            noise = [random.uniform(-0.5, 0.5) for _ in range(3)]

            status = (
                f"$STS,{self._limit},"
                f"{self._servo_positions[0] + noise[0]:.1f},"
                f"{self._servo_positions[1] + noise[1]:.1f},"
                f"{self._servo_positions[2] + noise[2]:.1f},"
                f"{self._light_state},0,0\n"
            )
            self._rx_buffer.extend(status.encode("ascii"))
            self._last_update = now


class UartComm(threading.Thread):
    """
    Bidirectional UART communication thread.

    Handles:
    - Sending command packets to ESP32 at regular intervals
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

    def run(self) -> None:
        """Main UART communication loop."""
        mode_str = "MOCK" if self.mock_mode else "HARDWARE"
        logger.info(f"UART communication thread starting ({mode_str} mode)...")
        logger.info(f"Platform: {config.PLATFORM_NAME}")

        if not self._connect():
            logger.error("Failed to connect to UART, thread exiting")
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

            logger.info(f"Opening UART port: {config.UART_PORT}")
            self.serial = pyserial.Serial(
                port=config.UART_PORT,
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
            logger.error(f"Failed to open UART port {config.UART_PORT}: {e}")
            self.state.add_error(f"UART open failed: {e}")

            # Offer helpful suggestions
            if config.IS_WINDOWS:
                logger.info("Tip: Check Device Manager for correct COM port")
                logger.info("Tip: Set UART_PORT in local_config.py")
            else:
                logger.info("Tip: Check that user has permission to access serial port")
                logger.info("Tip: Try: sudo usermod -a -G dialout $USER")

            return False

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
                    )
                    rx_str = f"$STS,{packet.limit},{packet.servo_positions[0]:.1f},{packet.servo_positions[1]:.1f},{packet.servo_positions[2]:.1f},{packet.light_state},{packet.flags},{packet.test_active}"
                    self.state.increment_uart_rx(rx_str)
                    logger.info(
                        f"RX: limit={packet.limit}, servos={packet.servo_positions}, "
                        f"light={packet.light_state}, test={packet.test_active}"
                    )

        except Exception as e:
            logger.error(f"UART receive error: {e}")
            if not self.mock_mode:
                raise

    def _transmit(self) -> None:
        """Send command packet to ESP32."""
        if not self.serial:
            return

        try:
            # Get current command state
            command = self.state.get_command()

            # Create and send packet
            packet = self.protocol.create_command(
                servo_targets=command.servo_targets,
                light_command=command.light_command,
                flags=command.flags,
                rgb_r=command.rgb_r,
                rgb_g=command.rgb_g,
                rgb_b=command.rgb_b,
                matrix_left=command.matrix_left,
                matrix_right=command.matrix_right,
            )

            self.serial.write(packet)
            self.state.increment_uart_tx(packet.decode("ascii"))

            logger.debug(
                f"TX: servos={command.servo_targets}, light={command.light_command}, "
                f"RGB=({command.rgb_r},{command.rgb_g},{command.rgb_b}), "
                f"matrix=({command.matrix_left},{command.matrix_right})"
            )

        except Exception as e:
            logger.error(f"UART transmit error: {e}")
            if not self.mock_mode:
                raise
