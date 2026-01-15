#include "led_matrix.h"
#include "config.h"
#include "scroll_texts.h"
#include <MD_MAX72XX.h>
#include <string.h>

// Matrix instance
static MD_MAX72XX* mx = nullptr;

// Current patterns for each matrix (for pattern mode)
static uint8_t current_left_pattern = MATRIX_SHAPE_OFF;
static uint8_t current_right_pattern = MATRIX_SHAPE_OFF;

// Total display width (2 matrices x 8 columns)
#define DISPLAY_WIDTH (MATRIX_NUM_DEVICES * 8)

// Scroll state - store text and position
static char scroll_text_buffer[64];
static int scroll_text_len = 0;
static int scroll_pos = 0;

// Pattern definitions (8x8 bitmaps) for pattern mode
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
 */
static void display_on_device(uint8_t device, const uint8_t pattern[8][8]) {
    if (!mx) return;

    if (pattern == nullptr) {
        for (uint8_t row = 0; row < 8; row++) {
            mx->setRow(device, row, 0);
        }
        return;
    }

    for (uint8_t row = 0; row < 8; row++) {
        uint8_t hwRow = 7 - row;
        uint8_t rowBits = 0;

        for (uint8_t col = 0; col < 8; col++) {
            if (pattern[row][col]) {
                rowBits |= (1 << col);
            }
        }

        mx->setRow(device, hwRow, rowBits);
    }
}

/**
 * Reverse a string in place for proper scroll direction.
 */
static void reverse_string(char* str, int len) {
    for (int i = 0; i < len / 2; i++) {
        char tmp = str[i];
        str[i] = str[len - 1 - i];
        str[len - 1 - i] = tmp;
    }
}

/**
 * Render a single character rotated 90 degrees clockwise.
 * After rotation: text scrolls vertically, characters are 8 tall x charWidth wide
 * row_offset: vertical position (0 = top of display)
 */
static void render_char_rotated(char c, int row_offset) {
    if (!mx) return;

    // Get character width and data from library
    uint8_t charWidth = mx->getChar(c, sizeof(scroll_text_buffer), (uint8_t*)scroll_text_buffer);

    // For 90° CW rotation:
    // Original col -> becomes row (from bottom)
    // Original row -> becomes col (from left)
    // Physical display: 8 cols wide, MATRIX_NUM_DEVICES*8 rows tall

    for (uint8_t srcCol = 0; srcCol < charWidth; srcCol++) {
        uint8_t colData = mx->getColumn(srcCol);  // Get the column we just rendered

        // This column becomes a row after 90° CW rotation
        int destRow = row_offset + srcCol;

        if (destRow >= 0 && destRow < DISPLAY_WIDTH) {
            // Each bit in colData becomes a pixel in the rotated row
            // Bit 0 (top) -> rightmost pixel (col 7)
            // Bit 7 (bottom) -> leftmost pixel (col 0)
            for (int bit = 0; bit < 8; bit++) {
                if (colData & (1 << bit)) {
                    int destCol = 7 - bit;  // Flip for CW rotation
                    mx->setPoint(destRow, destCol, true);
                }
            }
        }
    }
}

/**
 * Render current scroll frame with 90° CW rotation.
 * Text scrolls vertically through the rotated display.
 */
static void render_scroll_frame() {
    if (!mx) return;

    mx->clear();

    // With 90° CW rotation:
    // - Display is 8 pixels wide, DISPLAY_WIDTH pixels tall
    // - Text scrolls vertically (row position changes)
    // - Each character is ~6-8 rows tall after rotation

    int row_pos = scroll_pos;
    for (int i = 0; i < scroll_text_len; i++) {
        char c = scroll_text_buffer[i];

        // Get character width (which becomes height after rotation)
        uint8_t charWidth = mx->getChar(c, 8, nullptr);
        if (charWidth == 0) charWidth = 6;  // Default width

        // Only render if character is visible
        if (row_pos > -8 && row_pos < DISPLAY_WIDTH) {
            // Render character directly with rotation
            // Use setPoint for precise control
            uint8_t buf[8];
            mx->getChar(c, 8, buf);

            for (uint8_t srcCol = 0; srcCol < charWidth && srcCol < 8; srcCol++) {
                int destRow = row_pos + srcCol;
                if (destRow >= 0 && destRow < DISPLAY_WIDTH) {
                    for (int bit = 0; bit < 8; bit++) {
                        if (buf[srcCol] & (1 << bit)) {
                            int destCol = 7 - bit;
                            mx->setPoint(destRow, destCol, true);
                        }
                    }
                }
            }
        }

        row_pos += charWidth + 1;  // Move to next character position (with 1 pixel gap)
    }
}

