#ifndef CONFIG_H
#define CONFIG_H

// Include hardware pin definitions (edit pins.h to change wiring)
#include "pins.h"

// =============================================================================
// UART Settings
// =============================================================================

#define UART_BAUD_RATE 115200
#define UART_RX_BUFFER_SIZE 128
#define UART_TX_BUFFER_SIZE 128

// =============================================================================
// Servo Settings (3 servos)
// =============================================================================

#define SERVO_MIN_ANGLE 0.0f
#define SERVO_MAX_ANGLE 180.0f
#define SERVO_CENTER_ANGLE 90.0f

// Servo movement speed (degrees per update cycle)
#define SERVO_SPEED 2.0f

// PWM settings
#define SERVO_PWM_FREQ 50 // 50 Hz standard servo frequency
#define SERVO_PWM_RESOLUTION 16

// PWM channels for each servo (channels 0-2)
#define SERVO_1_PWM_CHANNEL 0
#define SERVO_2_PWM_CHANNEL 1
#define SERVO_3_PWM_CHANNEL 2

// Pulse width range (microseconds)
#define SERVO_MIN_PULSE_US 500  // 0 degrees
#define SERVO_MAX_PULSE_US 2500 // 180 degrees

// Valve servo settings (Servo 3 = index 2)
#define VALVE_SERVO_INDEX 2     // Servo index for valve control
#define VALVE_CLOSED_ANGLE 0.0f // Valve closed position (default start)
#define VALVE_OPEN_ANGLE 180.0f // Valve open position

// =============================================================================
// RGB Strip Settings
// =============================================================================

// PWM channels (channels 4-6 to avoid timer conflict with servos)
// Servo channels 0-2 use timers 0,0,1
// RGB channels 4-6 use timers 2,2,3 (no overlap)
#define RGB_CH_R 4
#define RGB_CH_G 5
#define RGB_CH_B 6

// PWM settings
#define RGB_PWM_FREQ 5000 // 5kHz PWM frequency
#define RGB_PWM_RES 8     // 8-bit resolution (0-255)

// Light command values (from protocol)
#define LIGHT_CMD_OFF 0
#define LIGHT_CMD_ON 1
#define LIGHT_CMD_AUTO 2

// =============================================================================
// LED Matrix Settings
// =============================================================================

#define MATRIX_DEFAULT_BRIGHTNESS 8 // 0-15

// =============================================================================
// Limit Switch Settings
// =============================================================================

// Limit switch directions
#define LIMIT_NONE 0
#define LIMIT_CW 1  // Clockwise limit
#define LIMIT_CCW 2 // Counter-clockwise limit

// Debounce time in milliseconds
#define LIMIT_DEBOUNCE_MS 50

// =============================================================================
// Timing Settings
// =============================================================================

// Main loop update rate
#define LOOP_RATE_HZ 100
#define LOOP_PERIOD_MS (1000 / LOOP_RATE_HZ)

// Status packet transmission rate
#define STATUS_TX_RATE_HZ 50
#define STATUS_TX_PERIOD_MS (1000 / STATUS_TX_RATE_HZ)

// Connection timeout (no commands received)
#define CONNECTION_TIMEOUT_MS 500

// =============================================================================
// Protocol Settings
// =============================================================================

#define PACKET_START_MARKER '$'
#define PACKET_END_MARKER '\n'
#define PACKET_MAX_SIZE 64

// Command flags (from Pi)
#define CMD_FLAG_LED_TEST 0x01 // Bit 0: Trigger LED blink test

// =============================================================================
// Test Settings
// =============================================================================

#define TEST_LED_DURATION_MS 500 // LED on for 0.5 seconds

// =============================================================================
// Debug Settings
// =============================================================================

// Set to 1 to enable debug output on USB serial
// WARNING: Debug output interferes with Pi communication - keep disabled!
#define DEBUG_ENABLED 0

#if DEBUG_ENABLED
#define DEBUG_PRINT(x) Serial.print(x)
#define DEBUG_PRINTLN(x) Serial.println(x)
#define DEBUG_PRINTF(...) Serial.printf(__VA_ARGS__)
#else
#define DEBUG_PRINT(x)
#define DEBUG_PRINTLN(x)
#define DEBUG_PRINTF(...)
#endif

#endif // CONFIG_H
