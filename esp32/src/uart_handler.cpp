#include "uart_handler.h"
#include "config.h"

// UART instance for Pi communication
HardwareSerial PiSerial(1);  // UART1

// Receive buffer
static char rx_buffer[UART_RX_BUFFER_SIZE];
static size_t rx_index = 0;

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

    DEBUG_PRINTF("CMD: servo=%.1f, light=%d, flags=%d\n", servo_target, light_cmd, flags);

    return true;
}

void uart_init() {
    // Initialize UART1 for Pi communication
    PiSerial.begin(UART_BAUD_RATE, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

    // Clear buffers
    rx_index = 0;
    memset(rx_buffer, 0, sizeof(rx_buffer));

    DEBUG_PRINTLN("UART initialized");
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

void uart_send_status(DeviceState* state) {
    // Build status packet
    // Format: $STS,<limit>,<servo_pos>,<light_state>,<flags>\n

    uint8_t limit = state->input.limit_direction;
    float servo_pos = state->output.servo_angle;
    uint8_t light_state = state->output.light_on ? 1 : 0;
    uint8_t flags = 0;

    // Set flags
    if (state->output.servo_moving) {
        flags |= 0x01;  // Bit 0: servo moving
    }

    // Send packet
    PiSerial.printf("$STS,%d,%.1f,%d,%d\n", limit, servo_pos, light_state, flags);

    DEBUG_PRINTF("STS: limit=%d, servo=%.1f, light=%d\n", limit, servo_pos, light_state);
}
