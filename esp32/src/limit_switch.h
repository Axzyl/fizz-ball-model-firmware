#ifndef LIMIT_SWITCH_H
#define LIMIT_SWITCH_H

#include <Arduino.h>

/**
 * Initialize limit switch input.
 *
 * Configures GPIO pin with internal pullup.
 */
void limit_switch_init();

/**
 * Read limit switch state with debouncing.
 *
 * @param active Output: true if limit switch is triggered
 * @param direction Output: limit direction (LIMIT_CW or LIMIT_CCW)
 */
void limit_switch_read(bool* active, uint8_t* direction);

/**
 * Check if limit switch is currently triggered (raw read).
 *
 * @return true if limit switch is active
 */
bool limit_switch_is_triggered();

#endif // LIMIT_SWITCH_H
