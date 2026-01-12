#include "led_matrix.h"
#include "config.h"
#include <MD_MAX72XX.h>

// Matrix instance
static MD_MAX72XX* mx = nullptr;

// Current patterns for each matrix
static uint8_t current_left_pattern = MATRIX_SHAPE_OFF;
static uint8_t current_right_pattern = MATRIX_SHAPE_OFF;

// Pattern definitions (8x8 bitmaps)
static const uint8_t circle[8][8] = {
    {0, 0, 1, 1, 1, 1, 0, 0},
    {0, 1, 1, 0, 0, 1, 1, 0},
    {1, 1, 0, 0, 0, 0, 1, 1},
    {1, 0, 0, 0, 0, 0, 0, 1},
    {1, 0, 0, 0, 0, 0, 0, 1},
    {1, 1, 0, 0, 0, 0, 1, 1},
    {0, 1, 1, 0, 0, 1, 1, 0},
    {0, 0, 1, 1, 1, 1, 0, 0}
};

static const uint8_t xShape[8][8] = {
    {1, 0, 0, 0, 0, 0, 0, 1},
    {0, 1, 0, 0, 0, 0, 1, 0},
    {0, 0, 1, 0, 0, 1, 0, 0},
    {0, 0, 0, 1, 1, 0, 0, 0},
    {0, 0, 0, 1, 1, 0, 0, 0},
    {0, 0, 1, 0, 0, 1, 0, 0},
    {0, 1, 0, 0, 0, 0, 1, 0},
    {1, 0, 0, 0, 0, 0, 0, 1}
};

/**
 * Get pattern array from pattern ID.
 */
static const uint8_t (*get_pattern_array(uint8_t pattern))[8] {
    switch (pattern) {
        case MATRIX_SHAPE_CIRCLE:
            return circle;
        case MATRIX_SHAPE_X:
            return xShape;
        default:
            return nullptr;  // OFF or unknown
    }
}

/**
 * Display a pattern on one matrix device.
 *
 * @param device Device index (0 or 1)
 * @param pattern 8x8 pattern array (nullptr to clear)
 */
static void display_on_device(uint8_t device, const uint8_t pattern[8][8]) {
    if (!mx) return;

    if (pattern == nullptr) {
        // Clear this device
        for (uint8_t row = 0; row < 8; row++) {
            mx->setRow(device, row, 0);
        }
        return;
    }

    for (uint8_t row = 0; row < 8; row++) {
        uint8_t hwRow = 7 - row;  // Flip row order for hardware
        uint8_t rowBits = 0;

        for (uint8_t col = 0; col < 8; col++) {
            if (pattern[row][col]) {
                rowBits |= (1 << col);
            }
        }

        mx->setRow(device, hwRow, rowBits);
    }
}

void led_matrix_init() {
    // Create matrix instance
    mx = new MD_MAX72XX(
        MD_MAX72XX::FC16_HW,
        MATRIX_DATA_PIN,
        MATRIX_CLK_PIN,
        MATRIX_CS_PIN,
        MATRIX_NUM_DEVICES
    );

    // Initialize
    mx->begin();
    mx->control(MD_MAX72XX::SHUTDOWN, MD_MAX72XX::OFF);
    mx->control(MD_MAX72XX::INTENSITY, MATRIX_DEFAULT_BRIGHTNESS);
    mx->clear();

    // Set default pattern (circle on left, X on right)
    led_matrix_set_patterns(MATRIX_SHAPE_CIRCLE, MATRIX_SHAPE_X);

    DEBUG_PRINTLN("LED matrix initialized");
}

void led_matrix_set_patterns(uint8_t left_pattern, uint8_t right_pattern) {
    if (!mx) return;

    current_left_pattern = left_pattern;
    current_right_pattern = right_pattern;

    // Display left matrix (device 0)
    const uint8_t (*left_arr)[8] = get_pattern_array(left_pattern);
    display_on_device(0, left_arr);

    // Display right matrix (device 1)
    const uint8_t (*right_arr)[8] = get_pattern_array(right_pattern);
    display_on_device(1, right_arr);

    DEBUG_PRINTF("Matrix patterns set: left=%d, right=%d\n", left_pattern, right_pattern);
}

void led_matrix_get_patterns(uint8_t* left_pattern, uint8_t* right_pattern) {
    if (left_pattern) *left_pattern = current_left_pattern;
    if (right_pattern) *right_pattern = current_right_pattern;
}

void led_matrix_clear() {
    if (mx) {
        mx->clear();
    }
    current_left_pattern = MATRIX_SHAPE_OFF;
    current_right_pattern = MATRIX_SHAPE_OFF;
}

void led_matrix_set_brightness(uint8_t brightness) {
    if (!mx) return;

    // Clamp to valid range (0-15)
    if (brightness > 15) brightness = 15;

    mx->control(MD_MAX72XX::INTENSITY, brightness);

    DEBUG_PRINTF("Matrix brightness set to %d\n", brightness);
}
