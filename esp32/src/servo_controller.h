#ifndef SERVO_CONTROLLER_H
#define SERVO_CONTROLLER_H

#include <Arduino.h>
#include "config.h"

/**
 * Initialize all servo controllers.
 *
 * Sets up PWM channels for all servos and moves them to center position.
 */
void servo_init();

/**
 * Set a specific servo to a specific angle.
 *
 * @param servo_index Servo index (0, 1, or 2)
 * @param angle Angle in degrees (0-180)
 */
void servo_set_angle(uint8_t servo_index, float angle);

/**
 * Move a servo toward target angle at specified speed.
 *
 * @param servo_index Servo index (0, 1, or 2)
 * @param current Current angle
 * @param target Target angle
 * @param speed Maximum degrees to move per call
 * @return New angle after movement
 */
float servo_move_toward(uint8_t servo_index, float current, float target, float speed);

/**
 * Get current servo angle.
 *
 * @param servo_index Servo index (0, 1, or 2)
 * @return Current angle in degrees
 */
float servo_get_angle(uint8_t servo_index);

#endif // SERVO_CONTROLLER_H
