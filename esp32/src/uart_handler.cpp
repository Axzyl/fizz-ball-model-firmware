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
 * Expected formats:
 *   Basic: $CMD,<servo1>,<servo2>,<servo3>,<light_cmd>,<flags>\n
 *   Extended: $CMD,<servo1>,<servo2>,<servo3>,<light_cmd>,<flags>,<r>,<g>,<b>,<left_pattern>,<right_pattern>\n
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

    // Parse fields - try extended format first
    float servo1_target, servo2_target, servo3_target;
    int light_cmd;
    int flags;
    int rgb_r = 0, rgb_g = 0, rgb_b = 0;
    int matrix_left = 1;   // Default: circle
    int matrix_right = 2;  // Default: X

    int parsed = sscanf(buffer + 5, "%f,%f,%f,%d,%d,%d,%d,%d,%d,%d",
                        &servo1_target, &servo2_target, &servo3_target,
                        &light_cmd, &flags,
                        &rgb_r, &rgb_g, &rgb_b, &matrix_left, &matrix_right);

    if (parsed < 5) {
        DEBUG_PRINTF("Parse error: got %d fields\n", parsed);
        return false;
    }

    // Validate ranges
    servo1_target = constrain(servo1_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    servo2_target = constrain(servo2_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    servo3_target = constrain(servo3_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    light_cmd = constrain(light_cmd, 0, 2);
    rgb_r = constrain(rgb_r, 0, 255);
    rgb_g = constrain(rgb_g, 0, 255);
    rgb_b = constrain(rgb_b, 0, 255);

    // Update state based on format
    if (parsed >= 10) {
        // Extended format with RGB and both patterns
        state_update_command_extended(state,
                                      servo1_target, servo2_target, servo3_target,
                                      (uint8_t)light_cmd, (uint8_t)flags,
                                      (uint8_t)rgb_r, (uint8_t)rgb_g, (uint8_t)rgb_b,
                                      (uint8_t)matrix_left, (uint8_t)matrix_right);
        DEBUG_PRINTF("CMD: servos=(%.1f,%.1f,%.1f), light=%d, RGB=(%d,%d,%d), matrix=(%d,%d)\n",
                     servo1_target, servo2_target, servo3_target,
                     light_cmd, rgb_r, rgb_g, rgb_b, matrix_left, matrix_right);
    } else {
        // Basic format
        state_update_command(state, servo1_target, servo2_target, servo3_target,
                            (uint8_t)light_cmd, (uint8_t)flags);
        DEBUG_PRINTF("CMD: servos=(%.1f,%.1f,%.1f), light=%d, flags=%d\n",
                     servo1_target, servo2_target, servo3_target, light_cmd, flags);
    }

    // Notify that we received a command (enables status responses)
    on_command_received();

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

        // Debug: show incoming characters
        DEBUG_PRINTF("RX char: '%c' (0x%02X)\n", c >= 32 ? c : '?', (uint8_t)c);

        // Check for packet start
        if (c == PACKET_START_MARKER) {
            // Start new packet
            rx_index = 0;
            rx_buffer[rx_index++] = c;
            DEBUG_PRINTLN("Packet start detected");
        }
        // Check for packet end
        else if (c == PACKET_END_MARKER) {
            if (rx_index > 0 && rx_index < UART_RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index] = '\0';  // Null terminate

                DEBUG_PRINTF("Packet received: %s\n", rx_buffer);

                // Parse packet
                if (parse_command_packet(rx_buffer, state)) {
                    DEBUG_PRINTLN("Packet parsed OK");
                } else {
                    DEBUG_PRINTLN("Packet parse FAILED");
                }
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
    // Format: $STS,<limit>,<servo1>,<servo2>,<servo3>,<light_state>,<flags>,<test>\n

    uint8_t limit = state->input.limit_direction;
    float servo1_pos = state->output.servo_angles[0];
    float servo2_pos = state->output.servo_angles[1];
    float servo3_pos = state->output.servo_angles[2];
    uint8_t light_state = state->output.light_on ? 1 : 0;
    uint8_t flags = 0;
    uint8_t test_active = is_test_active() ? 1 : 0;

    // Set flags - any servo moving sets bit 0
    for (int i = 0; i < NUM_SERVOS; i++) {
        if (state->output.servo_moving[i]) {
            flags |= 0x01;
            break;
        }
    }

    // Send packet with all servo positions
    PiSerial.printf("$STS,%d,%.1f,%.1f,%.1f,%d,%d,%d\n",
                    limit, servo1_pos, servo2_pos, servo3_pos,
                    light_state, flags, test_active);

    DEBUG_PRINTF("STS: limit=%d, servos=(%.1f,%.1f,%.1f), light=%d, test=%d\n",
                 limit, servo1_pos, servo2_pos, servo3_pos, light_state, test_active);
}
