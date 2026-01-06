# Project Status

## Current Phase: LED Test Feature

**Last Updated:** 2026-01-05

---

## Version History

### v0.1.3 - LED Blink Test Feature (2026-01-05)

**Status:** Complete

#### Changes
- Added LED blink test button to dashboard UI
- Implemented command flag system for special operations
- ESP32 runs non-blocking LED test state machine
- Clicking "LED Blink Test" button triggers 5 blinks on ESP32 built-in LED
- Verifies end-to-end UART communication

#### Files Modified
- `esp32/include/config.h` - Added `BUILTIN_LED_PIN`, `CMD_FLAG_LED_TEST`, blink timing constants
- `esp32/src/main.cpp` - Added LED init, `check_led_test()`, `run_led_test()` state machine
- `rpi/src/config.py` - Added `CMD_FLAG_LED_TEST` constant
- `rpi/src/state.py` - Added `set_command_flag()`, `clear_command_flag()`, `trigger_led_test()` methods
- `rpi/src/dashboard/telemetry_panel.py` - Added `ButtonInfo` dataclass, button rendering, click detection
- `rpi/src/dashboard/dashboard.py` - Added mouse callback, button click handling

#### Technical Details
- Command flags are transmitted in the UART protocol's flags field
- ESP32 clears the flag after receiving to prevent re-triggering
- Non-blocking state machine allows normal operation during test
- Button click detection uses coordinate transformation from dashboard to panel space

---

### v0.1.2 - MediaPipe Tasks API Migration (2026-01-05)

**Status:** Complete

#### Changes
- Migrated from legacy `mediapipe.solutions` to MediaPipe Tasks API
- Implemented automatic model downloading (`face_landmarker.task`)
- Added facial transformation matrix support for improved pose estimation
- Models stored in `rpi/src/models/` directory (gitignored)

#### Files Modified
- `rpi/src/vision/face_tracker.py` - Complete rewrite using Tasks API
- `.gitignore` - Added model file exclusions
- `CLAUDE.md` - Updated face detection documentation

#### Technical Details
- Uses `FaceLandmarker` instead of `FaceMesh`
- Model auto-downloads from Google Storage on first run
- 478 landmarks (vs 468 in old API)
- Transformation matrix provides more stable pose estimation

#### Why This Change
- The legacy `mediapipe.solutions` API throws `AttributeError` on newer MediaPipe versions
- Tasks API is the current recommended approach
- Better pose estimation via transformation matrices

---

### v0.1.1 - Cross-Platform Support (2026-01-05)

**Status:** Complete

#### Changes
- Added platform detection (Windows, Linux, Raspberry Pi)
- Implemented Mock UART for testing without ESP32 hardware
- Added local config override system (`local_config.py`)
- Platform-specific UART port defaults
- Updated startup logging to show platform info
- Added `.gitignore` entries for local config and PlatformIO

#### Files Modified
- `rpi/src/config.py` - Platform detection, mock UART flag, local config import
- `rpi/src/comm/uart_comm.py` - MockSerial class, cross-platform error handling
- `rpi/src/main.py` - Platform info logging at startup
- `.gitignore` - Added project-specific entries

#### Files Added
- `rpi/src/local_config.example.py` - Template for machine-specific settings

---

### v0.1.0 - Initial Scaffold (2026-01-05)

**Status:** Complete

#### Completed
- [x] Project architecture design
- [x] Directory structure created
- [x] Documentation files (CLAUDE.md, project_status.md, README.md)
- [x] UART protocol specification
- [x] Raspberry Pi code scaffolding
  - [x] Core modules (main, state, config)
  - [x] Vision module (face_tracker)
  - [x] Communication module (uart_comm, protocol)
  - [x] Dashboard module (dashboard, video_panel, telemetry_panel)
- [x] ESP32 code scaffolding
  - [x] Core modules (main, state, config)
  - [x] Peripheral modules (servo, light, limit_switch)
  - [x] UART handler

#### Architecture Decisions
1. **Bidirectional UART**: Added to support limit switch feedback from ESP32 to Pi
2. **Combined Face Tracker**: Merged angle calculation into face_tracker.py since both use MediaPipe
3. **Thread-safe State**: Centralized state with mutex lock for multi-threaded access
4. **OpenCV Dashboard**: Chose OpenCV for simplicity; can upgrade to web-based later

