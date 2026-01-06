#include "uart_handler.h"
#include "config.h"

// Use USB Serial for protocol communication
#define PiSerial Serial

// Receive buffer
static char rx_buffer[UART_RX_BUFFER_SIZE];
static size_t rx_index = 0;

// External function to notify command received (defined in main.cpp)
extern void on_command_received();

/**
 * Parse a command packet.
 *
 * Expected format: $CMD,<servo_target>,<light_cmd>,<flags>\n
 *
 * @param buffer Packet data (null-terminated)
 * @param state Pointer to device state to update
 * @return true if packet was valid and parsed
 */
static bool parse_command_packet(const char* buffer, DeviceState* state) {
    // Check packet type
    if (strncmp(buffer, "$CMD,", 5) != 0) {
        return false;
    }

    // Parse fields
    float servo_target;
    int light_cmd;
    int flags;

    int parsed = sscanf(buffer + 5, "%f,%d,%d", &servo_target, &light_cmd, &flags);

    if (parsed != 3) {
        DEBUG_PRINTF("Parse error: got %d fields\n", parsed);
        return false;
    }

    // Validate ranges
    servo_target = constrain(servo_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    light_cmd = constrain(light_cmd, 0, 2);

    // Update state
    state_update_command(state, servo_target, (uint8_t)light_cmd, (uint8_t)flags);

    // Notify that we received a command (enables status responses)
    on_command_received();

    DEBUG_PRINTF("CMD: servo=%.1f, light=%d, flags=%d\n", servo_target, light_cmd, flags);

    return true;
}

void uart_init() {
    // USB Serial is already initialized in setup()
    // Clear buffers
    rx_index = 0;
    memset(rx_buffer, 0, sizeof(rx_buffer));
}

void uart_receive(DeviceState* state) {
    while (PiSerial.available() > 0) {
        char c = PiSerial.read();

        // Check for packet start
        if (c == PACKET_START_MARKER) {
            // Start new packet
            rx_index = 0;
            rx_buffer[rx_index++] = c;
        }
        // Check for packet end
        else if (c == PACKET_END_MARKER) {
            if (rx_index > 0 && rx_index < UART_RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index] = '\0';  // Null terminate

                // Parse packet
                parse_command_packet(rx_buffer, state);
            }
            rx_index = 0;
        }
        // Add character to buffer
        else if (rx_index > 0 && rx_index < UART_RX_BUFFER_SIZE - 1) {
            rx_buffer[rx_index++] = c;
        }

        // Prevent buffer overflow
        if (rx_index >= UART_RX_BUFFER_SIZE - 1) {
            rx_index = 0;
            DEBUG_PRINTLN("UART RX buffer overflow");
        }
    }
}

// External function to check test status (defined in main.cpp)
extern bool is_test_active();

void uart_send_status(DeviceState* state) {
    // Build status packet
    // Format: $STS,<limit>,<servo_pos>,<light_state>,<flags>,<test>\n

    uint8_t limit = state->input.limit_direction;
    float servo_pos = state->output.servo_angle;
    uint8_t light_state = state->output.light_on ? 1 : 0;
    uint8_t flags = 0;
    uint8_t test_active = is_test_active() ? 1 : 0;

    // Set flags
    if (state->output.servo_moving) {
        flags |= 0x01;  // Bit 0: servo moving
    }

    // Send packet with test indicator
    PiSerial.printf("$STS,%d,%.1f,%d,%d,%d\n", limit, servo_pos, light_state, flags, test_active);

    DEBUG_PRINTF("STS: limit=%d, servo=%.1f, light=%d, test=%d\n", limit, servo_pos, light_state, test_active);
}
