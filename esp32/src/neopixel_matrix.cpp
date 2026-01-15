#include "neopixel_matrix.h"
#include "scroll_texts.h"
#include <string.h>

// NeoPixel strip object
static Adafruit_NeoPixel* npm_strip = nullptr;

// 5x5 font bitmaps for A-Z (each row is a 5-bit pattern)
// Pixel mapping: Row 0: 0-4, Row 1: 5-9, Row 2: 10-14, Row 3: 15-19, Row 4: 20-24
static const uint8_t font5x5[26][5] = {
    {0b01110, 0b10001, 0b11111, 0b10001, 0b10001}, // A
    {0b11110, 0b10001, 0b11110, 0b10001, 0b11110}, // B
    {0b01111, 0b10000, 0b10000, 0b10000, 0b01111}, // C
    {0b11110, 0b10001, 0b10001, 0b10001, 0b11110}, // D
    {0b11111, 0b10000, 0b11110, 0b10000, 0b11111}, // E
    {0b11111, 0b10000, 0b11110, 0b10000, 0b10000}, // F
    {0b01110, 0b10000, 0b10111, 0b10001, 0b01110}, // G
    {0b10001, 0b10001, 0b11111, 0b10001, 0b10001}, // H
    {0b11111, 0b00100, 0b00100, 0b00100, 0b11111}, // I
    {0b00111, 0b00001, 0b00001, 0b10001, 0b01110}, // J
    {0b10001, 0b10010, 0b11100, 0b10010, 0b10001}, // K
    {0b10000, 0b10000, 0b10000, 0b10000, 0b11111}, // L
    {0b10001, 0b11011, 0b10101, 0b10001, 0b10001}, // M
    {0b10001, 0b11001, 0b10101, 0b10011, 0b10001}, // N
    {0b01110, 0b10001, 0b10001, 0b10001, 0b01110}, // O
    {0b11110, 0b10001, 0b11110, 0b10000, 0b10000}, // P
    {0b01110, 0b10001, 0b10101, 0b10010, 0b01101}, // Q
    {0b11110, 0b10001, 0b11110, 0b10010, 0b10001}, // R
    {0b01111, 0b10000, 0b01110, 0b00001, 0b11110}, // S
    {0b11111, 0b00100, 0b00100, 0b00100, 0b00100}, // T
    {0b10001, 0b10001, 0b10001, 0b10001, 0b01110}, // U
    {0b10001, 0b10001, 0b10001, 0b01010, 0b00100}, // V
    {0b10001, 0b10001, 0b10101, 0b11011, 0b10001}, // W
    {0b10001, 0b01010, 0b00100, 0b01010, 0b10001}, // X
    {0b10001, 0b01010, 0b00100, 0b00100, 0b00100}, // Y
    {0b11111, 0b00010, 0b00100, 0b01000, 0b11111}  // Z
};

// Eye closed pattern (horizontal line across middle - sleeping eye)
static const uint8_t eye_closed_pattern[5] = {
    0b00000,
    0b00000,
    0b11111,  // Middle row lit
    0b00000,
    0b00000
};

// Eye open pattern (circle/dot in center - alert eye)
static const uint8_t eye_open_pattern[5] = {
    0b01110,
    0b10001,
    0b10101,  // Center pixel lit
    0b10001,
    0b01110
};

// Circle pattern (for ALIVE state - filled circle)
static const uint8_t circle_pattern[5] = {
    0b01110,
    0b11111,
    0b11111,
    0b11111,
    0b01110
};

// X pattern (for DEAD state)
static const uint8_t x_pattern[5] = {
    0b10001,
    0b01010,
    0b00100,
    0b01010,
    0b10001
};

