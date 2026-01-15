#include "servo_controller.h"
#include "config.h"

// Servo pin assignments
static const uint8_t servo_pins[NUM_SERVOS] = {
    SERVO_1_PIN,
    SERVO_2_PIN,
    SERVO_3_PIN
};

// Servo PWM channel assignments
static const uint8_t servo_channels[NUM_SERVOS] = {
    SERVO_1_PWM_CHANNEL,
    SERVO_2_PWM_CHANNEL,
    SERVO_3_PWM_CHANNEL
};

// Current servo angles (valve servo starts at closed position)
static float current_angles[NUM_SERVOS] = {
    SERVO_CENTER_ANGLE,
    SERVO_CENTER_ANGLE,
    VALVE_CLOSED_ANGLE  // Valve servo (index 2)
};

/**
 * Convert angle to PWM duty cycle.
 *
 * @param angle Angle in degrees (0-180)
 * @return PWM duty cycle value
 */
static uint32_t angle_to_duty(float angle) {
    // Constrain angle
    angle = constrain(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);

    // Calculate pulse width in microseconds
    float pulse_us = SERVO_MIN_PULSE_US +
        (angle / 180.0f) * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US);

    // Convert to duty cycle
    // PWM period at 50Hz = 20000 microseconds
    // Resolution is 16-bit = 65535 max
    float period_us = 1000000.0f / SERVO_PWM_FREQ;
    uint32_t max_duty = (1 << SERVO_PWM_RESOLUTION) - 1;
    uint32_t duty = (uint32_t)((pulse_us / period_us) * max_duty);

    return duty;
}

void servo_init() {
    // Configure PWM channels for all servos
    for (int i = 0; i < NUM_SERVOS; i++) {
        ledcSetup(servo_channels[i], SERVO_PWM_FREQ, SERVO_PWM_RESOLUTION);
        ledcAttachPin(servo_pins[i], servo_channels[i]);

        // Move to initial position (valve starts closed, others at center)
        float initial_angle = (i == VALVE_SERVO_INDEX) ? VALVE_CLOSED_ANGLE : SERVO_CENTER_ANGLE;
        servo_set_angle(i, initial_angle);

        DEBUG_PRINTF("Servo %d initialized on pin %d, channel %d\n",
                     i + 1, servo_pins[i], servo_channels[i]);
    }

    DEBUG_PRINTLN("All servos initialized");
}

void servo_set_angle(uint8_t servo_index, float angle) {
    if (servo_index >= NUM_SERVOS) {
        return;
    }

    // Constrain angle
    angle = constrain(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);

    // Update PWM
    uint32_t duty = angle_to_duty(angle);
    ledcWrite(servo_channels[servo_index], duty);

    current_angles[servo_index] = angle;

    DEBUG_PRINTF("Servo %d set to %.1f degrees (duty=%d)\n",
                 servo_index + 1, angle, duty);
}

float servo_move_toward(uint8_t servo_index, float current, float target, float speed) {
    if (servo_index >= NUM_SERVOS) {
        return current;
    }

    float diff = target - current;

    // Check if already at target
    if (abs(diff) < 0.1f) {
        return current;
    }

    // Calculate movement amount
    float move_amount;
    if (abs(diff) <= speed) {
        move_amount = diff;
    } else {
        move_amount = (diff > 0) ? speed : -speed;
    }

    float new_angle = current + move_amount;
    new_angle = constrain(new_angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);

    servo_set_angle(servo_index, new_angle);

    return new_angle;
}

float servo_get_angle(uint8_t servo_index) {
    if (servo_index >= NUM_SERVOS) {
        return SERVO_CENTER_ANGLE;
    }
    return current_angles[servo_index];
}
