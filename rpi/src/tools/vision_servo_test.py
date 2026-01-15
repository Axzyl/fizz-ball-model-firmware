#!/usr/bin/env python3
"""
Standalone computer vision + servo tracking test.

Uses YOLO for face detection, MediaPipe for pose estimation,
and controls the base servo (S1) to track the detected face.

Press 'q' to quit, 'r' to reset servo to center.
"""

import os
import sys
import time

# Add parent directory (rpi/src) to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(script_dir)  # rpi/src
sys.path.insert(0, src_dir)

import cv2
import numpy as np

import config
from vision.face_tracker import FaceTracker

# Try to import local_config overrides
try:
    from local_config import *
except ImportError:
    pass


class ServoController:
    """Simple servo controller via UART."""

    def __init__(self):
        self.serial = None
        self.connected = False
        self.current_angle = 90.0
        self._connect()

    def _connect(self) -> bool:
        """Connect to ESP32 via serial."""
        try:
            import serial
            import serial.tools.list_ports

            # Auto-detect port
            port = self._detect_port()
            if not port:
                print("[Servo] No serial port found, running without servo control")
                return False

            print(f"[Servo] Connecting to {port}...")
            self.serial = serial.Serial(
                port=port,
                baudrate=config.UART_BAUDRATE,
                timeout=0.01,
            )
            self.serial.dtr = False
            self.serial.rts = False
            self.connected = True
            print(f"[Servo] Connected to {port}")
            return True

        except ImportError:
            print("[Servo] pyserial not installed, running without servo control")
            return False
        except Exception as e:
            print(f"[Servo] Connection failed: {e}")
            return False

    def _detect_port(self) -> str:
        """Auto-detect ESP32 serial port."""
        try:
            import serial.tools.list_ports

            esp32_keywords = ["CP210", "CH340", "CH341", "FTDI", "USB Serial", "ESP32", "USB JTAG"]
            ports = list(serial.tools.list_ports.comports())

            print(f"[Servo] Available ports:")
            for p in ports:
                print(f"  - {p.device}: {p.description}")

            for port in ports:
                port_info = f"{port.description} {port.manufacturer or ''}".upper()
                for keyword in esp32_keywords:
                    if keyword.upper() in port_info:
                        return port.device

            # Fall back to first COM/ttyUSB port
            for port in ports:
                if port.device.startswith("COM") or "ttyUSB" in port.device or "ttyACM" in port.device:
                    return port.device

            return None
        except Exception:
            return None

    def set_angle(self, angle: float) -> None:
        """Set servo angle (0-180)."""
        angle = max(0.0, min(180.0, angle))
        self.current_angle = angle

        if self.connected and self.serial:
            try:
                # Send servo command: $SRV,<s1>,<s2>,<s3>\n
                # S1 = base servo, S2 = arm, S3 = unused
                cmd = f"$SRV,{angle:.1f},90.0,90.0\n"
                self.serial.write(cmd.encode('ascii'))
            except Exception as e:
                print(f"[Servo] Write error: {e}")

    def close(self):
        """Close serial connection."""
        if self.serial:
            self.serial.close()


