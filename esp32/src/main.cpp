#include <Arduino.h>
#include "config.h"
#include "state.h"
#include "uart_handler.h"
#include "servo_controller.h"
#include "light_controller.h"
#include "limit_switch.h"

// Global state
DeviceState g_state;

// Timing
uint32_t g_last_loop_time = 0;
uint32_t g_last_status_time = 0;

/**
 * Arduino setup function.
 */
void setup() {
    // Initialize USB serial for debugging
    #if DEBUG_ENABLED
    Serial.begin(115200);
    while (!Serial) {
        delay(10);
    }
    DEBUG_PRINTLN("Face Tracker ESP32 Starting...");
    #endif

    // Initialize state
    state_init(&g_state);

    // Initialize components
    uart_init();
    servo_init();
    light_init();
    limit_switch_init();

    DEBUG_PRINTLN("Initialization complete");
}

/**
 * Arduino main loop.
 */
void loop() {
    uint32_t now = millis();

    // Rate limit main loop
    if (now - g_last_loop_time < LOOP_PERIOD_MS) {
        return;
    }
    g_last_loop_time = now;

    // ---------------------------------------------------------------------
    // Read inputs
    // ---------------------------------------------------------------------

    // Read limit switch
    bool limit_active;
    uint8_t limit_dir;
    limit_switch_read(&limit_active, &limit_dir);
    state_update_limit(&g_state, limit_active, limit_dir);

    // ---------------------------------------------------------------------
    // Process UART
    // ---------------------------------------------------------------------

    // Receive and parse commands
    uart_receive(&g_state);

    // Check connection status
    state_check_connection(&g_state, CONNECTION_TIMEOUT_MS);

    // ---------------------------------------------------------------------
    // Update outputs
    // ---------------------------------------------------------------------

    // Update servo position
    update_servo(&g_state);

    // Update lights
    update_lights(&g_state);

    // ---------------------------------------------------------------------
    // Transmit status
    // ---------------------------------------------------------------------

    // Send status packet at configured rate
    if (now - g_last_status_time >= STATUS_TX_PERIOD_MS) {
        uart_send_status(&g_state);
        g_last_status_time = now;
    }
}

/**
 * Update servo based on current state.
 */
void update_servo(DeviceState* state) {
    float target = state->command.target_servo_angle;
    float current = state->output.servo_angle;

    // Check limit switch constraints
    if (state->input.limit_triggered) {
        if (state->input.limit_direction == LIMIT_CW) {
            // CW limit hit - don't allow movement toward higher angles
            if (target > current) {
                target = current;
                DEBUG_PRINTLN("CW limit - blocking movement");
            }
        } else if (state->input.limit_direction == LIMIT_CCW) {
            // CCW limit hit - don't allow movement toward lower angles
            if (target < current) {
                target = current;
                DEBUG_PRINTLN("CCW limit - blocking movement");
            }
        }
    }

    // Move servo toward target
    float new_angle = servo_move_toward(current, target, SERVO_SPEED);
    bool moving = (abs(new_angle - target) > 0.1f);

    state_update_servo(state, new_angle, moving);
}

/**
 * Update lights based on current state and command.
 */
void update_lights(DeviceState* state) {
    bool should_be_on = false;

    switch (state->command.light_command) {
        case LIGHT_CMD_OFF:
            should_be_on = false;
            break;

        case LIGHT_CMD_ON:
            should_be_on = true;
            break;

        case LIGHT_CMD_AUTO:
            // In AUTO mode, lights follow connection status
            // (Pi will send ON command when face is facing)
            // For now, keep current state or default to off
            should_be_on = state->output.light_on;
            break;

        default:
            should_be_on = false;
            break;
    }

    light_set(should_be_on);
    state_update_light(state, should_be_on);
}
