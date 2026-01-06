#ifndef CONFIG_H
#define CONFIG_H

// =============================================================================
// Pin Definitions
// =============================================================================

// UART pins (communicating with Raspberry Pi)
#define UART_RX_PIN         16
#define UART_TX_PIN         17

// Servo control
#define SERVO_PIN           18

// Light control
#define LIGHT_PIN           19

// Limit switch (active LOW with internal pullup)
#define LIMIT_SWITCH_PIN    21

// =============================================================================
// UART Settings
// =============================================================================

#define UART_BAUD_RATE      115200
#define UART_RX_BUFFER_SIZE 128
#define UART_TX_BUFFER_SIZE 128

// =============================================================================
// Servo Settings
// =============================================================================

#define SERVO_MIN_ANGLE     0.0f
#define SERVO_MAX_ANGLE     180.0f
#define SERVO_CENTER_ANGLE  90.0f

// Servo movement speed (degrees per update cycle)
#define SERVO_SPEED         2.0f

// PWM settings
#define SERVO_PWM_FREQ      50      // 50 Hz standard servo frequency
#define SERVO_PWM_CHANNEL   0
#define SERVO_PWM_RESOLUTION 16

// Pulse width range (microseconds)
#define SERVO_MIN_PULSE_US  500     // 0 degrees
#define SERVO_MAX_PULSE_US  2500    // 180 degrees

// =============================================================================
// Light Settings
// =============================================================================

// Light command values (from protocol)
#define LIGHT_CMD_OFF       0
#define LIGHT_CMD_ON        1
#define LIGHT_CMD_AUTO      2

// =============================================================================
// Limit Switch Settings
// =============================================================================

// Limit switch directions
#define LIMIT_NONE          0
#define LIMIT_CW            1       // Clockwise limit
#define LIMIT_CCW           2       // Counter-clockwise limit

// Debounce time in milliseconds
#define LIMIT_DEBOUNCE_MS   50

// =============================================================================
// Timing Settings
// =============================================================================

// Main loop update rate
#define LOOP_RATE_HZ        100
#define LOOP_PERIOD_MS      (1000 / LOOP_RATE_HZ)

// Status packet transmission rate
#define STATUS_TX_RATE_HZ   50
#define STATUS_TX_PERIOD_MS (1000 / STATUS_TX_RATE_HZ)

// Connection timeout (no commands received)
#define CONNECTION_TIMEOUT_MS 500

// =============================================================================
// Protocol Settings
// =============================================================================

#define PACKET_START_MARKER '$'
#define PACKET_END_MARKER   '\n'
#define PACKET_MAX_SIZE     64

// =============================================================================
// Debug Settings
// =============================================================================

// Set to 1 to enable debug output on USB serial
#define DEBUG_ENABLED       0

#if DEBUG_ENABLED
    #define DEBUG_PRINT(x)      Serial.print(x)
    #define DEBUG_PRINTLN(x)    Serial.println(x)
    #define DEBUG_PRINTF(...)   Serial.printf(__VA_ARGS__)
#else
    #define DEBUG_PRINT(x)
    #define DEBUG_PRINTLN(x)
    #define DEBUG_PRINTF(...)
#endif

#endif // CONFIG_H
