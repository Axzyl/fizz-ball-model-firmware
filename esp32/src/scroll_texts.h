#ifndef SCROLL_TEXTS_H
#define SCROLL_TEXTS_H

// =============================================================================
// Scroll Text Definitions for NeoPixel 5x5 Matrix
// =============================================================================
// Predefined text strings that can be scrolled across the matrix.
// Each text is identified by an ID (0-15) sent via UART.
// =============================================================================

// Scroll text IDs
#define SCROLL_TEXT_SCHRODINGER  0   // "SCHRODINGER"
#define SCROLL_TEXT_ALIVE        1   // "ALIVE"
#define SCROLL_TEXT_DEAD         2   // "DEAD"
#define SCROLL_TEXT_HELLO        3   // "HELLO"
#define SCROLL_TEXT_MEOW         4   // "MEOW"
#define SCROLL_TEXT_CAT          5   // "CAT"
#define SCROLL_TEXT_QUANTUM      6   // "QUANTUM"
#define SCROLL_TEXT_BOX          7   // "BOX"
#define SCROLL_TEXT_CHEERS       8   // "CHEERS"
#define SCROLL_TEXT_DRINK        9   // "DRINK"
#define SCROLL_TEXT_CUSTOM       10  // Reserved for future use
#define SCROLL_TEXT_COUNT        11  // Number of predefined texts

// Maximum text length (including null terminator)
#define SCROLL_TEXT_MAX_LEN      16

// Predefined scroll texts (must match IDs above)
static const char* const SCROLL_TEXTS[SCROLL_TEXT_COUNT] = {
    "SCHRODINGER",   // 0
    "ALIVE",         // 1
    "DEAD",          // 2
    "HELLO",         // 3
    "MEOW",          // 4
    "CAT",           // 5
    "QUANTUM",       // 6
    "BOX",           // 7
    "CHEERS",        // 8
    "DRINK",         // 9
    "?",             // 10 - placeholder
};

// Scroll animation speeds (ms per column shift)
#define SCROLL_SPEED_SLOW    200   // Slow scrolling
#define SCROLL_SPEED_MEDIUM  100   // Medium scrolling (default)
#define SCROLL_SPEED_FAST    50    // Fast scrolling

// 5x5 Column-based font for smooth scrolling
// Each character is 5 columns wide, each column is 5 bits (one per row)
// Bit 0 = top row, Bit 4 = bottom row
// Characters are stored as 5 consecutive bytes (columns left to right)
// Gap column (0x00) is added between characters during scrolling

static const uint8_t SCROLL_FONT_5X5[26][5] = {
    // A
    {0b01110, 0b10001, 0b11111, 0b10001, 0b10001},
    // B
    {0b11110, 0b10001, 0b11110, 0b10001, 0b11110},
    // C
    {0b01111, 0b10000, 0b10000, 0b10000, 0b01111},
    // D
    {0b11110, 0b10001, 0b10001, 0b10001, 0b11110},
    // E
    {0b11111, 0b10000, 0b11110, 0b10000, 0b11111},
    // F
    {0b11111, 0b10000, 0b11110, 0b10000, 0b10000},
    // G
    {0b01110, 0b10000, 0b10111, 0b10001, 0b01110},
    // H
    {0b10001, 0b10001, 0b11111, 0b10001, 0b10001},
    // I
    {0b11111, 0b00100, 0b00100, 0b00100, 0b11111},
    // J
    {0b00111, 0b00001, 0b00001, 0b10001, 0b01110},
    // K
    {0b10001, 0b10010, 0b11100, 0b10010, 0b10001},
    // L
    {0b10000, 0b10000, 0b10000, 0b10000, 0b11111},
    // M
    {0b10001, 0b11011, 0b10101, 0b10001, 0b10001},
    // N
    {0b10001, 0b11001, 0b10101, 0b10011, 0b10001},
    // O
    {0b01110, 0b10001, 0b10001, 0b10001, 0b01110},
    // P
    {0b11110, 0b10001, 0b11110, 0b10000, 0b10000},
    // Q
    {0b01110, 0b10001, 0b10101, 0b10010, 0b01101},
    // R
    {0b11110, 0b10001, 0b11110, 0b10010, 0b10001},
    // S
    {0b01111, 0b10000, 0b01110, 0b00001, 0b11110},
    // T
    {0b11111, 0b00100, 0b00100, 0b00100, 0b00100},
    // U
    {0b10001, 0b10001, 0b10001, 0b10001, 0b01110},
    // V
    {0b10001, 0b10001, 0b10001, 0b01010, 0b00100},
    // W
    {0b10001, 0b10001, 0b10101, 0b11011, 0b10001},
    // X
    {0b10001, 0b01010, 0b00100, 0b01010, 0b10001},
    // Y
    {0b10001, 0b01010, 0b00100, 0b00100, 0b00100},
    // Z
    {0b11111, 0b00010, 0b00100, 0b01000, 0b11111},
};

// Special characters (space, question mark, etc.)
static const uint8_t SCROLL_FONT_SPACE[5] = {0b00000, 0b00000, 0b00000, 0b00000, 0b00000};
static const uint8_t SCROLL_FONT_QUESTION[5] = {0b01110, 0b00001, 0b00110, 0b00000, 0b00100};

#endif // SCROLL_TEXTS_H
