#include "servo_controller.h"
#include "config.h"

// Current servo angle
static float current_angle = SERVO_CENTER_ANGLE;

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
    // Configure PWM channel
    ledcSetup(SERVO_PWM_CHANNEL, SERVO_PWM_FREQ, SERVO_PWM_RESOLUTION);
    ledcAttachPin(SERVO_PIN, SERVO_PWM_CHANNEL);

    // Move to center position
    servo_set_angle(SERVO_CENTER_ANGLE);

    DEBUG_PRINTLN("Servo initialized");
}

void servo_set_angle(float angle) {
    // Constrain angle
    angle = constrain(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);

    // Update PWM
    uint32_t duty = angle_to_duty(angle);
    ledcWrite(SERVO_PWM_CHANNEL, duty);

    current_angle = angle;

    DEBUG_PRINTF("Servo set to %.1f degrees (duty=%d)\n", angle, duty);
}

float servo_move_toward(float current, float target, float speed) {
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

    servo_set_angle(new_angle);

    return new_angle;
}

float servo_get_angle() {
    return current_angle;
}
