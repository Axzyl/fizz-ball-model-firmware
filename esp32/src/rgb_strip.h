#ifndef RGB_STRIP_H
#define RGB_STRIP_H

#include <Arduino.h>

// =============================================================================
// RGB LED Strip Module
// =============================================================================
// Controls a PWM-based RGB LED strip with various modes.
// =============================================================================

// RGB modes (matches original protocol)
#define RGB_MODE_SOLID      0       // Solid color (default)
#define RGB_MODE_RAINBOW    1       // Rainbow animation
#define RGB_MODE_GRADIENT   2       // Ping-pong gradient between 2 colors

// RGB state structure
typedef struct {
    uint8_t mode;
    uint8_t r, g, b;                // Primary color
    uint8_t r2, g2, b2;             // Second color for gradient
    uint8_t gradient_speed;         // Animation speed (1-50)
    uint16_t gradient_position;     // Current position (0-510 for ping-pong)
    uint16_t rainbow_hue;           // Current hue for rainbow mode (0-359)
    uint8_t prev_mode;
    uint8_t prev_r, prev_g, prev_b;
    bool needs_update;
} RgbState;

/**
 * Initialize the RGB LED strip.
 * Sets up PWM channels for R, G, B pins.
 */
void rgb_init();

/**
 * Initialize RGB state structure.
 *
 * @param state Pointer to state structure
 */
void rgb_state_init(RgbState* state);

/**
 * Set RGB mode and parameters.
 *
 * @param state Pointer to state structure
 * @param mode Display mode (RGB_MODE_*)
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 * @param r2 Gradient second color red (0-255)
 * @param g2 Gradient second color green (0-255)
 * @param b2 Gradient second color blue (0-255)
 * @param speed Gradient animation speed (1-50)
 */
void rgb_set_mode(RgbState* state, uint8_t mode, uint8_t r, uint8_t g, uint8_t b,
                  uint8_t r2 = 0, uint8_t g2 = 0, uint8_t b2 = 0, uint8_t speed = 10);

/**
 * Update the RGB strip (call from animation loop).
 * Handles state changes and animations.
 *
 * @param state Pointer to state structure
 */
void rgb_update(RgbState* state);

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