class VisionServoTracker:
    """Computer vision face tracker with servo control."""

    def __init__(self):
        # Initialize camera
        camera_index = getattr(config, 'CAMERA_INDEX', 0)
        print(f"[Vision] Opening camera {camera_index}...")

        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_index}")

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[Vision] Camera opened: {actual_w}x{actual_h}")

        # Initialize face tracker
        print("[Vision] Initializing face tracker...")
        self.tracker = FaceTracker()

        # Initialize servo controller
        self.servo = ServoController()

        # Tracking parameters
        self.servo_angle = 90.0  # Start centered
        self.tracking_gain = 0.15  # How fast to follow (0.0-1.0)
        self.deadzone = 0.05  # Fraction of frame width to ignore

        # FPS tracking
        self.fps_times = []
        self.fps = 0.0

    def run(self):
        """Main tracking loop."""
        print("\n" + "=" * 50)
        print("Vision + Servo Tracking Test")
        print("=" * 50)
        print("Controls:")
        print("  q - Quit")
        print("  r - Reset servo to center (90°)")
        print("  +/- - Adjust tracking gain")
        print("=" * 50 + "\n")

        cv2.namedWindow("Vision Servo Test", cv2.WINDOW_AUTOSIZE)

        while True:
            frame_start = time.time()

            # Capture frame
            ret, frame = self.cap.read()
            if not ret:
                print("[Vision] Failed to capture frame")
                time.sleep(0.1)
                continue

            # Process frame with face tracker
            result = self.tracker.process(frame)

            # Calculate servo target based on face position
            if result["detected"] and result["bbox"]:
                x, y, w, h = result["bbox"]
                frame_h, frame_w = frame.shape[:2]

                # Calculate face center as fraction of frame (0.0 = left, 1.0 = right)
                face_center_x = (x + w / 2) / frame_w

                # Calculate error from center (positive = face is right of center)
                error = face_center_x - 0.5

                # Apply deadzone
                if abs(error) > self.deadzone:
                    # Map error to servo adjustment
                    # Negative error (face left) -> increase angle (servo turns left)
                    # Positive error (face right) -> decrease angle (servo turns right)
                    adjustment = -error * 180.0 * self.tracking_gain
                    self.servo_angle += adjustment
                    self.servo_angle = max(0.0, min(180.0, self.servo_angle))

            # Send servo command
            self.servo.set_angle(self.servo_angle)

            # Draw annotations for all detected faces
            annotated = frame.copy()
            self._draw_all_faces(annotated, result)

            # Draw tracking info overlay
            self._draw_overlay(annotated, result)

            # Display
            cv2.imshow("Vision Servo Test", annotated)

            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('r'):
                self.servo_angle = 90.0
                print("[Control] Servo reset to 90°")
            elif key == ord('+') or key == ord('='):
                self.tracking_gain = min(1.0, self.tracking_gain + 0.05)
                print(f"[Control] Tracking gain: {self.tracking_gain:.2f}")
            elif key == ord('-'):
                self.tracking_gain = max(0.05, self.tracking_gain - 0.05)
                print(f"[Control] Tracking gain: {self.tracking_gain:.2f}")

            # Update FPS
            self._update_fps(frame_start)

        # Cleanup
        self.cap.release()
        self.servo.close()
        cv2.destroyAllWindows()
        print("[Vision] Stopped")

    def _draw_all_faces(self, frame: np.ndarray, result: dict) -> None:
        """Draw all detected faces with selection indicator."""
        if not result.get("detected"):
            return

        # Get all faces if available
        all_faces = result.get("all_faces", [])
        selected_bbox = result.get("bbox")

        if not all_faces:
            # Fallback: just draw the selected face
            if selected_bbox:
                x, y, w, h = selected_bbox
                color = (0, 255, 0) if result.get("is_facing") else (0, 165, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, "SELECTED", (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            return

        # Draw all faces
        for i, face in enumerate(all_faces):
            x, y, w, h = face['bbox']
            is_selected = (face['bbox'] == selected_bbox)

            if is_selected:
                # Selected face: bright green (facing) or orange (not facing)
                color = (0, 255, 0) if face['is_facing'] else (0, 165, 255)
                thickness = 3
                label = "TRACKING"
            else:
                # Other faces: dim color
                color = (100, 100, 100)  # Gray for non-selected
                if face['is_facing']:
                    color = (0, 150, 0)  # Dim green if facing
                thickness = 1
                label = f"#{i+1}"

            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

            # Draw label
            label_y = y - 8 if y > 20 else y + h + 15
            cv2.putText(frame, label, (x, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2 if is_selected else 1)

            # Draw facing indicator
            facing_text = "FACING" if face['is_facing'] else ""
            if facing_text and not is_selected:
                cv2.putText(frame, facing_text, (x, y + h + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 150, 0), 1)

        # Show face count
        num_faces = len(all_faces)
        num_facing = sum(1 for f in all_faces if f['is_facing'])
        cv2.putText(frame, f"Faces: {num_faces} ({num_facing} facing)",
                    (10, frame.shape[0] - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def _draw_overlay(self, frame: np.ndarray, result: dict) -> None:
        """Draw status overlay on frame."""
        h, w = frame.shape[:2]

        # Background panel
        cv2.rectangle(frame, (10, 10), (300, 160), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (300, 160), (100, 100, 100), 1)

        y = 30
        line_h = 22

        # Detection status
        if result["detected"]:
            status = "DETECTED"
            color = (0, 255, 0)
        else:
            status = "NO FACE"
            color = (0, 0, 255)
        cv2.putText(frame, f"Status: {status}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        y += line_h

        # Pose angles
        if result["detected"]:
            yaw, pitch, roll = result["yaw"], result["pitch"], result["roll"]
            cv2.putText(frame, f"Yaw: {yaw:.1f}  Pitch: {pitch:.1f}  Roll: {roll:.1f}",
                        (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += line_h

        # Facing status
        facing = "YES" if result.get("is_facing") else "NO"
        facing_color = (0, 255, 0) if result.get("is_facing") else (0, 0, 255)
        cv2.putText(frame, f"Facing: {facing}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, facing_color, 1)
        y += line_h

        # Servo angle
        cv2.putText(frame, f"Servo: {self.servo_angle:.1f} deg", (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)
        y += line_h

        # Tracking gain and FPS
        cv2.putText(frame, f"Gain: {self.tracking_gain:.2f}  FPS: {self.fps:.1f}",
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Draw center line
        cv2.line(frame, (w // 2, 0), (w // 2, h), (100, 100, 100), 1)

        # Draw deadzone
        dz_left = int(w * (0.5 - self.deadzone))
        dz_right = int(w * (0.5 + self.deadzone))
        cv2.line(frame, (dz_left, 0), (dz_left, h), (50, 50, 100), 1)
        cv2.line(frame, (dz_right, 0), (dz_right, h), (50, 50, 100), 1)

        # Draw servo position indicator at bottom
        servo_x = int(w * (self.servo_angle / 180.0))
        cv2.rectangle(frame, (0, h - 20), (w, h), (30, 30, 30), -1)
        cv2.circle(frame, (servo_x, h - 10), 8, (0, 200, 255), -1)
        cv2.putText(frame, "0", (5, h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
        cv2.putText(frame, "180", (w - 30, h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)

    def _update_fps(self, frame_start: float) -> None:
        """Update FPS calculation."""
        now = time.time()
        self.fps_times.append(now)
        self.fps_times = [t for t in self.fps_times if t > now - 1.0]
        if len(self.fps_times) > 1:
            self.fps = len(self.fps_times) / (self.fps_times[-1] - self.fps_times[0])


def main():
    try:
        tracker = VisionServoTracker()
        tracker.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
