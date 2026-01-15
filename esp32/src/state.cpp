#include "state.h"

void state_init(DeviceState* state) {
    // Initialize input state
    state->input.limit_triggered = false;
    state->input.limit_direction = LIMIT_NONE;
    state->input.limit_trigger_time = 0;

    // Initialize output state
    for (int i = 0; i < NUM_SERVOS; i++) {
        state->output.servo_angles[i] = SERVO_CENTER_ANGLE;
        state->output.servo_moving[i] = false;
    }
    // Valve servo starts at closed position
    state->output.servo_angles[VALVE_SERVO_INDEX] = VALVE_CLOSED_ANGLE;
    state->output.light_on = false;

    // Initialize command state
    for (int i = 0; i < NUM_SERVOS; i++) {
        state->command.target_servo_angles[i] = SERVO_CENTER_ANGLE;
    }
    // Valve servo target starts at closed position
    state->command.target_servo_angles[VALVE_SERVO_INDEX] = VALVE_CLOSED_ANGLE;
    state->command.light_command = LIGHT_CMD_AUTO;
    state->command.flags = 0;

    // RGB strip
    state->command.rgb_mode = 0;
    state->command.rgb_r = 0;
    state->command.rgb_g = 0;
    state->command.rgb_b = 0;
    state->command.rgb_r2 = 0;
    state->command.rgb_g2 = 0;
    state->command.rgb_b2 = 0;
    state->command.rgb_gradient_speed = 10;

    // MAX7219 matrix - will scroll text (handled separately)
    state->command.matrix_left = 0;   // Not used for scroll mode
    state->command.matrix_right = 0;

    // NeoPixel 5x5 matrix - OFF by default
    state->command.npm_mode = 0;      // NPM_MODE_OFF
    state->command.npm_letter = 'A';
    state->command.npm_r = 0;
    state->command.npm_g = 0;
    state->command.npm_b = 0;
    state->command.npm_r2 = 0;
    state->command.npm_g2 = 0;
    state->command.npm_b2 = 0;
    state->command.npm_gradient_speed = 10;

    // NeoPixel ring - OFF by default
    state->command.npr_mode = 0;
    state->command.npr_r = 0;
    state->command.npr_g = 0;
    state->command.npr_b = 0;
    state->command.npr_r2 = 0;
    state->command.npr_g2 = 0;
    state->command.npr_b2 = 0;
    state->command.npr_gradient_speed = 10;

    // Valve control
    state->command.valve_open = false;
    state->command.valve_enabled = true;

    state->command.last_command_time = 0;
    state->command.connected = false;
}

void state_update_limit(DeviceState* state, bool limit_active, uint8_t direction) {
    if (limit_active && !state->input.limit_triggered) {
        // Limit just triggered
        state->input.limit_trigger_time = millis();
    }

    state->input.limit_triggered = limit_active;
    state->input.limit_direction = limit_active ? direction : LIMIT_NONE;
}

void state_update_command(DeviceState* state, float servo1_target, float servo2_target,
                          float servo3_target, uint8_t light_cmd, uint8_t flags) {
    state->command.target_servo_angles[0] = constrain(servo1_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.target_servo_angles[1] = constrain(servo2_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.target_servo_angles[2] = constrain(servo3_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.light_command = light_cmd;
    state->command.flags = flags;
    // Keep existing RGB/matrix values for backwards compatibility
    state->command.last_command_time = millis();
    state->command.connected = true;
}

void state_update_command_extended(DeviceState* state,
                                   float servo1_target, float servo2_target, float servo3_target,
                                   uint8_t light_cmd, uint8_t flags,
                                   uint8_t rgb_r, uint8_t rgb_g, uint8_t rgb_b,
                                   uint8_t matrix_left, uint8_t matrix_right) {
    state->command.target_servo_angles[0] = constrain(servo1_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.target_servo_angles[1] = constrain(servo2_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.target_servo_angles[2] = constrain(servo3_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.light_command = light_cmd;
    state->command.flags = flags;
    state->command.rgb_r = rgb_r;
    state->command.rgb_g = rgb_g;
    state->command.rgb_b = rgb_b;
    state->command.matrix_left = matrix_left;
    state->command.matrix_right = matrix_right;
    state->command.last_command_time = millis();
    state->command.connected = true;
}

void state_update_servo(DeviceState* state, uint8_t servo_index, float angle, bool moving) {
    if (servo_index < NUM_SERVOS) {
        state->output.servo_angles[servo_index] = angle;
        state->output.servo_moving[servo_index] = moving;
    }
}

void state_update_light(DeviceState* state, bool on) {
    state->output.light_on = on;
}

void state_check_connection(DeviceState* state, uint32_t timeout_ms) {
    if (state->command.connected) {
        uint32_t elapsed = millis() - state->command.last_command_time;
        if (elapsed > timeout_ms) {
            state->command.connected = false;
            DEBUG_PRINTLN("Connection lost");
        }
    }
}
