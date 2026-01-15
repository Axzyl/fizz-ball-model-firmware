"""State machine for Schrödinger's Cat Alcohol Dispenser.

States:
- IDLE: Waiting for a person to approach
- TRACKING: Following a detected face, arm waving
- COLLAPSE: Quantum collapse animation (deciding outcome)
- ALIVE: Cat is alive - dispense drink
- DEAD: Cat is dead - 5-step dramatic sequence with partial pour
- RESET: Returning to initial position
- FAULT: Error state
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import config
from state import FaceState, EspState


# =============================================================================
# NeoPixel Matrix (5x5) Modes - npm_mode values
# =============================================================================
NPM_OFF = 0           # Off
NPM_LETTER = 1        # Display a letter
NPM_SCROLL = 2        # Scrolling text
NPM_RAINBOW = 3       # Rainbow animation
NPM_SOLID = 4         # Solid color fill
NPM_EYE_CLOSED = 5    # Closed eye icon (for IDLE)
NPM_EYE_OPEN = 6      # Open eye icon (for TRACKING)
NPM_CIRCLE = 7        # Circle icon (for ALIVE)
NPM_X = 8             # X icon (for DEAD)

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
    """State machine states."""
    IDLE = auto()
    TRACKING = auto()
    COLLAPSE = auto()
    ALIVE = auto()
    DEAD = auto()
    RESET = auto()
    FAULT = auto()


class DeadSubState(Enum):
    """Sub-states for the DEAD state 5-step procedure."""
    TENSION = 0       # Hold, solid red LEDs (~3s)
    PARTIAL_POUR = 1  # Valve open for 35% of pour time
    CHAOS = 2         # Violent shaking, red flicker (~2s)
    DARKNESS = 3      # All LEDs off, brief pause (~1s)
    FINAL_POUR = 4    # Valve open for remaining 65%


@dataclass
class StateMachineConfig:
    """Configuration parameters for the state machine."""

    # Tracking parameters - defaults from config.py
    tracking_velocity_gain: float = None  # How fast base rotates (from config.TRACKING_VELOCITY_GAIN)
    tracking_deadzone: float = None  # Deadzone as fraction of frame (from config.TRACKING_DEADZONE)
    tracking_max_velocity: float = None  # Max rotation speed degrees/tick (from config.TRACKING_MAX_VELOCITY)
    tracking_invert_direction: bool = False  # Invert tracking direction
    tracking_base_min: float = 0.0  # Minimum base servo angle
    tracking_base_max: float = 180.0  # Maximum base servo angle

    def __post_init__(self):
        """Load defaults from config.py if not specified."""
        if self.tracking_velocity_gain is None:
            self.tracking_velocity_gain = getattr(config, 'TRACKING_VELOCITY_GAIN', 0.15)
        if self.tracking_deadzone is None:
            self.tracking_deadzone = getattr(config, 'TRACKING_DEADZONE', 0.05)
        if self.tracking_max_velocity is None:
            self.tracking_max_velocity = getattr(config, 'TRACKING_MAX_VELOCITY', 5.0)

    # Idle behavior
    idle_arm_position: float = 90.0  # Arm position when idle
    idle_base_position: float = 90.0  # Base position when idle
    idle_return_speed: float = 2.0  # Speed of return to center

    # State durations
    collapse_duration: float = 3.0  # Duration of collapse animation
    alive_pour_duration: float = 3.0  # How long to pour (alive outcome)
    reset_duration: float = 2.0  # How long reset takes

    # DEAD state sub-step durations
    dead_tension_duration: float = 3.0  # Step 1: tension buildup
    dead_partial_pour_ratio: float = 0.35  # Step 2: 35% of total pour
    dead_chaos_duration: float = 2.0  # Step 3: violent shaking
    dead_darkness_duration: float = 1.0  # Step 4: all LEDs off
    dead_final_pour_ratio: float = 0.65  # Step 5: remaining 65%

    # Chaos shake parameters
    chaos_shake_speed: float = 15.0  # Degrees per tick
    chaos_shake_range: float = 30.0  # Max deviation from center

    # Tracking to collapse trigger
    tracking_min_time: float = 3.0  # Minimum time in tracking before collapse
    tracking_limit_hold_time: float = 1.0  # How long limit must be held

    # Arm wave parameters
    arm_wave_min: float = 60.0
    arm_wave_max: float = 120.0
    arm_wave_speed: float = 2.0  # Degrees per tick
    arm_wave_cooldown: float = 7.0  # 5-10s cooldown between waves

    # Collapse arm position
    collapse_arm_position: float = 45.0  # Forward-pointing pose

    # Target switching threshold
    target_switch_ratio: float = 1.5  # 150% size to switch target

    # Alive/dead probability
    alive_probability: float = 0.5  # 50% chance of alive

    # Alive state base return
    alive_base_return_speed: float = 1.0  # Slow return to 90


class StateMachine:
    """Main state machine for the dispenser."""

    def __init__(self, config: Optional[StateMachineConfig] = None):
        self.config = config or StateMachineConfig()

        # Current state
        self._state = State.IDLE
        self._state_start_time = time.time()
        self._prev_state = State.IDLE

        # Tracking state
        self.tracking_base_position: float = 90.0

        # Arm wave state
        self.arm_wave_position: float = 90.0
        self._arm_wave_direction: int = 1  # 1 = increasing, -1 = decreasing
        self._last_wave_time: float = 0.0
        self._wave_active: bool = False
        self._was_centered: bool = False
        self._last_face_count: int = 0

        # Face target tracking
        self._target_face_size: float = 0.0

        # Limit switch tracking
        self._limit_held_start: float = 0.0

        # DEAD sub-state tracking
        self._dead_sub_state: DeadSubState = DeadSubState.TENSION
        self._dead_sub_entry_time: float = 0.0
        self._shake_offset: float = 0.0
        self._shake_direction: int = 1

        # Collapse position snapshot
        self._collapse_base_position: float = 90.0

        # Outcome
        self._outcome: Optional[str] = None  # "ALIVE" or "DEAD"
        self.forced_outcome: Optional[str] = None  # Operator override

        # Safety
        self.dispensing_enabled: bool = True
        self._fault_reason: str = ""

        # Skip flags
        self._skip_requested: bool = False

    def get_state_name(self) -> str:
        """Get current state name."""
        return self._state.name

    def get_dead_sub_state_name(self) -> str:
        """Get current DEAD sub-state name (if in DEAD state)."""
        if self._state == State.DEAD:
            return self._dead_sub_state.name
        return ""

    def get_time_in_state(self) -> float:
        """Get time spent in current state."""
        return time.time() - self._state_start_time

    def get_time_in_sub_state(self) -> float:
        """Get time spent in current DEAD sub-state."""
        return time.time() - self._dead_sub_entry_time

    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state."""
        self._prev_state = self._state
        self._state = new_state
        self._state_start_time = time.time()
        self._skip_requested = False

        # State entry actions
        if new_state == State.IDLE:
            pass
        elif new_state == State.TRACKING:
            self._limit_held_start = 0.0
            # Trigger wave on state entry
            self._start_wave()
        elif new_state == State.COLLAPSE:
            # Snapshot current base position
            self._collapse_base_position = self.tracking_base_position
            # Determine outcome
            if self.forced_outcome:
                self._outcome = self.forced_outcome
                self.forced_outcome = None  # Reset after use
            else:
                self._outcome = "ALIVE" if random.random() < self.config.alive_probability else "DEAD"
        elif new_state == State.ALIVE:
            pass
        elif new_state == State.DEAD:
            # Initialize DEAD sub-state sequence
            self._dead_sub_state = DeadSubState.TENSION
            self._dead_sub_entry_time = time.time()
            self._shake_offset = 0.0
            self._shake_direction = 1
        elif new_state == State.RESET:
            self._outcome = None

    def _advance_dead_substate(self) -> None:
        """Advance to the next DEAD sub-state."""
        current_idx = self._dead_sub_state.value
        if current_idx < 4:
            self._dead_sub_state = DeadSubState(current_idx + 1)
            self._dead_sub_entry_time = time.time()
            self._shake_offset = 0.0

    def _start_wave(self) -> None:
        """Start arm wave if cooldown elapsed."""
        now = time.time()
        if now - self._last_wave_time >= self.config.arm_wave_cooldown:
            self._wave_active = True
            self._last_wave_time = now
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

        return self.arm_wave_position

    def _update_shake(self) -> float:
        """Update shake animation for CHAOS sub-state. Returns offset."""
        self._shake_offset += self._shake_direction * self.config.chaos_shake_speed

        if abs(self._shake_offset) >= self.config.chaos_shake_range:
            self._shake_direction = -self._shake_direction

        return self._shake_offset

    def _get_flicker_state(self) -> bool:
        """Get flicker on/off state for red flicker effect."""
        # Fast random flicker
        return random.random() > 0.3

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

        # Run state-specific logic
        if self._state == State.IDLE:
            return self._tick_idle(face, esp)
        elif self._state == State.TRACKING:
            return self._tick_tracking(face, esp)
        elif self._state == State.COLLAPSE:
            return self._tick_collapse(face, esp)
        elif self._state == State.ALIVE:
            return self._tick_alive(face, esp)
        elif self._state == State.DEAD:
            return self._tick_dead(face, esp)
        elif self._state == State.RESET:
            return self._tick_reset(face, esp)
        elif self._state == State.FAULT:
            return self._tick_fault(face, esp)

        return self._make_commands()

    def _tick_idle(self, face: FaceState, esp: EspState) -> dict:
        """IDLE state: waiting for someone to approach.

        Spec:
        - Base servo: Move to 90°
        - Arm servo: Move to 90°
        - Valve: Force closed
        - LED ring: Off or very dim
        - 5×5 matrix: Closed eye icon
        - RGB strip: Off or very dim
        """

        # Check for face detection to start tracking
        if face.detected and face.is_facing:
            self._transition_to(State.TRACKING)
            return self._tick_tracking(face, esp)

        # Move base toward 90°
        diff = self.config.idle_base_position - self.tracking_base_position
        if abs(diff) > 0.5:
            move = min(self.config.idle_return_speed, abs(diff))
            self.tracking_base_position += move if diff > 0 else -move

        # Spec: LED Ring off, 5x5 Matrix closed eye, RGB Strip off
        return self._make_commands(
            servo_target_2=self.config.idle_arm_position,  # Arm at 90°
            servo_target_1=self.tracking_base_position,    # Moving toward 90°
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=0, rgb_b=0,  # Off
            npm_mode=NPM_EYE_CLOSED,  # Closed eye icon
            npm_r=100, npm_g=100, npm_b=100,  # Dim white for eye
            npr_mode=NPR_OFF,  # Off
            npr_r=0, npr_g=0, npr_b=0,
            matrix_left=1,  # Circle
            matrix_right=1,  # Circle
        )

    def _tick_tracking(self, face: FaceState, esp: EspState) -> dict:
        """TRACKING state: following a face, arm waving.

        Spec:
        - Base servo: Rotate to center tracked target
        - Arm servo: Wave on entry, when centered, new person; 5-10s cooldown
        - Valve: Closed
        - LED ring: Bright blue/purple
        - 5×5 matrix: Open eye icon
        - RGB strip: Bright blue/purple
        """

        # Check if face lost
        if not face.detected:
            self._transition_to(State.IDLE)
            return self._tick_idle(face, esp)

        # Check if face is centered in frame (for wave trigger)
        # Use bbox position, not yaw
        is_centered = False
        frame_width = getattr(config, 'CAMERA_WIDTH', 640)
        if face.bbox is not None:
            x, y, w, h = face.bbox
            face_center_x = (x + w / 2) / frame_width  # Normalize to 0-1
            is_centered = abs(face_center_x - 0.5) < 0.1  # Within 10% of center

        # Trigger wave when becoming centered
        if is_centered and not self._was_centered:
            self._start_wave()
        self._was_centered = is_centered

        # Update base position based on face POSITION in frame (not yaw)
        # This matches how vision_servo_test.py works
        velocity = self._calculate_tracking_velocity_from_position(face)
        self.tracking_base_position += velocity
        self.tracking_base_position = max(
            self.config.tracking_base_min,
            min(self.config.tracking_base_max, self.tracking_base_position)
        )

        # Update arm wave animation
        arm_position = self._update_wave()
        if not self._wave_active:
            arm_position = 90.0  # Idle position when not waving

        # Check limit switch for collapse trigger
        if esp.limit_triggered:
            if self._limit_held_start == 0:
                self._limit_held_start = time.time()
            elif (time.time() - self._limit_held_start) >= self.config.tracking_limit_hold_time:
                if self.get_time_in_state() >= self.config.tracking_min_time:
                    self._transition_to(State.COLLAPSE)
                    return self._tick_collapse(face, esp)
        else:
            self._limit_held_start = 0

        # Spec: LED Ring bright blue/purple, 5x5 Matrix open eye, RGB Strip blue/purple
        return self._make_commands(
            servo_target_2=arm_position,
            servo_target_1=self.tracking_base_position,
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=80, rgb_g=0, rgb_b=255,  # Blue/purple
            npm_mode=NPM_EYE_OPEN,  # Open eye icon
            npm_r=80, npm_g=0, npm_b=255,  # Blue/purple
            npr_mode=NPR_CHASE,  # Chase animation (active observation)
            npr_r=80, npr_g=0, npr_b=255,  # Blue/purple
            matrix_left=1,  # Circle
            matrix_right=1,  # Circle
        )

    def _tick_collapse(self, face: FaceState, esp: EspState) -> dict:
        """COLLAPSE state: quantum collapse animation.

        Spec:
        - Base servo: Hold current position
        - Arm servo: Move to 45° (forward-pointing)
        - Valve: Closed
        - LED ring: Fast, bright rainbow
        - 5×5 matrix: Neutral/glitch pattern
        - RGB strip: Fast, bright rainbow
        """

        # Check for timeout or skip
        if self.get_time_in_state() >= self.config.collapse_duration or self._skip_requested:
            if self._outcome == "ALIVE":
                self._transition_to(State.ALIVE)
                return self._tick_alive(face, esp)
            else:
                self._transition_to(State.DEAD)
                return self._tick_dead(face, esp)

        # Spec: LED Ring rainbow, 5x5 Matrix neutral/glitch, RGB Strip rainbow
        return self._make_commands(
            servo_target_2=self.config.collapse_arm_position,  # 45° forward
            servo_target_1=self._collapse_base_position,  # Hold position
            valve_open=False,
            rgb_mode=RGB_RAINBOW,  # Rainbow cycle
            npm_mode=NPM_RAINBOW,  # Rainbow (neutral/glitch pattern)
            npr_mode=NPR_RAINBOW,  # Rainbow cycle
            matrix_left=1,  # Circle
            matrix_right=2,  # X (alternating for suspense)
        )

    def _tick_alive(self, face: FaceState, esp: EspState) -> dict:
        """ALIVE state: cat is alive, dispense drink.

        Spec:
        - Base servo: Slowly rotate back to 90°
        - Arm servo: Friendly motion or idle
        - Valve: Open for 100% pour duration
        - LED ring: Solid green or gentle pulse
        - 5×5 matrix: Green circle icon
        - RGB strip: Solid green
        """

        # Check for timeout or skip
        if self.get_time_in_state() >= self.config.alive_pour_duration or self._skip_requested:
            self._transition_to(State.RESET)
            return self._tick_reset(face, esp)

        # Slowly return base to 90°
        diff = 90.0 - self.tracking_base_position
        if abs(diff) > 0.5:
            move = min(self.config.alive_base_return_speed, abs(diff))
            self.tracking_base_position += move if diff > 0 else -move

        # Dispense if enabled
        should_dispense = self.dispensing_enabled

        # Spec: LED Ring solid green/pulse, 5x5 Matrix green circle, RGB Strip solid green
        return self._make_commands(
            servo_target_2=100.0,  # Arm slightly up (friendly)
            servo_target_1=self.tracking_base_position,  # Slowly returning to 90
            valve_open=should_dispense,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=255, rgb_b=0,  # Solid green
            npm_mode=NPM_CIRCLE,  # Green circle icon
            npm_r=0, npm_g=255, npm_b=0,  # Green
            npr_mode=NPR_BREATHE,  # Gentle pulse
            npr_r=0, npr_g=255, npr_b=0,  # Green
            matrix_left=1,  # Circle
            matrix_right=1,  # Circle
        )

    def _tick_dead(self, face: FaceState, esp: EspState) -> dict:
        """DEAD state: 5-step dramatic sequence.

        Spec:
        Step 1 - Tension (~3s): Hold, solid red LEDs
        Step 2 - Partial Pour: Valve open for 35% of pour time
        Step 3 - Chaos (~2s): Violent shaking, red flicker
        Step 4 - Darkness (~1s): All LEDs off
        Step 5 - Final Pour: Valve open for remaining 65%
        """

        time_in_sub = self.get_time_in_sub_state()

        # Calculate pour times
        total_pour_time = self.config.alive_pour_duration
        partial_pour_time = total_pour_time * self.config.dead_partial_pour_ratio
        final_pour_time = total_pour_time * self.config.dead_final_pour_ratio

        # Process current sub-state
        # Spec: 5x5 Matrix shows "Red X icon (static)" throughout DEAD state
        if self._dead_sub_state == DeadSubState.TENSION:
            # Step 1: Tension - solid red LEDs, hold position (~3s)
            if time_in_sub >= self.config.dead_tension_duration:
                self._advance_dead_substate()

            return self._make_commands(
                servo_target_2=90.0,  # Hold
                servo_target_1=self._collapse_base_position,  # Hold
                valve_open=False,
                rgb_mode=RGB_SOLID,
                rgb_r=255, rgb_g=0, rgb_b=0,  # Solid red
                npm_mode=NPM_X,  # Red X icon
                npm_r=255, npm_g=0, npm_b=0,  # Red
                npr_mode=NPR_SOLID,  # Solid red
                npr_r=255, npr_g=0, npr_b=0,
                matrix_left=2,  # X
                matrix_right=2,  # X
            )

        elif self._dead_sub_state == DeadSubState.PARTIAL_POUR:
            # Step 2: Partial pour - valve open 35%, lights remain red
            if time_in_sub >= partial_pour_time:
                self._advance_dead_substate()

            should_dispense = self.dispensing_enabled

            return self._make_commands(
                servo_target_2=90.0,
                servo_target_1=self._collapse_base_position,
                valve_open=should_dispense,
                rgb_mode=RGB_SOLID,
                rgb_r=255, rgb_g=0, rgb_b=0,  # Solid red
                npm_mode=NPM_X,  # Red X icon
                npm_r=255, npm_g=0, npm_b=0,
                npr_mode=NPR_SOLID,
                npr_r=255, npr_g=0, npr_b=0,
                matrix_left=2,
                matrix_right=2,
            )

        elif self._dead_sub_state == DeadSubState.CHAOS:
            # Step 3: Chaos - violent shaking, red flicker (~2s)
            if time_in_sub >= self.config.dead_chaos_duration:
                self._advance_dead_substate()

            shake = self._update_shake()
            flicker_on = self._get_flicker_state()
            flicker_brightness = 255 if flicker_on else 30

            return self._make_commands(
                servo_target_2=90.0 + shake,  # Shake arm
                servo_target_1=self._collapse_base_position + shake * 0.5,  # Shake base
                valve_open=False,
                rgb_mode=RGB_SOLID,
                rgb_r=flicker_brightness, rgb_g=0, rgb_b=0,  # Red flicker
                npm_mode=NPM_X,  # Red X icon (flickering)
                npm_r=flicker_brightness, npm_g=0, npm_b=0,
                npr_mode=NPR_SOLID,
                npr_r=flicker_brightness, npr_g=0, npr_b=0,
                matrix_left=2,
                matrix_right=2,
            )

        elif self._dead_sub_state == DeadSubState.DARKNESS:
            # Step 4: Darkness - all LEDs off, brief pause (~1s)
            if time_in_sub >= self.config.dead_darkness_duration:
                self._advance_dead_substate()

            return self._make_commands(
                servo_target_2=90.0,
                servo_target_1=self._collapse_base_position,
                valve_open=False,
                rgb_mode=RGB_SOLID,
                rgb_r=0, rgb_g=0, rgb_b=0,  # Off
                npm_mode=NPM_OFF,  # Off
                npr_mode=NPR_OFF,  # Off
                matrix_left=0,  # Off
                matrix_right=0,  # Off
            )

        elif self._dead_sub_state == DeadSubState.FINAL_POUR:
            # Step 5: Final pour - valve open 65%, LEDs off or minimal
            if time_in_sub >= final_pour_time or self._skip_requested:
                self._transition_to(State.RESET)
                return self._tick_reset(face, esp)

            should_dispense = self.dispensing_enabled

            return self._make_commands(
                servo_target_2=90.0,
                servo_target_1=self._collapse_base_position,
                valve_open=should_dispense,
                rgb_mode=RGB_SOLID,
                rgb_r=0, rgb_g=0, rgb_b=0,  # Off (spec: off or minimal)
                npm_mode=NPM_X,  # Keep X visible but dim
                npm_r=30, npm_g=0, npm_b=0,  # Very dim red
                npr_mode=NPR_OFF,  # Off
                matrix_left=2,
                matrix_right=2,
            )

        # Fallback
        return self._make_commands()

    def _tick_reset(self, face: FaceState, esp: EspState) -> dict:
        """RESET state: returning to initial position.

        Spec:
        - Base servo: Move to 90°
        - Arm servo: Move to 90°
        - Valve: Force closed
        - LED ring: Off
        - 5×5 matrix: Off
        - RGB strip: Off
        """

        # Check for timeout
        if self.get_time_in_state() >= self.config.reset_duration:
            self._transition_to(State.IDLE)
            return self._tick_idle(face, esp)

        # Move back to center
        diff = 90.0 - self.tracking_base_position
        if abs(diff) > 1.0:
            move = min(2.0, abs(diff))
            self.tracking_base_position += move if diff > 0 else -move

        # Spec: All LEDs off
        return self._make_commands(
            servo_target_2=90.0,
            servo_target_1=self.tracking_base_position,
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=0, rgb_g=0, rgb_b=0,  # Off
            npm_mode=NPM_OFF,  # Off
            npr_mode=NPR_OFF,  # Off
            matrix_left=0,  # Off
            matrix_right=0,  # Off
        )

    def _tick_fault(self, face: FaceState, esp: EspState) -> dict:
        """FAULT state: error occurred."""

        # Check if connection restored
        if esp.connected and self.dispensing_enabled:
            self._transition_to(State.RESET)
            return self._tick_reset(face, esp)

        # Flash red to indicate fault
        flash = int(time.time() * 2) % 2 == 0
        flash_brightness = 255 if flash else 0

        return self._make_commands(
            servo_target_2=90.0,
            servo_target_1=90.0,
            valve_open=False,
            rgb_mode=RGB_SOLID,
            rgb_r=flash_brightness, rgb_g=0, rgb_b=0,
            npm_mode=NPM_X,  # X icon flashing
            npm_r=flash_brightness, npm_g=0, npm_b=0,
            npr_mode=NPR_SOLID,
            npr_r=flash_brightness, npr_g=0, npr_b=0,
            matrix_left=2,  # X
            matrix_right=2,  # X
        )

    def _calculate_tracking_velocity_from_position(self, face: FaceState) -> float:
        """
        Calculate base rotation velocity from face position in frame.

        This uses the face's POSITION in the frame (bbox), not the head's yaw angle.
        This matches how vision_servo_test.py works EXACTLY.

        Args:
            face: Face state with bbox

        Returns:
            Velocity to apply to servo (degrees per tick)
        """
        if not face.detected or face.bbox is None:
            return 0.0

        x, y, w, h = face.bbox

        # Use ACTUAL frame dimensions from face state (same as vision_servo_test.py)
        frame_width = face.frame_width if face.frame_width > 0 else 640

        # Calculate face center as fraction of frame (0.0 = left, 1.0 = right)
        # Same calculation as vision_servo_test.py
        face_center_x = (x + w / 2) / frame_width

        # Calculate error from center (positive = face is right of center)
        error = face_center_x - 0.5

        # Apply deadzone (as fraction of frame, e.g., 0.05 = 5%)
        if abs(error) < self.config.tracking_deadzone:
            return 0.0

        # Calculate velocity - same formula as vision_servo_test.py
        velocity = -error * 180.0 * self.config.tracking_velocity_gain

        # Clamp velocity to prevent overshoot
        velocity = max(-self.config.tracking_max_velocity,
                      min(self.config.tracking_max_velocity, velocity))

        if self.config.tracking_invert_direction:
            velocity = -velocity

        return velocity

    def _calculate_tracking_velocity(self, yaw: float) -> float:
        """Calculate base rotation velocity from face yaw (DEPRECATED - use position-based)."""
        if abs(yaw) < self.config.tracking_deadzone:
            return 0.0

        sign = 1.0 if yaw > 0 else -1.0
        effective_yaw = abs(yaw) - self.config.tracking_deadzone
        velocity = effective_yaw * self.config.tracking_velocity_gain * sign
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
        rgb_mode: int = 0,
        rgb_r: int = 0,
        rgb_g: int = 0,
        rgb_b: int = 0,
        npm_mode: int = 0,
        npm_letter: str = "A",
        npm_r: int = 255,
        npm_g: int = 255,
        npm_b: int = 255,
        npr_mode: int = 0,
        npr_r: int = 255,
        npr_g: int = 255,
        npr_b: int = 255,
        matrix_left: int = 1,
        matrix_right: int = 2,
    ) -> dict:
        """Create command dictionary."""
        return {
            "servo_target_1": servo_target_1,
            "servo_target_2": servo_target_2,
            "valve_open": valve_open,
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
        """Force transition to COLLAPSE state (only from TRACKING)."""
        if self._state == State.TRACKING:
            self._transition_to(State.COLLAPSE)

    def force_reset(self) -> None:
        """Force transition to RESET state."""
        self._transition_to(State.RESET)

    def skip_animation(self) -> None:
        """Skip current animation."""
        self._skip_requested = True

    def emergency_stop(self) -> None:
        """Emergency stop - disable dispensing."""
        self.dispensing_enabled = False
        # Force valve close is handled by setting valve_open=False

    def enable_dispensing(self) -> None:
        """Re-enable dispensing after emergency stop."""
        self.dispensing_enabled = True
        if self._state == State.FAULT:
            self._transition_to(State.RESET)

    def set_forced_outcome(self, outcome: Optional[str]) -> None:
        """Set forced outcome for next collapse (ALIVE, DEAD, or None for random)."""
        if outcome in ("ALIVE", "DEAD", None):
            self.forced_outcome = outcome
