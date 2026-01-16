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

        # Print available ports for debugging
        if ports:
            print(f"[Config] Available serial ports:")
            for p in ports:
                print(f"  - {p.device}: {p.description} ({p.manufacturer or 'unknown'})")
        else:
            print("[Config] No serial ports found")

        for port in ports:
            port_info = f"{port.description} {port.manufacturer or ''} {port.product or ''}"
            port_info_upper = port_info.upper()

            for keyword in esp32_keywords:
                if keyword.upper() in port_info_upper:
                    print(f"[Config] Auto-detected ESP32 port: {port.device} ({port.description})")
                    return port.device

        # If no match found, try first available COM/ttyUSB port
        for port in ports:
            if IS_WINDOWS and port.device.startswith("COM"):
                print(f"[Config] Using first available COM port: {port.device}")
                return port.device
            elif IS_LINUX and ("ttyUSB" in port.device or "ttyACM" in port.device):
                print(f"[Config] Using first available USB serial port: {port.device}")
                return port.device

        print("[Config] WARNING: No serial ports detected, using platform default")

    except ImportError:
        print("[Config] WARNING: pyserial not installed, using platform default port")
    except Exception as e:
        print(f"[Config] WARNING: Serial port auto-detection failed: {e}")

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
CAMERA_INDEX = 1
CAMERA_WIDTH = 640*2
CAMERA_HEIGHT = 480*2
CAMERA_FPS = 30
CAMERA_MAX_FAILURES = 30  # Consecutive failures before declaring disconnect (~1s at 30fps)

# Camera crop settings (percentage of frame to remove from each edge)
# Useful for excluding enclosure edges, reflections, or irrelevant areas
# Values are 0.0 to 0.5 (0% to 50%) - combined left+right or top+bottom must be < 1.0
CAMERA_CROP_LEFT = 0.0    # Crop from left edge (0.1 = 10%)
CAMERA_CROP_RIGHT = 0.0   # Crop from right edge
CAMERA_CROP_TOP = 0.0     # Crop from top edge
CAMERA_CROP_BOTTOM = 0.0  # Crop from bottom edge

# Dark frame detection (door closed detection)
# When the door is closed, the camera sees darkness. However, internal LEDs (strip lights,
# neopixels) may produce some ambient light even with the door closed.
#
# Two detection methods available:
#   1. Brightness only: Simple threshold on pixel brightness
#   2. Brightness + Variance: Also checks color uniformity (more robust)
#
# DARK_THRESHOLD: Brightness level (0-255) below which frame is considered "dark"
#   - Lower values = stricter (requires complete darkness)
#   - Higher values = more lenient (tolerates some internal LED light)
#   - Typical range: 15-50 depending on internal LED brightness
#
# DARK_PERCENTILE: What percentage of pixels must be below threshold (0-100)
#   - 50 = median (half of pixels must be dark)
#   - 90 = most of the frame must be dark (ignores bright LED spots)
#   - Higher values = more robust to small bright spots from LEDs
#
# DARK_USE_VARIANCE: Enable variance-based detection (True/False)
#   - When True: Both brightness AND variance must indicate "closed"
#   - Helps distinguish closed door (uniform dark) from dark room (varied dark objects)
#
# DARK_VARIANCE_THRESHOLD: Maximum std deviation for "uniform" colors (0-100)
#   - Lower values = stricter (requires very uniform colors)
#   - Door closed typically has std dev ~5-15
#   - Door open typically has std dev ~30+
#
# Tuning: Use test_brightness.py to find optimal values for your setup
DARK_THRESHOLD = 40  # 0-255 scale - raised from 15 to tolerate some internal LED light
DARK_PERCENTILE = 75  # Use 75th percentile (robust to bright LED spots)
DARK_USE_VARIANCE = True  # Set True to also check color uniformity
DARK_VARIANCE_THRESHOLD = 40  # Std dev below this = uniform (door closed)

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
print(f"[Config] Using UART port: {UART_PORT}")

UART_BAUDRATE = 115200
UART_TIMEOUT = 0.01  # seconds
UART_TX_RATE_HZ = 30
UART_CONNECTION_TIMEOUT_MS = 500

# Enable mock UART for testing without hardware
UART_MOCK_ENABLED = False  # Set True to simulate ESP32 responses

# -----------------------------------------------------------------------------
# Face Detection Settings
# -----------------------------------------------------------------------------
FACE_DETECTION_CONFIDENCE = 0.3
FACE_TRACKING_CONFIDENCE = 0.3
MAX_NUM_FACES = 4

# YOLO Face Detection (hybrid mode)
# Model size: 'n' (nano/fast), 's' (small/balanced), 'm' (medium/accurate), 'l' (large/best)
YOLO_MODEL_SIZE = 'n'  # 'small' - good balance of speed and distance detection

# Minimum face width as ratio of frame width (reject faces smaller than this)
# 0.05 = 5% = ~32 pixels on 640px frame - filters small false positives
MIN_FACE_WIDTH_RATIO = 0.04

# -----------------------------------------------------------------------------
# Facing Detection
# -----------------------------------------------------------------------------
FACING_YAW_THRESHOLD = 90.0  # degrees - subject considered facing if |yaw| < this
FACING_PITCH_THRESHOLD = 15.0  # degrees

# -----------------------------------------------------------------------------
# Servo Control
# -----------------------------------------------------------------------------
SERVO_MIN_ANGLE = 0.0
SERVO_MAX_ANGLE = 180.0
SERVO_CENTER_ANGLE = 90.0
SERVO_TRACKING_GAIN = 0.5  # How aggressively servo follows face (0.0-1.0)
SERVO_DEADZONE = 2.0  # degrees - don't move if target within this range

# -----------------------------------------------------------------------------
# Face Tracking (State Machine)
# -----------------------------------------------------------------------------
TRACKING_VELOCITY_GAIN = 0.05  # How fast servo follows face position (0.0-1.0)
TRACKING_MAX_VELOCITY = 3.0    # Max servo movement per tick in degrees (higher = faster)
TRACKING_MIN_VELOCITY = 0.5    # Min servo movement per tick when outside deadzone (degrees)
TRACKING_DEADZONE = 0.05       # Fraction of frame width to ignore (0.05 = 5%)
TRACKING_MIN_WIDTH_RATIO = 0.06 # Min face width ratio to track (0.15 = 15% of frame width)

# -----------------------------------------------------------------------------
# Dispensing / Pour Settings
# -----------------------------------------------------------------------------
POUR_DURATION = 10.0           # How long valve stays open when limit switch pressed (seconds)
DISPENSE_FLASH_DURATION = 10.0 # How long aqua flash continues after dispense (seconds)
REJECT_FLASH_DURATION = 1.0   # How long red flash on reject/repeat press (seconds)
DISPENSE_HOLD_DURATION = 1.0  # How long limit switch must be held to start dispense (seconds)

# -----------------------------------------------------------------------------
# State Durations (seconds)
# -----------------------------------------------------------------------------
COLLAPSE_DURATION = 2.0       # Quantum collapse animation duration (door open)

# -----------------------------------------------------------------------------
# Arm Wave Settings
# -----------------------------------------------------------------------------
ARM_WAVE_INTERVAL = 4.0       # Seconds between periodic arm waves when person detected

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
DASHBOARD_HEIGHT = 800  # Increased for state machine controls
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
