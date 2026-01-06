# Fizz Ball Model Firmware

## Project Overview

A face-tracking camera platform using a Raspberry Pi and ESP32. The system uses computer vision to track a person's face and rotate a servo-mounted camera platform to keep the subject centered. Lights activate when the subject is facing the camera.

## Architecture

### System Components

```
┌─────────────────────┐         UART          ┌─────────────────────┐
│    Raspberry Pi     │◄─────────────────────►│       ESP32         │
│  - Face detection   │                       │  - Servo control    │
│  - Pose estimation  │                       │  - Light control    │
│  - Dashboard UI     │                       │  - Limit switch     │
│  - Command logic    │                       │  - Hardware I/O     │
└─────────────────────┘                       └─────────────────────┘
```

### Raspberry Pi Architecture

```
rpi/src/
├── main.py                 # Entry point, thread orchestration
├── state.py                # Thread-safe centralized state
├── config.py               # Configuration constants
├── vision/
│   └── face_tracker.py     # MediaPipe face detection + angle calculation
├── comm/
│   ├── uart_comm.py        # Bidirectional UART communication
│   └── protocol.py         # Packet encoding/decoding
└── dashboard/
    ├── dashboard.py        # Main dashboard controller
    ├── video_panel.py      # Camera feed with overlays
    └── telemetry_panel.py  # Live state values display
```

### ESP32 Architecture

```
esp32/
├── src/
│   ├── main.cpp            # Setup/loop
│   ├── state.cpp/.h        # Centralized device state
│   ├── uart_handler.cpp/.h # UART packet handling
│   ├── servo_controller.cpp/.h
│   ├── light_controller.cpp/.h
│   └── limit_switch.cpp/.h
├── include/
│   └── config.h            # Pin definitions, constants
└── platformio.ini
```

## Thread Model (Raspberry Pi)

| Thread | Responsibility | Update Rate |
|--------|----------------|-------------|
| Camera | Frame capture | 30-60 fps |
| FaceTracker | MediaPipe processing, angle calculation | ~30 fps |
| UartComm | Bidirectional UART TX/RX | 50-100 Hz |
| Main (Dashboard) | UI rendering, user interaction | ~30 fps |

## State Management

### Raspberry Pi State (`state.py`)
- `FrameData`: Raw camera frame, timestamp
- `FaceState`: Detection results, bbox, landmarks, yaw/pitch/roll, is_facing
- `EspState`: Limit switch, servo position, light state, connection status
- `SystemState`: FPS, uptime, errors

### ESP32 State (`state.h`)
- `InputState`: Limit switch readings
- `OutputState`: Current servo angle, light state
- `CommandState`: Target values received from Pi

## UART Protocol

Bidirectional ASCII protocol at 115200 baud.

**Pi → ESP32:** `$CMD,<servo_target>,<light_cmd>,<flags>\n`
**ESP32 → Pi:** `$STS,<limit>,<servo_pos>,<light_state>,<flags>\n`

See `protocol/uart_protocol.md` for full specification.

## Hardware Connections

### UART Wiring
```
Pi GPIO14 (TX) ──────── ESP32 GPIO16 (RX)
Pi GPIO15 (RX) ──────── ESP32 GPIO17 (TX)
Pi GND ─────────────── ESP32 GND
```

### ESP32 Pinout (defined in `esp32/include/config.h`)
- Servo PWM: GPIO 18
- Light output: GPIO 19
- Limit switch input: GPIO 21

## Dashboard UI

OpenCV-based dashboard with two panels:

```
┌─────────────────────────────┬───────────────────────┐
│                             │  FACE                 │
│   [Live Camera Feed]        │  Detected: ✓          │
│                             │  Yaw/Pitch/Roll       │
│   - Bounding box overlay    │  Facing: YES/NO       │
│   - Facial landmarks        │                       │
│   - Pose axes               │  SERVO                │
│   - Facing indicator        │  Target/Actual        │
│                             │  Limit: CLEAR/HIT     │
│                             │                       │
│                             │  SYSTEM               │
│                             │  FPS, UART status     │
└─────────────────────────────┴───────────────────────┘
```

