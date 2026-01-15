#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
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

// =============================================================================
// RTOS Configuration
// =============================================================================
#define TASK_COMM_STACK_SIZE      4096
#define TASK_ANIMATION_STACK_SIZE 4096
#define TASK_CONTROL_STACK_SIZE   4096

#define TASK_COMM_PRIORITY        2
#define TASK_ANIMATION_PRIORITY   1
#define TASK_CONTROL_PRIORITY     2

#define TASK_COMM_CORE            0   // Communication on Core 0
#define TASK_ANIMATION_CORE       1   // Animation on Core 1
#define TASK_CONTROL_CORE         1   // Control on Core 1

// Task periods in milliseconds
#define COMM_TASK_PERIOD_MS       33  // ~30Hz
#define ANIMATION_TASK_PERIOD_MS  20  // 50Hz
#define CONTROL_TASK_PERIOD_MS    10  // 100Hz

// =============================================================================
// Global State (protected by mutex)
// =============================================================================
DeviceState g_state;
ValveState g_valve_state;
NpmState g_npm_state;
NprState g_npr_state;
MatrixScrollState g_matrix_scroll_state;

// Mutex for protecting shared state
SemaphoreHandle_t g_state_mutex = NULL;

// Communication tracking (accessed by comm task)
volatile uint32_t g_last_command_time = 0;
volatile bool g_has_received_command = false;

// Test LED state
volatile uint32_t g_test_triggered_time = 0;
volatile bool g_test_led_on = false;

// Task handles
TaskHandle_t g_comm_task_handle = NULL;
TaskHandle_t g_animation_task_handle = NULL;
TaskHandle_t g_control_task_handle = NULL;

// =============================================================================
// Helper Functions
// =============================================================================

// Lock the state mutex (with timeout)
inline bool state_lock(TickType_t timeout = portMAX_DELAY) {
    return xSemaphoreTake(g_state_mutex, timeout) == pdTRUE;
}

// Unlock the state mutex
inline void state_unlock() {
    xSemaphoreGive(g_state_mutex);
}

// =============================================================================
// Communication Task - UART RX/TX (Core 0)
// =============================================================================
void comm_task(void* pvParameters) {
    TickType_t last_status_time = 0;
    const TickType_t period = pdMS_TO_TICKS(COMM_TASK_PERIOD_MS);
    const TickType_t status_interval = pdMS_TO_TICKS(STATUS_TX_PERIOD_MS);

    DEBUG_PRINTF("[RTOS] Communication task started on Core %d\n", xPortGetCoreID());

    for (;;) {
        TickType_t task_start = xTaskGetTickCount();

        // Receive and parse commands (locks mutex internally if needed)
        if (state_lock(pdMS_TO_TICKS(10))) {
            uart_receive(&g_state);
            state_check_connection(&g_state, CONNECTION_TIMEOUT_MS);
            state_unlock();
        }

        // Send status if connected
        TickType_t now = xTaskGetTickCount();
        bool connected = g_has_received_command &&
                        ((now - g_last_command_time) < pdMS_TO_TICKS(1000));

        if (connected && (now - last_status_time >= status_interval)) {
            if (state_lock(pdMS_TO_TICKS(10))) {
                uart_send_status(&g_state);
                state_unlock();
            }
            last_status_time = now;
        }

        // Delay until next period
        vTaskDelayUntil(&task_start, period);
    }
}

// =============================================================================
// Animation Task - NeoPixel & RGB animations (Core 1)
// =============================================================================
void animation_task(void* pvParameters) {
    const TickType_t period = pdMS_TO_TICKS(ANIMATION_TASK_PERIOD_MS);
    uint16_t rainbow_hue = 0;

    DEBUG_PRINTF("[RTOS] Animation task started on Core %d\n", xPortGetCoreID());

    for (;;) {
        TickType_t task_start = xTaskGetTickCount();

        // Update NeoPixel matrix
        npm_update(&g_npm_state);

        // Update NeoPixel ring animation
        npr_update(&g_npr_state);

        // Update MAX7219 LED matrix scrolling text
        led_matrix_update_scroll(&g_matrix_scroll_state);

        // Update RGB strip rainbow animation if in rainbow mode
        if (state_lock(pdMS_TO_TICKS(5))) {
            if (g_state.command.rgb_mode == 1 && g_state.output.light_on) {
                // Rainbow mode - cycle through colors
                uint8_t region = rainbow_hue / 43;
                uint8_t remainder = (rainbow_hue - (region * 43)) * 6;
                uint8_t r, g, b;
                uint8_t q = 255 - remainder;
                uint8_t t = remainder;

                switch (region) {
                    case 0:  r = 255; g = t;   b = 0;   break;
                    case 1:  r = q;   g = 255; b = 0;   break;
                    case 2:  r = 0;   g = 255; b = t;   break;
                    case 3:  r = 0;   g = q;   b = 255; break;
                    case 4:  r = t;   g = 0;   b = 255; break;
                    default: r = 255; g = 0;   b = q;   break;
                }

                rgb_set(r, g, b);
                rainbow_hue = (rainbow_hue + 2) % 256;
            }
            state_unlock();
        }

        // Delay until next period
        vTaskDelayUntil(&task_start, period);
    }
}

