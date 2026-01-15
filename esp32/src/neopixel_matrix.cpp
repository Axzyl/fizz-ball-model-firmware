#include "neopixel_matrix.h"

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
    state->mode = NPM_MODE_OFF;
    state->letter = 'A';
    state->r = 255;
    state->g = 255;
    state->b = 255;
    state->prev_mode = 255;  // Force initial update
    state->prev_letter = 0;
    state->prev_r = 0;
    state->prev_g = 0;
    state->prev_b = 0;
    state->rainbow_offset = 0;
    state->needs_update = true;
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
}

void npm_update(NpmState* state) {
    if (npm_strip == nullptr) return;

    // Check if state changed
    bool changed = state->needs_update ||
                   state->mode != state->prev_mode ||
                   state->letter != state->prev_letter ||
                   state->r != state->prev_r ||
                   state->g != state->prev_g ||
                   state->b != state->prev_b;

    // Rainbow mode always updates
    if (state->mode == NPM_MODE_RAINBOW) {
        npm_update_rainbow(state);
        state->prev_mode = state->mode;
        return;
    }

    if (!changed) return;

    // Handle mode
    switch (state->mode) {
        case NPM_MODE_OFF:
            npm_clear();
            break;

        case NPM_MODE_LETTER:
            npm_display_letter(state->letter, state->r, state->g, state->b);
            break;

        case NPM_MODE_SOLID:
            npm_display_solid(state->r, state->g, state->b);
            break;

        case NPM_MODE_EYE_CLOSED:
            npm_display_eye_closed(state->r, state->g, state->b);
            break;

        case NPM_MODE_EYE_OPEN:
            npm_display_eye_open(state->r, state->g, state->b);
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
