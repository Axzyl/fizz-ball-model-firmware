# Fizz Ball Model Firmware

## Project Overview

A face-tracking animatronic platform using a Raspberry Pi and ESP32. The system uses computer vision to track a person's face and control multiple servos, RGB lighting, and LED matrix displays. All outputs activate when the subject is detected facing the camera.

## Architecture

### System Components

```
┌─────────────────────┐         UART          ┌─────────────────────┐
│    Raspberry Pi     │◄─────────────────────►│       ESP32         │
│  - Face detection   │      (USB Serial)     │  - 3x Servo control │
│  - Pose estimation  │                       │  - RGB LED strip    │
│  - Dashboard UI     │                       │  - LED matrix (2x)  │
│  - Command logic    │                       │  - Limit switch     │
└─────────────────────┘                       └─────────────────────┘
```

### Raspberry Pi Architecture

```
rpi/src/
├── main.py                 # Entry point, thread orchestration
├── state.py                # Thread-safe centralized state
├── config.py               # Configuration constants
├── local_config.py         # Machine-specific overrides (gitignored)
├── vision/
│   └── face_tracker.py     # YOLO + MediaPipe hybrid face detection
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
│   ├── main.cpp            # Setup/loop, servo updates
│   ├── state.cpp/.h        # Centralized device state
│   ├── uart_handler.cpp/.h # UART packet handling
│   ├── servo_controller.cpp/.h  # Multi-servo PWM control
│   ├── rgb_strip.cpp/.h    # RGB LED strip control
│   ├── led_matrix.cpp/.h   # MAX7219 LED matrix control
│   └── limit_switch.cpp/.h # Limit switch input
├── include/
│   ├── config.h            # Configuration constants
│   └── pins.h              # Hardware pin definitions
└── platformio.ini
```

## Thread Model (Raspberry Pi)

| Thread | Responsibility | Update Rate |
|--------|----------------|-------------|
| Camera | Frame capture | 30-60 fps |
| FaceTracker | YOLO + MediaPipe processing | ~30 fps |
| UartComm | Bidirectional UART TX/RX | 30 Hz |
| Main (Dashboard) | UI rendering, user interaction | ~30 fps |

## State Management

### Raspberry Pi State (`state.py`)
- `FrameData`: Raw camera frame, timestamp
- `FaceState`: Detection results, bbox, landmarks, yaw/pitch/roll, is_facing
- `EspState`: Limit switch, 3x servo positions, light state, connection status
- `CommandState`: 3x servo targets, light command, RGB values, matrix patterns
- `SystemState`: FPS, uptime, errors

### ESP32 State (`state.h`)
- `InputState`: Limit switch readings
- `OutputState`: 3x servo angles, 3x servo moving flags, light state
- `CommandState`: 3x target angles, light command, RGB values, matrix patterns

## UART Protocol

Bidirectional ASCII protocol at 115200 baud over USB Serial.

**Pi → ESP32 (Command):**
```
$CMD,<s1>,<s2>,<s3>,<light>,<flags>,<r>,<g>,<b>,<ml>,<mr>\n
```

| Field | Description | Range |
|-------|-------------|-------|
| s1, s2, s3 | Servo target angles | 0.0 - 180.0 |
| light | Light command | 0=OFF, 1=ON, 2=AUTO |
| flags | Command flags | Bit field |
| r, g, b | RGB LED values | 0 - 255 |
| ml, mr | Matrix patterns (left/right) | 0=OFF, 1=Circle, 2=X |

**ESP32 → Pi (Status):**
```
$STS,<limit>,<s1>,<s2>,<s3>,<light>,<flags>,<test>\n
```

| Field | Description | Range |
|-------|-------------|-------|
| limit | Limit switch state | 0=CLEAR, 1=CW, 2=CCW |
| s1, s2, s3 | Servo positions | 0.0 - 180.0 |
| light | Light state | 0=OFF, 1=ON |
| flags | Status flags | Bit field |
| test | Test active | 0=NO, 1=YES |

## Hardware Connections

### ESP32 Pinout (defined in `esp32/include/pins.h`)

| GPIO | Function | Notes |
|------|----------|-------|
| 8 | Servo 1 PWM | Channel 0, Timer 0 |
| 7 | Servo 2 PWM | Channel 1, Timer 0 |
| 5 | Servo 3 PWM | Channel 2, Timer 1 |
| 27 | RGB Red | Channel 4, Timer 2 |
| 14 | RGB Green | Channel 5, Timer 2 |
| 12 | RGB Blue | Channel 6, Timer 3 |
| 25 | Matrix Data (DIN) | SPI MOSI |
| 32 | Matrix Clock (CLK) | SPI SCK |
| 26 | Matrix CS (Load) | SPI CS |
| 21 | Limit Switch | Input, internal pullup |
| 9 | Test LED | Status indicator |

### PWM Channel / Timer Mapping

**Important:** Channels sharing a timer must use the same frequency/resolution.

