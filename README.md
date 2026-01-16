# Schrödinger's Cat Dispenser

A face-tracking animatronic drink dispenser used for UBC FIZZ's 2026 ball model. When the door opens, the system performs a "quantum collapse" to determine ALIVE or DEAD state. If ALIVE and a person faces the camera, they can dispense a drink.

## Hardware Setup

1. Plug both USB devices (camera and ESP32 cable) into your computer
2. Connect the banana clips into a 5V power supply (max. current draw is about 1.5A)
3. Ensure power supply is turned off when not in use

## Software Setup

### ESP32 (if not already flashed)

I am using PlatformIO, so to open the project in vscode, select the esp32/ folder as the project folder. Alternatively, run the commands below:

```bash
cd esp32
pio run              # Build
pio run -t upload    # Upload to ESP32
```

### Computer

```bash
cd rpi
python -m venv venv
source venv/bin/activate  # Linux/Pi
# or: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Running

```bash
cd rpi/src
python main.py
```

## Configuration

All settings are in `rpi/src/config.py`. Key settings:

### Camera

```python
CAMERA_INDEX = 1              # Camera device index
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_AUTO_EXPOSURE = False  # Set False for manual control
CAMERA_EXPOSURE = -5          # Lower = darker (-10 to 0)
```

### Door Detection (Dark Frame)

```python
DARK_THRESHOLD = 60           # Brightness threshold (0-255)
DARK_PERCENTILE = 75          # Percentile for robustness to LED spots
DARK_USE_VARIANCE = True      # Also check color uniformity
DARK_VARIANCE_THRESHOLD = 50  # Std dev threshold
DARK_TO_INACTIVE_DURATION = 1.0  # Seconds of dark before INACTIVE
```

### Face Detection

```python
FACING_YAW_THRESHOLD = 90.0   # Max yaw to be "facing" (degrees)
FACING_PITCH_THRESHOLD = 20.0 # Max pitch to be "facing" (degrees)
```

### Dispensing

```python
POUR_DURATION = 2.0          # Valve open time (seconds)
DISPENSE_HOLD_DURATION = 2.0  # Button hold time to dispense (seconds)
```

### Dashboard Controls

| Key     | Action                              |
| ------- | ----------------------------------- |
| Q / ESC | Quit                                |
| E       | Emergency stop (disable dispensing) |
| D       | Enable dispensing                   |
| V       | Open valve (manual)                 |
| C       | Close valve                         |
| I       | Force INACTIVE state                |
| F       | Force COLLAPSE state                |
| 1/2/3   | Set next outcome: Random/Alive/Dead |

### UI Features

- **Pour Time:** Click the text field to edit dispense duration
- **Color Wheel:** Click to set RGB color
- **Scroll:** Mouse wheel on telemetry panel

## State Machine

```
INACTIVE (door closed)
    |
    v door opens (light detected)
COLLAPSE (2s quantum animation)
    |
    |--50%--> ALIVE (can dispense)
    |
    +--50%--> DEAD (no dispense)
    |
    v door closes (dark detected)
INACTIVE
```

### ALIVE Behavior

- **Yellow-green:** Face detected but not facing camera
- **Green:** Face detected AND facing camera (can dispense)
- Hold limit switch while facing to dispense

### DEAD Behavior

- Static red display
- No dispensing allowed

## Tuning Tools

### Brightness/Dark Detection

```bash
cd rpi/src
python test_brightness.py
```

- Adjust thresholds with arrow keys
- Press P to print config values
- Press C to preview camera crop

## Troubleshooting

### Camera too bright/dark

Set `CAMERA_AUTO_EXPOSURE = False` and adjust `CAMERA_EXPOSURE` (-10 to 0).

### Face not detected

- Check camera exposure
- Ensure adequate lighting
- Lower `FACE_DETECTION_CONFIDENCE` in config

### Door state not detecting correctly

Run `test_brightness.py` to tune `DARK_THRESHOLD` and `DARK_VARIANCE_THRESHOLD`.