// =============================================================================
// Control Task - Servos, sensors, valve (Core 1)
// =============================================================================
void control_task(void* pvParameters) {
    const TickType_t period = pdMS_TO_TICKS(CONTROL_TASK_PERIOD_MS);

    // Track previous values for change detection
    uint8_t prev_matrix_left = 255;
    uint8_t prev_matrix_right = 255;
    uint8_t prev_rgb_mode = 255;
    uint8_t prev_rgb_r = 255, prev_rgb_g = 255, prev_rgb_b = 255;
    uint8_t prev_light_cmd = 255;

    DEBUG_PRINTF("[RTOS] Control task started on Core %d\n", xPortGetCoreID());

    for (;;) {
        TickType_t task_start = xTaskGetTickCount();

        // Read limit switch (no mutex needed - atomic operation)
        bool limit_active;
        uint8_t limit_dir;
        limit_switch_read(&limit_active, &limit_dir);

        if (state_lock(pdMS_TO_TICKS(10))) {
            // Update limit switch state
            state_update_limit(&g_state, limit_active, limit_dir);

            // Check for test command
            if ((g_state.command.flags & CMD_FLAG_LED_TEST) && !g_test_led_on) {
                g_test_led_on = true;
                g_test_triggered_time = xTaskGetTickCount();
                digitalWrite(TEST_LED_PIN, HIGH);
                g_state.command.flags &= ~CMD_FLAG_LED_TEST;
            }

            // Update valve (command is set by uart_handler when $VLV received, not here)
            // valve_safety_set_command is called in uart_handler, not every tick
            bool valve_should_open = valve_safety_update(&g_valve_state, g_state.command.connected);
            g_state.command.target_servo_angles[VALVE_SERVO_INDEX] =
                valve_should_open ? VALVE_OPEN_ANGLE : VALVE_CLOSED_ANGLE;

            // Update servos
            for (int i = 0; i < NUM_SERVOS; i++) {
                float target = g_state.command.target_servo_angles[i];
                float current = g_state.output.servo_angles[i];
                float new_angle = servo_move_toward(i, current, target, SERVO_SPEED);
                bool moving = (abs(new_angle - target) > 0.1f);
                state_update_servo(&g_state, i, new_angle, moving);
            }

            // Update MAX7219 LED matrix mode (scroll vs pattern)
            uint8_t left = g_state.command.matrix_left;
            uint8_t right = g_state.command.matrix_right;
            if (left != prev_matrix_left || right != prev_matrix_right) {
                if (left == 0 && right == 0) {
                    // Enable scroll mode (patterns are 0,0)
                    led_matrix_set_scroll_mode(&g_matrix_scroll_state, true);
                } else {
                    // Disable scroll mode and set patterns
                    led_matrix_set_scroll_mode(&g_matrix_scroll_state, false);
                    led_matrix_set_patterns(left, right);
                }
                prev_matrix_left = left;
                prev_matrix_right = right;
            }

            // Update RGB strip solid color (rainbow handled in animation task)
            uint8_t mode = g_state.command.rgb_mode;
            uint8_t r = g_state.command.rgb_r;
            uint8_t g = g_state.command.rgb_g;
            uint8_t b = g_state.command.rgb_b;
            uint8_t light_cmd = g_state.command.light_command;

            bool should_be_on = false;
            switch (light_cmd) {
                case LIGHT_CMD_OFF: should_be_on = false; break;
                case LIGHT_CMD_ON:  should_be_on = true;  break;
                case LIGHT_CMD_AUTO:
                    should_be_on = (mode == 1) || (r > 0 || g > 0 || b > 0);
                    break;
            }

            if (!should_be_on) {
                if (prev_light_cmd != LIGHT_CMD_OFF || prev_rgb_r != 0 || prev_rgb_g != 0 || prev_rgb_b != 0) {
                    rgb_off();
                    prev_rgb_r = 0;
                    prev_rgb_g = 0;
                    prev_rgb_b = 0;
                }
            } else if (mode == 0) {
                // Solid color mode
                if (r == 0 && g == 0 && b == 0) { r = g = b = 255; }
                if (r != prev_rgb_r || g != prev_rgb_g || b != prev_rgb_b || mode != prev_rgb_mode) {
                    rgb_set(r, g, b);
                    prev_rgb_r = r;
                    prev_rgb_g = g;
                    prev_rgb_b = b;
                }
            }

            prev_light_cmd = light_cmd;
            prev_rgb_mode = mode;
            state_update_light(&g_state, should_be_on);

            // Update NeoPixel matrix colors from command (text selection is autonomous)
            npm_set_mode(&g_npm_state,
                        g_state.command.npm_mode,
                        g_state.command.npm_letter,
                        g_state.command.npm_r,
                        g_state.command.npm_g,
                        g_state.command.npm_b);

            // Update NeoPixel ring mode
            npr_set_mode(&g_npr_state,
                        g_state.command.npr_mode,
                        g_state.command.npr_r,
                        g_state.command.npr_g,
                        g_state.command.npr_b);

            state_unlock();
        }

        // Update test LED (non-blocking, outside mutex)
        if (g_test_led_on) {
            if ((xTaskGetTickCount() - g_test_triggered_time) >= pdMS_TO_TICKS(TEST_LED_DURATION_MS)) {
                digitalWrite(TEST_LED_PIN, LOW);
                g_test_led_on = false;
            }
        }

        // Delay until next period
        vTaskDelayUntil(&task_start, period);
    }
}