| Channels | Timer | Usage | Frequency | Resolution |
|----------|-------|-------|-----------|------------|
| 0, 1 | Timer 0 | Servo 1, 2 | 50 Hz | 16-bit |
| 2, 3 | Timer 1 | Servo 3 | 50 Hz | 16-bit |
| 4, 5 | Timer 2 | RGB R, G | 5 kHz | 8-bit |
| 6, 7 | Timer 3 | RGB B | 5 kHz | 8-bit |

### UART Connection

ESP32 connects to Pi via USB cable. The ESP32 appears as:
- Windows: `COMx` (e.g., COM6)
- Linux/Pi: `/dev/ttyUSB0` or `/dev/ttyACM0`

## Command Flags

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `CMD_FLAG_LED_TEST` | Trigger LED blink test |

## Servo Behavior

All 3 servos move together based on face detection:
- **Face detected AND facing camera:** All servos → 180°
- **No face OR not facing:** All servos → 0°

## Dashboard UI

OpenCV-based dashboard with two panels:

```
┌─────────────────────────────┬───────────────────────┐
│                             │  FACE                 │
│   [Live Camera Feed]        │  Detected: YES/NO     │
│                             │  Yaw/Pitch/Roll       │
│   - Bounding box overlay    │  Facing: YES/NO       │
│   - Facial landmarks        │                       │
│   - Pose axes               │  SERVOS               │
│   - Facing indicator        │  Targets: X°/Y°/Z°    │
│                             │  Actual: X°/Y°/Z°     │
│                             │  Limit: CLEAR/CW/CCW  │
│                             │                       │
│                             │  LIGHTS               │
│                             │  Command/State        │
│                             │                       │
│                             │  SYSTEM               │
│                             │  FPS, UART status     │
│                             │                       │
│                             │  TEST                 │
│                             │  [LED Blink Test]     │
│                             │                       │
│   [========= SERVO ========]│                       │
└─────────────────────────────┴───────────────────────┘
```

### Dashboard Controls
- **Keyboard:**
  - `Q` / `ESC`: Quit application
  - `R`: Reset all servos to center (90°)
  - `L`: Cycle light mode (OFF → ON → AUTO)
- **Mouse:**
  - Click "LED Blink Test" button: Triggers test LED on ESP32

## Key Algorithms

### Face Detection (Hybrid YOLO + MediaPipe)
1. **YOLO-face** detects faces robustly (handles partial occlusion)
2. **Crop** detected face region with padding
3. **MediaPipe FaceLandmarker** extracts 478 landmarks for pose estimation
4. **Fallback:** MediaPipe-only mode if YOLO unavailable

### Face Angle Calculation
Uses MediaPipe's facial transformation matrix for head pose:
- Yaw: Horizontal rotation (left/right)
- Pitch: Vertical rotation (up/down)
- Roll: Tilt rotation

### Facing Detection
Subject is "facing" when `|yaw| < FACING_YAW_THRESHOLD` (default: 15°)

## Cross-Platform Development

### Platform Detection

`config.py` auto-detects platform and sets defaults:

| Platform | UART Port Default | Detection |
|----------|-------------------|-----------|
| Windows | `COM3` | `platform.system() == "Windows"` |
| Raspberry Pi | `/dev/ttyS0` | Linux + `/proc/device-tree/model` |
| Linux | `/dev/ttyUSB0` | `platform.system() == "Linux"` |

### Local Configuration

Machine-specific settings in `rpi/src/local_config.py` (gitignored):

```python
# Windows development
UART_PORT = "COM6"
UART_MOCK_ENABLED = False

# Raspberry Pi with USB-connected ESP32
UART_PORT = "/dev/ttyUSB0"
```

### Mock UART Mode

For testing without hardware:
```python
UART_MOCK_ENABLED = True
```

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
pio device monitor      # Serial monitor (115200 baud)
```

## Configuration Files

### `esp32/include/pins.h`
All hardware pin assignments. Edit this file to change wiring.

### `esp32/include/config.h`
- PWM settings (frequency, resolution, channels)
- Servo limits and speed
- Timing intervals
- Debug enable flag

### `rpi/src/config.py`
- Platform detection
- Camera settings
- Face detection thresholds
- UART settings
- Dashboard layout

### `rpi/src/local_config.py`
- Machine-specific UART port
- Mock mode toggle

## Debugging

### Enable ESP32 Debug Output
In `esp32/include/config.h`:
```c
#define DEBUG_ENABLED       1
```

### View UART Traffic
Debug mode prints all received/sent packets to Serial.

## Important Notes

1. **Thread Safety**: All Pi state access goes through `AppState.lock`
2. **Timer Conflicts**: PWM channels sharing a timer must use same freq/resolution
3. **USB Serial**: ESP32 uses USB Serial for communication, not GPIO UART
4. **Limit Switch**: Only affects Servo 1 (main servo)
5. **Cross-Platform**: Code runs on Windows (development) and Pi (deployment)
6. **Pin 5**: ESP32 strapping pin - works on ESP32-PICO, may need pull-up on others
