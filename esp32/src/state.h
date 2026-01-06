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
    float servo_angle;          // Current servo position (degrees)
    bool light_on;              // Current light state
    bool servo_moving;          // True if servo is in motion
} OutputState;

/**
 * Command state received from Raspberry Pi.
 */
typedef struct {
    float target_servo_angle;   // Desired servo position (degrees)
    uint8_t light_command;      // LIGHT_CMD_OFF, LIGHT_CMD_ON, or LIGHT_CMD_AUTO
    uint8_t flags;              // Reserved flags
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
 * Update command state from received packet.
 *
 * @param state Pointer to device state
 * @param servo_target Target servo angle
 * @param light_cmd Light command value
 * @param flags Reserved flags
 */
void state_update_command(DeviceState* state, float servo_target, uint8_t light_cmd, uint8_t flags);

/**
 * Update output state for servo position.
 *
 * @param state Pointer to device state
 * @param angle Current servo angle
 * @param moving True if servo is still moving
 */
void state_update_servo(DeviceState* state, float angle, bool moving);

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
