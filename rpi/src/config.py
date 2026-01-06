"""Configuration constants for the face tracking system."""

import platform
import os

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
# Platform-specific default ports
if IS_WINDOWS:
    UART_PORT = "COM3"  # Change to match your USB-Serial adapter
elif IS_RASPBERRY_PI:
    UART_PORT = "/dev/ttyS0"  # Pi GPIO UART (pins 14/15)
else:
    UART_PORT = "/dev/ttyUSB0"  # Generic Linux USB-Serial

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
# Dashboard Settings
# -----------------------------------------------------------------------------
DASHBOARD_WIDTH = 1024
DASHBOARD_HEIGHT = 600
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