// Convert HSV to RGB color
static uint32_t hsvToColor(uint16_t hue, uint8_t sat, uint8_t val) {
    uint8_t r, g, b;
    uint8_t region = hue / 43;
    uint8_t remainder = (hue - (region * 43)) * 6;

    uint8_t p = (val * (255 - sat)) >> 8;
    uint8_t q = (val * (255 - ((sat * remainder) >> 8))) >> 8;
    uint8_t t = (val * (255 - ((sat * (255 - remainder)) >> 8))) >> 8;

    switch (region) {
        case 0:  r = val; g = t;   b = p;   break;
        case 1:  r = q;   g = val; b = p;   break;
        case 2:  r = p;   g = val; b = t;   break;
        case 3:  r = p;   g = q;   b = val; break;
        case 4:  r = t;   g = p;   b = val; break;
        default: r = val; g = p;   b = q;   break;
    }

    return npm_strip->Color(r, g, b);
}

void npm_init(uint8_t pin) {
    if (npm_strip != nullptr) {
        delete npm_strip;
    }
    npm_strip = new Adafruit_NeoPixel(NPM_NUM_PIXELS, pin, NEO_GRB + NEO_KHZ800);
    npm_strip->begin();
    npm_strip->setBrightness(NPM_BRIGHTNESS);
    npm_strip->clear();  // Clear any random data in LED memory
    npm_strip->show();
}

void npm_state_init(NpmState* state) {
    state->mode = NPM_MODE_OFF;  // Default to OFF
    state->letter = 'A';
    state->r = 0;
    state->g = 0;
    state->b = 0;
    state->prev_mode = 255;  // Force initial update
    state->prev_letter = 0;
    state->prev_r = 0;
    state->prev_g = 0;
    state->prev_b = 0;
    state->rainbow_offset = 0;
    state->needs_update = true;

    // Initialize scroll state
    state->scroll_text_id = 0;
    state->scroll_buffer_len = 0;
    state->scroll_position = 0;
    state->scroll_last_update = 0;
    state->scroll_speed = NPM_SCROLL_SPEED;
    state->scroll_looping = true;
    state->prev_scroll_text_id = 255;
    memset(state->scroll_buffer, 0, sizeof(state->scroll_buffer));
}

void npm_set_mode(NpmState* state, uint8_t mode, char letter, uint8_t r, uint8_t g, uint8_t b) {
    // Check if anything changed
    if (state->mode != mode ||
        state->letter != letter ||
        state->r != r ||
        state->g != g ||
        state->b != b) {
        state->needs_update = true;
    }

    state->mode = mode;
    state->letter = letter;
    state->r = r;
    state->g = g;
    state->b = b;

    // For scroll mode, interpret letter as text ID
    // '0'-'9' maps to text IDs 0-9, 'A'-'Z' maps to 0-25 as fallback
    if (mode == NPM_MODE_SCROLL) {
        uint8_t text_id = 0;
        if (letter >= '0' && letter <= '9') {
            text_id = letter - '0';
        } else if (letter >= 'A' && letter <= 'Z') {
            text_id = letter - 'A';
        } else if (letter >= 'a' && letter <= 'z') {
            text_id = letter - 'a';
        }
        state->scroll_text_id = text_id;
    }
}

void npm_update(NpmState* state) {
    if (npm_strip == nullptr) return;

    // Check if mode changed
    bool mode_changed = (state->mode != state->prev_mode);

    switch (state->mode) {
        case NPM_MODE_OFF:
            if (mode_changed || state->needs_update) {
                npm_clear();
            }
            break;

        case NPM_MODE_LETTER:
            if (mode_changed || state->needs_update ||
                state->letter != state->prev_letter ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_letter(state->letter, state->r, state->g, state->b);
            }
            break;

        case NPM_MODE_SCROLL:
            npm_update_scroll(state);
            break;

        case NPM_MODE_RAINBOW:
            npm_update_rainbow(state);
            break;

        case NPM_MODE_SOLID:
            if (mode_changed || state->needs_update ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_solid(state->r, state->g, state->b);
            }
            break;

        case NPM_MODE_EYE_CLOSED:
            if (mode_changed || state->needs_update ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_eye_closed(state->r, state->g, state->b);
            }
            break;

        case NPM_MODE_EYE_OPEN:
            if (mode_changed || state->needs_update ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_eye_open(state->r, state->g, state->b);
            }
            break;

        case NPM_MODE_CIRCLE:
            if (mode_changed || state->needs_update ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_circle(state->r, state->g, state->b);
            }
            break;

        case NPM_MODE_X:
            if (mode_changed || state->needs_update ||
                state->r != state->prev_r || state->g != state->prev_g || state->b != state->prev_b) {
                npm_display_x(state->r, state->g, state->b);
            }
            break;

        default:
            npm_clear();
            break;
    }

    // Update previous state
    state->prev_mode = state->mode;
    state->prev_letter = state->letter;
    state->prev_r = state->r;
    state->prev_g = state->g;
    state->prev_b = state->b;
    state->needs_update = false;
}

