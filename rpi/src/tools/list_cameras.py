#!/usr/bin/env python3
"""List available camera devices and their capabilities."""

import cv2


def list_cameras(max_index: int = 10) -> None:
    """
    List all available camera devices.

    Args:
        max_index: Maximum camera index to check
    """
    print("Scanning for cameras...")
    print("-" * 50)

    found_cameras = []

    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            # Get camera properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            backend = cap.getBackendName()

            # Try to read a frame to confirm it works
            ret, frame = cap.read()
            status = "OK" if ret else "NO FRAMES"

            print(f"Camera {index}: {width}x{height} @ {fps:.0f}fps ({backend}) [{status}]")
            found_cameras.append(index)

            cap.release()

    print("-" * 50)

    if found_cameras:
        print(f"Found {len(found_cameras)} camera(s): {found_cameras}")
        print(f"\nTo use camera {found_cameras[-1]}, set in local_config.py:")
        print(f"  CAMERA_INDEX = {found_cameras[-1]}")
    else:
        print("No cameras found!")


if __name__ == "__main__":
    list_cameras()
