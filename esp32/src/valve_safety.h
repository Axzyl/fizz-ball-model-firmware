#ifndef VALVE_SAFETY_H
#define VALVE_SAFETY_H

#include <Arduino.h>
#include "config.h"

// =============================================================================
// Valve Safety Module
// =============================================================================
// Implements safety features for the alcohol dispensing valve:
// - Maximum open time limit (prevents overflow)
// - Emergency stop functionality
// - Connection loss failsafe (auto-close)
// =============================================================================

// Valve safety settings
#define VALVE_MAX_OPEN_MS       5000    // Auto-close after 5 seconds
#define VALVE_COOLDOWN_MS       500     // Minimum time between pours (0.5 seconds)
#define VALVE_PULSE_MIN_MS      100     // Minimum pulse duration

// Valve state structure
typedef struct {
    bool commanded_open;        // What Pi wants (true = open, false = close)
    bool actual_open;           // What valve actually is
    bool enabled;               // Emergency stop state (true = enabled, false = disabled)
    uint32_t open_start_time;   // When valve was opened
    uint32_t total_open_ms;     // How long valve has been open this session
    uint32_t last_close_time;   // When valve was last closed (for cooldown)
    bool safety_triggered;      // True if safety limit was hit
} ValveState;

/**
 * Initialize valve safety module.
 *
 * @param state Pointer to valve state structure
 */
void valve_safety_init(ValveState* state);

/**
 * Set valve command (from Pi).
 *
 * @param state Pointer to valve state
 * @param open True to open valve, false to close
 */
void valve_safety_set_command(ValveState* state, bool open);

/**
 * Set emergency stop state.
 *
 * @param state Pointer to valve state
 * @param enabled True to enable valve operation, false to disable (emergency stop)
 */
void valve_safety_set_enabled(ValveState* state, bool enabled);

/**
 * Update valve safety state (call from main loop).
 * Handles timeout, cooldown, and connection loss.
 *
 * @param state Pointer to valve state
 * @param connected True if Pi connection is active
 * @return True if valve should be open, false if should be closed
 */
bool valve_safety_update(ValveState* state, bool connected);

/**
 * Get current open duration in milliseconds.
 *
 * @param state Pointer to valve state
 * @return Duration valve has been open (0 if closed)
 */
uint32_t valve_safety_get_open_ms(const ValveState* state);

/**
 * Check if valve is enabled (not in emergency stop).
 *
 * @param state Pointer to valve state
 * @return True if valve can be operated
 */
bool valve_safety_is_enabled(const ValveState* state);

/**
 * Check if safety limit was triggered.
 *
 * @param state Pointer to valve state
 * @return True if timeout or safety limit triggered
 */
bool valve_safety_is_triggered(const ValveState* state);

/**
 * Reset safety trigger flag (after acknowledgment).
 *
 * @param state Pointer to valve state
 */
void valve_safety_reset_trigger(ValveState* state);

#endif // VALVE_SAFETY_H
