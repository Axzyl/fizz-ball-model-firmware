#include "valve_safety.h"

void valve_safety_init(ValveState* state) {
    state->commanded_open = false;
    state->actual_open = false;
    state->enabled = true;  // Start enabled
    state->open_start_time = 0;
    state->total_open_ms = 0;
    state->last_close_time = 0;
    state->safety_triggered = false;
}

void valve_safety_set_command(ValveState* state, bool open) {
    state->commanded_open = open;
}

void valve_safety_set_enabled(ValveState* state, bool enabled) {
    state->enabled = enabled;

    // If disabling (emergency stop), force valve closed
    if (!enabled && state->actual_open) {
        state->actual_open = false;
        state->last_close_time = millis();
        DEBUG_PRINTLN("Emergency stop - valve forced closed");
    }
}

bool valve_safety_update(ValveState* state, bool connected) {
    uint32_t now = millis();

    // Safety check 1: Emergency stop active
    if (!state->enabled) {
        if (state->actual_open) {
            state->actual_open = false;
            state->last_close_time = now;
        }
        return false;
    }

    // Safety check 2: Connection lost - close valve
    if (!connected) {
        if (state->actual_open) {
            state->actual_open = false;
            state->last_close_time = now;
            DEBUG_PRINTLN("Connection lost - valve closed");
        }
        return false;
    }

    // Safety check 3: Maximum open time
    if (state->actual_open) {
        uint32_t open_duration = now - state->open_start_time;
        if (open_duration >= VALVE_MAX_OPEN_MS) {
            state->actual_open = false;
            state->last_close_time = now;
            state->safety_triggered = true;
            DEBUG_PRINTLN("Valve timeout - forced closed");
            return false;
        }
        state->total_open_ms = open_duration;
    }

    // Handle commanded state changes
    if (state->commanded_open && !state->actual_open) {
        // Want to open
        // Check cooldown period
        if (state->last_close_time > 0) {
            uint32_t since_close = now - state->last_close_time;
            if (since_close < VALVE_COOLDOWN_MS) {
                // Still in cooldown, don't open yet
                return false;
            }
        }

        // Open the valve
        state->actual_open = true;
        state->open_start_time = now;
        state->total_open_ms = 0;
        state->safety_triggered = false;
        DEBUG_PRINTLN("Valve opened");
    }
    else if (!state->commanded_open && state->actual_open) {
        // Want to close
        state->actual_open = false;
        state->last_close_time = now;
        DEBUG_PRINTLN("Valve closed");
    }

    return state->actual_open;
}

uint32_t valve_safety_get_open_ms(const ValveState* state) {
    if (state->actual_open) {
        return millis() - state->open_start_time;
    }
    return 0;
}

bool valve_safety_is_enabled(const ValveState* state) {
    return state->enabled;
}

bool valve_safety_is_triggered(const ValveState* state) {
    return state->safety_triggered;
}

void valve_safety_reset_trigger(ValveState* state) {
    state->safety_triggered = false;
}
