# Schrödinger’s Cat Alcohol Dispenser

## System Design & State Specification (v1.1 – with Control Center)

This document defines the **hardware behavior, state machine, interaction rules, and operator control center** for the Schrödinger’s Cat–themed alcohol dispenser.

---

## 1. System Architecture

### Processing Split

- **Raspberry Pi**

  - Runs the **state machine**
  - Handles **camera vision**
  - Chooses **Alive / Dead outcome**
  - Selects and locks **tracking target**
  - Hosts **operator control center UI**
  - Sends high-level commands to ESP

- **ESP (Microcontroller)**
  - Controls **servos**
  - Drives **LEDs (Neopixel ring, 5×5 matrix, RGB strip)**
  - Reads and debounces **limit switch**
  - Enforces **valve safety (failsafe close, max open time)**
  - Executes animations and motions

---

## 2. Hardware Components

### Inputs

- Camera (Pi)
- Limit switch (ESP)
- Operator UI inputs (Pi)

### Actuators

- Base servo (rotation)
- Arm servo (gestures)
- Valve servo (dispensing)

### LEDs

- Neopixel LED ring (camera eye)
- Neopixel 5×5 matrix (other eye)
- RGB LED strip (ambient lighting)

> **Note:**  
> MAX7219 matrix text output is intentionally ignored for now.

---

## 3. Control Center – Purpose & Philosophy

The control center is operated by a **human supervisor** positioned behind the dispenser.

### Goals

- Ensure **safety**
- Allow **fairness intervention**
- Provide **fast recovery from faults**
- Avoid micromanaging theatrics

### Design Rule

> The operator overrides **outcomes and safety**, not **storytelling mechanics**.

---

## 4. Control Center – Always-Available Controls

These controls are visible and active in **all states**.

### 4.1 Emergency Stop (Hard Kill)

- Immediately:
  - Close valve
  - Disable dispensing
  - Freeze state machine
- Requires manual re-enable

**UI Element**

- Button: `EMERGENCY STOP`
- Status indicator: `DISPENSING ENABLED / DISABLED`

---

### 4.2 Force Valve Close

- Immediately closes valve
- Does NOT freeze state machine

**UI Element**

- Button: `CLOSE VALVE NOW`

---

### 4.3 Force Reset

- Forces transition to RESET
- Returns system to safe baseline
- Does not reboot hardware

**UI Element**

- Button: `FORCE RESET`
- Confirmation required

---

## 5. Control Center – State-Level Overrides

These controls are context-sensitive.

### 5.1 Force Outcome (Next Cycle Only)

Allows operator to override randomness.

- Options:
  - RANDOM
  - FORCE ALIVE
  - FORCE DEAD
- Applies only to the **next COLLAPSE**
- Automatically resets to RANDOM afterward

**UI Element**

- Dropdown: `NEXT OUTCOME`

---

### 5.2 Force Collapse

Used if:

- Tracking fails to stabilize
- Limit switch fails
- Crowd pressure

**Availability**

- Enabled only in **TRACKING**

**UI Element**

- Button: `FORCE COLLAPSE`

---

### 5.3 Skip Animation / Skip to Reset

Used to maintain pacing or recover from awkward timing.

**UI Elements**

- `SKIP CURRENT ANIMATION`
- `SKIP TO RESET`

---

## 6. Control Center – System Visibility

### 6.1 Current State Display

Large and unambiguous.

Example:

STATE: TRACKING
TARGET: LOCKED

Color-coded:

- IDLE → Purple
- TRACKING → Blue
- COLLAPSE → White
- ALIVE → Green
- DEAD → Red
- FAULT → Orange/Red

---

### 6.2 Vision Diagnostics

Simple indicators only (no raw camera feed).

- Face detected: YES / NO
- Number of people in frame
- Active target ID
- Target bounding box size
- Tracking centered: YES / NO

---

### 6.3 Hardware Status

Live indicators:

- Valve: OPEN / CLOSED
- Limit switch: PRESSED / RELEASED
- Base servo: OK / MOVING / LIMITED
- Arm servo: OK / MOVING / LIMITED
- ESP connection: CONNECTED / LOST

---

## 7. Control Center – Fault Handling

If a fault occurs, the system:

- Enters a safe state
- Disables dispensing
- Displays fault information

### Example Faults

- Limit switch stuck
- Valve timeout exceeded
- ESP communication loss
- Servo limit exceeded

### UI Behavior

FAULT: VALVE TIMEOUT
ACTION: DISPENSING DISABLED
OPTIONS:
[RESET] [RE-ENABLE DISPENSING]

---

## 8. Control Center – Configuration Panel (Non-Live)

Settings here **apply next cycle only**.

Examples:

- Full pour duration (100%)
- Limit switch hold time
- Tracking wave cooldown (5–10s)
- Reset duration
- Alive/Dead probability bias
- Servo speed limits

These controls are hidden behind a **Settings** panel.

---

## 9. Control Center – Operator Workflow

### Normal Operation

- Observe state
- Do nothing

### Common Interventions

- Force reset
- Close valve early
- Force outcome for fairness

### Rare Interventions

- Emergency stop
- Fault recovery

> If the operator UI feels boring, it is working correctly.

---

## 10. State Definitions (Summary)

| State    | Operator Influence    |
| -------- | --------------------- |
| IDLE     | Reset, Emergency Stop |
| TRACKING | Force Collapse        |
| COLLAPSE | Force Reset           |
| ALIVE    | Force Valve Close     |
| DEAD     | Force Valve Close     |
| RESET    | None (wait only)      |

---

## 11. Safety & Authority Rules

- ESP enforces all physical safety
- Pi owns logic and outcomes
- Operator overrides Pi decisions
- Operator cannot directly command servos or LEDs
- All overrides are logged (recommended)

---

## 12. Design Principles

- Safety over spectacle
- Stability over cleverness
- Operator clarity over control density
- The cat must always appear intentional

---
