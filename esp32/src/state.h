#ifndef STATE_H
#define STATE_H

#include <Arduino.h>
#include "config.h"

/**
 * Input state from hardware sensors.
 */
typedef struct {
    bool limit_triggered;       // True if any limit switch is active
    uint8_t limit_direction;    // LIMIT_NONE, LIMIT_CW, or LIMIT_CCW
    uint32_t limit_trigger_time; // Timestamp when limit was triggered
} InputState;

/**
 * Output state for actuators.
 */
typedef struct {
    float servo_angles[NUM_SERVOS];     // Current servo positions (degrees)
    bool servo_moving[NUM_SERVOS];      // True if servo is in motion
    bool light_on;                      // Current light state
} OutputState;

/**
 * Command state received from Raspberry Pi.
 */
typedef struct {
    float target_servo_angles[NUM_SERVOS];  // Desired servo positions (degrees)
    uint8_t light_command;      // LIGHT_CMD_OFF, LIGHT_CMD_ON, or LIGHT_CMD_AUTO
    uint8_t flags;              // Reserved flags
    uint8_t rgb_r;              // RGB red value (0-255)
    uint8_t rgb_g;              // RGB green value (0-255)
    uint8_t rgb_b;              // RGB blue value (0-255)
    uint8_t matrix_left;        // Left matrix pattern ID
    uint8_t matrix_right;       // Right matrix pattern ID
    uint32_t last_command_time; // Timestamp of last received command
    bool connected;             // True if receiving commands
} CommandState;

/**
 * Complete device state.
 */
typedef struct {
    InputState input;
    OutputState output;
    CommandState command;
} DeviceState;

/**
 * Initialize device state with default values.
 *
 * @param state Pointer to state structure to initialize
 */
void state_init(DeviceState* state);

/**
 * Update input state from limit switch reading.
 *
 * @param state Pointer to device state
 * @param limit_active True if limit switch is triggered
 * @param direction Limit direction (LIMIT_CW or LIMIT_CCW)
 */
void state_update_limit(DeviceState* state, bool limit_active, uint8_t direction);

/**
 * Update command state from received packet (basic - for backwards compatibility).
 *
 * @param state Pointer to device state
 * @param servo1_target Target servo 1 angle
 * @param servo2_target Target servo 2 angle
 * @param servo3_target Target servo 3 angle
 * @param light_cmd Light command value
 * @param flags Reserved flags
 */
void state_update_command(DeviceState* state, float servo1_target, float servo2_target,
                          float servo3_target, uint8_t light_cmd, uint8_t flags);

/**
 * Update command state from received packet (extended with RGB and matrix).
 *
 * @param state Pointer to device state
 * @param servo1_target Target servo 1 angle
 * @param servo2_target Target servo 2 angle
 * @param servo3_target Target servo 3 angle
 * @param light_cmd Light command value
 * @param flags Reserved flags
 * @param rgb_r RGB red value (0-255)
 * @param rgb_g RGB green value (0-255)
 * @param rgb_b RGB blue value (0-255)
 * @param matrix_left Left matrix pattern ID
 * @param matrix_right Right matrix pattern ID
 */
void state_update_command_extended(DeviceState* state,
                                   float servo1_target, float servo2_target, float servo3_target,
                                   uint8_t light_cmd, uint8_t flags,
                                   uint8_t rgb_r, uint8_t rgb_g, uint8_t rgb_b,
                                   uint8_t matrix_left, uint8_t matrix_right);

/**
 * Update output state for a specific servo position.
 *
 * @param state Pointer to device state
 * @param servo_index Servo index (0, 1, or 2)
 * @param angle Current servo angle
 * @param moving True if servo is still moving
 */
void state_update_servo(DeviceState* state, uint8_t servo_index, float angle, bool moving);

/**
 * Update output state for light.
 *
 * @param state Pointer to device state
 * @param on True if light is on
 */
void state_update_light(DeviceState* state, bool on);

/**
 * Check if connection to Pi is still active.
 *
 * @param state Pointer to device state
 * @param timeout_ms Connection timeout in milliseconds
 */
void state_check_connection(DeviceState* state, uint32_t timeout_ms);

#endif // STATE_H
