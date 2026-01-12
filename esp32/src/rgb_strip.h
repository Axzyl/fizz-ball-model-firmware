#ifndef RGB_STRIP_H
#define RGB_STRIP_H

#include <Arduino.h>

/**
 * Initialize the RGB LED strip.
 * Sets up PWM channels for R, G, B pins.
 */
void rgb_init();

/**
 * Set RGB color directly.
 *
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void rgb_set(uint8_t r, uint8_t g, uint8_t b);

/**
 * Set RGB color using HSV (hue only, full saturation/value).
 * Useful for rainbow effects.
 *
 * @param hue Hue value (0-359 degrees)
 */
void rgb_set_hsv(uint16_t hue);

/**
 * Turn RGB strip off.
 */
void rgb_off();

/**
 * Get current RGB state.
 *
 * @param r Pointer to store red value
 * @param g Pointer to store green value
 * @param b Pointer to store blue value
 */
void rgb_get_state(uint8_t* r, uint8_t* g, uint8_t* b);

#endif // RGB_STRIP_H
