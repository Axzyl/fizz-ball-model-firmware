#ifndef COLOR_UTILS_H
#define COLOR_UTILS_H

#include <Arduino.h>

// =============================================================================
// Color Utility Functions
// =============================================================================
// Shared color interpolation functions for gradient animations.
// =============================================================================

/**
 * Linear interpolation between two 8-bit values.
 * @param a Start value
 * @param b End value
 * @param t Position (0-255, where 0=a, 255=b)
 * @return Interpolated value
 */
inline uint8_t lerp8(uint8_t a, uint8_t b, uint8_t t) {
    return a + (((int16_t)b - a) * t) >> 8;
}

/**
 * Calculate gradient color between two RGB colors.
 * @param t Position in gradient (0-255)
 * @param r1,g1,b1 Start color
 * @param r2,g2,b2 End color
 * @param out_r,out_g,out_b Output color pointers
 */
inline void gradient_color(
    uint8_t t,
    uint8_t r1, uint8_t g1, uint8_t b1,
    uint8_t r2, uint8_t g2, uint8_t b2,
    uint8_t* out_r, uint8_t* out_g, uint8_t* out_b
) {
    *out_r = lerp8(r1, r2, t);
    *out_g = lerp8(g1, g2, t);
    *out_b = lerp8(b1, b2, t);
}

/**
 * Update ping-pong gradient position.
 * Position cycles 0 -> 510 -> 0 continuously (510 steps total for smooth animation).
 * @param position Current position (0-510)
 * @param speed Step size per update (1-50)
 * @return New position
 */
inline uint16_t gradient_advance_pingpong(uint16_t position, uint8_t speed) {
    // Simple linear position that wraps at 510
    // 0-255 = forward (color1 to color2)
    // 256-510 = backward (color2 to color1)
    position += speed;
    if (position > 510) {
        position = position - 510;  // Wrap around
    }
    return position;
}

/**
 * Convert ping-pong position to interpolation factor.
 * @param position Position (0-510)
 * @return Interpolation factor (0-255)
 */
inline uint8_t gradient_position_to_t(uint16_t position) {
    // 0-255: t goes 0->255 (forward)
    // 256-510: t goes 255->0 (backward, mapped as 510-position)
    if (position <= 255) {
        return (uint8_t)position;
    } else {
        return (uint8_t)(510 - position);
    }
}

#endif // COLOR_UTILS_H
