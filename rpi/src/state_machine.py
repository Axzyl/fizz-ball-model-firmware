"""State machine for Schrödinger's Cat Alcohol Dispenser.

New simplified state model:
- INACTIVE: Door closed (dark), all lights off, CV skipped to save CPU
- COLLAPSE: Quantum collapse animation (deciding ALIVE/DEAD)
- ALIVE: Cat is alive - persistent state with sub-behaviors
- DEAD: Cat is dead - persistent static state
- FAULT: Error state (ESP disconnect)

State flow:
INACTIVE -> (door opens) -> COLLAPSE -> ALIVE or DEAD -> (door closes) -> INACTIVE
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import config
from state import FaceState, EspState


# =============================================================================
# NeoPixel Matrix (5x5) Modes - npm_mode values
# =============================================================================
NPM_OFF = 0           # Off
NPM_LETTER = 1        # Display a letter
NPM_SCROLL = 2        # Scrolling text (NOT USED per spec - no text on matrix)
NPM_RAINBOW = 3       # Rainbow animation
NPM_SOLID = 4         # Solid color fill
NPM_EYE_CLOSED = 5    # Closed eye icon (for IDLE)
NPM_EYE_OPEN = 6      # Open eye icon (for TRACKING)
NPM_CIRCLE = 7        # Circle/filled icon (for ALIVE)
NPM_X = 8             # X icon (for DEAD)

# =============================================================================
# Scroll Text IDs (for NPM_SCROLL mode)
# =============================================================================
# Pass as npm_letter field when using NPM_SCROLL mode
SCROLL_SCHRODINGER = '0'   # "SCHRODINGER"
SCROLL_ALIVE = '1'         # "ALIVE"
SCROLL_DEAD = '2'          # "DEAD"
SCROLL_HELLO = '3'         # "HELLO"
SCROLL_MEOW = '4'          # "MEOW"
SCROLL_CAT = '5'           # "CAT"
SCROLL_QUANTUM = '6'       # "QUANTUM"
SCROLL_BOX = '7'           # "BOX"
SCROLL_CHEERS = '8'        # "CHEERS"
SCROLL_DRINK = '9'         # "DRINK"

# =============================================================================
# NeoPixel Ring Modes - npr_mode values
# =============================================================================
NPR_OFF = 0           # Off
NPR_SOLID = 1         # Solid color
NPR_RAINBOW = 2       # Rainbow cycle
NPR_CHASE = 3         # Chase animation
NPR_BREATHE = 4       # Breathing/pulse effect
NPR_SPINNER = 5       # Spinner animation

# =============================================================================
# RGB Strip Modes - rgb_mode values
# =============================================================================
RGB_SOLID = 0         # Solid color (use r,g,b values)
RGB_RAINBOW = 1       # Rainbow cycle (ignore r,g,b)


class State(Enum):
    """State machine states - simplified model."""
    INACTIVE = auto()   # Door closed, all off
    COLLAPSE = auto()   # Quantum collapse (2s)
    ALIVE = auto()      # Cat alive - persistent
    DEAD = auto()       # Cat dead - persistent
    FAULT = auto()      # ESP disconnect


class AliveBehavior(Enum):
    """Sub-behaviors for ALIVE state."""
    ENTRY = auto()              # Entry animation after collapse (~2s)
    IDLE = auto()               # No detection - aqua dim, eyes closed
    DETECTED = auto()           # Face detected - green, tracking, arm static
    DISPENSING = auto()         # Valve open, aqua flash
    DISPENSE_REJECT = auto()    # Already dispensed - shake, red flash


class DeadBehavior(Enum):
    """Sub-behaviors for DEAD state."""
    ENTRY = auto()      # Entry animation after collapse (~2s) - red + X
    NORMAL = auto()     # Static red + X
    REJECT = auto()     # Limit switch pressed - flash red briefly


@dataclass
class StateMachineConfig:
    """Configuration parameters for the state machine."""

    # Tracking parameters - defaults from config.py
    tracking_velocity_gain: float = None  # How fast base rotates
    tracking_deadzone: float = None       # Deadzone as fraction of frame
    tracking_max_velocity: float = None   # Max rotation speed degrees/tick
    tracking_min_velocity: float = None   # Min rotation speed when outside deadzone
    tracking_invert_direction: bool = False  # Invert tracking direction
    tracking_base_min: float = 0.0   # Minimum base servo angle
    tracking_base_max: float = 180.0  # Maximum base servo angle
    tracking_min_width_ratio: float = None  # Min face width to track (as fraction of frame)

    # State durations
    collapse_duration: float = None       # Duration of collapse animation (2s)
    alive_entry_duration: float = 2.0     # Entry animation duration
    dead_entry_duration: float = 2.0      # Entry animation duration
    dispense_duration: float = None       # How long valve stays open
    dispense_flash_duration: float = None # How long to flash during dispense
    reject_flash_duration: float = None   # How long to flash on reject
    dispense_hold_duration: float = None  # How long to hold switch before dispense

    # Door detection thresholds
    dark_to_inactive_duration: float = 2.0  # Seconds of darkness to enter INACTIVE
    light_to_collapse_duration: float = 1.0  # Seconds of light to trigger COLLAPSE

    # Arm wave parameters
    arm_wave_min: float = 45.0    # Lower for more dramatic wave
    arm_wave_max: float = 135.0   # Higher for more dramatic wave
    arm_wave_speed: float = 4.0   # Degrees per tick (faster wave)
    arm_wave_interval: float = None  # Seconds between waves when detected

    # Shake parameters (for reject animation)
    shake_speed: float = 15.0   # Degrees per tick
    shake_range: float = 30.0   # Max deviation from center

    # Alive/dead probability
    alive_probability: float = 0.5  # 50% chance of alive

    def __post_init__(self):
        """Load defaults from config.py if not specified."""
        # Tracking settings
        if self.tracking_velocity_gain is None:
            self.tracking_velocity_gain = getattr(config, 'TRACKING_VELOCITY_GAIN', 0.1)
        if self.tracking_deadzone is None:
            self.tracking_deadzone = getattr(config, 'TRACKING_DEADZONE', 0.067)
        if self.tracking_max_velocity is None:
            self.tracking_max_velocity = getattr(config, 'TRACKING_MAX_VELOCITY', 4.0)
        if self.tracking_min_velocity is None:
            self.tracking_min_velocity = getattr(config, 'TRACKING_MIN_VELOCITY', 0.5)
        if self.tracking_min_width_ratio is None:
            self.tracking_min_width_ratio = getattr(config, 'TRACKING_MIN_WIDTH_RATIO', 0.15)
        # State durations
        if self.collapse_duration is None:
            self.collapse_duration = getattr(config, 'COLLAPSE_DURATION', 2.0)
        # Dispense settings
        if self.dispense_duration is None:
            self.dispense_duration = getattr(config, 'POUR_DURATION', 3.0)
        if self.dispense_flash_duration is None:
            self.dispense_flash_duration = getattr(config, 'DISPENSE_FLASH_DURATION', 2.0)
        if self.reject_flash_duration is None:
            self.reject_flash_duration = getattr(config, 'REJECT_FLASH_DURATION', 1.0)
        if self.dispense_hold_duration is None:
            self.dispense_hold_duration = getattr(config, 'DISPENSE_HOLD_DURATION', 1.0)
        # Arm wave interval
        if self.arm_wave_interval is None:
            self.arm_wave_interval = getattr(config, 'ARM_WAVE_INTERVAL', 5.0)


class StateMachine:
    """Main state machine for the dispenser."""

    def __init__(self, config: Optional[StateMachineConfig] = None):
        self.config = config or StateMachineConfig()

        # Current state
        self._state = State.INACTIVE
        self._state_start_time = time.time()
        self._prev_state = State.INACTIVE

        # Current behavior (for ALIVE/DEAD states)
        self._current_behavior: Optional[Enum] = None

        # Tracking state
        self.tracking_base_position: float = 90.0

        # Arm wave state
        self.arm_wave_position: float = 90.0
        self._arm_wave_direction: int = 1  # 1 = increasing, -1 = decreasing
        self._last_wave_time: float = 0.0
        self._wave_active: bool = False

        # Shake state (for reject animation)
        self._shake_offset: float = 0.0
        self._shake_direction: int = 1

        # Session tracking (reset when door closes)
        self._has_dispensed: bool = False

        # Timing for behaviors
        self._dispense_start: float = 0.0
        self._reject_start: float = 0.0
        self._limit_switch_hold_start: float = 0.0  # When limit switch was first pressed

        # Outcome
        self._outcome: Optional[str] = None  # "ALIVE" or "DEAD"
        self.forced_outcome: Optional[str] = None  # Operator override

        # Safety
        self.dispensing_enabled: bool = True
        self._fault_reason: str = ""

        # Skip flags
        self._skip_requested: bool = False

        # Dark/light tracking for door detection
        self._dark_start_time: float = 0.0   # When darkness started
        self._light_start_time: float = 0.0  # When light started

        # Manual valve override (for dashboard button)
        self._manual_valve_open: bool = False
        self._manual_valve_open_time: float = 0.0  # When manual valve was opened

    def get_state_name(self) -> str:
        """Get current state name."""
        return self._state.name

    def get_behavior_name(self) -> str:
        """Get current behavior name (for ALIVE/DEAD states)."""
        if self._current_behavior is not None:
            return self._current_behavior.name
        return ""

    def get_time_in_state(self) -> float:
        """Get time spent in current state."""
        return time.time() - self._state_start_time

    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state."""
        self._prev_state = self._state
        self._state = new_state
        self._state_start_time = time.time()
        self._skip_requested = False
        self._current_behavior = None

        # State entry actions
        if new_state == State.INACTIVE:
            # Reset session state when door closes
            self._has_dispensed = False
            self._light_start_time = 0.0
            self._dispense_start = 0.0
            self._reject_start = 0.0
        elif new_state == State.COLLAPSE:
            # Determine outcome
            if self.forced_outcome:
                self._outcome = self.forced_outcome
                self.forced_outcome = None  # Reset after use
            else:
                self._outcome = "ALIVE" if random.random() < self.config.alive_probability else "DEAD"
        elif new_state == State.ALIVE:
            # Reset wave for entry animation
            self._start_wave()
        elif new_state == State.DEAD:
            pass

    def _start_wave(self) -> None:
        """Start arm wave animation."""
        self._wave_active = True
        self.arm_wave_position = 90.0
        self._arm_wave_direction = 1

    def _update_wave(self) -> float:
        """Update wave animation. Returns current arm position."""
        if not self._wave_active:
            return 90.0

        # Animate wave
        self.arm_wave_position += self._arm_wave_direction * self.config.arm_wave_speed

        if self.arm_wave_position >= self.config.arm_wave_max:
            self._arm_wave_direction = -1
        elif self.arm_wave_position <= self.config.arm_wave_min:
            self._arm_wave_direction = 1
            # One full wave cycle complete
            self._wave_active = False
            self.arm_wave_position = 90.0
            # Record when wave ended so next wave triggers after interval
            self._last_wave_time = time.time()

        return self.arm_wave_position

    def _update_shake(self) -> float:
        """Update shake animation. Returns offset to apply to servos."""
        self._shake_offset += self._shake_direction * self.config.shake_speed

        if abs(self._shake_offset) >= self.config.shake_range:
            self._shake_direction = -self._shake_direction

        return self._shake_offset

    def _should_transition_to_inactive(self, face: FaceState) -> bool:
        """Check if dark long enough to return to INACTIVE."""
        if face.is_dark:
            if self._dark_start_time == 0:
                self._dark_start_time = time.time()
            elif (time.time() - self._dark_start_time) >= self.config.dark_to_inactive_duration:
                return True
        else:
            self._dark_start_time = 0
        return False

    def tick(self, face: FaceState, esp: EspState) -> dict:
        """
        Run one tick of the state machine.

        Args:
            face: Current face detection state
            esp: Current ESP32 state

        Returns:
            Dictionary of commands to send
        """
        # Check for faults
        if not esp.connected and self._state != State.FAULT:
            self._fault_reason = "ESP connection lost"
            self._transition_to(State.FAULT)

        # Check for camera disconnect - return to INACTIVE from any non-INACTIVE state
        if not face.camera_connected and self._state not in (State.INACTIVE, State.FAULT):
            self._fault_reason = "Camera disconnected"
            self._transition_to(State.INACTIVE)
            return self._tick_inactive(face, esp)

        # Track light duration for INACTIVE -> COLLAPSE transition
        if not face.is_dark:
            if self._light_start_time == 0:
                self._light_start_time = time.time()
        else:
            self._light_start_time = 0

        # Run state-specific logic
        if self._state == State.INACTIVE:
            return self._tick_inactive(face, esp)
        elif self._state == State.COLLAPSE:
            return self._tick_collapse(face, esp)
        elif self._state == State.ALIVE:
            return self._tick_alive(face, esp)
        elif self._state == State.DEAD:
            return self._tick_dead(face, esp)
        elif self._state == State.FAULT:
            return self._tick_fault(face, esp)

        return self._make_commands()

    def _tick_inactive(self, face: FaceState, esp: EspState) -> dict:
        """INACTIVE state: door closed, all lights off, CV skipped.

        - Entry: Reset _has_dispensed flag
        - Exit: 1 second of light -> COLLAPSE (only if camera connected)
        - Outputs: All off, servos at 90
        """
        self._current_behavior = None

        # Only transition if camera is connected
        if not face.camera_connected:
            # Reset light timer when camera disconnected - stay in INACTIVE
            self._light_start_time = 0
        elif not face.is_dark and self._light_start_time > 0:
            # Check if light has been detected long enough to trigger collapse
            light_duration = time.time() - self._light_start_time
            if light_duration >= self.config.light_to_collapse_duration:
                self._transition_to(State.COLLAPSE)
                return self._tick_collapse(face, esp)

        # Everything off
        return self._make_commands(
            servo_target_1=90.0,
            servo_target_2=90.0,
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=0, rgb_b=0,
            npm_mode=NPM_OFF,
            npm_r=0, npm_g=0, npm_b=0,
            npr_mode=NPR_OFF,
            npr_r=0, npr_g=0, npr_b=0,
            matrix_left=0,
            matrix_right=0,
        )

    def _tick_collapse(self, face: FaceState, esp: EspState) -> dict:
        """COLLAPSE state: quantum collapse animation (2 seconds).

        - On entry: Determine outcome (ALIVE/DEAD)
        - Duration: 2 seconds
        - Exit: -> ALIVE or DEAD based on outcome
        - Outputs: Rainbow on all LEDs, servos at 90
        """
        self._current_behavior = None

        # Check for timeout or skip
        if self.get_time_in_state() >= self.config.collapse_duration or self._skip_requested:
            if self._outcome == "ALIVE":
                self._transition_to(State.ALIVE)
                return self._tick_alive(face, esp)
            else:
                self._transition_to(State.DEAD)
                return self._tick_dead(face, esp)

        # COLLAPSE lighting: fast rainbow everywhere
        return self._make_commands(
            servo_target_1=90.0,
            servo_target_2=90.0,
            valve_open=False,
            rgb_mode=RGB_RAINBOW,
            rgb_r=255, rgb_g=255, rgb_b=255,
            npm_mode=NPM_RAINBOW,
            npm_r=255, npm_g=255, npm_b=255,
            npr_mode=NPR_RAINBOW,
            npr_r=255, npr_g=255, npr_b=255,
        )

    def _tick_alive(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE state: persistent state with sub-behaviors.

        Sub-behaviors:
        - ENTRY: Wave + green (~2s)
        - IDLE: No detection - aqua dim, eyes closed
        - DETECTED_NOT_FACING: Green, tracking, arm static
        - LOOKING_DIRECTLY: Yellow, tracking, arm waves periodically
        - DISPENSING: Valve open, aqua flash
        - DISPENSE_REJECT: Already dispensed - shake, red flash

        Exit: 2s of dark -> INACTIVE
        """
        # Check for door close -> INACTIVE
        if self._should_transition_to_inactive(face):
            self._transition_to(State.INACTIVE)
            return self._tick_inactive(face, esp)

        # Determine current behavior
        behavior = self._determine_alive_behavior(face, esp)
        self._current_behavior = behavior

        # Execute behavior-specific logic
        if behavior == AliveBehavior.ENTRY:
            return self._alive_entry(face, esp)
        elif behavior == AliveBehavior.DISPENSING:
            return self._alive_dispensing(face, esp)
        elif behavior == AliveBehavior.DISPENSE_REJECT:
            return self._alive_dispense_reject(face, esp)
        elif behavior == AliveBehavior.DETECTED:
            return self._alive_detected(face, esp)
        else:  # IDLE
            return self._alive_idle(face, esp)

    def _determine_alive_behavior(self, face: FaceState, esp: EspState) -> AliveBehavior:
        """Determine which ALIVE sub-behavior to execute."""
        # Entry animation takes priority (first 2 seconds)
        if self.get_time_in_state() < self.config.alive_entry_duration:
            return AliveBehavior.ENTRY

        # Check if currently in dispense or reject animation
        if self._dispense_start > 0:
            dispense_elapsed = time.time() - self._dispense_start
            if dispense_elapsed < self.config.dispense_flash_duration:
                return AliveBehavior.DISPENSING

        if self._reject_start > 0:
            reject_elapsed = time.time() - self._reject_start
            if reject_elapsed < self.config.reject_flash_duration:
                return AliveBehavior.DISPENSE_REJECT

        # Limit switch handling
        if esp.limit_triggered:
            if not self._has_dispensed:
                # First dispense - requires holding for dispense_hold_duration
                # AND at least one person must be facing the camera
                any_facing = face.detected and face.num_facing > 0
                if any_facing:
                    if self._limit_switch_hold_start == 0:
                        # Start tracking hold time
                        self._limit_switch_hold_start = time.time()

                    hold_elapsed = time.time() - self._limit_switch_hold_start
                    if hold_elapsed >= self.config.dispense_hold_duration:
                        # Held long enough while facing - start dispense
                        self._has_dispensed = True
                        self._dispense_start = time.time()
                        self._limit_switch_hold_start = 0  # Reset for next time
                        return AliveBehavior.DISPENSING
                    # Still holding, not long enough yet - continue with normal behavior
                else:
                    # No one facing camera - reset hold timer (must face to dispense)
                    self._limit_switch_hold_start = 0
            else:
                # Already dispensed - reject immediately (no hold required)
                self._reject_start = time.time()
                self._shake_offset = 0.0
                self._shake_direction = 1
                return AliveBehavior.DISPENSE_REJECT
        else:
            # Limit switch released - reset hold timer
            self._limit_switch_hold_start = 0

        # Face detection behavior (tracking cutoff is separate - handled in velocity calc)
        if face.detected:
            return AliveBehavior.DETECTED

        return AliveBehavior.IDLE

    def _alive_entry(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE entry: Wave + solid green, eyes open."""
        # Arm wave animation
        arm_pos = self._update_wave()

        return self._make_commands(
            servo_target_1=90.0,
            servo_target_2=arm_pos,
            valve_open=False,
            npm_mode=NPM_EYE_OPEN,
            npm_r=0, npm_g=255, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=0, npr_g=255, npr_b=0,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=200, rgb_b=0,
        )

    def _alive_idle(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE idle: No detection - aqua dim, eyes closed."""
        # Move base back to 90
        diff = 90.0 - self.tracking_base_position
        if abs(diff) > 0.5:
            move = min(2.0, abs(diff))
            self.tracking_base_position += move if diff > 0 else -move

        return self._make_commands(
            servo_target_1=self.tracking_base_position,
            servo_target_2=90.0,
            valve_open=False,
            npm_mode=NPM_EYE_CLOSED,
            npm_r=0, npm_g=180, npm_b=180,  # Aqua
            npr_mode=NPR_BREATHE,
            npr_r=0, npr_g=150, npr_b=150,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=80, rgb_b=80,  # Dim aqua
        )

    def _alive_detected(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE detected: Green if facing, yellow-green if not facing."""
        # Update tracking position
        velocity = self._calculate_tracking_velocity_from_position(face)
        self.tracking_base_position += velocity
        self.tracking_base_position = max(
            self.config.tracking_base_min,
            min(self.config.tracking_base_max, self.tracking_base_position)
        )

        # Periodic arm wave - triggers every arm_wave_interval seconds
        arm_pos = 90.0
        now = time.time()
        time_since_last_wave = now - self._last_wave_time

        # Start new wave if not currently waving and enough time has passed
        if not self._wave_active and time_since_last_wave >= self.config.arm_wave_interval:
            self._start_wave()

        # Update wave animation if active
        if self._wave_active:
            arm_pos = self._update_wave()

        # Check if ANY face is facing the camera
        any_facing = face.num_facing > 0

        if any_facing:
            # Green - someone is facing the camera
            return self._make_commands(
                servo_target_1=self.tracking_base_position,
                servo_target_2=arm_pos,
                valve_open=False,
                npm_mode=NPM_EYE_OPEN,
                npm_r=0, npm_g=255, npm_b=0,  # Green
                npr_mode=NPR_SOLID,
                npr_r=0, npr_g=255, npr_b=0,
                rgb_mode=RGB_SOLID,
                rgb_r=0, rgb_g=200, rgb_b=0,
            )
        else:
            # Yellow-green - detected but not facing
            return self._make_commands(
                servo_target_1=self.tracking_base_position,
                servo_target_2=arm_pos,
                valve_open=False,
                npm_mode=NPM_EYE_OPEN,
                npm_r=180, npm_g=255, npm_b=0,  # Yellow-green
                npr_mode=NPR_SOLID,
                npr_r=180, npr_g=255, npr_b=0,
                rgb_mode=RGB_SOLID,
                rgb_r=150, rgb_g=200, rgb_b=0,
            )

    def _alive_dispensing(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE dispensing: Valve open, aqua flash with open eyes."""
        dispense_elapsed = time.time() - self._dispense_start

        # Check if dispense animation complete
        if dispense_elapsed >= self.config.dispense_flash_duration:
            # _has_dispensed was already set at start of dispense
            self._dispense_start = 0

        # Valve open only for the actual pour duration
        valve_open = self.dispensing_enabled and (dispense_elapsed < self.config.dispense_duration)

        # Fast flashing aqua/cyan (8Hz for obvious blink, full on/off)
        flash = int(time.time() * 8) % 2 == 0
        brightness = 255 if flash else 0

        return self._make_commands(
            servo_target_1=self.tracking_base_position,
            servo_target_2=90.0,
            valve_open=valve_open,
            npm_mode=NPM_EYE_OPEN,  # Open eyes = dispensing (not X)
            npm_r=0, npm_g=brightness, npm_b=brightness,  # Aqua flash
            npr_mode=NPR_SOLID,
            npr_r=0, npr_g=brightness, npr_b=brightness,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=brightness, rgb_b=brightness,
        )

    def _alive_dispense_reject(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE already dispensed: Shake, red flash, X eyes."""
        reject_elapsed = time.time() - self._reject_start

        # Check if reject animation complete
        if reject_elapsed >= self.config.reject_flash_duration:
            self._reject_start = 0
            self._shake_offset = 0

        # Shake animation
        shake = self._update_shake()

        # Fast flashing red (8Hz for obvious blink, full on/off)
        flash = int(time.time() * 8) % 2 == 0
        brightness = 255 if flash else 0

        return self._make_commands(
            servo_target_1=90.0 + shake * 0.5,
            servo_target_2=90.0 + shake,
            valve_open=False,
            npm_mode=NPM_X,  # X to indicate rejection
            npm_r=brightness, npm_g=0, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=brightness, npr_g=0, npr_b=0,
            rgb_mode=RGB_SOLID,
            rgb_r=brightness, rgb_g=0, rgb_b=0,
        )

    def _tick_dead(self, face: FaceState, esp: EspState) -> dict:
        """DEAD state: simple static state - no tracking, no dispensing.

        Sub-behaviors:
        - ENTRY: Solid red + X eyes (~2s)
        - NORMAL: Static red + X (same as entry)
        - REJECT: Limit switch pressed - flash red briefly

        Exit: 2s of dark -> INACTIVE
        """
        # Check for door close -> INACTIVE
        if self._should_transition_to_inactive(face):
            self._transition_to(State.INACTIVE)
            return self._tick_inactive(face, esp)

        # Determine behavior
        behavior = self._determine_dead_behavior(face, esp)
        self._current_behavior = behavior

        if behavior == DeadBehavior.REJECT:
            return self._dead_reject(face, esp)
        else:  # ENTRY or NORMAL (same visuals)
            return self._dead_normal(face, esp)

    def _determine_dead_behavior(self, face: FaceState, esp: EspState) -> DeadBehavior:
        """Determine DEAD sub-behavior."""
        # Entry animation (first 2 seconds)
        if self.get_time_in_state() < self.config.dead_entry_duration:
            return DeadBehavior.ENTRY

        # Check if currently in reject animation
        if self._reject_start > 0:
            reject_elapsed = time.time() - self._reject_start
            if reject_elapsed < self.config.reject_flash_duration:
                return DeadBehavior.REJECT

        # Limit switch pressed - trigger reject
        if esp.limit_triggered:
            self._reject_start = time.time()
            return DeadBehavior.REJECT

        return DeadBehavior.NORMAL

    def _dead_normal(self, face: FaceState, esp: EspState) -> dict:
        """DEAD normal: Static red + X, no tracking."""
        return self._make_commands(
            servo_target_1=90.0,  # No tracking
            servo_target_2=90.0,
            valve_open=False,  # Never dispense
            npm_mode=NPM_X,
            npm_r=255, npm_g=0, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=255, npr_g=0, npr_b=0,
            rgb_mode=RGB_SOLID,
            rgb_r=200, rgb_g=0, rgb_b=0,
        )

    def _dead_reject(self, face: FaceState, esp: EspState) -> dict:
        """DEAD reject: Flash red on limit switch."""
        reject_elapsed = time.time() - self._reject_start

        if reject_elapsed >= self.config.reject_flash_duration:
            self._reject_start = 0

        # Fast flashing red (8Hz for obvious blink, full on/off)
        flash = int(time.time() * 8) % 2 == 0
        brightness = 255 if flash else 0

        return self._make_commands(
            servo_target_1=90.0,
            servo_target_2=90.0,
            valve_open=False,
            npm_mode=NPM_X,
            npm_r=brightness, npm_g=0, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=brightness, npr_g=0, npr_b=0,
            rgb_mode=RGB_SOLID,
            rgb_r=brightness, rgb_g=0, rgb_b=0,
        )

    def _tick_fault(self, face: FaceState, esp: EspState) -> dict:
        """FAULT state: error occurred (ESP disconnect)."""
        self._current_behavior = None

        # Check if connection restored
        if esp.connected and self.dispensing_enabled:
            self._transition_to(State.INACTIVE)
            return self._tick_inactive(face, esp)

        # Fast flash red to indicate fault (8Hz, full on/off)
        flash = int(time.time() * 8) % 2 == 0
        brightness = 255 if flash else 0

        return self._make_commands(
            servo_target_1=90.0,
            servo_target_2=90.0,
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=brightness, rgb_g=0, rgb_b=0,
            npm_mode=NPM_X,
            npm_r=brightness, npm_g=0, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=brightness, npr_g=0, npr_b=0,
            matrix_left=2,  # X
            matrix_right=2,  # X
        )

    def _is_face_trackable(self, face: FaceState) -> bool:
        """Check if face is large enough to be considered for tracking/detection."""
        if not face.detected or face.bbox is None:
            return False

        x, y, w, h = face.bbox
        frame_width = face.frame_width if face.frame_width > 0 else 640
        face_width_ratio = w / frame_width

        return face_width_ratio >= self.config.tracking_min_width_ratio

    def _calculate_tracking_velocity_from_position(self, face: FaceState) -> float:
        """
        Calculate base rotation velocity from face position in frame.

        Uses the face's POSITION in the frame (bbox), not the head's yaw angle.

        Args:
            face: Face state with bbox

        Returns:
            Velocity to apply to servo (degrees per tick)
        """
        if not self._is_face_trackable(face):
            return 0.0

        x, y, w, h = face.bbox

        # Use ACTUAL frame dimensions from face state
        frame_width = face.frame_width if face.frame_width > 0 else 640

        # Calculate face center as fraction of frame (0.0 = left, 1.0 = right)
        face_center_x = (x + w / 2) / frame_width

        # Calculate error from center (positive = face is right of center)
        error = face_center_x - 0.5

        # Apply deadzone (as fraction of frame)
        if abs(error) < self.config.tracking_deadzone:
            return 0.0

        # Calculate velocity
        velocity = -error * 180.0 * self.config.tracking_velocity_gain

        # Apply minimum velocity (ensure servo actually moves when outside deadzone)
        if velocity > 0 and velocity < self.config.tracking_min_velocity:
            velocity = self.config.tracking_min_velocity
        elif velocity < 0 and velocity > -self.config.tracking_min_velocity:
            velocity = -self.config.tracking_min_velocity

        # Clamp velocity to prevent overshoot
        velocity = max(-self.config.tracking_max_velocity,
                      min(self.config.tracking_max_velocity, velocity))

        if self.config.tracking_invert_direction:
            velocity = -velocity

        return velocity

    def _make_commands(
        self,
        servo_target_1: float = 90.0,
        servo_target_2: float = 90.0,
        valve_open: bool = False,
        rgb_mode: int = RGB_SOLID,
        rgb_r: int = 0,
        rgb_g: int = 0,
        rgb_b: int = 0,
        npm_mode: int = NPM_OFF,
        npm_letter: str = "A",
        npm_r: int = 0,
        npm_g: int = 0,
        npm_b: int = 0,
        npr_mode: int = NPR_OFF,
        npr_r: int = 0,
        npr_g: int = 0,
        npr_b: int = 0,
        matrix_left: int = 0,
        matrix_right: int = 0,
    ) -> dict:
        """Create command dictionary."""
        # Apply manual valve override (dashboard button can force valve open)
        # Auto-close after pour duration
        if self._manual_valve_open:
            elapsed = time.time() - self._manual_valve_open_time
            if elapsed >= self.config.dispense_duration:
                self._manual_valve_open = False

        actual_valve_open = valve_open or self._manual_valve_open

        return {
            "servo_target_1": servo_target_1,
            "servo_target_2": servo_target_2,
            "valve_open": actual_valve_open,
            "rgb_mode": rgb_mode,
            "rgb_r": rgb_r,
            "rgb_g": rgb_g,
            "rgb_b": rgb_b,
            "npm_mode": npm_mode,
            "npm_letter": npm_letter,
            "npm_r": npm_r,
            "npm_g": npm_g,
            "npm_b": npm_b,
            "npr_mode": npr_mode,
            "npr_r": npr_r,
            "npr_g": npr_g,
            "npr_b": npr_b,
            "matrix_left": matrix_left,
            "matrix_right": matrix_right,
        }

    # --- Operator controls ---

    def force_collapse(self) -> None:
        """Force transition to COLLAPSE state (from any state except FAULT)."""
        if self._state != State.FAULT:
            self._transition_to(State.COLLAPSE)

    def force_inactive(self) -> None:
        """Force transition to INACTIVE state."""
        self._transition_to(State.INACTIVE)

    def skip_animation(self) -> None:
        """Skip current animation (COLLAPSE only)."""
        self._skip_requested = True

    def emergency_stop(self) -> None:
        """Emergency stop - disable dispensing."""
        self.dispensing_enabled = False

    def enable_dispensing(self) -> None:
        """Re-enable dispensing after emergency stop."""
        self.dispensing_enabled = True
        if self._state == State.FAULT:
            self._transition_to(State.INACTIVE)

    def set_forced_outcome(self, outcome: Optional[str]) -> None:
        """Set forced outcome for next collapse (ALIVE, DEAD, or None for random)."""
        if outcome in ("ALIVE", "DEAD", None):
            self.forced_outcome = outcome

    def open_valve(self) -> None:
        """Manually open the valve (dashboard override). Auto-closes after pour duration."""
        self._manual_valve_open = True
        self._manual_valve_open_time = time.time()

    def close_valve(self) -> None:
        """Manually close the valve (clears override)."""
        self._manual_valve_open = False

    def is_valve_manually_open(self) -> bool:
        """Check if valve is manually held open."""
        return self._manual_valve_open
