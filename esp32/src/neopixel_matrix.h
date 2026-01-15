#ifndef NEOPIXEL_MATRIX_H
#define NEOPIXEL_MATRIX_H

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include "config.h"

// =============================================================================
// NeoPixel 5x5 Matrix Module
// =============================================================================
// Controls a 5x5 NeoPixel matrix for displaying letters, patterns, and effects.
// =============================================================================

// Matrix configuration
#define NPM_NUM_PIXELS      25      // 5x5 matrix
#define NPM_BRIGHTNESS      50      // Default brightness (0-255)

// Matrix modes
#define NPM_MODE_OFF        0       // All LEDs off
#define NPM_MODE_LETTER     1       // Display a single letter (A-Z)
#define NPM_MODE_SCROLL     2       // Scroll text (not implemented yet)
#define NPM_MODE_RAINBOW    3       // Rainbow animation
#define NPM_MODE_SOLID      4       // Solid color fill
#define NPM_MODE_EYE_CLOSED 5       // Closed eye pattern (sleeping)
#define NPM_MODE_EYE_OPEN   6       // Open eye pattern (alert)

// Animation speeds
#define NPM_RAINBOW_SPEED   10      // Rainbow color cycling speed
#define NPM_SCROLL_SPEED    100     // Scroll speed (ms per column shift)

// Maximum scroll buffer size
#define NPM_SCROLL_BUFFER_SIZE  128  // Max columns in scroll buffer

// Matrix state structure
typedef struct {
    uint8_t mode;
    char letter;
    uint8_t r, g, b;
    uint8_t prev_mode;
    char prev_letter;
    uint8_t prev_r, prev_g, prev_b;
    uint16_t rainbow_offset;        // For rainbow animation
    bool needs_update;

    // Scroll state
    uint8_t scroll_text_id;         // Current scroll text ID
    uint8_t scroll_buffer[NPM_SCROLL_BUFFER_SIZE];  // Column data for scrolling
    uint16_t scroll_buffer_len;     // Length of scroll buffer in columns
    uint16_t scroll_position;       // Current scroll position (column offset)
    uint32_t scroll_last_update;    // Last scroll update time (ms)
    uint16_t scroll_speed;          // Scroll speed (ms per column shift)
    bool scroll_looping;            // Whether to loop the scroll
    uint8_t prev_scroll_text_id;    // Previous text ID for change detection
} NpmState;

/**
 * Initialize the NeoPixel matrix.
 *
 * @param pin GPIO pin connected to matrix data line
 */
void npm_init(uint8_t pin);

/**
 * Initialize matrix state structure.
 *
 * @param state Pointer to state structure
 */
void npm_state_init(NpmState* state);

/**
 * Set matrix mode and parameters.
 *
 * @param state Pointer to state structure
 * @param mode Display mode (NPM_MODE_*)
 * @param letter Letter to display (for NPM_MODE_LETTER)
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_set_mode(NpmState* state, uint8_t mode, char letter, uint8_t r, uint8_t g, uint8_t b);

/**
 * Update the matrix display (call from animation loop).
 * Handles state changes and animations.
 *
 * @param state Pointer to state structure
 */
void npm_update(NpmState* state);

/**
 * Set matrix brightness.
 *
 * @param brightness Brightness level (0-255)
 */
void npm_set_brightness(uint8_t brightness);

/**
 * Turn off all LEDs.
 */
void npm_clear(void);

/**
 * Display a letter on the matrix.
 *
 * @param letter Letter to display (A-Z)
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_display_letter(char letter, uint8_t r, uint8_t g, uint8_t b);

/**
 * Display solid color on all pixels.
 *
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_display_solid(uint8_t r, uint8_t g, uint8_t b);

/**
 * Display closed eye pattern.
 *
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_display_eye_closed(uint8_t r, uint8_t g, uint8_t b);

/**
 * Display open eye pattern.
 *
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_display_eye_open(uint8_t r, uint8_t g, uint8_t b);

/**
 * Update rainbow animation (call periodically).
 *
 * @param state Pointer to state structure
 */
void npm_update_rainbow(NpmState* state);

/**
 * Set scroll text by ID.
 * Builds the scroll buffer from predefined text.
 *
 * @param state Pointer to state structure
 * @param text_id Scroll text ID (see scroll_texts.h)
 * @param r Red value (0-255)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void npm_set_scroll_text(NpmState* state, uint8_t text_id, uint8_t r, uint8_t g, uint8_t b);

/**
 * Update scroll animation (call periodically).
 *
 * @param state Pointer to state structure
 */
void npm_update_scroll(NpmState* state);

#endif // NEOPIXEL_MATRIX_H
