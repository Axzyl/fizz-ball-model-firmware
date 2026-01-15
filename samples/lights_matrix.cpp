#include <MD_MAX72XX.h>

// ===== HARDWARE CONFIG =====
#define DATA_PIN 25
#define CLK_PIN 32
#define CS_PIN 26
#define NUM_DEVICES 1 // THREE matrices (24x8 total)

// FC-16 style modules
MD_MAX72XX mx = MD_MAX72XX(
    MD_MAX72XX::FC16_HW,
    DATA_PIN,
    CLK_PIN,
    CS_PIN,
    NUM_DEVICES);

// ===== SCROLLING TEXT CONFIG =====
String scrollText = "WE FIZZ OUR PANTS";
int scrollPos = 0;

unsigned long lastScroll = 0;
const unsigned long scrollDelay = 100; // ms (lower = faster)

// ===== SCROLL FUNCTION =====
void scrollString(const String &text)
{
    mx.clear();

    int totalCols = NUM_DEVICES * 8;

    for (int i = 0; i < text.length(); i++)
    {
        int col = scrollPos + i * 8;

        if (col > -8 && col < totalCols)
        {
            mx.setChar(col, text[i]);
        }
    }

    // ←→ reverse scroll direction
    scrollPos++;

    int textWidth = text.length() * 8;
    if (scrollPos > totalCols)
        scrollPos = -textWidth;
}

String reverseString(const String &s)
{
    String out = "";
    for (int i = s.length() - 1; i >= 0; i--)
    {
        out += s[i];
    }
    return out;
}

void setup()
{
    mx.begin();
    mx.control(MD_MAX72XX::INTENSITY, 8);
    mx.clear();

    // Reverse once so left→right scroll reads correctly
    scrollText = reverseString(scrollText);

    scrollPos = -scrollText.length() * 8;
}

void loop()
{
    if (millis() - lastScroll > scrollDelay)
    {
        lastScroll = millis();
        scrollString(scrollText);
    }
}