void npm_set_brightness(uint8_t brightness) {
    if (npm_strip != nullptr) {
        npm_strip->setBrightness(brightness);
    }
}

void npm_clear(void) {
    if (npm_strip != nullptr) {
        npm_strip->clear();
        npm_strip->show();
    }
}

void npm_display_letter(char letter, uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    npm_strip->clear();

    // Convert to uppercase and validate
    if (letter >= 'a' && letter <= 'z') {
        letter = letter - 'a' + 'A';
    }
    if (letter < 'A' || letter > 'Z') {
        npm_strip->show();
        return;
    }

    int index = letter - 'A';
    uint32_t color = npm_strip->Color(r, g, b);

    // Draw the letter from bitmap (same bit order as sample)
    for (int row = 0; row < 5; row++) {
        for (int col = 0; col < 5; col++) {
            if (font5x5[index][row] & (0b00001 << col)) {
                int pixel = row * 5 + col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }
    npm_strip->show();
}

void npm_display_solid(uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    uint32_t color = npm_strip->Color(r, g, b);
    for (int i = 0; i < NPM_NUM_PIXELS; i++) {
        npm_strip->setPixelColor(i, color);
    }
    npm_strip->show();
}

void npm_display_eye_closed(uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    npm_strip->clear();
    uint32_t color = npm_strip->Color(r, g, b);

    // Draw closed eye pattern (same bit order as sample)
    for (int row = 0; row < 5; row++) {
        for (int col = 0; col < 5; col++) {
            if (eye_closed_pattern[row] & (0b00001 << col)) {
                int pixel = row * 5 + col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }
    npm_strip->show();
}

void npm_display_eye_open(uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    npm_strip->clear();
    uint32_t color = npm_strip->Color(r, g, b);

    // Draw open eye pattern (same bit order as sample)
    for (int row = 0; row < 5; row++) {
        for (int col = 0; col < 5; col++) {
            if (eye_open_pattern[row] & (0b00001 << col)) {
                int pixel = row * 5 + col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }
    npm_strip->show();
}

void npm_display_circle(uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    npm_strip->clear();
    uint32_t color = npm_strip->Color(r, g, b);

    // Draw circle pattern
    for (int row = 0; row < 5; row++) {
        for (int col = 0; col < 5; col++) {
            if (circle_pattern[row] & (0b00001 << col)) {
                int pixel = row * 5 + col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }
    npm_strip->show();
}

void npm_display_x(uint8_t r, uint8_t g, uint8_t b) {
    if (npm_strip == nullptr) return;

    npm_strip->clear();
    uint32_t color = npm_strip->Color(r, g, b);

    // Draw X pattern
    for (int row = 0; row < 5; row++) {
        for (int col = 0; col < 5; col++) {
            if (x_pattern[row] & (0b00001 << col)) {
                int pixel = row * 5 + col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }
    npm_strip->show();
}

void npm_update_rainbow(NpmState* state) {
    if (npm_strip == nullptr) return;

    // Create rainbow across all pixels
    for (int i = 0; i < NPM_NUM_PIXELS; i++) {
        uint16_t hue = (state->rainbow_offset + (i * 256 / NPM_NUM_PIXELS)) & 0xFF;
        npm_strip->setPixelColor(i, hsvToColor(hue, 255, 255));
    }
    npm_strip->show();

    // Advance animation
    state->rainbow_offset = (state->rainbow_offset + NPM_RAINBOW_SPEED) & 0xFF;
}

// Helper: Get column data for a character (5 rows packed into a byte)
static uint8_t get_char_column(char c, int col) {
    if (c >= 'A' && c <= 'Z') {
        // Convert row-based font to column
        int idx = c - 'A';
        uint8_t column = 0;
        for (int row = 0; row < 5; row++) {
            // Check if this row has a pixel in this column
            if (SCROLL_FONT_5X5[idx][row] & (1 << (4 - col))) {
                column |= (1 << row);
            }
        }
        return column;
    } else if (c >= 'a' && c <= 'z') {
        return get_char_column(c - 'a' + 'A', col);
    } else if (c == ' ') {
        return 0;  // Empty column
    } else if (c == '?') {
        uint8_t column = 0;
        for (int row = 0; row < 5; row++) {
            if (SCROLL_FONT_QUESTION[row] & (1 << (4 - col))) {
                column |= (1 << row);
            }
        }
        return column;
    }
    return 0;  // Unknown character
}

void npm_set_scroll_text(NpmState* state, uint8_t text_id, uint8_t r, uint8_t g, uint8_t b) {
    // Get text string
    const char* text = nullptr;
    if (text_id < SCROLL_TEXT_COUNT) {
        text = SCROLL_TEXTS[text_id];
    } else {
        text = "?";  // Fallback
    }

    // Build scroll buffer: each character is 5 columns + 1 gap column
    // Add 5 blank columns at start and end for smooth scroll on/off
    uint16_t buf_pos = 0;

    // Leading blank columns (matrix width)
    for (int i = 0; i < 5 && buf_pos < NPM_SCROLL_BUFFER_SIZE; i++) {
        state->scroll_buffer[buf_pos++] = 0;
    }

    // Add each character
    for (int i = 0; text[i] != '\0' && buf_pos < NPM_SCROLL_BUFFER_SIZE - 6; i++) {
        char c = text[i];

        // Add 5 columns for this character
        for (int col = 0; col < 5; col++) {
            state->scroll_buffer[buf_pos++] = get_char_column(c, col);
        }

        // Add gap column between characters
        state->scroll_buffer[buf_pos++] = 0;
    }

    // Trailing blank columns (matrix width)
    for (int i = 0; i < 5 && buf_pos < NPM_SCROLL_BUFFER_SIZE; i++) {
        state->scroll_buffer[buf_pos++] = 0;
    }

    state->scroll_buffer_len = buf_pos;
    state->scroll_position = 0;
    state->scroll_last_update = millis();
    state->scroll_text_id = text_id;
    state->r = r;
    state->g = g;
    state->b = b;
}

void npm_update_scroll(NpmState* state) {
    if (npm_strip == nullptr) return;

    uint32_t now = millis();

    // Initialize scroll buffer on first run with a random text
    if (state->scroll_buffer_len == 0) {
        uint8_t initial_text_id = random(0, SCROLL_TEXT_COUNT);
        npm_set_scroll_text(state, initial_text_id, state->r, state->g, state->b);
    }

    // Check if it's time to advance the scroll
    if (now - state->scroll_last_update >= state->scroll_speed) {
        state->scroll_last_update = now;
        state->scroll_position++;

        // Check for wrap - pick a new random text
        if (state->scroll_position >= state->scroll_buffer_len) {
            uint8_t new_text_id = random(0, SCROLL_TEXT_COUNT);
            npm_set_scroll_text(state, new_text_id, state->r, state->g, state->b);
            state->scroll_position = 0;
        }
    }

    // Render current 5 columns to the matrix
    npm_strip->clear();
    uint32_t color = npm_strip->Color(state->r, state->g, state->b);

    for (int display_col = 0; display_col < 5; display_col++) {
        // Get column from buffer (with wrapping)
        uint16_t buf_col = state->scroll_position + display_col;
        if (buf_col >= state->scroll_buffer_len) {
            buf_col = buf_col % state->scroll_buffer_len;
        }

        uint8_t column_data = state->scroll_buffer[buf_col];

        // Render this column (5 rows)
        for (int row = 0; row < 5; row++) {
            if (column_data & (1 << row)) {
                // Calculate pixel index (row * 5 + col)
                int pixel = row * 5 + display_col;
                npm_strip->setPixelColor(pixel, color);
            }
        }
    }

    npm_strip->show();
}
