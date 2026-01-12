#include <Arduino.h>
#include "config.h"
#include "state.h"
#include "uart_handler.h"
#include "servo_controller.h"
#include "rgb_strip.h"
#include "led_matrix.h"
#include "limit_switch.h"

// Global state
DeviceState g_state;

// Timing
uint32_t g_last_loop_time = 0;
uint32_t g_last_status_time = 0;
uint32_t g_last_command_time = 0;
bool g_has_received_command = false;

// Test LED state
uint32_t g_test_triggered_time = 0;
bool g_test_led_on = false;

// Forward declarations
void update_servos(DeviceState *state);
void update_rgb(DeviceState *state);
void update_matrix(DeviceState *state);
void check_test_command(DeviceState *state);
void update_test_led();

void setup()
{
    // Initialize USB serial for protocol communication
    Serial.begin(115200);
    delay(100); // Brief delay for serial init

    // Initialize test LED
    pinMode(TEST_LED_PIN, OUTPUT);
    digitalWrite(TEST_LED_PIN, LOW);

    // Initialize state
    state_init(&g_state);

    // Initialize components
    uart_init();
    servo_init();
    rgb_init();
    led_matrix_init();
    limit_switch_init();
}

void loop()
{
    uint32_t now = millis();

    // Update test LED (non-blocking)
    update_test_led();

    // Rate limit main loop
    if (now - g_last_loop_time < LOOP_PERIOD_MS)
    {
        delay(1);
        return;
    }
    g_last_loop_time = now;

    // Read limit switch
    bool limit_active;
    uint8_t limit_dir;
    limit_switch_read(&limit_active, &limit_dir);
    state_update_limit(&g_state, limit_active, limit_dir);

    // Receive and parse commands
    uart_receive(&g_state);

    // Check connection status
    state_check_connection(&g_state, CONNECTION_TIMEOUT_MS);

    // Check for test command
    check_test_command(&g_state);

    // Update all servo positions
    update_servos(&g_state);

    // Update RGB strip and LED matrix
    update_rgb(&g_state);
    update_matrix(&g_state);

    // Send status if connected (received command within 1 second)
    bool connected = g_has_received_command && (now - g_last_command_time) < 1000;
    if (connected && (now - g_last_status_time >= STATUS_TX_PERIOD_MS))
    {
        uart_send_status(&g_state);
        g_last_status_time = now;
    }
}

void on_command_received()
{
    g_last_command_time = millis();
    g_has_received_command = true;
}

bool is_test_active()
{
    if (g_test_triggered_time == 0)
    {
        return false;
    }
    return (millis() - g_test_triggered_time) < 1000;
}

void check_test_command(DeviceState *state)
{
    if ((state->command.flags & CMD_FLAG_LED_TEST) && !g_test_led_on)
    {
        // Turn on LED and record time
        g_test_led_on = true;
        g_test_triggered_time = millis();
        digitalWrite(TEST_LED_PIN, HIGH);

        // Clear flag
        state->command.flags &= ~CMD_FLAG_LED_TEST;
    }
}

void update_test_led()
{
    if (g_test_led_on)
    {
        if ((millis() - g_test_triggered_time) >= TEST_LED_DURATION_MS)
        {
            // Turn off LED after duration
            digitalWrite(TEST_LED_PIN, LOW);
            g_test_led_on = false;
        }
    }
}

void update_servos(DeviceState *state)
{
    // Update all servos
    // Note: Servo 0 is controlled by Pi based on limit switch state,
    // so we don't apply limit switch blocking here (Pi handles the logic)
    for (int i = 0; i < NUM_SERVOS; i++)
    {
        float target = state->command.target_servo_angles[i];
        float current = state->output.servo_angles[i];

        // DEBUG: Blink LED when servo 0 target > 100 (limit switch pressed)
        if (i == 0 && target > 100.0f)
        {
            digitalWrite(TEST_LED_PIN, HIGH);
        }
        else if (i == 0)
        {
            digitalWrite(TEST_LED_PIN, LOW);
        }

        // Move servo toward target
        float new_angle = servo_move_toward(i, current, target, SERVO_SPEED);
        bool moving = (abs(new_angle - target) > 0.1f);

        state_update_servo(state, i, new_angle, moving);
    }
}

void update_rgb(DeviceState *state)
{
    // Track previous RGB values to avoid unnecessary updates
    static uint8_t prev_r = 255, prev_g = 255, prev_b = 255;
    static uint8_t prev_light_cmd = 255;

    uint8_t r = state->command.rgb_r;
    uint8_t g = state->command.rgb_g;
    uint8_t b = state->command.rgb_b;
    bool should_be_on = false;

    // Determine if lights should be on based on light command
    switch (state->command.light_command)
    {
    case LIGHT_CMD_OFF:
        should_be_on = false;
        break;
    case LIGHT_CMD_ON:
        should_be_on = true;
        break;
    case LIGHT_CMD_AUTO:
        should_be_on = state->output.light_on;
        break;
    default:
        should_be_on = false;
        break;
    }

    // Apply RGB based on light command
    if (!should_be_on)
    {
        // Light is off - turn off RGB
        if (prev_light_cmd != LIGHT_CMD_OFF || prev_r != 0 || prev_g != 0 || prev_b != 0)
        {
            rgb_off();
            prev_r = 0;
            prev_g = 0;
            prev_b = 0;
        }
    }
    else
    {
        // Light is on - use RGB values (default to white if all zeros)
        if (r == 0 && g == 0 && b == 0)
        {
            r = 255;
            g = 255;
            b = 255;
        }

        // Only update if values changed
        if (r != prev_r || g != prev_g || b != prev_b)
        {
            rgb_set(r, g, b);
            prev_r = r;
            prev_g = g;
            prev_b = b;
        }
    }

    prev_light_cmd = state->command.light_command;
    state_update_light(state, should_be_on);
}

void update_matrix(DeviceState *state)
{
    // Track previous patterns to avoid unnecessary updates
    static uint8_t prev_left = 255;
    static uint8_t prev_right = 255;

    uint8_t left = state->command.matrix_left;
    uint8_t right = state->command.matrix_right;

    // Only update if patterns changed
    if (left != prev_left || right != prev_right)
    {
        led_matrix_set_patterns(left, right);
        prev_left = left;
        prev_right = right;
    }
}
