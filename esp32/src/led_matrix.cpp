#include "led_matrix.h"
#include "config.h"
#include "scroll_texts.h"
#include <MD_MAX72XX.h>

// Matrix instance
static MD_MAX72XX* mx = nullptr;

// Current patterns for each matrix (for pattern mode)
static uint8_t current_left_pattern = MATRIX_SHAPE_OFF;
static uint8_t current_right_pattern = MATRIX_SHAPE_OFF;

// Total display width (2 matrices x 8 columns)
#define DISPLAY_WIDTH 16

// 8x5 Font for A-Z (8 rows, 5 columns per character)
// Each entry is 5 bytes representing 5 columns, each byte is 8 bits for 8 rows
// Bit 0 = top row, Bit 7 = bottom row
static const uint8_t FONT_8X5[26][5] = {
    // A
    {0x7E, 0x11, 0x11, 0x11, 0x7E},
    // B
    {0x7F, 0x49, 0x49, 0x49, 0x36},
    // C
    {0x3E, 0x41, 0x41, 0x41, 0x22},
    // D
    {0x7F, 0x41, 0x41, 0x41, 0x3E},
    // E
    {0x7F, 0x49, 0x49, 0x49, 0x41},
    // F
    {0x7F, 0x09, 0x09, 0x09, 0x01},
    // G
    {0x3E, 0x41, 0x49, 0x49, 0x7A},
    // H
    {0x7F, 0x08, 0x08, 0x08, 0x7F},
    // I
    {0x00, 0x41, 0x7F, 0x41, 0x00},
    // J
    {0x20, 0x40, 0x41, 0x3F, 0x01},
    // K
    {0x7F, 0x08, 0x14, 0x22, 0x41},
    // L
    {0x7F, 0x40, 0x40, 0x40, 0x40},
    // M
    {0x7F, 0x02, 0x0C, 0x02, 0x7F},
    // N
    {0x7F, 0x04, 0x08, 0x10, 0x7F},
    // O
    {0x3E, 0x41, 0x41, 0x41, 0x3E},
    // P
    {0x7F, 0x09, 0x09, 0x09, 0x06},
    // Q
    {0x3E, 0x41, 0x51, 0x21, 0x5E},
    // R
    {0x7F, 0x09, 0x19, 0x29, 0x46},
    // S
    {0x46, 0x49, 0x49, 0x49, 0x31},
    // T
    {0x01, 0x01, 0x7F, 0x01, 0x01},
    // U
    {0x3F, 0x40, 0x40, 0x40, 0x3F},
    // V
    {0x1F, 0x20, 0x40, 0x20, 0x1F},
    // W
    {0x3F, 0x40, 0x38, 0x40, 0x3F},
    // X
    {0x63, 0x14, 0x08, 0x14, 0x63},
    // Y
    {0x07, 0x08, 0x70, 0x08, 0x07},
    // Z
    {0x61, 0x51, 0x49, 0x45, 0x43},
};

// Space character (blank column)
static const uint8_t FONT_SPACE = 0x00;

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
 * Get column data for a character.
 */
static uint8_t get_char_column(char c, int col) {
    if (c >= 'A' && c <= 'Z') {
        int idx = c - 'A';
        if (col >= 0 && col < 5) {
            return FONT_8X5[idx][col];
        }
    } else if (c >= 'a' && c <= 'z') {
        int idx = c - 'a';
        if (col >= 0 && col < 5) {
            return FONT_8X5[idx][col];
        }
    } else if (c == ' ') {
        return FONT_SPACE;
    }
    return 0;
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
    state->scroll_buffer_len = 0;
    state->scroll_position = 0;
    state->scroll_last_update = 0;
    state->scroll_speed = MATRIX_SCROLL_SPEED;
    state->current_text_id = 0;
    memset(state->scroll_buffer, 0, sizeof(state->scroll_buffer));
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

    // Build scroll buffer: each character is 5 columns + 1 gap column
    // Add display width blank columns at start and end for smooth scroll
    uint16_t buf_pos = 0;

    // Leading blank columns (display width)
    for (int i = 0; i < DISPLAY_WIDTH && buf_pos < MATRIX_SCROLL_BUFFER_SIZE; i++) {
        state->scroll_buffer[buf_pos++] = 0;
    }

    // Add each character
    for (int i = 0; text[i] != '\0' && buf_pos < MATRIX_SCROLL_BUFFER_SIZE - 6; i++) {
        char c = text[i];

        if (c == ' ') {
            // Space is 3 blank columns
            for (int j = 0; j < 3 && buf_pos < MATRIX_SCROLL_BUFFER_SIZE; j++) {
                state->scroll_buffer[buf_pos++] = 0;
            }
        } else {
            // Add 5 columns for this character
            for (int col = 0; col < 5; col++) {
                state->scroll_buffer[buf_pos++] = get_char_column(c, col);
            }
            // Add gap column between characters
            state->scroll_buffer[buf_pos++] = 0;
        }
    }

    // Trailing blank columns (display width)
    for (int i = 0; i < DISPLAY_WIDTH && buf_pos < MATRIX_SCROLL_BUFFER_SIZE; i++) {
        state->scroll_buffer[buf_pos++] = 0;
    }

    state->scroll_buffer_len = buf_pos;
    state->scroll_position = 0;
    state->scroll_last_update = millis();
    state->current_text_id = text_id;
}

void led_matrix_update_scroll(MatrixScrollState* state) {
    if (!mx) return;
    if (state->mode != MATRIX_MODE_SCROLL) return;

    uint32_t now = millis();

    // Initialize scroll buffer on first run with a random text
    if (state->scroll_buffer_len == 0) {
        uint8_t initial_text_id = random(0, SCROLL_TEXT_COUNT);
        led_matrix_set_scroll_text(state, initial_text_id);
    }

    // Check if it's time to advance the scroll
    if (now - state->scroll_last_update >= state->scroll_speed) {
        state->scroll_last_update = now;
        state->scroll_position++;

        // Check for wrap - pick a new random text
        if (state->scroll_position >= state->scroll_buffer_len) {
            uint8_t new_text_id = random(0, SCROLL_TEXT_COUNT);
            led_matrix_set_scroll_text(state, new_text_id);
            state->scroll_position = 0;
        }
    }

    // Render current DISPLAY_WIDTH columns to the matrices
    // The display is 2 matrices, each 8 columns wide
    // Device 0 = columns 0-7, Device 1 = columns 8-15
    for (int display_col = 0; display_col < DISPLAY_WIDTH; display_col++) {
        // Get column from buffer
        uint16_t buf_col = state->scroll_position + display_col;
        if (buf_col >= state->scroll_buffer_len) {
            buf_col = buf_col % state->scroll_buffer_len;
        }

        uint8_t column_data = state->scroll_buffer[buf_col];

        // Determine which device and which column within that device
        // Columns scroll right to left, so we need to map correctly
        // display_col 0 = leftmost column on display (device 1, col 7)
        // display_col 15 = rightmost column on display (device 0, col 0)
        int device = (display_col < 8) ? 1 : 0;
        int dev_col = (display_col < 8) ? (7 - display_col) : (15 - display_col);

        mx->setColumn(device, dev_col, column_data);
    }
}

void led_matrix_set_scroll_mode(MatrixScrollState* state, bool enabled) {
    state->mode = enabled ? MATRIX_MODE_SCROLL : MATRIX_MODE_PATTERN;

    if (!enabled && mx) {
        // Clear display when switching to pattern mode
        mx->clear();
    }
}
