#include "state.h"

void state_init(DeviceState* state) {
    // Initialize input state
    state->input.limit_triggered = false;
    state->input.limit_direction = LIMIT_NONE;
    state->input.limit_trigger_time = 0;

    // Initialize output state
    state->output.servo_angle = SERVO_CENTER_ANGLE;
    state->output.light_on = false;
    state->output.servo_moving = false;

    // Initialize command state
    state->command.target_servo_angle = SERVO_CENTER_ANGLE;
    state->command.light_command = LIGHT_CMD_AUTO;
    state->command.flags = 0;
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

void state_update_command(DeviceState* state, float servo_target, uint8_t light_cmd, uint8_t flags) {
    state->command.target_servo_angle = constrain(servo_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    state->command.light_command = light_cmd;
    state->command.flags = flags;
    state->command.last_command_time = millis();
    state->command.connected = true;
}

void state_update_servo(DeviceState* state, float angle, bool moving) {
    state->output.servo_angle = angle;
    state->output.servo_moving = moving;
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
