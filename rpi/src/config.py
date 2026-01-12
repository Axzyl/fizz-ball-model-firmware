"""Configuration constants for the face tracking system."""

import platform
import os
import logging

_config_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Platform Detection
# -----------------------------------------------------------------------------
PLATFORM = platform.system()  # 'Windows', 'Linux', 'Darwin'
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX = PLATFORM == "Linux"
IS_RASPBERRY_PI = IS_LINUX and os.path.exists("/proc/device-tree/model")

def _get_platform_name() -> str:
    """Get human-readable platform name."""
    if IS_RASPBERRY_PI:
        return "Raspberry Pi"
    return PLATFORM

PLATFORM_NAME = _get_platform_name()


def _auto_detect_serial_port() -> str:
    """
    Auto-detect ESP32 serial port.

    Looks for common USB-serial chips used by ESP32 boards:
    - CP210x (Silicon Labs)
    - CH340/CH341
    - FTDI
    - ESP32 native USB CDC

    Returns:
        Detected port name, or platform default if not found
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

        for port in ports:
            port_info = f"{port.description} {port.manufacturer or ''} {port.product or ''}"
            port_info_upper = port_info.upper()

            for keyword in esp32_keywords:
                if keyword.upper() in port_info_upper:
                    _config_logger.info(f"Auto-detected serial port: {port.device} ({port.description})")
                    return port.device

        # If no match found, try first available COM/ttyUSB port
        for port in ports:
            if IS_WINDOWS and port.device.startswith("COM"):
                _config_logger.info(f"Using first available COM port: {port.device}")
                return port.device
            elif IS_LINUX and ("ttyUSB" in port.device or "ttyACM" in port.device):
                _config_logger.info(f"Using first available USB serial port: {port.device}")
                return port.device

        _config_logger.warning("No serial ports detected, using platform default")

    except ImportError:
        _config_logger.warning("pyserial not installed, using platform default port")
    except Exception as e:
        _config_logger.warning(f"Serial port auto-detection failed: {e}")

    # Fall back to platform defaults
    if IS_WINDOWS:
        return "COM3"
    elif IS_RASPBERRY_PI:
        return "/dev/ttyUSB0"  # Changed default to USB for ESP32
    else:
        return "/dev/ttyUSB0"

# -----------------------------------------------------------------------------
# Camera Settings
# -----------------------------------------------------------------------------
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Platform-specific camera backend
if IS_WINDOWS:
    CAMERA_BACKEND = None  # Use default (DirectShow)
elif IS_RASPBERRY_PI:
    CAMERA_BACKEND = None  # Use default (V4L2)
else:
    CAMERA_BACKEND = None

# -----------------------------------------------------------------------------
# UART Settings
# -----------------------------------------------------------------------------
# Auto-detect serial port (can be overridden in local_config.py)
UART_PORT = _auto_detect_serial_port()

UART_BAUDRATE = 115200
UART_TIMEOUT = 0.01  # seconds
UART_TX_RATE_HZ = 30
UART_CONNECTION_TIMEOUT_MS = 500

# Enable mock UART for testing without hardware
UART_MOCK_ENABLED = False  # Set True to simulate ESP32 responses

# -----------------------------------------------------------------------------
# Face Detection Settings
# -----------------------------------------------------------------------------
FACE_DETECTION_CONFIDENCE = 0.5
FACE_TRACKING_CONFIDENCE = 0.5
MAX_NUM_FACES = 1

# YOLO Face Detection (hybrid mode)
# Minimum face width as ratio of frame width (reject faces smaller than this)
MIN_FACE_WIDTH_RATIO = 0.08  # 8% of frame width

# -----------------------------------------------------------------------------
# Facing Detection
# -----------------------------------------------------------------------------
FACING_YAW_THRESHOLD = 15.0  # degrees - subject considered facing if |yaw| < this
FACING_PITCH_THRESHOLD = 20.0  # degrees

# -----------------------------------------------------------------------------
# Servo Control
# -----------------------------------------------------------------------------
SERVO_MIN_ANGLE = 0.0
SERVO_MAX_ANGLE = 180.0
SERVO_CENTER_ANGLE = 90.0
SERVO_TRACKING_GAIN = 0.5  # How aggressively servo follows face (0.0-1.0)
SERVO_DEADZONE = 2.0  # degrees - don't move if target within this range

# -----------------------------------------------------------------------------
# Light Control
# -----------------------------------------------------------------------------
LIGHT_CMD_OFF = 0
LIGHT_CMD_ON = 1
LIGHT_CMD_AUTO = 2

# -----------------------------------------------------------------------------
# Command Flags
# -----------------------------------------------------------------------------
CMD_FLAG_LED_TEST = 0x01  # Bit 0: Trigger LED blink test on ESP32

# -----------------------------------------------------------------------------
# Dashboard Settings
# -----------------------------------------------------------------------------
DASHBOARD_WIDTH = 1024
DASHBOARD_HEIGHT = 720  # Increased for RGB and Matrix controls
DASHBOARD_FPS = 30
VIDEO_PANEL_WIDTH = 640
VIDEO_PANEL_HEIGHT = 480

# Colors (BGR format for OpenCV)
COLOR_BBOX = (0, 255, 0)  # Green
COLOR_LANDMARKS = (255, 0, 0)  # Blue
COLOR_POSE_X = (0, 0, 255)  # Red
COLOR_POSE_Y = (0, 255, 0)  # Green
COLOR_POSE_Z = (255, 0, 0)  # Blue
COLOR_FACING_YES = (0, 255, 0)  # Green
COLOR_FACING_NO = (0, 0, 255)  # Red
COLOR_TEXT = (255, 255, 255)  # White
COLOR_PANEL_BG = (40, 40, 40)  # Dark gray

# -----------------------------------------------------------------------------
# System Settings
# -----------------------------------------------------------------------------
LOG_LEVEL = "INFO"
FRAME_QUEUE_SIZE = 2  # Keep small to reduce latency

# -----------------------------------------------------------------------------
# Local Config Override
# -----------------------------------------------------------------------------
# Load local_config.py if it exists (not checked into git)
# This allows per-machine settings like COM port
try:
    from local_config import *  # noqa: F401, F403
except ImportError:
    pass