## Key Algorithms

### Face Detection & Landmarks
Uses MediaPipe Tasks API with FaceLandmarker:
- Model: `face_landmarker.task` (auto-downloaded on first run)
- Provides 478 facial landmarks
- Includes facial transformation matrix for pose estimation
- Model stored in `rpi/src/models/` (gitignored)

### Face Angle Calculation
Two methods for head pose estimation:
1. **Transformation Matrix** (preferred): Uses FaceLandmarker's built-in pose output
2. **solvePnP Fallback**: Estimates pose from 6 key landmarks using OpenCV

Outputs:
- Yaw: Horizontal rotation (left/right)
- Pitch: Vertical rotation (up/down)
- Roll: Tilt rotation

### Facing Detection
Subject is considered "facing" when `|yaw| < FACING_THRESHOLD` (configurable).

### Servo Tracking
Servo target = 90° + (face_x_offset * TRACKING_GAIN)
Clamped to safe range, respects limit switch boundaries.

## Cross-Platform Development

The Pi code supports development on Windows before deployment to Raspberry Pi.

### Platform Detection

`config.py` automatically detects the platform and sets appropriate defaults:

| Platform | UART Port Default | Detection |
|----------|-------------------|-----------|
| Windows | `COM3` | `platform.system() == "Windows"` |
| Raspberry Pi | `/dev/ttyS0` | Linux + `/proc/device-tree/model` exists |
| Linux | `/dev/ttyUSB0` | `platform.system() == "Linux"` |

### Mock UART Mode

For testing without ESP32 hardware, enable mock mode:

```python
# In rpi/src/local_config.py
UART_MOCK_ENABLED = True
```

The `MockSerial` class simulates:
- ESP32 status responses at 50Hz
- Servo position tracking with movement simulation
- Limit switch triggering at servo extremes
- Realistic noise on position readings

### Local Configuration

Machine-specific settings go in `rpi/src/local_config.py` (gitignored):

```python
# Windows development
UART_PORT = "COM5"
UART_MOCK_ENABLED = True

# Or Raspberry Pi with USB adapter
UART_PORT = "/dev/ttyUSB0"
```

See `local_config.example.py` for all available overrides.

## Development Commands

### Raspberry Pi / Windows

```bash
cd rpi
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Pi
source venv/bin/activate

pip install -r requirements.txt
cd src
python main.py
```

### ESP32
```bash
cd esp32
pio run                 # Build
pio run -t upload       # Upload to device
pio device monitor      # Serial monitor
```

## Configuration

### Raspberry Pi (`rpi/src/config.py`)
- Platform detection (`IS_WINDOWS`, `IS_LINUX`, `IS_RASPBERRY_PI`)
- Camera settings (resolution, fps, backend)
- Face detection thresholds
- UART port (platform-specific defaults) and baud rate
- Mock UART toggle for hardware-less testing
- Dashboard layout

### Local Overrides (`rpi/src/local_config.py`)
- Machine-specific UART port
- Mock mode enable/disable
- Camera index override
- Debug settings

### ESP32 (`esp32/include/config.h`)
- Pin assignments
- Servo limits and speed
- UART settings
- Timing intervals

## Important Notes

1. **Thread Safety**: All state access on Pi goes through `AppState.lock`
2. **Limit Switch Safety**: ESP32 immediately stops servo and reports to Pi when limit is hit
3. **Graceful Degradation**: System continues operating if UART disconnects (using last known values)
4. **Light Controller**: Currently uses placeholder functions - implement based on actual hardware
5. **Cross-Platform**: Code runs on Windows (for development) and Raspberry Pi (for deployment)
6. **Mock Mode**: Test full application without ESP32 by enabling `UART_MOCK_ENABLED`
