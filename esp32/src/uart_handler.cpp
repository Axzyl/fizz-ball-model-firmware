#include "uart_handler.h"
#include "config.h"
#include "valve_safety.h"

// Use USB Serial for protocol communication
#define PiSerial Serial

// Receive buffer
static char rx_buffer[UART_RX_BUFFER_SIZE];
static size_t rx_index = 0;

// External function to notify command received (defined in main.cpp)
extern void on_command_received();

// External valve state (defined in main.cpp)
extern ValveState g_valve_state;

// External functions for valve state (defined in main.cpp)
extern bool get_valve_open();
extern bool get_valve_enabled();
extern uint32_t get_valve_open_ms();

/**
 * Parse a servo command packet.
 * Format: $SRV,<s1>,<s2>,<s3>
 */
static bool parse_servo_packet(const char* buffer, DeviceState* state) {
    float servo1_target, servo2_target, servo3_target;

    int parsed = sscanf(buffer + 5, "%f,%f,%f",
                        &servo1_target, &servo2_target, &servo3_target);

    if (parsed != 3) {
        DEBUG_PRINTF("SRV parse error: got %d fields\n", parsed);
        return false;
    }

    // Validate ranges
    servo1_target = constrain(servo1_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    servo2_target = constrain(servo2_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    servo3_target = constrain(servo3_target, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);

    // Update state
    state->command.target_servo_angles[0] = servo1_target;
    state->command.target_servo_angles[1] = servo2_target;
    state->command.target_servo_angles[2] = servo3_target;
    state->command.last_command_time = millis();
    state->command.connected = true;

    DEBUG_PRINTF("SRV: (%.1f,%.1f,%.1f)\n", servo1_target, servo2_target, servo3_target);
    return true;
}

/**
 * Parse a light command packet.
 * Format: $LGT,<cmd>
 */
static bool parse_light_packet(const char* buffer, DeviceState* state) {
    int light_cmd;

    int parsed = sscanf(buffer + 5, "%d", &light_cmd);

    if (parsed != 1) {
        DEBUG_PRINTF("LGT parse error: got %d fields\n", parsed);
        return false;
    }

    light_cmd = constrain(light_cmd, 0, 2);
    state->command.light_command = (uint8_t)light_cmd;

    DEBUG_PRINTF("LGT: %d\n", light_cmd);
    return true;
}

/**
 * Parse an RGB strip command packet.
 * Format: $RGB,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]
 * Extended format adds gradient parameters (backwards compatible)
 */
static bool parse_rgb_packet(const char* buffer, DeviceState* state) {
    int mode, r, g, b;
    int r2 = 0, g2 = 0, b2 = 0, speed = 10;  // Defaults for gradient

    int parsed = sscanf(buffer + 5, "%d,%d,%d,%d,%d,%d,%d,%d",
                        &mode, &r, &g, &b, &r2, &g2, &b2, &speed);

    if (parsed < 4) {
        DEBUG_PRINTF("RGB parse error: got %d fields\n", parsed);
        return false;
    }

    mode = constrain(mode, 0, 2);  // 0=OFF, 1=SOLID, 2=GRADIENT
    r = constrain(r, 0, 255);
    g = constrain(g, 0, 255);
    b = constrain(b, 0, 255);
    r2 = constrain(r2, 0, 255);
    g2 = constrain(g2, 0, 255);
    b2 = constrain(b2, 0, 255);
    speed = constrain(speed, 1, 50);

    state->command.rgb_mode = (uint8_t)mode;
    state->command.rgb_r = (uint8_t)r;
    state->command.rgb_g = (uint8_t)g;
    state->command.rgb_b = (uint8_t)b;
    state->command.rgb_r2 = (uint8_t)r2;
    state->command.rgb_g2 = (uint8_t)g2;
    state->command.rgb_b2 = (uint8_t)b2;
    state->command.rgb_gradient_speed = (uint8_t)speed;

    DEBUG_PRINTF("RGB: mode=%d, (%d,%d,%d)->(%d,%d,%d) speed=%d\n",
                 mode, r, g, b, r2, g2, b2, speed);
    return true;
}

/**
 * Parse a MAX7219 matrix command packet.
 * Format: $MTX,<left>,<right>
 */
static bool parse_matrix_packet(const char* buffer, DeviceState* state) {
    int left, right;

    int parsed = sscanf(buffer + 5, "%d,%d", &left, &right);

    if (parsed != 2) {
        DEBUG_PRINTF("MTX parse error: got %d fields\n", parsed);
        return false;
    }

    state->command.matrix_left = (uint8_t)left;
    state->command.matrix_right = (uint8_t)right;

    DEBUG_PRINTF("MTX: (%d,%d)\n", left, right);
    return true;
}

/**
 * Parse a NeoPixel matrix command packet.
 * Format: $NPM,<mode>,<letter>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]
 * Extended format adds gradient parameters (backwards compatible)
 */
static bool parse_npm_packet(const char* buffer, DeviceState* state) {
    int mode;
    char letter;
    int r, g, b;
    int r2 = 0, g2 = 0, b2 = 0, speed = 10;  // Defaults for gradient

    int parsed = sscanf(buffer + 5, "%d,%c,%d,%d,%d,%d,%d,%d,%d",
                        &mode, &letter, &r, &g, &b, &r2, &g2, &b2, &speed);

    if (parsed < 5) {
        DEBUG_PRINTF("NPM parse error: got %d fields\n", parsed);
        return false;
    }

    mode = constrain(mode, 0, 10);
    r = constrain(r, 0, 255);
    g = constrain(g, 0, 255);
    b = constrain(b, 0, 255);
    r2 = constrain(r2, 0, 255);
    g2 = constrain(g2, 0, 255);
    b2 = constrain(b2, 0, 255);
    speed = constrain(speed, 1, 50);

    state->command.npm_mode = (uint8_t)mode;
    state->command.npm_letter = letter;
    state->command.npm_r = (uint8_t)r;
    state->command.npm_g = (uint8_t)g;
    state->command.npm_b = (uint8_t)b;
    state->command.npm_r2 = (uint8_t)r2;
    state->command.npm_g2 = (uint8_t)g2;
    state->command.npm_b2 = (uint8_t)b2;
    state->command.npm_gradient_speed = (uint8_t)speed;

    DEBUG_PRINTF("NPM: mode=%d, letter=%c, (%d,%d,%d)->(%d,%d,%d) speed=%d\n",
                 mode, letter, r, g, b, r2, g2, b2, speed);
    return true;
}

/**
 * Parse a NeoPixel ring command packet.
 * Format: $NPR,<mode>,<r>,<g>,<b>[,<r2>,<g2>,<b2>,<speed>]
 * Extended format adds gradient parameters (backwards compatible)
 */
static bool parse_npr_packet(const char* buffer, DeviceState* state) {
    int mode, r, g, b;
    int r2 = 0, g2 = 0, b2 = 0, speed = 10;  // Defaults for gradient

    int parsed = sscanf(buffer + 5, "%d,%d,%d,%d,%d,%d,%d,%d",
                        &mode, &r, &g, &b, &r2, &g2, &b2, &speed);

    if (parsed < 4) {
        DEBUG_PRINTF("NPR parse error: got %d fields\n", parsed);
        return false;
    }

    mode = constrain(mode, 0, 10);
    r = constrain(r, 0, 255);
    g = constrain(g, 0, 255);
    b = constrain(b, 0, 255);
    r2 = constrain(r2, 0, 255);
    g2 = constrain(g2, 0, 255);
    b2 = constrain(b2, 0, 255);
    speed = constrain(speed, 1, 50);

    state->command.npr_mode = (uint8_t)mode;
    state->command.npr_r = (uint8_t)r;
    state->command.npr_g = (uint8_t)g;
    state->command.npr_b = (uint8_t)b;
    state->command.npr_r2 = (uint8_t)r2;
    state->command.npr_g2 = (uint8_t)g2;
    state->command.npr_b2 = (uint8_t)b2;
    state->command.npr_gradient_speed = (uint8_t)speed;

    DEBUG_PRINTF("NPR: mode=%d, (%d,%d,%d)->(%d,%d,%d) speed=%d\n",
                 mode, r, g, b, r2, g2, b2, speed);
    return true;
}

/**
 * Parse a valve command packet.
 * Format: $VLV,<open>
 */
static bool parse_valve_packet(const char* buffer, DeviceState* state) {
    int open;

    int parsed = sscanf(buffer + 5, "%d", &open);

    if (parsed != 1) {
        DEBUG_PRINTF("VLV parse error: got %d fields\n", parsed);
        return false;
    }

    bool should_open = (open != 0);
    state->command.valve_open = should_open;

    // Set valve command in safety module (this is the only place it should be set)
    valve_safety_set_command(&g_valve_state, should_open);

    DEBUG_PRINTF("VLV: %d\n", open);
    return true;
}

/**
 * Parse an emergency stop command packet.
 * Format: $EST,<enable>
 */
static bool parse_estop_packet(const char* buffer, DeviceState* state) {
    int enable;

    int parsed = sscanf(buffer + 5, "%d", &enable);

    if (parsed != 1) {
        DEBUG_PRINTF("EST parse error: got %d fields\n", parsed);
        return false;
    }

    state->command.valve_enabled = (enable != 0);

    DEBUG_PRINTF("EST: %d\n", enable);
    return true;
}

/**
 * Parse a flags command packet.
 * Format: $FLG,<flags>
 */
static bool parse_flags_packet(const char* buffer, DeviceState* state) {
    int flags;

    int parsed = sscanf(buffer + 5, "%d", &flags);

    if (parsed != 1) {
        DEBUG_PRINTF("FLG parse error: got %d fields\n", parsed);
        return false;
    }

    state->command.flags = (uint8_t)flags;

    DEBUG_PRINTF("FLG: %d\n", flags);
    return true;
}

/**
 * Parse any incoming packet based on its header.
 */
static bool parse_packet(const char* buffer, DeviceState* state) {
    if (strncmp(buffer, "$SRV,", 5) == 0) {
        return parse_servo_packet(buffer, state);
    }
    else if (strncmp(buffer, "$LGT,", 5) == 0) {
        return parse_light_packet(buffer, state);
    }
    else if (strncmp(buffer, "$RGB,", 5) == 0) {
        return parse_rgb_packet(buffer, state);
    }
    else if (strncmp(buffer, "$MTX,", 5) == 0) {
        return parse_matrix_packet(buffer, state);
    }
    else if (strncmp(buffer, "$NPM,", 5) == 0) {
        return parse_npm_packet(buffer, state);
    }
    else if (strncmp(buffer, "$NPR,", 5) == 0) {
        return parse_npr_packet(buffer, state);
    }
    else if (strncmp(buffer, "$VLV,", 5) == 0) {
        return parse_valve_packet(buffer, state);
    }
    else if (strncmp(buffer, "$EST,", 5) == 0) {
        return parse_estop_packet(buffer, state);
    }
    else if (strncmp(buffer, "$FLG,", 5) == 0) {
        return parse_flags_packet(buffer, state);
    }

    DEBUG_PRINTF("Unknown packet type: %.5s\n", buffer);
    return false;
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

                DEBUG_PRINTF("Packet received: %s\n", rx_buffer);

                // Parse packet
                if (parse_packet(rx_buffer, state)) {
                    // Notify that we received a valid command
                    on_command_received();
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
    // Build status packet (extended format with valve state)
    // Format: $STS,<limit>,<s1>,<s2>,<s3>,<light>,<flags>,<test>,<valve_open>,<valve_enabled>,<valve_ms>

    uint8_t limit = state->input.limit_direction;
    float servo1_pos = state->output.servo_angles[0];
    float servo2_pos = state->output.servo_angles[1];
    float servo3_pos = state->output.servo_angles[2];
    uint8_t light_state = state->output.light_on ? 1 : 0;
    uint8_t flags = 0;
    uint8_t test_active = is_test_active() ? 1 : 0;

    // Get valve state from external functions
    uint8_t valve_open = get_valve_open() ? 1 : 0;
    uint8_t valve_enabled = get_valve_enabled() ? 1 : 0;
    uint32_t valve_ms = get_valve_open_ms();

    // Set flags - any servo moving sets bit 0
    for (int i = 0; i < NUM_SERVOS; i++) {
        if (state->output.servo_moving[i]) {
            flags |= 0x01;
            break;
        }
    }

    // Send packet with all fields including valve state
    PiSerial.printf("$STS,%d,%.1f,%.1f,%.1f,%d,%d,%d,%d,%d,%lu\n",
                    limit, servo1_pos, servo2_pos, servo3_pos,
                    light_state, flags, test_active,
                    valve_open, valve_enabled, valve_ms);

    DEBUG_PRINTF("STS: limit=%d, servos=(%.1f,%.1f,%.1f), valve=%d/%d/%lu\n",
                 limit, servo1_pos, servo2_pos, servo3_pos,
                 valve_open, valve_enabled, valve_ms);
}
