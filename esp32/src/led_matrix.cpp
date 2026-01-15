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
 * Render current scroll frame using library's setChar.
 */
static void render_scroll_frame() {
    if (!mx) return;

    mx->clear();

    for (int i = 0; i < scroll_text_len; i++) {
        int col = scroll_pos + i * 8;

        // Only render if character is visible
        if (col > -8 && col < DISPLAY_WIDTH) {
            mx->setChar(col, scroll_text_buffer[i]);
        }
    }
}

void led_matrix_init() {
    mx = new MD_MAX72XX(
        MD_MAX72XX::FC16_HW,
        MATRIX_DATA_PIN,
        MATRIX_CLK_PIN,
        MATRIX_CS_PIN,
        MATRIX_NUM_DEVICES
    );

    mx->begin();
    mx->control(MD_MAX72XX::SHUTDOWN, MD_MAX72XX::OFF);
    mx->control(MD_MAX72XX::INTENSITY, MATRIX_DEFAULT_BRIGHTNESS);
    mx->clear();

    DEBUG_PRINTLN("LED matrix initialized");
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

    // Copy and reverse text for proper scroll direction (like sample does)
    scroll_text_len = strlen(text);
    if (scroll_text_len > 63) scroll_text_len = 63;

    strncpy(scroll_text_buffer, text, scroll_text_len);
    scroll_text_buffer[scroll_text_len] = '\0';

    // Reverse so left→right scroll reads correctly
    reverse_string(scroll_text_buffer, scroll_text_len);

    // Start position off screen (negative = text width)
    int text_width = scroll_text_len * 8;
    scroll_pos = -text_width;

    state->scroll_last_update = millis();
    state->current_text_id = text_id;
}

void led_matrix_update_scroll(MatrixScrollState* state) {
    if (!mx) return;
    if (state->mode != MATRIX_MODE_SCROLL) return;

    uint32_t now = millis();

    // Initialize scroll text on first run with a random text
    if (scroll_text_len == 0) {
        uint8_t initial_text_id = random(0, SCROLL_TEXT_COUNT);
        led_matrix_set_scroll_text(state, initial_text_id);
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
