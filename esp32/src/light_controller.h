#ifndef LIGHT_CONTROLLER_H
#define LIGHT_CONTROLLER_H

#include <Arduino.h>

/**
 * Initialize light controller.
 *
 * Sets up GPIO pin for light control.
 */
void light_init();

/**
 * Set light state.
 *
 * @param on True to turn light on, false to turn off
 */
void light_set(bool on);

/**
 * Get current light state.
 *
 * @return True if light is on
 */
bool light_get_state();

// =============================================================================
// Placeholder functions for future implementation
// =============================================================================

/**
 * Set light brightness (placeholder).
 *
 * TODO: Implement PWM-based brightness control if hardware supports it.
 *
 * @param brightness Brightness level (0-255)
 */
void light_set_brightness(uint8_t brightness);

/**
 * Set light color (placeholder).
 *
 * TODO: Implement for RGB lights if hardware supports it.
 *
 * @param r Red component (0-255)
 * @param g Green component (0-255)
 * @param b Blue component (0-255)
 */
void light_set_color(uint8_t r, uint8_t g, uint8_t b);

/**
 * Start light pattern (placeholder).
 *
 * TODO: Implement various light patterns (blink, fade, pulse, etc.)
 *
 * @param pattern Pattern ID
 * @param speed Pattern speed (ms per cycle)
 */
void light_start_pattern(uint8_t pattern, uint16_t speed);

/**
 * Stop any running light pattern (placeholder).
 */
void light_stop_pattern();

/**
 * Update light pattern state (placeholder).
 *
 * TODO: Call this from main loop to update pattern animations.
 */
void light_update();

#endif // LIGHT_CONTROLLER_H
