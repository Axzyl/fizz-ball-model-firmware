#ifndef LED_MATRIX_H
#define LED_MATRIX_H

#include <Arduino.h>

// Single-matrix pattern IDs
#define MATRIX_SHAPE_OFF        0   // All LEDs off
#define MATRIX_SHAPE_CIRCLE     1   // Circle (eye open)
#define MATRIX_SHAPE_X          2   // X shape (eye closed)

/**
 * Initialize the LED matrix.
 * Sets up MD_MAX72XX library and displays default pattern.
 */
void led_matrix_init();

/**
 * Set the pattern for each matrix independently.
 *
 * @param left_pattern Pattern ID for left matrix (device 0)
 * @param right_pattern Pattern ID for right matrix (device 1)
 */
void led_matrix_set_patterns(uint8_t left_pattern, uint8_t right_pattern);

/**
 * Get the current pattern IDs.
 *
 * @param left_pattern Pointer to store left pattern (can be NULL)
 * @param right_pattern Pointer to store right pattern (can be NULL)
 */
void led_matrix_get_patterns(uint8_t* left_pattern, uint8_t* right_pattern);

/**
 * Clear the matrix (turn all LEDs off).
 */
void led_matrix_clear();

/**
 * Set matrix brightness.
 *
 * @param brightness Brightness level (0-15)
 */
void led_matrix_set_brightness(uint8_t brightness);

#endif // LED_MATRIX_H
