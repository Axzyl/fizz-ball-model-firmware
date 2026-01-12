#include <Arduino.h>
#include <MD_MAX72XX.h>

/* =====================================================
 * ================= RGB LED STRIP =====================
 * ===================================================== */

// ----- RGB PINS -----
#define PIN_R 27
#define PIN_G 14
#define PIN_B 12

// ----- LEDC CHANNELS -----
#define CH_R 0
#define CH_G 1
#define CH_B 2

// ----- PWM SETTINGS -----
#define PWM_FREQ 5000
#define PWM_RES 8 // 0–255

void setRGB(uint8_t r, uint8_t g, uint8_t b)
{
    ledcWrite(CH_R, r);
    ledcWrite(CH_G, g);
    ledcWrite(CH_B, b);
}

// HSV → RGB (simple, no libs)
void setRGB_HSV(uint16_t hue)
{
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

    setRGB(
        (uint8_t)(r * 255),
        (uint8_t)(g * 255),
        (uint8_t)(b * 255));
}

/* =====================================================
 * =============== LED MATRIX (MAX7219) ================
 * ===================================================== */

#define DATA_PIN 25
#define CLK_PIN 32
#define CS_PIN 26
#define NUM_DEVICES 2

MD_MAX72XX mx(
    MD_MAX72XX::FC16_HW,
    DATA_PIN,
    CLK_PIN,
    CS_PIN,
    NUM_DEVICES);

bool swapXO = false;
unsigned long lastSwapTime = 0;

void displayMatrix(const uint8_t (*left)[8],
                   const uint8_t (*right)[8])
{
    for (uint8_t row = 0; row < 8; row++)
    {
        uint8_t hwRow = 7 - row;

        uint8_t rowBitsL = 0;
        uint8_t rowBitsR = 0;

        for (uint8_t col = 0; col < 8; col++)
        {
            if (left[row][col])
                rowBitsL |= (1 << col);
            if (right[row][col])
                rowBitsR |= (1 << col);
        }

        mx.setRow(0, hwRow, rowBitsL);
        mx.setRow(1, hwRow, rowBitsR);
    }
}

const uint8_t circle[8][8] = {
    {0, 0, 1, 1, 1, 1, 0, 0},
    {0, 1, 1, 0, 0, 1, 1, 0},
    {1, 1, 0, 0, 0, 0, 1, 1},
    {1, 0, 0, 0, 0, 0, 0, 1},
    {1, 0, 0, 0, 0, 0, 0, 1},
    {1, 1, 0, 0, 0, 0, 1, 1},
    {0, 1, 1, 0, 0, 1, 1, 0},
    {0, 0, 1, 1, 1, 1, 0, 0}};

const uint8_t xShape[8][8] = {
    {1, 0, 0, 0, 0, 0, 0, 1},
    {0, 1, 0, 0, 0, 0, 1, 0},
    {0, 0, 1, 0, 0, 1, 0, 0},
    {0, 0, 0, 1, 1, 0, 0, 0},
    {0, 0, 0, 1, 1, 0, 0, 0},
    {0, 0, 1, 0, 0, 1, 0, 0},
    {0, 1, 0, 0, 0, 0, 1, 0},
    {1, 0, 0, 0, 0, 0, 0, 1}};

/* =====================================================
 * ===================== SETUP =========================
 * ===================================================== */

void setup()
{
    // ----- MATRIX INIT FIRST (quiet power window) -----
    mx.begin();
    mx.control(MD_MAX72XX::SHUTDOWN, MD_MAX72XX::OFF);
    mx.control(MD_MAX72XX::INTENSITY, 8);
    mx.clear();

    displayMatrix(circle, xShape);

    // Let MAX7219 fully settle
    delay(50);

    // ----- PWM INIT AFTER -----
    ledcSetup(CH_R, PWM_FREQ, PWM_RES);
    ledcSetup(CH_G, PWM_FREQ, PWM_RES);
    ledcSetup(CH_B, PWM_FREQ, PWM_RES);

    ledcAttachPin(PIN_R, CH_R);
    ledcAttachPin(PIN_G, CH_G);
    ledcAttachPin(PIN_B, CH_B);

    setRGB(0, 0, 0);
}

/* =====================================================
 * ====================== LOOP =========================
 * ===================================================== */

void loop()
{
    // -------- Rainbow LED strip (continuous) --------
    static uint16_t hue = 0;
    setRGB_HSV(hue);
    hue = (hue + 1) % 360;

    // -------- Matrix X/O swap every 2 seconds --------
    unsigned long now = millis();
    if (now - lastSwapTime >= 2000)
    {
        lastSwapTime = now;
        swapXO = !swapXO;

        if (swapXO)
            displayMatrix(xShape, circle);
        else
            displayMatrix(circle, xShape);
    }

    delay(20); // controls rainbow speed only
}
