#include <Arduino.h>
#include "config.h"
#include "state.h"
#include "uart_handler.h"
#include "servo_controller.h"
#include "rgb_strip.h"
#include "led_matrix.h"
#include "limit_switch.h"
#include "valve_safety.h"
#include "neopixel_matrix.h"
#include "neopixel_ring.h"

// Global state
DeviceState g_state;
ValveState g_valve_state;
NpmState g_npm_state;
NprState g_npr_state;

// Timing
uint32_t g_last_loop_time = 0;
uint32_t g_last_status_time = 0;
uint32_t g_last_animation_time = 0;
uint32_t g_last_command_time = 0;
bool g_has_received_command = false;

// Test LED state
uint32_t g_test_triggered_time = 0;
bool g_test_led_on = false;

// Animation timing
#define ANIMATION_INTERVAL_MS 20  // 50Hz animation update

// Forward declarations
void update_servos(DeviceState* state);
void update_rgb(DeviceState* state);
void update_matrix(DeviceState* state);
void update_valve(DeviceState* state);
void update_neopixel_matrix(DeviceState* state);
void update_neopixel_ring(DeviceState* state);
void check_test_command(DeviceState* state);
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
    valve_safety_init(&g_valve_state);
    npm_state_init(&g_npm_state);
    npr_state_init(&g_npr_state);

    // Initialize components
    uart_init();
    servo_init();
    rgb_init();
    led_matrix_init();
    limit_switch_init();

    // Initialize NeoPixel devices
    npm_init(NPM_DATA_PIN);
    npr_init(NPR_DATA_PIN);
}

void loop()
{
    uint32_t now = millis();

    // Update test LED (non-blocking)
    update_test_led();

    // Update animations at regular interval (50Hz)
    if (now - g_last_animation_time >= ANIMATION_INTERVAL_MS)
    {
        g_last_animation_time = now;

        // Update NeoPixel animations
        npm_update(&g_npm_state);
        npr_update(&g_npr_state);
    }

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

    // Update valve
    update_valve(&g_state);

    // Update RGB strip
    update_rgb(&g_state);

    // Update MAX7219 LED matrix
    update_matrix(&g_state);

    // Update NeoPixel matrix and ring modes (animations updated above)
    update_neopixel_matrix(&g_state);
    update_neopixel_ring(&g_state);

    // Send status if connected (received command within 1 second)
    bool connected = g_has_received_command && (now - g_last_command_time) < 1000;
    if (connected && (now - g_last_status_time >= STATUS_TX_PERIOD_MS))
    {
        uart_send_status(&g_state);
        g_last_status_time = now;
    }
}

// Called by uart_handler when a valid command is received
void on_command_received()
{
    g_last_command_time = millis();
    g_has_received_command = true;
}

// Functions called by uart_handler for valve state
bool get_valve_open()
{
    return g_valve_state.actual_open;
}

bool get_valve_enabled()
{
    return g_valve_state.enabled;
}

uint32_t get_valve_open_ms()
{
    return valve_safety_get_open_ms(&g_valve_state);
}

bool is_test_active()
{
    if (g_test_triggered_time == 0)
    {
        return false;
    }
    return (millis() - g_test_triggered_time) < 1000;
}

void check_test_command(DeviceState* state)
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

void update_servos(DeviceState* state)
{
    // Update all servos
    for (int i = 0; i < NUM_SERVOS; i++)
    {
        float target = state->command.target_servo_angles[i];
        float current = state->output.servo_angles[i];

        // Move servo toward target
        float new_angle = servo_move_toward(i, current, target, SERVO_SPEED);
        bool moving = (abs(new_angle - target) > 0.1f);

        state_update_servo(state, i, new_angle, moving);
    }
}

void update_valve(DeviceState* state)
{
    // Update valve command from state
    valve_safety_set_command(&g_valve_state, state->command.valve_open);
    valve_safety_set_enabled(&g_valve_state, state->command.valve_enabled);

    // Update valve safety (handles timeouts, connection loss, etc.)
    bool valve_should_open = valve_safety_update(&g_valve_state, state->command.connected);

    // TODO: Actually control valve servo/solenoid here
    // For now, servo 1 (index 0) is the valve servo
    // When valve should be open, move servo 1 to open position
    // This would typically be done via a dedicated valve servo position
    // state->command.target_servo_angles[0] = valve_should_open ? VALVE_OPEN_ANGLE : VALVE_CLOSED_ANGLE;
}

void update_rgb(DeviceState* state)
{
    // Track previous values to avoid unnecessary updates
    static uint8_t prev_mode = 255;
    static uint8_t prev_r = 255, prev_g = 255, prev_b = 255;
    static uint8_t prev_light_cmd = 255;
    static uint16_t rainbow_hue = 0;

    uint8_t mode = state->command.rgb_mode;
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

    // Apply RGB based on mode and light command
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
    else if (mode == 1)
    {
        // Rainbow mode - cycle through colors
        // Simple HSV to RGB conversion
        uint8_t region = rainbow_hue / 43;
        uint8_t remainder = (rainbow_hue - (region * 43)) * 6;

        uint8_t q = 255 - remainder;
        uint8_t t = remainder;

        switch (region)
        {
        case 0:  r = 255; g = t;   b = 0;   break;
        case 1:  r = q;   g = 255; b = 0;   break;
        case 2:  r = 0;   g = 255; b = t;   break;
        case 3:  r = 0;   g = q;   b = 255; break;
        case 4:  r = t;   g = 0;   b = 255; break;
        default: r = 255; g = 0;   b = q;   break;
        }

        rgb_set(r, g, b);
        rainbow_hue = (rainbow_hue + 2) % 256;

        prev_mode = mode;
    }
    else
    {
        // Solid color mode
        if (r == 0 && g == 0 && b == 0)
        {
            r = 255;
            g = 255;
            b = 255;
        }

        // Only update if values changed
        if (r != prev_r || g != prev_g || b != prev_b || mode != prev_mode)
        {
            rgb_set(r, g, b);
            prev_r = r;
            prev_g = g;
            prev_b = b;
        }
    }

    prev_light_cmd = state->command.light_command;
    prev_mode = mode;
    state_update_light(state, should_be_on);
}

void update_matrix(DeviceState* state)
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

void update_neopixel_matrix(DeviceState* state)
{
    // Update NeoPixel matrix mode from command state
    npm_set_mode(&g_npm_state,
                 state->command.npm_mode,
                 state->command.npm_letter,
                 state->command.npm_r,
                 state->command.npm_g,
                 state->command.npm_b);
}

void update_neopixel_ring(DeviceState* state)
{
    // Update NeoPixel ring mode from command state
    npr_set_mode(&g_npr_state,
                 state->command.npr_mode,
                 state->command.npr_r,
                 state->command.npr_g,
                 state->command.npr_b);
}
