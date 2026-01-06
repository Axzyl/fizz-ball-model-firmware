# Fizz Ball Model Firmware

A face-tracking camera platform using Raspberry Pi and ESP32. The system tracks a person's face using computer vision and rotates a servo-mounted camera to keep the subject centered. Lights activate when the subject faces the camera.

## Features

- Real-time face detection and pose estimation using MediaPipe
- Automatic camera pan to follow subject
- Light activation based on subject orientation
- Operator dashboard for monitoring
- Bidirectional UART communication between Pi and ESP32
- Limit switch protection for servo bounds

## Hardware Requirements

- Raspberry Pi (3B+ or newer recommended)
- ESP32 development board
- USB camera or Pi Camera
- Servo motor (standard hobby servo)
- Limit switch
- LED lights (or relay-controlled lights)

## Quick Start

### Raspberry Pi Setup

```bash
cd rpi
pip install -r requirements.txt
python src/main.py
```

### ESP32 Setup

Requires [PlatformIO](https://platformio.org/).

```bash
cd esp32
pio run -t upload
```

## Wiring

### UART Connection
| Raspberry Pi | ESP32 |
|--------------|-------|
| GPIO14 (TX)  | GPIO16 (RX) |
| GPIO15 (RX)  | GPIO17 (TX) |
| GND          | GND |

### ESP32 Peripherals
| Component | GPIO Pin |
|-----------|----------|
| Servo PWM | 18 |
| Light Output | 19 |
| Limit Switch | 21 |

## Configuration

- **Raspberry Pi**: Edit `rpi/src/config.py`
- **ESP32**: Edit `esp32/include/config.h`

## Documentation

- [CLAUDE.md](CLAUDE.md) - Architecture and development guide
- [project_status.md](project_status.md) - Development progress tracking
- [protocol/uart_protocol.md](protocol/uart_protocol.md) - UART protocol specification

## License

MIT
