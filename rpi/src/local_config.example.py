"""
Local configuration overrides.

Copy this file to local_config.py and modify as needed.
local_config.py is gitignored and won't be committed.

Any variable defined here will override the default in config.py.
"""

# -----------------------------------------------------------------------------
# Windows Development Settings
# -----------------------------------------------------------------------------

# Set your COM port (check Device Manager)
# UART_PORT = "COM3"

# Enable mock UART to test without ESP32 connected
# UART_MOCK_ENABLED = True

# -----------------------------------------------------------------------------
# Camera Settings
# -----------------------------------------------------------------------------

# If you have multiple cameras, change the index
# CAMERA_INDEX = 0

# Lower resolution for slower machines
# CAMERA_WIDTH = 320
# CAMERA_HEIGHT = 240

# -----------------------------------------------------------------------------
# Raspberry Pi Settings
# -----------------------------------------------------------------------------

# Pi GPIO UART
# UART_PORT = "/dev/ttyS0"

# Pi USB serial adapter
# UART_PORT = "/dev/ttyUSB0"

# -----------------------------------------------------------------------------
# Debug Settings
# -----------------------------------------------------------------------------

# More verbose logging
# LOG_LEVEL = "DEBUG"
