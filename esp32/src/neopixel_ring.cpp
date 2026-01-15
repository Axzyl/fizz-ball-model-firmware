#include "neopixel_ring.h"

// NeoPixel strip object
static Adafruit_NeoPixel* npr_strip = nullptr;

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

    return npr_strip->Color(r, g, b);
}

void npr_init(uint8_t pin) {
    if (npr_strip != nullptr) {
        delete npr_strip;
    }
    npr_strip = new Adafruit_NeoPixel(NPR_NUM_PIXELS, pin, NEO_GRB + NEO_KHZ800);
    npr_strip->begin();
    npr_strip->setBrightness(NPR_BRIGHTNESS);
    npr_strip->clear();  // Clear any random data in LED memory
    npr_strip->show();
}

void npr_state_init(NprState* state) {
    state->mode = NPR_MODE_OFF;
    state->r = 0;  // OFF - no color
    state->g = 0;
    state->b = 0;
    state->prev_mode = 255;  // Force initial update
    state->prev_r = 0;
    state->prev_g = 0;
    state->prev_b = 0;
    state->animation_offset = 0;
    state->breathe_value = 0;
    state->breathe_direction = 1;
    state->last_update = 0;
    state->needs_update = true;
}

void npr_set_mode(NprState* state, uint8_t mode, uint8_t r, uint8_t g, uint8_t b) {
    // Check if anything changed
    if (state->mode != mode ||
        state->r != r ||
        state->g != g ||
        state->b != b) {
        state->needs_update = true;

        // Reset animation state on mode change
        if (state->mode != mode) {
            state->animation_offset = 0;
            state->breathe_value = 0;
            state->breathe_direction = 1;
        }
    }

    state->mode = mode;
    state->r = r;
    state->g = g;
    state->b = b;
}

void npr_update(NprState* state) {
    if (npr_strip == nullptr) return;

    uint32_t now = millis();

    // Handle animated modes
    switch (state->mode) {
        case NPR_MODE_RAINBOW: {
            // Rainbow wave - always animate
            for (int i = 0; i < NPR_NUM_PIXELS; i++) {
                uint16_t hue = ((i * 256 / NPR_NUM_PIXELS) + state->animation_offset) & 0xFF;
                npr_strip->setPixelColor(i, hsvToColor(hue, 255, 255));
            }
            npr_strip->show();
            state->animation_offset = (state->animation_offset + NPR_RAINBOW_SPEED) & 0xFF;
            state->prev_mode = state->mode;
            return;
        }

        case NPR_MODE_CHASE: {
            // Chase animation - single LED moves around
            if (now - state->last_update >= NPR_CHASE_SPEED) {
                npr_strip->clear();
                uint32_t color = npr_strip->Color(state->r, state->g, state->b);
                npr_strip->setPixelColor(state->animation_offset % NPR_NUM_PIXELS, color);
                npr_strip->show();
                state->animation_offset++;
                state->last_update = now;
            }
            state->prev_mode = state->mode;
            return;
        }

        case NPR_MODE_BREATHE: {
            // Breathing effect - fade in and out
            // Update brightness based on sine-like curve
            state->breathe_value += state->breathe_direction * NPR_BREATHE_SPEED;

            if (state->breathe_value >= 255) {
                state->breathe_value = 255;
                state->breathe_direction = -1;
            } else if (state->breathe_value <= 0) {
                state->breathe_value = 0;
                state->breathe_direction = 1;
            }

            // Apply color with breathing brightness
            uint8_t br = (state->r * state->breathe_value) / 255;
            uint8_t bg = (state->g * state->breathe_value) / 255;
            uint8_t bb = (state->b * state->breathe_value) / 255;

            uint32_t color = npr_strip->Color(br, bg, bb);
            for (int i = 0; i < NPR_NUM_PIXELS; i++) {
                npr_strip->setPixelColor(i, color);
            }
            npr_strip->show();
            state->prev_mode = state->mode;
            return;
        }

        case NPR_MODE_SPINNER: {
            // Spinner - two opposite LEDs spinning
            if (now - state->last_update >= NPR_SPINNER_SPEED) {
                npr_strip->clear();
                uint32_t color = npr_strip->Color(state->r, state->g, state->b);
                int pos1 = state->animation_offset % NPR_NUM_PIXELS;
                int pos2 = (pos1 + NPR_NUM_PIXELS / 2) % NPR_NUM_PIXELS;
                npr_strip->setPixelColor(pos1, color);
                npr_strip->setPixelColor(pos2, color);
                npr_strip->show();
                state->animation_offset++;
                state->last_update = now;
            }
            state->prev_mode = state->mode;
            return;
        }

        default:
            break;
    }

    // Check if non-animated state changed
    bool changed = state->needs_update ||
                   state->mode != state->prev_mode ||
                   state->r != state->prev_r ||
                   state->g != state->prev_g ||
                   state->b != state->prev_b;

    if (!changed) return;

    // Handle static modes
    switch (state->mode) {
        case NPR_MODE_OFF:
            npr_clear();
            break;

        case NPR_MODE_SOLID:
            npr_display_solid(state->r, state->g, state->b);
            break;

        default:
            npr_clear();
            break;
    }

    // Update previous state
    state->prev_mode = state->mode;
    state->prev_r = state->r;
    state->prev_g = state->g;
    state->prev_b = state->b;
    state->needs_update = false;
}

void npr_set_brightness(uint8_t brightness) {
    if (npr_strip != nullptr) {
        npr_strip->setBrightness(brightness);
    }
}

void npr_clear(void) {
    if (npr_strip != nullptr) {
        npr_strip->clear();
        npr_strip->show();
    }
}

void npr_display_solid(uint8_t r, uint8_t g, uint8_t b) {
    if (npr_strip == nullptr) return;

    uint32_t color = npr_strip->Color(r, g, b);
    for (int i = 0; i < NPR_NUM_PIXELS; i++) {
        npr_strip->setPixelColor(i, color);
    }
    npr_strip->show();
}
