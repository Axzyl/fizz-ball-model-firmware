#include "rgb_strip.h"
#include "config.h"
#include "color_utils.h"

// Current RGB state
static uint8_t current_r = 0;
static uint8_t current_g = 0;
static uint8_t current_b = 0;

void rgb_state_init(RgbState* state) {
    state->mode = RGB_MODE_SOLID;
    state->r = 0;
    state->g = 0;
    state->b = 0;
    state->r2 = 0;
    state->g2 = 0;
    state->b2 = 0;
    state->gradient_speed = 10;
    state->gradient_position = 0;
    state->rainbow_hue = 0;
    state->prev_mode = 255;  // Force initial update
    state->prev_r = 0;
    state->prev_g = 0;
    state->prev_b = 0;
    state->needs_update = true;
}

void rgb_set_mode(RgbState* state, uint8_t mode, uint8_t r, uint8_t g, uint8_t b,
                  uint8_t r2, uint8_t g2, uint8_t b2, uint8_t speed) {
    // Check if anything changed
    if (state->mode != mode ||
        state->r != r ||
        state->g != g ||
        state->b != b ||
        state->r2 != r2 ||
        state->g2 != g2 ||
        state->b2 != b2 ||
        state->gradient_speed != speed) {
        state->needs_update = true;

        // Reset gradient animation on mode change
        if (state->mode != mode) {
            state->gradient_position = 0;
        }
    }

    state->mode = mode;
    state->r = r;
    state->g = g;
    state->b = b;
    state->r2 = r2;
    state->g2 = g2;
    state->b2 = b2;
    state->gradient_speed = (speed > 0) ? speed : 1;  // Ensure minimum speed of 1
}

void rgb_update(RgbState* state) {
    // Handle animated modes
    switch (state->mode) {
        case RGB_MODE_RAINBOW: {
            // Rainbow cycle through hue
            rgb_set_hsv(state->rainbow_hue);
            state->rainbow_hue = (state->rainbow_hue + 2) % 360;
            state->prev_mode = state->mode;
            return;
        }

        case RGB_MODE_GRADIENT: {
            // Ping-pong gradient between two colors
            uint8_t t = gradient_position_to_t(state->gradient_position);

            uint8_t r, g, b;
            gradient_color(t, state->r, state->g, state->b,
                          state->r2, state->g2, state->b2, &r, &g, &b);

            // Skip update if lerp produced black (edge case bug workaround)
            if (r == 0 && g == 0 && b == 0) {
                state->gradient_position = gradient_advance_pingpong(
                    state->gradient_position, state->gradient_speed);
                return;
            }

            rgb_set(r, g, b);

            state->gradient_position = gradient_advance_pingpong(
                state->gradient_position, state->gradient_speed);
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

    // Handle static modes (RGB_MODE_SOLID is 0)
    if (state->mode == RGB_MODE_SOLID) {
        rgb_set(state->r, state->g, state->b);
    }

    // Update previous state
    state->prev_mode = state->mode;
    state->prev_r = state->r;
    state->prev_g = state->g;
    state->prev_b = state->b;
    state->needs_update = false;
}

void rgb_init()
{
    // Setup PWM channels
    ledcSetup(RGB_CH_R, RGB_PWM_FREQ, RGB_PWM_RES);
    ledcSetup(RGB_CH_G, RGB_PWM_FREQ, RGB_PWM_RES);
    ledcSetup(RGB_CH_B, RGB_PWM_FREQ, RGB_PWM_RES);

    // Attach pins to channels
    ledcAttachPin(RGB_PIN_R, RGB_CH_R);
    ledcAttachPin(RGB_PIN_G, RGB_CH_G);
    ledcAttachPin(RGB_PIN_B, RGB_CH_B);

    // Start with LED off
    rgb_off();

    DEBUG_PRINTLN("RGB strip initialized");
}

void rgb_set(uint8_t r, uint8_t g, uint8_t b)
{
    current_r = r;
    current_g = g;
    current_b = b;

    ledcWrite(RGB_CH_R, r);
    ledcWrite(RGB_CH_G, g);
    ledcWrite(RGB_CH_B, b);
}

void rgb_set_hsv(uint16_t hue)
{
    // HSV to RGB conversion (S=1, V=1)
    float h = hue / 60.0f;
    int i = (int)h;
    float f = h - i;

    float r, g, b;

    switch (i % 6)
    {
    case 0:
        r = 1;
        g = f;
        b = 0;
        break;
    case 1:
        r = 1 - f;
        g = 1;
        b = 0;
        break;
    case 2:
        r = 0;
        g = 1;
        b = f;
        break;
    case 3:
        r = 0;
        g = 1 - f;
        b = 1;
        break;
    case 4:
        r = f;
        g = 0;
        b = 1;
        break;
    default:
        r = 1;
        g = 0;
        b = 1 - f;
        break;
    }

    rgb_set(
        (uint8_t)(r * 255),
        (uint8_t)(g * 255),
        (uint8_t)(b * 255));
}

void rgb_off()
{
    rgb_set(0, 0, 0);
}

void rgb_get_state(uint8_t *r, uint8_t *g, uint8_t *b)
{
    if (r)
        *r = current_r;
    if (g)
        *g = current_g;
    if (b)
        *b = current_b;
}
