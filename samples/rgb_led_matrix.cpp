#include <Adafruit_NeoPixel.h>

// --- Configuration ---
#define PIN        13   // Your data pin
#define NUMPIXELS  25   // 5x5 Matrix = 25 LEDs
#define BRIGHTNESS 50   // Set brightness (0 to 255). Start low to save power!

// Initialize the strip object
// Parameter 1 = Number of pixels in strip
// Parameter 2 = Arduino pin number (most are valid)
// Parameter 3 = Pixel type flags, add together as needed:
//   NEO_GRB     Pixels are wired for GRB bitstream (most NeoPixel products)
//   NEO_KHZ800  800 KHz bitstream (most NeoPixel products w/WS2812 LEDs)
Adafruit_NeoPixel matrix(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

// 5x5 font bitmaps for A-Z (each row is a 5-bit pattern)
// Pixel mapping: Row 0: 0-4, Row 1: 5-9, Row 2: 10-14, Row 3: 15-19, Row 4: 20-24
const uint8_t font5x5[26][5] = {
  {0b01110, 0b10001, 0b11111, 0b10001, 0b10001}, // A
  {0b11110, 0b10001, 0b11110, 0b10001, 0b11110}, // B
  {0b01111, 0b10000, 0b10000, 0b10000, 0b01111}, // C
  {0b11110, 0b10001, 0b10001, 0b10001, 0b11110}, // D
  {0b11111, 0b10000, 0b11110, 0b10000, 0b11111}, // E
  {0b11111, 0b10000, 0b00111, 0b10000, 0b00001}, // F
  {0b01110, 0b10000, 0b11001, 0b10001, 0b01110}, // G
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

// Display a letter (A-Z) on the 5x5 matrix with a specified color
void displayLetter(char letter, uint8_t r, uint8_t g, uint8_t b) {
  matrix.clear();
  
  // Convert to uppercase and validate
  if (letter >= 'a' && letter <= 'z') {
    letter = letter - 'a' + 'A';
  }
  if (letter < 'A' || letter > 'Z') {
    matrix.show();
    return; // Invalid letter
  }
  
  int index = letter - 'A';
  uint32_t color = matrix.Color(r, g, b);
  
  // Draw the letter from bitmap
  for (int row = 0; row < 5; row++) {
    for (int col = 0; col < 5; col++) {
      if (font5x5[index][row] & (0b00001 << col)) {
        int pixel = row * 5 + col;
        matrix.setPixelColor(pixel, color);
      }
    }
  }
  matrix.show();
}

// Display a red 'X' on the 5x5 matrix
void displayX() {
  displayLetter('X', 255, 0, 0);
}

// Display a green 'O' (circle) on the 5x5 matrix
void displayO() {
  displayLetter('O', 0, 255, 0);
}

void setup() {
  matrix.begin();           // Initialize the object
  matrix.setBrightness(BRIGHTNESS);
  matrix.show();            // Initialize all pixels to 'off'
}

void loop() {
  displayLetter('F', 0, 0, 255); // Display 'F' in blue
  delay(500);
  displayLetter('I', 255, 255, 0); // Display 'I' in yellow
  delay(500);
  displayLetter('Z', 255, 0, 255); // Display 'Z' in magenta
  delay(500);
  displayLetter('Z', 0, 255, 255); // Display 'Z' in cyan
  delay(500);
  displayLetter('A', 160, 32, 240); // Display 'T' in white
  delay(500);
}