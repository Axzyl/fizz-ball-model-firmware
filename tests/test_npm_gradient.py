#!/usr/bin/env python3
"""Minimal test script for NeoPixel 5x5 matrix red-blue gradient."""

import serial
import time
import sys

# Configuration
PORT = "COM9"  # Change to your port
BAUD = 115200

# NPM gradient mode command
# $NPM,<mode>,<letter>,<r>,<g>,<b>,<r2>,<g2>,<b2>,<speed>
# Mode 9 = gradient, Red (255,0,0) to Blue (0,0,255), speed 10
NPM_GRADIENT_CMD = b"$NPM,9,A,255,0,0,0,0,255,10\n"


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else PORT

    print(f"Connecting to {port}...")
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        print("Usage: python test_npm_gradient.py [COM_PORT]")
        return 1

    print("Connected. Sending NPM gradient command...")
    print(f"Command: {NPM_GRADIENT_CMD.decode().strip()}")

    try:
        while True:
            # Send command repeatedly to keep gradient active
            ser.write(NPM_GRADIENT_CMD)

            # Read any response
            if ser.in_waiting:
                response = ser.readline().decode('ascii', errors='ignore').strip()
                if response:
                    print(f"< {response}")

            time.sleep(0.1)  # 10Hz update rate

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        ser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
