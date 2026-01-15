#ifndef NEOPIXEL_RING_H
#define NEOPIXEL_RING_H

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include "config.h"

// =============================================================================
// NeoPixel Ring Module
// =============================================================================
// Controls a NeoPixel ring (8 LEDs) with various animation modes.
// =============================================================================

// Ring configuration
#define NPR_NUM_PIXELS      8       // 8-LED ring
#define NPR_BRIGHTNESS      50      // Default brightness (0-255)

// Ring modes
#define NPR_MODE_OFF        0       // All LEDs off
#define NPR_MODE_SOLID      1       // Solid color fill
#define NPR_MODE_RAINBOW    2       // Rainbow wave animation
#define NPR_MODE_CHASE      3       // Single LED chase animation
#define NPR_MODE_BREATHE    4       // Breathing/pulse effect
#define NPR_MODE_SPINNER    5       // Spinning dot animation
#define NPR_MODE_GRADIENT   6       // Ping-pong gradient between 2 colors

// Animation speeds
#define NPR_RAINBOW_SPEED   3       // Rainbow cycling speed
#define NPR_CHASE_SPEED     100     // Chase update interval (ms)
#define NPR_BREATHE_SPEED   10      // Breathe cycle speed
#define NPR_SPINNER_SPEED   50      // Spinner update interval (ms)

// Ring state structure
typedef struct {
    uint8_t mode;
    uint8_t r, g, b;
    uint8_t prev_mode;
    uint8_t prev_r, prev_g, prev_b;
    uint16_t animation_offset;      // For animations
    uint8_t breathe_value;          // For breathe effect
    int8_t breathe_direction;       // 1 = increasing, -1 = decreasing
    uint32_t last_update;           // For timing
    bool needs_update;
    // Gradient mode fields
    uint8_t r2, g2, b2;             // Second color for gradient
    uint8_t gradient_speed;         // Animation speed (1-50)
    uint16_t gradient_position;     // Current position (0-510 for ping-pong)
} NprState;

/**
 * Initialize the NeoPixel ring.
 *
 * @param pin GPIO pin connected to ring data line
 */
void npr_init(uint8_t pin);

/**
 * Initialize ring state structure.
 *
 * @param state Pointer to state structure
 */
void npr_state_init(NprState* state);

/**
 * Set ring mode and parameters.
 *
 * @param state Pointer to state structure
 * @param mode Display mode (NPR_MODE_*)
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 * @param r2 Gradient second color red (0-255)
 * @param g2 Gradient second color green (0-255)
 * @param b2 Gradient second color blue (0-255)
 * @param speed Gradient animation speed (1-50)
 */
void npr_set_mode(NprState* state, uint8_t mode, uint8_t r, uint8_t g, uint8_t b,
                  uint8_t r2 = 0, uint8_t g2 = 0, uint8_t b2 = 0, uint8_t speed = 10);

/**
 * Update the ring display (call from animation loop).
 * Handles state changes and animations.
 *
 * @param state Pointer to state structure
 */
void npr_update(NprState* state);

/**
 * Set ring brightness.
 *
 * @param brightness Brightness level (0-255)
 */
void npr_set_brightness(uint8_t brightness);

/**
 * Turn off all LEDs.
 */
void npr_clear(void);

/**
 * Display solid color on all pixels.
 *
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npr_display_solid(uint8_t r, uint8_t g, uint8_t b);

#endif // NEOPIXEL_RING_H
