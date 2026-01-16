"""
Brightness Detection Test Script

A minimal script to test and tune the dark frame detection settings.
Shows live camera feed with brightness values and allows real-time adjustment.

Metrics:
    - Brightness (percentile): How bright the frame is
    - Std Dev: Standard deviation of pixel values (low = uniform, high = varied)
    - Entropy: Information entropy (low = uniform colors, high = varied scene)
    - Color Variance: Variance across color channels

Controls:
    Q / ESC  - Quit
    UP/DOWN  - Adjust brightness threshold (+/- 5)
    LEFT/RIGHT - Adjust percentile (+/- 5)
    W/S      - Adjust variance threshold (+/- 5)
    R        - Reset to defaults
    P        - Print current values for config.py
    M        - Toggle detection mode (brightness only / brightness + variance)
    C        - Toggle crop preview (show crop boundaries on original frame)
"""

import cv2
import numpy as np
import sys

# Try to load config values as defaults
try:
    import config
    DEFAULT_THRESHOLD = getattr(config, 'DARK_THRESHOLD', 25)
    DEFAULT_PERCENTILE = getattr(config, 'DARK_PERCENTILE', 75)
    DEFAULT_VARIANCE_THRESHOLD = getattr(config, 'DARK_VARIANCE_THRESHOLD', 15)
    CAMERA_INDEX = getattr(config, 'CAMERA_INDEX', 0)
    # Crop settings
    CROP_LEFT = getattr(config, 'CAMERA_CROP_LEFT', 0.0)
    CROP_RIGHT = getattr(config, 'CAMERA_CROP_RIGHT', 0.0)
    CROP_TOP = getattr(config, 'CAMERA_CROP_TOP', 0.0)
    CROP_BOTTOM = getattr(config, 'CAMERA_CROP_BOTTOM', 0.0)
except ImportError:
    DEFAULT_THRESHOLD = 25
    DEFAULT_PERCENTILE = 75
    DEFAULT_VARIANCE_THRESHOLD = 15
    CAMERA_INDEX = 0
    CROP_LEFT = 0.0
    CROP_RIGHT = 0.0
    CROP_TOP = 0.0
    CROP_BOTTOM = 0.0


def calculate_entropy(gray):
    """Calculate image entropy (information content)."""
    # Calculate histogram
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.flatten()

    # Normalize to get probabilities
    hist = hist / hist.sum()

    # Remove zeros to avoid log(0)
    hist = hist[hist > 0]

    # Calculate entropy: -sum(p * log2(p))
    entropy = -np.sum(hist * np.log2(hist))
    return entropy


def calculate_color_variance(frame):
    """Calculate variance across color channels."""
    if len(frame.shape) < 3:
        return 0.0

    # Calculate mean of each channel
    means = frame.mean(axis=(0, 1))

    # Calculate variance of the means (how different are the channels)
    channel_variance = np.var(means)

    # Also calculate spatial variance within each channel
    spatial_variances = [frame[:, :, i].var() for i in range(3)]
    avg_spatial_variance = np.mean(spatial_variances)

    return avg_spatial_variance


def crop_frame(frame):
    """Apply configured crop to frame."""
    # Skip if no crop configured
    if (CROP_LEFT == 0 and CROP_RIGHT == 0 and
        CROP_TOP == 0 and CROP_BOTTOM == 0):
        return frame

    h, w = frame.shape[:2]

    # Calculate pixel offsets
    left = int(w * CROP_LEFT)
    right = int(w * (1.0 - CROP_RIGHT))
    top = int(h * CROP_TOP)
    bottom = int(h * (1.0 - CROP_BOTTOM))

    # Ensure valid crop region
    if left >= right or top >= bottom:
        return frame

    return frame[top:bottom, left:right]


