#!/usr/bin/env python3
"""
Hardware Test UI for Fizz Ball Model Firmware
Simple GUI to test all ESP32-controlled hardware components.
"""

import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time


# NeoPixel Matrix modes (5x5 matrix)
NPM_MODES = [
    (0, "Off"),
    (1, "Letter"),
    (3, "Rainbow"),
    (4, "Solid Color"),
    (5, "Eye Closed"),
    (6, "Eye Open"),
]

# NeoPixel Ring modes (8 LED ring)
NPR_MODES = [
    (0, "Off"),
    (1, "Solid Color"),
    (2, "Rainbow"),
    (3, "Chase"),
    (4, "Breathe"),
    (5, "Spinner"),
]


class HardwareTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fizz Ball Hardware Tester")
        self.root.geometry("850x750")

        self.serial_port = None
        self.serial_thread = None
        self.running = False
        self.heartbeat_id = None  # Timer ID for heartbeat
        self.synced_with_esp = False  # Wait for first status before sending commands

        # Status data from ESP32
        self.status = {
            'limit': 0,
            'servo1': 0.0, 'servo2': 0.0, 'servo3': 0.0,
            'light': 0, 'flags': 0, 'test': 0,
            'valve_open': 0, 'valve_enabled': 0, 'valve_ms': 0
        }

        self._build_ui()
        self._refresh_ports()

        # Auto-connect after UI is displayed
        self.root.after(100, self._auto_connect)

    def _build_ui(self):
        # Main container with padding
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)

        # === Connection Frame ===
        conn_frame = ttk.LabelFrame(main, text="Connection", padding="5")
        conn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=20)
        self.port_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(conn_frame, text="Refresh", command=self._refresh_ports).pack(side=tk.LEFT)
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # === Servos Frame ===
        servo_frame = ttk.LabelFrame(main, text="Servos", padding="5")
        servo_frame.pack(fill=tk.X, pady=(0, 10))

        self.servo_vars = []
        servo_labels = ["Base (S1)", "Arm (S2)"]  # Valve controlled separately
        for i, label in enumerate(servo_labels):
            row = ttk.Frame(servo_frame)
            row.pack(fill=tk.X, pady=2)

            ttk.Label(row, text=f"{label}:", width=12).pack(side=tk.LEFT)

            var = tk.DoubleVar(value=90.0)  # Default to 90 (center position)
            self.servo_vars.append(var)

            scale = ttk.Scale(row, from_=0, to=180, variable=var, orient=tk.HORIZONTAL, length=400,
                              command=lambda v: self._send_servos())
            scale.pack(side=tk.LEFT, padx=5)

            val_label = ttk.Label(row, textvariable=var, width=6)
            val_label.pack(side=tk.LEFT)

            ttk.Button(row, text="0", width=3, command=lambda v=var: self._set_servo(v, 0)).pack(side=tk.LEFT, padx=2)
            ttk.Button(row, text="90", width=3, command=lambda v=var: self._set_servo(v, 90)).pack(side=tk.LEFT, padx=2)
            ttk.Button(row, text="180", width=3, command=lambda v=var: self._set_servo(v, 180)).pack(side=tk.LEFT, padx=2)

        ttk.Button(servo_frame, text="Send Servos", command=self._send_servos).pack(pady=5)

        # === Middle Row (Light + RGB + Valve) ===
        mid_row = ttk.Frame(main)
        mid_row.pack(fill=tk.X, pady=(0, 10))

        # Light controls
        light_frame = ttk.LabelFrame(mid_row, text="Light", padding="5")
        light_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.light_var = tk.IntVar(value=0)
        for text, val in [("OFF", 0), ("ON", 1), ("AUTO", 2)]:
            ttk.Radiobutton(light_frame, text=text, variable=self.light_var, value=val,
                           command=self._send_light).pack(side=tk.LEFT, padx=5)

        # RGB controls
        rgb_frame = ttk.LabelFrame(mid_row, text="RGB Strip", padding="5")
        rgb_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.rgb_mode = tk.IntVar(value=0)
        ttk.Checkbutton(rgb_frame, text="Enable", variable=self.rgb_mode,
                       command=self._send_rgb).pack(anchor=tk.W)

        self.rgb_vars = []
        for color in ["R", "G", "B"]:
            row = ttk.Frame(rgb_frame)
            row.pack(fill=tk.X)
            ttk.Label(row, text=f"{color}:", width=3).pack(side=tk.LEFT)
            var = tk.IntVar(value=0)
            self.rgb_vars.append(var)
            scale = ttk.Scale(row, from_=0, to=255, variable=var, orient=tk.HORIZONTAL, length=100)
            scale.pack(side=tk.LEFT)
            scale.bind("<ButtonRelease-1>", lambda e: self._send_rgb())

        # Valve controls (simplified: just open/close buttons)
        valve_frame = ttk.LabelFrame(mid_row, text="Valve (auto-closes after 5s)", padding="5")
        valve_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        valve_btn_row = ttk.Frame(valve_frame)
        valve_btn_row.pack(fill=tk.X, pady=5)

        # Track commanded valve state (what we last sent)
        self.valve_commanded = False

        self.valve_open_btn = ttk.Button(valve_btn_row, text="OPEN", width=10,
                                         command=self._valve_open)
        self.valve_open_btn.pack(side=tk.LEFT, padx=5)

        self.valve_close_btn = ttk.Button(valve_btn_row, text="CLOSE", width=10,
                                          command=self._valve_close)
        self.valve_close_btn.pack(side=tk.LEFT, padx=5)

        self.valve_status = ttk.Label(valve_frame, text="CLOSED", font=("Consolas", 12, "bold"))
        self.valve_status.pack(pady=5)

        # === LED Matrix Frame ===
        matrix_frame = ttk.LabelFrame(main, text="LED Matrix (MAX7219)", padding="5")
        matrix_frame.pack(fill=tk.X, pady=(0, 10))

        matrix_row = ttk.Frame(matrix_frame)
        matrix_row.pack()

        patterns = [("OFF", 0), ("Circle", 1), ("X", 2)]

        ttk.Label(matrix_row, text="Left:").pack(side=tk.LEFT)
        self.matrix_left = tk.IntVar(value=0)
        for text, val in patterns:
            ttk.Radiobutton(matrix_row, text=text, variable=self.matrix_left, value=val,
                           command=self._send_matrix).pack(side=tk.LEFT)

        ttk.Label(matrix_row, text="    Right:").pack(side=tk.LEFT)
        self.matrix_right = tk.IntVar(value=0)
        for text, val in patterns:
            ttk.Radiobutton(matrix_row, text=text, variable=self.matrix_right, value=val,
                           command=self._send_matrix).pack(side=tk.LEFT)

        # === NeoPixel Matrix Frame ===
        npm_frame = ttk.LabelFrame(main, text="NeoPixel Matrix (5x5)", padding="5")
        npm_frame.pack(fill=tk.X, pady=(0, 10))

        npm_row1 = ttk.Frame(npm_frame)
        npm_row1.pack(fill=tk.X, pady=2)

        ttk.Label(npm_row1, text="Mode:").pack(side=tk.LEFT)
        self.npm_mode = tk.IntVar(value=0)
        self.npm_mode_combo = ttk.Combobox(npm_row1, width=15, state="readonly")
        self.npm_mode_combo['values'] = [name for _, name in NPM_MODES]
        self.npm_mode_combo.current(0)
        self.npm_mode_combo.pack(side=tk.LEFT, padx=5)
        self.npm_mode_combo.bind("<<ComboboxSelected>>", lambda e: self._send_npm())

        ttk.Label(npm_row1, text="Letter:").pack(side=tk.LEFT, padx=(10, 0))
        self.npm_letter = tk.StringVar(value="A")
        letter_combo = ttk.Combobox(npm_row1, textvariable=self.npm_letter, width=3, state="readonly")
        letter_combo['values'] = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        letter_combo.current(0)
        letter_combo.pack(side=tk.LEFT, padx=5)
        letter_combo.bind("<<ComboboxSelected>>", lambda e: self._send_npm())

        npm_row2 = ttk.Frame(npm_frame)
        npm_row2.pack(fill=tk.X, pady=2)

        ttk.Label(npm_row2, text="Color:").pack(side=tk.LEFT)
        self.npm_r = tk.IntVar(value=255)
        self.npm_g = tk.IntVar(value=0)
        self.npm_b = tk.IntVar(value=0)

        for label, var in [("R", self.npm_r), ("G", self.npm_g), ("B", self.npm_b)]:
            ttk.Label(npm_row2, text=f"  {label}:").pack(side=tk.LEFT)
            scale = ttk.Scale(npm_row2, from_=0, to=255, variable=var, orient=tk.HORIZONTAL, length=80)
            scale.pack(side=tk.LEFT)
            scale.bind("<ButtonRelease-1>", lambda e: self._send_npm())

        # Quick color buttons
        npm_row3 = ttk.Frame(npm_frame)
        npm_row3.pack(fill=tk.X, pady=2)
        ttk.Label(npm_row3, text="Quick:").pack(side=tk.LEFT)
        for name, r, g, b in [("Red", 255, 0, 0), ("Green", 0, 255, 0), ("Blue", 0, 0, 255),
                               ("White", 255, 255, 255), ("Yellow", 255, 255, 0), ("Purple", 255, 0, 255)]:
            ttk.Button(npm_row3, text=name, width=6,
                      command=lambda r=r, g=g, b=b: self._set_npm_color(r, g, b)).pack(side=tk.LEFT, padx=2)

        # === NeoPixel Ring Frame ===
        npr_frame = ttk.LabelFrame(main, text="NeoPixel Ring (8 LED)", padding="5")
        npr_frame.pack(fill=tk.X, pady=(0, 10))

        npr_row1 = ttk.Frame(npr_frame)
        npr_row1.pack(fill=tk.X, pady=2)

        ttk.Label(npr_row1, text="Mode:").pack(side=tk.LEFT)
        self.npr_mode = tk.IntVar(value=0)
        self.npr_mode_combo = ttk.Combobox(npr_row1, width=15, state="readonly")
        self.npr_mode_combo['values'] = [name for _, name in NPR_MODES]
        self.npr_mode_combo.current(0)
        self.npr_mode_combo.pack(side=tk.LEFT, padx=5)
        self.npr_mode_combo.bind("<<ComboboxSelected>>", lambda e: self._send_npr())

        npr_row2 = ttk.Frame(npr_frame)
        npr_row2.pack(fill=tk.X, pady=2)

        ttk.Label(npr_row2, text="Color:").pack(side=tk.LEFT)
        self.npr_r = tk.IntVar(value=255)
        self.npr_g = tk.IntVar(value=0)
        self.npr_b = tk.IntVar(value=0)

        for label, var in [("R", self.npr_r), ("G", self.npr_g), ("B", self.npr_b)]:
            ttk.Label(npr_row2, text=f"  {label}:").pack(side=tk.LEFT)
            scale = ttk.Scale(npr_row2, from_=0, to=255, variable=var, orient=tk.HORIZONTAL, length=80)
            scale.pack(side=tk.LEFT)
            scale.bind("<ButtonRelease-1>", lambda e: self._send_npr())

        # Quick color buttons
        npr_row3 = ttk.Frame(npr_frame)
        npr_row3.pack(fill=tk.X, pady=2)
        ttk.Label(npr_row3, text="Quick:").pack(side=tk.LEFT)
        for name, r, g, b in [("Red", 255, 0, 0), ("Green", 0, 255, 0), ("Blue", 0, 0, 255),
                               ("White", 255, 255, 255), ("Yellow", 255, 255, 0), ("Purple", 255, 0, 255)]:
            ttk.Button(npr_row3, text=name, width=6,
                      command=lambda r=r, g=g, b=b: self._set_npr_color(r, g, b)).pack(side=tk.LEFT, padx=2)

        # === Status Frame ===
        status_frame = ttk.LabelFrame(main, text="ESP32 Status", padding="5")
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = tk.Text(status_frame, height=6, font=("Consolas", 10))
        self.status_text.pack(fill=tk.BOTH, expand=True)

        # === Quick Test Buttons ===
        test_frame = ttk.Frame(main)
        test_frame.pack(fill=tk.X, pady=10)

        ttk.Button(test_frame, text="All Servos 0", command=lambda: self._all_servos(0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_frame, text="All Servos 90", command=lambda: self._all_servos(90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_frame, text="All Servos 180", command=lambda: self._all_servos(180)).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_frame, text="LED Test", command=self._send_led_test).pack(side=tk.LEFT, padx=10)
        ttk.Button(test_frame, text="All Off", command=self._all_off).pack(side=tk.LEFT, padx=2)

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            # Try to select a reasonable default
            for p in ports:
                if 'USB' in p or 'COM' in p:
                    self.port_var.set(p)
                    break
            else:
                self.port_var.set(ports[0])

    def _auto_connect(self):
        """Automatically connect to the first available port on startup."""
        if self.port_var.get():
            self._connect()

    def _toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get()
        if not port:
            return

        try:
            self.serial_port = serial.Serial(port, 115200, timeout=0.1)
            self.running = True
            self.serial_thread = threading.Thread(target=self._serial_reader, daemon=True)
            self.serial_thread.start()

            self.connect_btn.config(text="Disconnect")
            self.status_label.config(text=f"Connected to {port}", foreground="green")

            # Reset valve state and ensure valve is closed on connect
            self.valve_commanded = False
            self.synced_with_esp = False  # Wait for first status to sync sliders
            self._send("$VLV,0")

            # Start heartbeat to keep ESP32 connection alive
            self._start_heartbeat()
        except Exception as e:
            self._log(f"Connection error: {e}")

    def _disconnect(self):
        self._stop_heartbeat()
        self.running = False
        if self.serial_thread:
            self.serial_thread.join(timeout=1)
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None

        self.connect_btn.config(text="Connect")
        self.status_label.config(text="Disconnected", foreground="red")

    def _start_heartbeat(self):
        """Start periodic heartbeat to keep ESP32 connection alive."""
        def heartbeat():
            if self.running and self.serial_port and self.serial_port.is_open:
                # Only send servo commands after syncing with ESP32's actual positions
                if self.synced_with_esp:
                    self._send_servos()
                self.heartbeat_id = self.root.after(200, heartbeat)  # 5Hz heartbeat

        self.heartbeat_id = self.root.after(200, heartbeat)

    def _stop_heartbeat(self):
        """Stop the heartbeat timer."""
        if self.heartbeat_id:
            self.root.after_cancel(self.heartbeat_id)
            self.heartbeat_id = None

    def _serial_reader(self):
        while self.running and self.serial_port:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line.startswith('$STS,'):
                        self._parse_status(line)
            except Exception as e:
                self._log(f"Read error: {e}")
                break
            time.sleep(0.01)

    def _parse_status(self, line):
        try:
            parts = line[5:].split(',')
            if len(parts) >= 10:
                self.status['limit'] = int(parts[0])
                self.status['servo1'] = float(parts[1])
                self.status['servo2'] = float(parts[2])
                self.status['servo3'] = float(parts[3])
                self.status['light'] = int(parts[4])
                self.status['flags'] = int(parts[5])
                self.status['test'] = int(parts[6])
                self.status['valve_open'] = int(parts[7])
                self.status['valve_enabled'] = int(parts[8])
                self.status['valve_ms'] = int(parts[9])

                self.root.after(0, self._update_status_display)
        except Exception:
            pass

    def _update_status_display(self):
        s = self.status
        limit_str = ["CLEAR", "CW", "CCW"][s['limit']] if s['limit'] < 3 else "?"
        moving = "MOVING" if s['flags'] & 0x01 else "IDLE"

        # On first status, sync sliders with ESP32's actual positions (prevents servo jump)
        if not self.synced_with_esp:
            self.servo_vars[0].set(s['servo1'])  # Base
            self.servo_vars[1].set(s['servo2'])  # Arm
            # Valve (servo3) is controlled via $VLV, not slider
            self.synced_with_esp = True

        # Update valve status label and sync commanded state
        if s['valve_open']:
            self.valve_status.config(text=f"OPEN ({s['valve_ms']}ms)", foreground="red")
        else:
            self.valve_status.config(text="CLOSED", foreground="green")
            # Reset commanded state when ESP32 reports closed (e.g., after auto-close)
            # This allows user to click Open again
            self.valve_commanded = False

        text = (
            f"Servos:  Base={s['servo1']:.1f}  Arm={s['servo2']:.1f}  Valve={s['servo3']:.1f}  [{moving}]\n"
            f"Limit:   {limit_str}\n"
            f"Light:   {'ON' if s['light'] else 'OFF'}\n"
            f"Test:    {'ACTIVE' if s['test'] else 'idle'}\n"
        )

        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, text)

    def _send(self, cmd):
        if self.serial_port and self.serial_port.is_open:
            full_cmd = cmd + '\n'
            self.serial_port.write(full_cmd.encode())
            self._log(f"TX: {cmd}")

    def _log(self, msg):
        self.root.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self.status_text.insert(tk.END, f"{msg}\n")
        self.status_text.see(tk.END)

    # === Command Senders ===

    def _set_servo(self, var, value):
        var.set(value)
        self._send_servos()

    def _send_servos(self):
        s1 = self.servo_vars[0].get()
        s2 = self.servo_vars[1].get()
        # Servo 3 (valve) controlled separately via $VLV command
        self._send(f"$SRV,{s1:.1f},{s2:.1f},0.0")

    def _send_light(self):
        self._send(f"$LGT,{self.light_var.get()}")

    def _send_rgb(self):
        mode = self.rgb_mode.get()
        r = self.rgb_vars[0].get()
        g = self.rgb_vars[1].get()
        b = self.rgb_vars[2].get()
        self._send(f"$RGB,{mode},{r},{g},{b}")

    def _send_matrix(self):
        left = self.matrix_left.get()
        right = self.matrix_right.get()
        self._send(f"$MTX,{left},{right}")

    def _send_npm(self):
        # Get mode value from combo selection
        mode_idx = self.npm_mode_combo.current()
        mode = NPM_MODES[mode_idx][0]
        letter = self.npm_letter.get()[:1] or 'A'
        r = self.npm_r.get()
        g = self.npm_g.get()
        b = self.npm_b.get()
        self._send(f"$NPM,{mode},{letter},{r},{g},{b}")

    def _set_npm_color(self, r, g, b):
        self.npm_r.set(r)
        self.npm_g.set(g)
        self.npm_b.set(b)
        self._send_npm()

    def _send_npr(self):
        # Get mode value from combo selection
        mode_idx = self.npr_mode_combo.current()
        mode = NPR_MODES[mode_idx][0]
        r = self.npr_r.get()
        g = self.npr_g.get()
        b = self.npr_b.get()
        self._send(f"$NPR,{mode},{r},{g},{b}")

    def _set_npr_color(self, r, g, b):
        self.npr_r.set(r)
        self.npr_g.set(g)
        self.npr_b.set(b)
        self._send_npr()

    def _valve_open(self):
        """Send valve open command (only if not already commanded open)."""
        if not self.valve_commanded:
            self._send("$VLV,1")
            self.valve_commanded = True

    def _valve_close(self):
        """Send valve close command and reset commanded state."""
        self._send("$VLV,0")
        self.valve_commanded = False

    def _send_led_test(self):
        self._send("$FLG,1")

    def _all_servos(self, angle):
        # Only sets Base and Arm servos (not valve)
        for var in self.servo_vars:
            var.set(angle)
        self._send_servos()

    def _all_off(self):
        self._send("$LGT,0")
        self._send("$RGB,0,0,0,0")
        self._send("$MTX,0,0")
        self._send("$NPM,0,A,0,0,0")
        self._send("$NPR,0,0,0,0")
        self._send("$VLV,0")
        self.valve_commanded = False

    def on_close(self):
        self._disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = HardwareTestUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
