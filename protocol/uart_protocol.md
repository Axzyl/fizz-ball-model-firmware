# UART Protocol Specification

## Overview

Bidirectional ASCII-based protocol for communication between Raspberry Pi and ESP32.

## Physical Layer

| Parameter | Value |
|-----------|-------|
| Baud Rate | 115200 |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |
| Flow Control | None |

## Packet Format

```
$<TYPE>,<field1>,<field2>,...,<fieldN>\n
```

- **Start marker**: `$`
- **Type**: 3-character packet type identifier
- **Fields**: Comma-separated values
- **End marker**: `\n` (newline)

## Packet Types

### Pi → ESP32

#### CMD - Command Packet

Sends servo target position and light command.

```
$CMD,<servo_target>,<light_cmd>,<flags>\n
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| servo_target | float | 0.0-180.0 | Target servo angle in degrees |
| light_cmd | int | 0-2 | Light command (see below) |
| flags | int | 0-255 | Reserved for future use |

**Light Command Values:**
- `0` = OFF
- `1` = ON
- `2` = AUTO (based on facing detection)

**Example:**
```
$CMD,87.5,2,0\n
```
Sets servo target to 87.5°, lights to AUTO mode.

---

### ESP32 → Pi

#### STS - Status Packet

Reports current device state.

```
$STS,<limit>,<servo_pos>,<light_state>,<flags>\n
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| limit | int | 0-2 | Limit switch state (see below) |
| servo_pos | float | 0.0-180.0 | Current servo position |
| light_state | int | 0-1 | Current light state |
| flags | int | 0-255 | Status flags (see below) |

**Limit Switch Values:**
- `0` = Clear (no limit hit)
- `1` = CW limit triggered
- `2` = CCW limit triggered

**Status Flags (bitmask):**
- Bit 0: Servo moving
- Bit 1: UART buffer overflow
- Bit 2-7: Reserved

**Example:**
```
$STS,0,85.0,1,0\n
```
Limit clear, servo at 85°, lights on, no flags.

---

## Timing

| Parameter | Value | Notes |
|-----------|-------|-------|
| Pi TX rate | 30 Hz | Matches face detection rate |
| ESP32 TX rate | 50 Hz | Status updates |
| Response timeout | 100 ms | Consider connection lost |

## Error Handling

### Invalid Packets
- Packets without `$` start marker are discarded
- Packets without `\n` terminator within 100 bytes are discarded
- Packets with wrong number of fields are discarded
- Out-of-range values are clamped to valid range

### Connection Loss
- Pi: If no STS received for 500ms, mark ESP as disconnected
- ESP32: If no CMD received for 500ms, hold last servo position

## Buffer Sizes

| Side | RX Buffer | TX Buffer |
|------|-----------|-----------|
| Pi | 256 bytes | 256 bytes |
| ESP32 | 128 bytes | 128 bytes |

## Example Communication Sequence

```
Time    Pi → ESP32              ESP32 → Pi
────────────────────────────────────────────
0ms     $CMD,90.0,2,0\n
20ms                            $STS,0,88.0,0,1\n
33ms    $CMD,92.0,2,0\n
40ms                            $STS,0,89.5,0,1\n
66ms    $CMD,92.0,2,0\n
60ms                            $STS,0,91.0,1,0\n
...
```

## Future Extensions

The `flags` field in both packet types is reserved for future features:

**Potential CMD flags:**
- Emergency stop
- Calibration mode
- Speed override

**Potential STS flags:**
- Error codes
- Calibration status
- Temperature warnings