---

## Current Status

### What Works (Expected)
- [x] Cross-platform config detection
- [x] Mock UART mode for testing without hardware
- [x] Local config override system
- [x] MediaPipe Tasks API integration
- [x] Automatic model downloading
- [ ] Camera capture (not yet tested)
- [ ] Face detection (not yet tested)
- [ ] Dashboard rendering (not yet tested)

### Pending Testing
- [ ] Run application on Windows with mock UART
- [ ] Verify MediaPipe face detection works
- [ ] Test FaceLandmarker model download
- [ ] Test dashboard UI renders correctly
- [ ] Test on Raspberry Pi
- [ ] Test real UART with ESP32

### Known Issues
- None yet

### Resolved Issues
- ~~`AttributeError: module 'mediapipe' has no attribute 'solutions'`~~ - Fixed by migrating to Tasks API

---

## Planned Milestones

### v0.2.0 - Basic Functionality
- [ ] Camera capture verified on Windows
- [ ] Camera capture verified on Raspberry Pi
- [ ] Face detection working with MediaPipe
- [ ] Dashboard displays camera feed
- [ ] Mock UART testing complete

### v0.3.0 - Hardware Integration
- [ ] UART communication with real ESP32
- [ ] Servo responds to face tracking
- [ ] Limit switch stops servo at bounds
- [ ] Lights respond to facing detection

### v0.4.0 - Dashboard Complete
- [ ] Video panel with all overlays
- [ ] Telemetry panel with live values
- [ ] Basic operator controls
- [ ] Keyboard shortcuts working

### v1.0.0 - Production Ready
- [ ] Robust error handling
- [ ] Configuration persistence
- [ ] Performance optimization
- [ ] Documentation complete

---

## Hardware Status

| Component | Status | Notes |
|-----------|--------|-------|
| Raspberry Pi | Not tested | Cross-platform code ready |
| ESP32 | Not tested | Firmware scaffolded |
| Camera | Not tested | OpenCV capture ready |
| Servo | Not tested | Need calibration |
| Limit Switch | Not tested | Need to verify polarity |
| Lights | Not tested | Placeholder implementation |

---

## Development Environment

### Windows (Development)
- Python 3.10+
- OpenCV, MediaPipe, pyserial
- Mock UART available for testing
- Virtual environment in `rpi/venv/`

### Raspberry Pi (Deployment)
- Python 3.10+
- Same dependencies
- Real UART on GPIO pins

### ESP32
- PlatformIO
- Arduino framework
- Build with `pio run`

---

## Testing Checklist

### Unit Tests
- [ ] Protocol packet encoding/decoding
- [ ] State management thread safety
- [ ] Angle calculation accuracy
- [ ] Mock UART behavior

### Integration Tests
- [ ] Pi ↔ ESP32 UART communication
- [ ] Face detection → Servo movement
- [ ] Limit switch → Servo stop

### Platform Tests
- [ ] Windows with mock UART
- [ ] Windows with real USB-Serial
- [ ] Raspberry Pi with GPIO UART
- [ ] Raspberry Pi with USB-Serial

### Hardware Tests
- [ ] Camera frame rate
- [ ] Servo range and speed
- [ ] Light switching
- [ ] Limit switch triggering

---

## Notes & Observations

### 2026-01-05 (Update 2)
- Added cross-platform support for Windows development
- MockSerial class simulates ESP32 responses realistically
- Local config system allows machine-specific settings without git conflicts
- Platform is auto-detected and logged at startup

### 2026-01-05 (Update 1)
- Initial project scaffold created
- Architecture designed for extensibility (future features can add to state)
- Light controller left as placeholder pending hardware details
- Dashboard designed for monitoring; controls can be added later

---

## Future Considerations

1. **Web Dashboard**: Could add Flask + WebSocket for remote monitoring
2. **Multiple Faces**: Current design tracks single face; could extend to multi-face
3. **Recording**: Could add video recording with tracking overlay
4. **Presets**: Could add servo position presets for quick positioning
5. **Auto-calibration**: Could add limit switch-based servo range calibration
6. **Configuration UI**: Could add in-dashboard config editing