void led_matrix_init() {
    // Try different hardware types - GENERIC_HW is most compatible
    // Other options: FC16_HW, PAROLA_HW, ICSTATION_HW
    mx = new MD_MAX72XX(
        MD_MAX72XX::GENERIC_HW,
        MATRIX_DATA_PIN,
        MATRIX_CLK_PIN,
        MATRIX_CS_PIN,
        MATRIX_NUM_DEVICES
    );

    mx->begin();
    mx->control(MD_MAX72XX::INTENSITY, MATRIX_DEFAULT_BRIGHTNESS);
    mx->clear();

    // Quick test - display all LEDs on briefly to verify hardware works
    Serial.printf("[MTX] Testing %d matrices (GENERIC_HW) - all LEDs on...\n", MATRIX_NUM_DEVICES);
    for (int dev = 0; dev < MATRIX_NUM_DEVICES; dev++) {
        for (int row = 0; row < 8; row++) {
            mx->setRow(dev, row, 0xFF);
        }
    }
    delay(500);  // Show for 500ms
    mx->clear();

    Serial.println("[MTX] LED matrix initialized");
}

void led_matrix_scroll_init(MatrixScrollState* state) {
    state->mode = MATRIX_MODE_SCROLL;  // Start in scroll mode
    state->scroll_last_update = 0;
    state->scroll_speed = MATRIX_SCROLL_SPEED;
    state->current_text_id = 0;

    // Reset static scroll variables
    scroll_text_len = 0;
    scroll_pos = 0;
    scroll_text_buffer[0] = '\0';
}

void led_matrix_set_patterns(uint8_t left_pattern, uint8_t right_pattern) {
    if (!mx) return;

    current_left_pattern = left_pattern;
    current_right_pattern = right_pattern;

    const uint8_t (*left_arr)[8] = get_pattern_array(left_pattern);
    display_on_device(0, left_arr);

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

    if (brightness > 15) brightness = 15;
    mx->control(MD_MAX72XX::INTENSITY, brightness);

    DEBUG_PRINTF("Matrix brightness set to %d\n", brightness);
}

void led_matrix_set_scroll_text(MatrixScrollState* state, uint8_t text_id) {
    // Get text string from scroll_texts.h
    const char* text = nullptr;
    if (text_id < SCROLL_TEXT_COUNT) {
        text = SCROLL_TEXTS[text_id];
    } else {
        text = "?";
    }

    // Copy text (no reversal needed for rotated display)
    scroll_text_len = strlen(text);
    if (scroll_text_len > 63) scroll_text_len = 63;

    strncpy(scroll_text_buffer, text, scroll_text_len);
    scroll_text_buffer[scroll_text_len] = '\0';

    // Calculate total text height (in rotated space, ~7 pixels per char + 1 gap)
    int text_height = scroll_text_len * 7;

    // Start position off screen (negative = above display)
    scroll_pos = -text_height;

    state->scroll_last_update = millis();
    state->current_text_id = text_id;
}

void led_matrix_update_scroll(MatrixScrollState* state) {
    if (!mx) {
        return;
    }
    if (state->mode != MATRIX_MODE_SCROLL) {
        return;
    }

    uint32_t now = millis();

    // Initialize scroll text on first run with a random text
    if (scroll_text_len == 0) {
        uint8_t initial_text_id = random(0, SCROLL_TEXT_COUNT);
        led_matrix_set_scroll_text(state, initial_text_id);
        Serial.printf("[MTX] Init scroll text id=%d: %s\n", initial_text_id, scroll_text_buffer);
    }

    // Check if it's time to advance the scroll
    if (now - state->scroll_last_update >= state->scroll_speed) {
        state->scroll_last_update = now;

        // Advance scroll position (scroll direction: left to right)
        scroll_pos++;

        // Check for wrap - when text has scrolled off screen, pick new text
        if (scroll_pos > DISPLAY_WIDTH) {
            uint8_t new_text_id = random(0, SCROLL_TEXT_COUNT);
            led_matrix_set_scroll_text(state, new_text_id);
            Serial.printf("[MTX] New scroll text id=%d\n", new_text_id);
        }
    }

    // Render current frame
    render_scroll_frame();
}

void led_matrix_set_scroll_mode(MatrixScrollState* state, bool enabled) {
    state->mode = enabled ? MATRIX_MODE_SCROLL : MATRIX_MODE_PATTERN;

    if (!enabled && mx) {
        // Clear display when switching to pattern mode
        mx->clear();
    }
}
