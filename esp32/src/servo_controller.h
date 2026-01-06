#ifndef SERVO_CONTROLLER_H
#define SERVO_CONTROLLER_H

#include <Arduino.h>

/**
 * Initialize servo controller.
 *
 * Sets up PWM channel and moves servo to center position.
 */
void servo_init();

/**
 * Set servo to specific angle.
 *
 * @param angle Angle in degrees (0-180)
 */
void servo_set_angle(float angle);

/**
 * Move servo toward target angle at specified speed.
 *
 * @param current Current angle
 * @param target Target angle
 * @param speed Maximum degrees to move per call
 * @return New angle after movement
 */
float servo_move_toward(float current, float target, float speed);

/**
 * Get current servo angle.
 *
 * @return Current angle in degrees
 */
float servo_get_angle();

#endif // SERVO_CONTROLLER_H
