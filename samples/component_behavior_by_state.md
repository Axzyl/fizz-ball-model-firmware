# Schrödinger’s Cat Dispenser

## Electronic Component Behavior by State (Concise Spec)

This document defines **exact behaviors for each electronic component** in each system state.

This is a **low-level execution contract**, not a narrative description.

---

## Components

### Inputs

- Camera (Pi)
- Limit switch (ESP)

### Actuators

- Base servo
- Arm servo
- Valve servo

### LEDs

- Neopixel LED ring (camera eye)
- Neopixel 5×5 matrix (other eye)
- RGB LED strip (ambient)

---

## STATE 1 — IDLE

### Camera

- Passive detection only
- No target tracking

### Limit Switch

- Ignored

### Base Servo

- Move to 90°
- Hold position

### Arm Servo

- Move to 90°
- Hold position

### Valve Servo

- Force closed
- Safety timer inactive

### LED Ring

- Off or very dim idle glow

### 5×5 Matrix

- Closed eye icon (static)

### RGB Strip

- Off or extremely dim ambient

---

## STATE 2 — TRACKING

### Camera

- Detect people in frame
- Track selected target horizontally
- Target rules:
  - First entrant is target
  - Switch only if another bounding box ≥ 150% size
- Report centered/not-centered status

### Limit Switch

- Monitored
- Accepted only if:
  - Tracking stable
  - Rising edge detected

### Base Servo

- Rotate to center tracked target
- Rate-limited motion

### Arm Servo

- Wave:
  - Once on state entry
  - When camera becomes centered
  - When a new person enters frame
- Wave cooldown: 5–10s

### Valve Servo

- Closed

### LED Ring

- Bright blue/purple gradient
- Indicates active observation

### 5×5 Matrix

- Open eye icon (static)

### RGB Strip

- Bright blue/purple gradient

---

## STATE 3 — COLLAPSE

### Camera

- Ignored

### Limit Switch

- Ignored

### Base Servo

- Hold current position

### Arm Servo

- Move to fixed forward-pointing pose (≈45°)

### Valve Servo

- Closed

### LED Ring

- Fast, bright rainbow animation

### 5×5 Matrix

- Optional neutral or glitch pattern (no symbols)

### RGB Strip

- Fast, bright rainbow animation

### Logic

- Pi selects and locks outcome (ALIVE or DEAD)

---

## STATE 4A — ALIVE

### Camera

- Ignored

### Limit Switch

- Ignored

### Base Servo

- Slowly rotate back to 90°

### Arm Servo

- Friendly motion or idle

### Valve Servo

- Open for 100% pour duration
- ESP enforces max-open timeout

### LED Ring

- Solid green or gentle pulse

### 5×5 Matrix

- Green circle icon

### RGB Strip

- Solid green

---

## STATE 4B — DEAD

### Camera

- Ignored

### Limit Switch

- Ignored

### Procedure (Sequential)

#### Step 1 — Tension

- Base servo: hold
- Arm servo: hold
- Valve: closed
- LED ring: solid red
- RGB strip: solid red
- Duration: ~3s

#### Step 2 — Partial Pour

- Valve: open for 35% of total pour time
- Base + arm: still
- Lights remain red

#### Step 3 — Chaos

- Base servo: violent shaking
- Arm servo: violent shaking
- Valve: closed
- LED ring: red flicker
- RGB strip: red flicker
- Duration: ~2s

#### Step 4 — Darkness

- All LEDs off
- Valve closed
- Brief pause

#### Step 5 — Final Pour

- Valve opens for remaining 65%
- LEDs remain off or minimal

### 5×5 Matrix

- Red X icon (static)

---

## STATE 5 — RESET

### Camera

- Ignored

### Limit Switch

- Ignored

### Base Servo

- Move to 90°

### Arm Servo

- Move to 90°

### Valve Servo

- Force closed

### LED Ring

- Off

### 5×5 Matrix

- Off

### RGB Strip

- Off

---

## Global Safety Rules (ESP-Enforced)

- Valve closes if:
  - Max open time exceeded
  - Communication lost
  - RESET or IDLE entered
- Valve closed on boot
- Servo angles clamped to safe limits

---

## Notes

- No text output is used on any LED matrix
- All timing values are configurable externally
- Pi commands are high-level; ESP handles execution details
- This document defines **what must happen**, not how it is implemented

---
