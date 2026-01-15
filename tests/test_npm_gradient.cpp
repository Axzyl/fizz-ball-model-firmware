/**
 * Minimal test for NeoPixel 5x5 matrix red-blue gradient.
 *
 * To use: Replace esp32/src/main.cpp with this file temporarily,
 * or create a separate PlatformIO environment for testing.
 */

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// Pin configuration (match your hardware)
#define NPM_DATA_PIN    4
#define NPM_NUM_PIXELS  25
#define NPM_BRIGHTNESS  50

// Gradient colors
#define COLOR1_R  255
#define COLOR1_G  0
#define COLOR1_B  0

#define COLOR2_R  0
#define COLOR2_G  0
#define COLOR2_B  255

#define GRADIENT_SPEED  5

// NeoPixel strip
Adafruit_NeoPixel strip(NPM_NUM_PIXELS, NPM_DATA_PIN, NEO_GRB + NEO_KHZ800);

// Gradient state
uint16_t gradient_position = 0;

// Linear interpolation
uint8_t lerp8(uint8_t a, uint8_t b, uint8_t t) {
    return a + (((int16_t)b - a) * t) >> 8;
}

// Get interpolation factor from position (0-510 -> 0-255-0)
uint8_t position_to_t(uint16_t pos) {
    if (pos <= 255) {
        return (uint8_t)pos;
    } else {
        return (uint8_t)(510 - pos);
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println("NPM Gradient Test Starting...");

    strip.begin();
    strip.setBrightness(NPM_BRIGHTNESS);
    strip.clear();
    strip.show();

    Serial.println("Red -> Blue gradient running");
}

void loop() {
    // Calculate interpolation factor
    uint8_t t = position_to_t(gradient_position);

    // Interpolate colors
    uint8_t r = lerp8(COLOR1_R, COLOR2_R, t);
    uint8_t g = lerp8(COLOR1_G, COLOR2_G, t);
    uint8_t b = lerp8(COLOR1_B, COLOR2_B, t);

    // Set all pixels to gradient color
    uint32_t color = strip.Color(r, g, b);
    for (int i = 0; i < NPM_NUM_PIXELS; i++) {
        strip.setPixelColor(i, color);
    }
    strip.show();

    // Advance position (wraps at 510)
    gradient_position += GRADIENT_SPEED;
    if (gradient_position > 510) {
        gradient_position -= 510;
    }

    // Debug output every ~1 second
    static uint32_t last_print = 0;
    if (millis() - last_print > 1000) {
        Serial.printf("pos=%d, t=%d, RGB=(%d,%d,%d)\n",
                      gradient_position, t, r, g, b);
        last_print = millis();
    }

    delay(20);  // 50Hz update rate
}
