#ifndef UART_HANDLER_H
#define UART_HANDLER_H

#include <Arduino.h>
#include "state.h"

/**
 * Initialize UART for communication with Raspberry Pi.
 */
void uart_init();

/**
 * Receive and parse incoming UART data.
 *
 * Checks for complete packets and updates device state with received commands.
 *
 * @param state Pointer to device state to update
 */
void uart_receive(DeviceState* state);

/**
 * Send status packet to Raspberry Pi.
 *
 * @param state Pointer to device state to read
 */
void uart_send_status(DeviceState* state);

#endif // UART_HANDLER_H
