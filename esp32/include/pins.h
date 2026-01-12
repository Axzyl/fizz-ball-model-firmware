#ifndef PINS_H
#define PINS_H

// =============================================================================
// Hardware Pin Configuration
// =============================================================================
// Edit this file to match your hardware wiring.
// All GPIO pin assignments are defined here for easy modification.
// =============================================================================

// -----------------------------------------------------------------------------
// Servo Motors (3 servos)
// -----------------------------------------------------------------------------
#define NUM_SERVOS 3

// NOTE: GPIO 6-11 are used by internal flash on ESP32-WROOM-32 - avoid them!
// Safe GPIOs: 2, 4, 5, 12-19, 21-23, 25-27, 32-33
#define SERVO_1_PIN 2  // Servo 1 PWM output
#define SERVO_2_PIN 15 // Servo 2 PWM output
#define SERVO_3_PIN 13 // Servo 3 PWM output

// -----------------------------------------------------------------------------
// Limit Switch
// -----------------------------------------------------------------------------
#define LIMIT_SWITCH_PIN 33 // Input from limit switch (active LOW)

// -----------------------------------------------------------------------------
// Test/Status LED
// -----------------------------------------------------------------------------
#define TEST_LED_PIN 9 // Built-in or external status LED

// -----------------------------------------------------------------------------
// RGB LED Strip (Common Anode or PWM-controlled)
// -----------------------------------------------------------------------------
#define RGB_PIN_R 27 // Red channel PWM
#define RGB_PIN_G 14 // Green channel PWM
#define RGB_PIN_B 12 // Blue channel PWM

// -----------------------------------------------------------------------------
// LED Matrix (MAX7219 SPI)
// -----------------------------------------------------------------------------
#define MATRIX_DATA_PIN 25   // DIN (Data In / MOSI)
#define MATRIX_CLK_PIN 32    // CLK (Clock / SCK)
#define MATRIX_CS_PIN 26     // CS (Chip Select / Load)
#define MATRIX_NUM_DEVICES 2 // Number of 8x8 matrices chained

// =============================================================================
// Pin Usage Summary
// =============================================================================
//
//  GPIO  | Function           | Direction | Notes
// -------|--------------------|-----------|---------------------------------
//    4   | Servo 1 PWM        | Output    | 50Hz PWM signal
//    5   | Servo 3 PWM        | Output    | 50Hz PWM signal
//    7   | Servo 2 PWM        | Output    | 50Hz PWM signal
//    9   | Test LED           | Output    | Status indicator
//   12   | RGB Blue           | Output    | PWM (5kHz)
//   14   | RGB Green          | Output    | PWM (5kHz)
//   25   | Matrix Data (DIN)  | Output    | SPI MOSI
//   26   | Matrix CS (Load)   | Output    | SPI chip select
//   27   | RGB Red            | Output    | PWM (5kHz)
//   32   | Matrix Clock       | Output    | SPI SCK
//   33   | Limit Switch       | Input     | Internal pullup, active LOW
//
// IMPORTANT: Avoid GPIO 6-11 on ESP32-WROOM-32 (used by internal flash)
// =============================================================================

#endif // PINS_H
