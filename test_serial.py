import serial
import time

PORT = "COM3"
BAUD = 115200

print(f"Opening {PORT}...")
ser = serial.Serial(PORT, BAUD, timeout=1)
ser.dtr = False
ser.rts = False
time.sleep(2)

print("Enter angle (0-180) or 'q' to quit:")

while True:
    angle = input("> ")

    if angle.lower() == 'q':
        break

    ser.write(f"{angle}\n".encode())
    time.sleep(0.2)

    while ser.in_waiting:
        print(ser.readline().decode().strip())

ser.close()
print("Done")
