#include "rgb_strip.h"
#include "config.h"

// Current RGB state
static uint8_t current_r = 0;
static uint8_t current_g = 0;
static uint8_t current_b = 0;

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
