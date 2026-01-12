# Project Status

## Current Phase: Multi-Servo & Peripheral Integration

**Last Updated:** 2026-01-10

---

## Version History

### v0.2.0 - Multi-Servo & Peripheral Integration (2026-01-10)

**Status:** In Progress

#### Changes
- Expanded from 1 servo to 3 servos (pins 8, 7, 5)
- Added RGB LED strip support (pins 27, 14, 12)
- Added dual MAX7219 LED matrix support (pins 25, 32, 26)
- Created `pins.h` for centralized pin configuration
- Fixed PWM timer conflict (RGB channels moved from 3-5 to 4-6)
- Extended UART protocol for 3 servos + RGB + matrix patterns
- Updated dashboard to display 3 servo targets/positions
- All servos move together: 180° when face detected, 0° otherwise

#### Files Added
- `esp32/include/pins.h` - Hardware pin definitions
- `esp32/src/rgb_strip.cpp/.h` - RGB LED strip PWM control
- `esp32/src/led_matrix.cpp/.h` - MAX7219 matrix control
- `rpi/src/local_config.py` - Machine-specific settings

#### Files Modified
- `esp32/include/config.h` - PWM channels, 3 servo support
- `esp32/src/state.cpp/.h` - Arrays for 3 servos
- `esp32/src/servo_controller.cpp/.h` - Multi-servo support
- `esp32/src/uart_handler.cpp` - Extended protocol parsing
- `esp32/src/main.cpp` - Multi-servo update loop
- `rpi/src/comm/protocol.py` - 3-servo packet format
- `rpi/src/state.py` - Tuples for 3 servos
- `rpi/src/comm/uart_comm.py` - Extended protocol support
- `rpi/src/main.py` - 3-servo control logic
- `rpi/src/dashboard/dashboard.py` - Reset all servos
- `rpi/src/dashboard/telemetry_panel.py` - Display 3 servos

#### Technical Details
- **PWM Timer Fix:** Servo 3 (channel 2) shares Timer 1 with original RGB channel 3. Moving RGB to channels 4-6 avoids timer conflict.
- **Protocol Format:**
  - CMD: `$CMD,<s1>,<s2>,<s3>,<light>,<flags>,<r>,<g>,<b>,<ml>,<mr>\n`
  - STS: `$STS,<limit>,<s1>,<s2>,<s3>,<light>,<flags>,<test>\n`

#### Known Issues Resolved
- Servo 3 not working → Fixed by resolving PWM timer conflict

---

### v0.1.3 - LED Blink Test Feature (2026-01-05)

**Status:** Complete

#### Changes
- Added LED blink test button to dashboard UI
- Implemented command flag system for special operations
- ESP32 runs non-blocking LED test state machine
- Verifies end-to-end UART communication

---

### v0.1.2 - MediaPipe Tasks API Migration (2026-01-05)

**Status:** Complete

#### Changes
- Migrated from legacy `mediapipe.solutions` to MediaPipe Tasks API
- Implemented automatic model downloading (`face_landmarker.task`)
- Added facial transformation matrix support for improved pose estimation

---

### v0.1.1 - Cross-Platform Support (2026-01-05)

**Status:** Complete

#### Changes
- Added platform detection (Windows, Linux, Raspberry Pi)
- Implemented Mock UART for testing without ESP32 hardware
- Added local config override system (`local_config.py`)

---

### v0.1.0 - Initial Scaffold (2026-01-05)

**Status:** Complete

#### Completed
- Project architecture design
- Raspberry Pi code scaffolding
- ESP32 code scaffolding
- UART protocol specification
- Documentation

---

## Current Status

### What Works
- [x] Cross-platform config detection
- [x] Mock UART mode for testing
- [x] Local config override system
- [x] MediaPipe Tasks API integration
- [x] ESP32 3-servo PWM control
- [x] ESP32 RGB LED strip control
- [x] ESP32 LED matrix control
- [x] UART protocol (extended format)
- [x] Dashboard 3-servo display
- [ ] Face detection → servo control (testing)
- [ ] End-to-end system test

### Pending Testing
- [ ] Verify face detection triggers servo movement
- [ ] Test RGB lighting responds to commands
- [ ] Test LED matrix patterns
- [ ] Full system integration test

### Known Issues
- None currently

### Resolved Issues
- ~~Servo 3 not working~~ - Fixed PWM timer conflict (RGB channels 3→4, 4→5, 5→6)
- ~~`AttributeError: module 'mediapipe' has no attribute 'solutions'`~~ - Fixed by migrating to Tasks API
- ~~`'CommandState' object has no attribute 'servo_target'`~~ - Fixed dashboard to use `servo_targets` tuple

---

## Hardware Configuration

### ESP32 Pinout (ESP32-PICO)

| GPIO | Function | PWM Channel | Timer |
|------|----------|-------------|-------|
| 8 | Servo 1 | 0 | Timer 0 |
| 7 | Servo 2 | 1 | Timer 0 |
| 5 | Servo 3 | 2 | Timer 1 |
| 27 | RGB Red | 4 | Timer 2 |
| 14 | RGB Green | 5 | Timer 2 |
| 12 | RGB Blue | 6 | Timer 3 |
| 25 | Matrix DIN | - | - |
| 32 | Matrix CLK | - | - |
| 26 | Matrix CS | - | - |
| 21 | Limit Switch | - | - |
| 9 | Test LED | - | - |

### Connection
- ESP32 connects to Pi/PC via USB cable
- USB Serial used for UART protocol (not GPIO UART)

---

## Development Environment

### Windows (Development)
- Python 3.10+
- OpenCV, MediaPipe, pyserial, ultralytics (YOLO)
- UART port: COM6 (configured in `local_config.py`)

### Raspberry Pi (Deployment)
- Python 3.10+
- Same dependencies
- UART port: `/dev/ttyUSB0` or `/dev/ttyACM0`

### ESP32 (ESP32-PICO)
- PlatformIO with Arduino framework
- Libraries: MD_MAX72XX

---

## Planned Milestones

### v0.2.1 - Integration Testing
- [ ] Verify face detection → servo movement
- [ ] Test all peripherals (RGB, matrix)
- [ ] Performance tuning

### v0.3.0 - Behavior Refinement
- [ ] Smooth servo transitions
- [ ] RGB color presets
- [ ] Matrix animation patterns

### v1.0.0 - Production Ready
- [ ] Robust error handling
- [ ] Performance optimization
- [ ] Documentation complete

---

## Notes & Observations

### 2026-01-10
- Fixed PWM timer conflict causing Servo 3 to fail
- ESP32 LEDC channels share timers in pairs (0-1, 2-3, 4-5, 6-7)
- Channels sharing a timer must use same frequency/resolution
- Moving RGB from channels 3-5 to 4-6 resolved the conflict
- ESP32-PICO allows use of GPIO 5, 7, 8 (unlike standard ESP32-WROOM)

### 2026-01-05
- Initial project scaffold created
- Cross-platform support added for Windows development
- MediaPipe Tasks API migration completed