// =============================================================================
// Callbacks for uart_handler
// =============================================================================
void on_command_received() {
    g_last_command_time = xTaskGetTickCount();
    g_has_received_command = true;
}

bool get_valve_open() {
    return g_valve_state.actual_open;
}

bool get_valve_enabled() {
    return g_valve_state.enabled;
}

uint32_t get_valve_open_ms() {
    return valve_safety_get_open_ms(&g_valve_state);
}

bool is_test_active() {
    if (g_test_triggered_time == 0) return false;
    return (xTaskGetTickCount() - g_test_triggered_time) < pdMS_TO_TICKS(1000);
}

// =============================================================================
// Setup & Loop
// =============================================================================
void setup() {
    // Initialize USB serial for protocol communication
    Serial.begin(115200);
    delay(100);

    DEBUG_PRINTLN("=================================");
    DEBUG_PRINTLN("ESP32 RTOS Firmware Starting...");
    DEBUG_PRINTLN("=================================");

    // Seed random number generator
    randomSeed(analogRead(0) ^ micros());

    // Initialize test LED
    pinMode(TEST_LED_PIN, OUTPUT);
    digitalWrite(TEST_LED_PIN, LOW);

    // Initialize state
    state_init(&g_state);
    valve_safety_init(&g_valve_state);
    npm_state_init(&g_npm_state);
    npr_state_init(&g_npr_state);
    led_matrix_scroll_init(&g_matrix_scroll_state);

    // Initialize hardware components
    uart_init();
    servo_init();
    rgb_init();
    led_matrix_init();
    limit_switch_init();
    npm_init(NPM_DATA_PIN);
    npr_init(NPR_DATA_PIN);

    // Create mutex for state protection
    g_state_mutex = xSemaphoreCreateMutex();
    if (g_state_mutex == NULL) {
        DEBUG_PRINTLN("[ERROR] Failed to create state mutex!");
        while (1) { delay(1000); }
    }

    // Create RTOS tasks
    DEBUG_PRINTLN("[RTOS] Creating tasks...");

    // Communication task on Core 0
    xTaskCreatePinnedToCore(
        comm_task,
        "CommTask",
        TASK_COMM_STACK_SIZE,
        NULL,
        TASK_COMM_PRIORITY,
        &g_comm_task_handle,
        TASK_COMM_CORE
    );

    // Animation task on Core 1
    xTaskCreatePinnedToCore(
        animation_task,
        "AnimTask",
        TASK_ANIMATION_STACK_SIZE,
        NULL,
        TASK_ANIMATION_PRIORITY,
        &g_animation_task_handle,
        TASK_ANIMATION_CORE
    );

    // Control task on Core 1
    xTaskCreatePinnedToCore(
        control_task,
        "CtrlTask",
        TASK_CONTROL_STACK_SIZE,
        NULL,
        TASK_CONTROL_PRIORITY,
        &g_control_task_handle,
        TASK_CONTROL_CORE
    );

    DEBUG_PRINTLN("[RTOS] All tasks created successfully!");
    DEBUG_PRINTLN("=================================");
}

void loop() {
    // Empty - all work done in RTOS tasks
    // Could add watchdog or system monitoring here
    vTaskDelay(pdMS_TO_TICKS(1000));
}
