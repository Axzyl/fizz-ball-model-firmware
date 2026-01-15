#include <Adafruit_NeoPixel.h>

#define PIN        13   // Data pin connected to DI
#define NUMPIXELS  8    // The ring has 8 LEDs
#define BRIGHTNESS 50   // Moderate brightness

Adafruit_NeoPixel ring(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

uint16_t waveOffset = 0; // Offset for the wave animation

// Convert HSV to RGB color
// hue: 0-255, sat: 0-255, val: 0-255
uint32_t hsvToColor(uint8_t hue, uint8_t sat, uint8_t val) {
  uint8_t region = hue / 43;
  uint8_t remainder = (hue - (region * 43)) * 6;

  uint8_t p = (val * (255 - sat)) >> 8;
  uint8_t q = (val * (255 - ((sat * remainder) >> 8))) >> 8;
  uint8_t t = (val * (255 - ((sat * (255 - remainder)) >> 8))) >> 8;

  switch (region) {
    case 0:  return ring.Color(val, t, p);
    case 1:  return ring.Color(q, val, p);
    case 2:  return ring.Color(p, val, t);
    case 3:  return ring.Color(p, q, val);
    case 4:  return ring.Color(t, p, val);
    default: return ring.Color(val, p, q);
  }
}

void setup() {
  ring.begin();
  ring.setBrightness(BRIGHTNESS);
  ring.show(); // Start with all LEDs off
}

void loop() {
  // RGB wave pattern - each LED gets a different hue based on position + offset
  for (int i = 0; i < NUMPIXELS; i++) {
    // Calculate hue for each pixel
    // Spread the rainbow across all pixels and shift by waveOffset
    uint8_t hue = ((i * 256 / NUMPIXELS) + waveOffset) & 0xFF;
    
    // Set the pixel color using full saturation and brightness
    ring.setPixelColor(i, hsvToColor(hue, 255, 255));
  }
  
  ring.show();  // Push the data to the ring
  
  waveOffset += 2;  // Increment offset to animate the wave (adjust for speed)
  delay(20);        // Small delay for smooth animation
}