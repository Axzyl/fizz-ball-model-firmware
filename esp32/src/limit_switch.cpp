#include "limit_switch.h"
#include "config.h"

// Debounce state
static bool last_state = false;
static bool stable_state = false;
static uint32_t last_change_time = 0;

void limit_switch_init() {
    // Configure pin with internal pullup
    // Switch is active LOW (connects to GND when triggered)
    pinMode(LIMIT_SWITCH_PIN, INPUT_PULLUP);

    // Initialize state
    last_state = digitalRead(LIMIT_SWITCH_PIN) == LOW;
    stable_state = last_state;
    last_change_time = millis();

    DEBUG_PRINTLN("Limit switch initialized");
}

void limit_switch_read(bool* active, uint8_t* direction) {
    // Read current state (active LOW)
    bool current_state = digitalRead(LIMIT_SWITCH_PIN) == LOW;

    // Debounce logic
    if (current_state != last_state) {
        last_change_time = millis();
        last_state = current_state;
    }

    // Update stable state after debounce period
    if ((millis() - last_change_time) >= LIMIT_DEBOUNCE_MS) {
        if (stable_state != last_state) {
            stable_state = last_state;
            DEBUG_PRINTF("Limit switch changed to %s\n", stable_state ? "TRIGGERED" : "CLEAR");
        }
    }

    *active = stable_state;

    // Determine direction based on current servo position
    // TODO: This is a simplified implementation. In a real system,
    // you might have separate CW and CCW limit switches, or
    // determine direction based on servo movement direction.
    //
    // Current implementation assumes:
    // - Single limit switch
    // - Direction determined by which end of travel we're at
    // - Default to CW limit (can be adjusted based on mechanical design)

    if (stable_state) {
        // For now, assume CW limit if servo angle > 90, CCW if < 90
        // This should be refined based on actual mechanical setup
        *direction = LIMIT_CW;  // Default assumption
    } else {
        *direction = LIMIT_NONE;
    }
}

bool limit_switch_is_triggered() {
    return stable_state;
}
