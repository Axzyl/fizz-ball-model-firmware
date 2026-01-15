#ifndef LED_MATRIX_H
#define LED_MATRIX_H

#include <Arduino.h>

// =============================================================================
// LED Matrix Module (MAX7219 8x8 x 2)
// =============================================================================
// Controls two chained MAX7219 8x8 LED matrices for displaying scrolling text
// or static patterns.
// =============================================================================

// Pattern IDs for static display mode
#define MATRIX_SHAPE_OFF        0   // All LEDs off
#define MATRIX_SHAPE_CIRCLE     1   // Circle pattern
#define MATRIX_SHAPE_X          2   // X pattern

// Matrix modes
#define MATRIX_MODE_PATTERN     0   // Display static patterns
#define MATRIX_MODE_SCROLL      1   // Scroll text

// Scroll configuration
#define MATRIX_SCROLL_SPEED     80  // ms per column shift
#define MATRIX_SCROLL_BUFFER_SIZE 256  // Max columns in scroll buffer

// Scroll state structure
typedef struct {
    uint8_t mode;                   // MATRIX_MODE_PATTERN or MATRIX_MODE_SCROLL
    uint8_t scroll_buffer[MATRIX_SCROLL_BUFFER_SIZE];  // Column data
    uint16_t scroll_buffer_len;     // Length in columns
    uint16_t scroll_position;       // Current scroll position
    uint32_t scroll_last_update;    // Last update time (ms)
    uint16_t scroll_speed;          // Speed (ms per column)
    uint8_t current_text_id;        // Current text ID for random selection
} MatrixScrollState;

/**
 * Initialize the LED matrix.
 */
void led_matrix_init();

/**
 * Initialize the scroll state structure.
 */
void led_matrix_scroll_init(MatrixScrollState* state);

/**
 * Set the pattern for each matrix (static mode).
 */
void led_matrix_set_patterns(uint8_t left_pattern, uint8_t right_pattern);

/**
 * Get the current pattern IDs.
 */
void led_matrix_get_patterns(uint8_t* left_pattern, uint8_t* right_pattern);

/**
 * Clear the matrix.
 */
void led_matrix_clear();

/**
 * Set matrix brightness.
 */
void led_matrix_set_brightness(uint8_t brightness);

/**
 * Set scroll text by ID.
 */
void led_matrix_set_scroll_text(MatrixScrollState* state, uint8_t text_id);

/**
 * Update scroll animation (call periodically from animation task).
 */
void led_matrix_update_scroll(MatrixScrollState* state);

/**
 * Set scroll mode enabled/disabled.
 */
void led_matrix_set_scroll_mode(MatrixScrollState* state, bool enabled);

#endif // LED_MATRIX_H