class BrightnessTester:
    """Simple brightness detection tester with live UI."""

    def __init__(self):
        self.threshold = DEFAULT_THRESHOLD
        self.percentile = DEFAULT_PERCENTILE
        self.variance_threshold = DEFAULT_VARIANCE_THRESHOLD
        self.camera_index = CAMERA_INDEX

        # Detection mode: True = use both brightness AND variance
        self.use_variance = True

        # Crop preview mode: True = show original frame with crop boundaries
        self.show_crop_preview = False

        # History for smoothing display
        self.brightness_history = []
        self.variance_history = []
        self.history_size = 10

    def run(self):
        """Run the brightness test UI."""
        print("=" * 60)
        print("Brightness & Variance Detection Tester")
        print("=" * 60)
        print(f"Camera index: {self.camera_index}")
        print(f"Brightness threshold: {self.threshold}")
        print(f"Brightness percentile: {self.percentile}")
        print(f"Variance threshold: {self.variance_threshold}")
        if CROP_LEFT > 0 or CROP_RIGHT > 0 or CROP_TOP > 0 or CROP_BOTTOM > 0:
            print(f"Crop: L={CROP_LEFT*100:.0f}% R={CROP_RIGHT*100:.0f}% T={CROP_TOP*100:.0f}% B={CROP_BOTTOM*100:.0f}%")
        print()
        print("Controls:")
        print("  UP/DOWN    - Adjust brightness threshold (+/- 5)")
        print("  LEFT/RIGHT - Adjust percentile (+/- 5)")
        print("  W/S        - Adjust variance threshold (+/- 5)")
        print("  M          - Toggle mode (brightness only / brightness+variance)")
        print("  C          - Toggle crop preview (show boundaries)")
        print("  R          - Reset to defaults")
        print("  P          - Print values for config.py")
        print("  Q/ESC      - Quit")
        print("=" * 60)

        # Open camera
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print(f"ERROR: Could not open camera {self.camera_index}")
            return

        # Try to set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        cv2.namedWindow("Brightness Tester", cv2.WINDOW_AUTOSIZE)

        while True:
            ret, frame_original = cap.read()
            if not ret:
                print("Failed to capture frame")
                continue

            # Apply crop before any processing (same as main.py)
            frame = crop_frame(frame_original)

            # Calculate brightness (same algorithm as main.py)
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Percentile-based brightness
            brightness = np.percentile(gray, self.percentile)
            is_bright_dark = brightness < self.threshold

            # Also calculate mean for comparison
            mean_brightness = gray.mean()

            # Calculate variance metrics
            std_dev = gray.std()  # Standard deviation of brightness
            entropy = calculate_entropy(gray)  # Information entropy
            color_var = calculate_color_variance(frame)  # Color variance

            # Determine if "dark" based on mode
            is_var_low = std_dev < self.variance_threshold
            if self.use_variance:
                # Both brightness AND variance must indicate closed door
                is_dark = is_bright_dark and is_var_low
            else:
                # Brightness only
                is_dark = is_bright_dark

            # Update history for smoothed display
            self.brightness_history.append(brightness)
            if len(self.brightness_history) > self.history_size:
                self.brightness_history.pop(0)
            avg_brightness = sum(self.brightness_history) / len(self.brightness_history)

            self.variance_history.append(std_dev)
            if len(self.variance_history) > self.history_size:
                self.variance_history.pop(0)
            avg_variance = sum(self.variance_history) / len(self.variance_history)

            # Create display frame
            metrics = {
                'brightness': brightness,
                'mean_brightness': mean_brightness,
                'avg_brightness': avg_brightness,
                'std_dev': std_dev,
                'avg_variance': avg_variance,
                'entropy': entropy,
                'color_var': color_var,
                'is_bright_dark': is_bright_dark,
                'is_var_low': is_var_low,
            }
            display = self._create_display(frame, frame_original, gray, metrics, is_dark)

            cv2.imshow("Brightness Tester", display)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # Q or ESC
                break
            elif key == 82 or key == 0:  # UP arrow
                self.threshold = min(255, self.threshold + 5)
                print(f"Brightness threshold: {self.threshold}")
            elif key == 84 or key == 1:  # DOWN arrow
                self.threshold = max(0, self.threshold - 5)
                print(f"Brightness threshold: {self.threshold}")
            elif key == 83 or key == 3:  # RIGHT arrow
                self.percentile = min(100, self.percentile + 5)
                print(f"Percentile: {self.percentile}")
            elif key == 81 or key == 2:  # LEFT arrow
                self.percentile = max(0, self.percentile - 5)
                print(f"Percentile: {self.percentile}")
            elif key == ord('w'):  # Variance threshold up
                self.variance_threshold = min(100, self.variance_threshold + 5)
                print(f"Variance threshold: {self.variance_threshold}")
            elif key == ord('s'):  # Variance threshold down
                self.variance_threshold = max(0, self.variance_threshold - 5)
                print(f"Variance threshold: {self.variance_threshold}")
            elif key == ord('m'):  # Toggle mode
                self.use_variance = not self.use_variance
                mode_str = "Brightness + Variance" if self.use_variance else "Brightness only"
                print(f"Mode: {mode_str}")
            elif key == ord('c'):  # Toggle crop preview
                self.show_crop_preview = not self.show_crop_preview
                preview_str = "ON (showing original with crop bounds)" if self.show_crop_preview else "OFF (showing cropped)"
                print(f"Crop preview: {preview_str}")
            elif key == ord('r'):  # Reset
                self.threshold = DEFAULT_THRESHOLD
                self.percentile = DEFAULT_PERCENTILE
                self.variance_threshold = DEFAULT_VARIANCE_THRESHOLD
                self.use_variance = True
                print(f"Reset to defaults")
            elif key == ord('p'):  # Print/save
                print()
                print("# Copy these values to config.py:")
                print(f"DARK_THRESHOLD = {self.threshold}")
                print(f"DARK_PERCENTILE = {self.percentile}")
                if self.use_variance:
                    print(f"DARK_VARIANCE_THRESHOLD = {self.variance_threshold}")
                    print(f"DARK_USE_VARIANCE = True")
                else:
                    print(f"DARK_USE_VARIANCE = False")
                print()

        cap.release()
        cv2.destroyAllWindows()
        print("Done.")

    def _create_display(self, frame, frame_original, gray, metrics, is_dark):
        """Create the display frame with overlays."""
        # Decide which frame to show
        if self.show_crop_preview:
            # Show original frame with crop boundaries
            display_frame = frame_original.copy()
            orig_h, orig_w = frame_original.shape[:2]

            # Calculate crop boundaries in pixels
            left = int(orig_w * CROP_LEFT)
            right = int(orig_w * (1.0 - CROP_RIGHT))
            top = int(orig_h * CROP_TOP)
            bottom = int(orig_h * (1.0 - CROP_BOTTOM))

            # Draw excluded regions with semi-transparent red overlay
            overlay = display_frame.copy()
            # Left region
            if left > 0:
                cv2.rectangle(overlay, (0, 0), (left, orig_h), (0, 0, 150), -1)
            # Right region
            if right < orig_w:
                cv2.rectangle(overlay, (right, 0), (orig_w, orig_h), (0, 0, 150), -1)
            # Top region (between left and right)
            if top > 0:
                cv2.rectangle(overlay, (left, 0), (right, top), (0, 0, 150), -1)
            # Bottom region (between left and right)
            if bottom < orig_h:
                cv2.rectangle(overlay, (left, bottom), (right, orig_h), (0, 0, 150), -1)

            # Blend overlay
            cv2.addWeighted(overlay, 0.4, display_frame, 0.6, 0, display_frame)

            # Draw crop boundary rectangle (cyan)
            cv2.rectangle(display_frame, (left, top), (right, bottom), (255, 255, 0), 2)

            # Label
            cv2.putText(display_frame, "CROP PREVIEW (C to toggle)", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(display_frame, f"L:{CROP_LEFT*100:.0f}% R:{CROP_RIGHT*100:.0f}% T:{CROP_TOP*100:.0f}% B:{CROP_BOTTOM*100:.0f}%",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            h, w = display_frame.shape[:2]
        else:
            # Show cropped frame (normal mode)
            display_frame = frame
            h, w = frame.shape[:2]

        # Create a wider canvas to show info panel
        canvas_width = w + 280
        canvas = np.zeros((h, canvas_width, 3), dtype=np.uint8)
        canvas[:, :w] = display_frame

        # Info panel background
        cv2.rectangle(canvas, (w, 0), (canvas_width, h), (30, 30, 30), -1)

        # Draw info text
        x_text = w + 10
        y = 25
        line_height = 18

        # Title and mode
        mode_str = "Brightness + Variance" if self.use_variance else "Brightness Only"
        cv2.putText(canvas, "DOOR DETECTION TESTER", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += line_height
        cv2.putText(canvas, f"Mode: {mode_str}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height + 5

        # Status indicator (large)
        status_text = "DARK (door closed)" if is_dark else "LIGHT (door open)"
        status_color = (0, 0, 255) if is_dark else (0, 255, 0)
        cv2.putText(canvas, status_text, (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
        y += line_height + 10

        # Brightness section
        cv2.putText(canvas, "BRIGHTNESS", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += line_height

        # Brightness check indicator
        bright_check = "DARK" if metrics['is_bright_dark'] else "LIGHT"
        bright_color = (0, 100, 255) if metrics['is_bright_dark'] else (0, 200, 0)
        cv2.putText(canvas, f"  Value: {metrics['brightness']:.1f} -> {bright_check}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, bright_color, 1)
        y += line_height

        cv2.putText(canvas, f"  Threshold: {self.threshold}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height

        cv2.putText(canvas, f"  Percentile: {self.percentile}%", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height + 5

        # Draw brightness bar
        bar_x = x_text
        bar_width = 220
        bar_height = 15
        self._draw_bar(canvas, bar_x, y, bar_width, bar_height,
                       metrics['brightness'], 255, self.threshold,
                       metrics['is_bright_dark'])
        y += bar_height + 20

        # Variance section
        cv2.putText(canvas, "VARIANCE (color uniformity)", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += line_height

        # Variance check indicator
        var_check = "UNIFORM" if metrics['is_var_low'] else "VARIED"
        var_color = (0, 100, 255) if metrics['is_var_low'] else (0, 200, 0)
        active_indicator = " *" if self.use_variance else ""
        cv2.putText(canvas, f"  Std Dev: {metrics['std_dev']:.1f} -> {var_check}{active_indicator}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, var_color, 1)
        y += line_height

        cv2.putText(canvas, f"  Threshold: {self.variance_threshold}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height + 5

        # Draw variance bar (scale 0-100 for std dev)
        self._draw_bar(canvas, bar_x, y, bar_width, bar_height,
                       min(metrics['std_dev'], 100), 100, self.variance_threshold,
                       metrics['is_var_low'])
        y += bar_height + 15

        # Additional metrics
        cv2.putText(canvas, "OTHER METRICS", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += line_height

        cv2.putText(canvas, f"  Entropy: {metrics['entropy']:.2f} bits", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height

        cv2.putText(canvas, f"  Color Var: {metrics['color_var']:.1f}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height

        cv2.putText(canvas, f"  Mean Bright: {metrics['mean_brightness']:.1f}", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        y += line_height + 10

        # Draw histogram
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        hist = hist.flatten()
        hist_max = hist.max() if hist.max() > 0 else 1
        hist_normalized = hist / hist_max

        hist_x = x_text
        hist_y = y
        hist_width = 220
        hist_height = 60

        # Histogram background
        cv2.rectangle(canvas, (hist_x, hist_y), (hist_x + hist_width, hist_y + hist_height),
                      (40, 40, 40), -1)

        # Draw histogram bars
        bar_w = hist_width // len(hist)
        for i, val in enumerate(hist_normalized):
            bx = hist_x + i * bar_w
            bh = int(val * hist_height)
            bin_center = (i + 0.5) * (256 / len(hist))
            if bin_center < self.threshold:
                color = (100, 100, 100)
            else:
                color = (150, 150, 150)
            cv2.rectangle(canvas, (bx, hist_y + hist_height - bh),
                          (bx + bar_w - 1, hist_y + hist_height), color, -1)

        # Threshold line
        thresh_hist_x = hist_x + int(self.threshold / 256 * hist_width)
        cv2.line(canvas, (thresh_hist_x, hist_y), (thresh_hist_x, hist_y + hist_height),
                 (0, 255, 255), 1)

        y = hist_y + hist_height + 15

        # Controls help
        cv2.putText(canvas, "CONTROLS", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += line_height
        cv2.putText(canvas, "UP/DOWN: Brightness thresh", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
        y += 14
        cv2.putText(canvas, "LEFT/RIGHT: Percentile", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
        y += 14
        cv2.putText(canvas, "W/S: Variance threshold", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
        y += 14
        cv2.putText(canvas, "M: Toggle mode  C: Crop preview", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
        y += 14
        cv2.putText(canvas, "R: Reset  P: Print  Q: Quit", (x_text, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)

        # Add "DARK" overlay on video if dark (only in normal mode, not crop preview)
        if is_dark and not self.show_crop_preview:
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 100), -1)
            cv2.addWeighted(overlay, 0.3, canvas[:, :w], 0.7, 0, canvas[:, :w])
            cv2.putText(canvas, "DOOR CLOSED", (w // 2 - 100, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)

        return canvas

    def _draw_bar(self, canvas, x, y, width, height, value, max_val, threshold, is_below):
        """Draw a bar with threshold marker."""
        # Background
        cv2.rectangle(canvas, (x, y), (x + width, y + height), (60, 60, 60), -1)

        # Threshold marker
        thresh_x = x + int(threshold / max_val * width)
        cv2.line(canvas, (thresh_x, y - 3), (thresh_x, y + height + 3), (0, 255, 255), 2)

        # Value fill
        fill_width = int(min(value, max_val) / max_val * width)
        fill_color = (0, 100, 255) if is_below else (0, 180, 0)
        cv2.rectangle(canvas, (x, y), (x + fill_width, y + height), fill_color, -1)

        # Border
        cv2.rectangle(canvas, (x, y), (x + width, y + height), (100, 100, 100), 1)


def main():
    """Entry point."""
    tester = BrightnessTester()
    tester.run()


if __name__ == "__main__":
    main()
