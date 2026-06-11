"""
Falcon Controller - PC Server
Receives joystick data from Flutter app → drives virtual Xbox 360 controller
Contains a dark-themed Tkinter GUI dashboard.
"""

import socket
import json
import threading
import time
import sys
import os
import subprocess
import shutil
import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext

# ── Configuration Constants ──────────────────────────────────────────────────
HOST = '0.0.0.0'
DEFAULT_PORT = 9000
DISCOVERY_PORT = 9001

# Global Server/Gamepad References
_gamepad = None
_server_sock = None
_client_conn = None
_udp_sock = None
_bt_server_sock = None
_bt_client_conn = None

_server_running = False
_sys_redirector = None

# ── Helper Functions ─────────────────────────────────────────────────────────

def clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))

def get_local_ip() -> str:
    """Get the active local network IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to an external host to find the active outgoing interface IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def check_vgamepad_quietly() -> bool:
    """Check if the vgamepad module is loadable and can create a gamepad device."""
    try:
        import vgamepad as vg
        # Attempt device instantiation to confirm driver service is actually running
        g = vg.VX360Gamepad()
        del g
        return True
    except Exception:
        return False

def find_adb_path() -> str:
    """Locate adb.exe in application directory, PATH, or local Android SDK."""
    # 1. Local execution dir
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local_adb = os.path.join(exe_dir, "adb.exe")
    if os.path.exists(local_adb):
        return local_adb

    # 2. PATH env variable
    adb_which = shutil.which("adb")
    if adb_which:
        return adb_which

    # 3. Default AppData Android SDK path
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        sdk_adb = os.path.join(userprofile, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe")
        if os.path.exists(sdk_adb):
            return sdk_adb

    return ""

def run_adb_reverse(port: int):
    """Run adb reverse tcp:port tcp:port in a subprocess."""
    adb_path = find_adb_path()
    if not adb_path:
        print("[-] ADB not found. Skipping programmatic USB reverse tunnel.")
        return False, "ADB Not Found"

    try:
        print(f"[*] Running: {adb_path} reverse tcp:{port} tcp:{port}")
        result = subprocess.run([adb_path, "reverse", f"tcp:{port}", f"tcp:{port}"],
                                capture_output=True, text=True, check=True)
        print(f"[+] ADB reverse tunnel active: {result.stdout.strip() if result.stdout else 'Success'}")
        return True, "Active"
    except Exception as e:
        print(f"[-] ADB reverse tunnel setup failed: {e}")
        return False, "Failed"

# ── Log Redirection (Thread Safe) ───────────────────────────────────────────

class ConsoleRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.running = True
        self.check_queue()

    def write(self, string):
        if self.running:
            self.queue.put(string)
        # Still mirror logs to standard console output
        sys.__stdout__.write(string)
        sys.__stdout__.flush()

    def flush(self):
        sys.__stdout__.flush()

    def check_queue(self):
        if not self.running:
            return
        try:
            while True:
                msg = self.queue.get_nowait()
                self.text_widget.configure(state='normal')
                self.text_widget.insert('end', msg)
                self.text_widget.configure(state='disabled')
                self.text_widget.see('end')
                self.queue.task_done()
        except queue.Empty:
            pass
        self.text_widget.after(50, self.check_queue)

    def stop(self):
        self.running = False

# ── Sockets and Client Handlers ──────────────────────────────────────────────

def handle_client(conn: socket.socket, gamepad):
    """Read newline-delimited JSON from the client and update the virtual gamepad."""
    buffer = ""
    conn.settimeout(0.5)  # 500ms timeout for safety heartbeat
    consecutive_timeouts = 0
    try:
        while _server_running:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                # Center joysticks for safety on timeout
                if gamepad:
                    gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                    gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                    gamepad.update()

                consecutive_timeouts += 1
                if consecutive_timeouts >= 5:
                    print("[-] Connection timed out (no heartbeat for 2.5s)")
                    break
                continue

            if not data:
                break

            consecutive_timeouts = 0
            buffer += data.decode('utf-8', errors='ignore')
            lines = buffer.split('\n')
            buffer = lines[-1]  # keep incomplete line

            for line in lines[:-1]:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    lx = clamp(float(d.get('lx', 0)))  # Yaw
                    ly = clamp(float(d.get('ly', 0)))  # Throttle
                    rx = clamp(float(d.get('rx', 0)))  # Roll
                    ry = clamp(float(d.get('ry', 0)))  # Pitch

                    # Map to Xbox sticks (Left stick: X=Yaw, Y=Throttle | Right stick: X=Roll, Y=Pitch)
                    if gamepad:
                        gamepad.left_joystick_float(x_value_float=lx, y_value_float=ly)
                        gamepad.right_joystick_float(x_value_float=rx, y_value_float=ry)
                        gamepad.update()

                except (json.JSONDecodeError, ValueError, KeyError):
                    pass  # skip malformed packets

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ── Background Thread Loops ──────────────────────────────────────────────────

def run_tcp_server_thread(port: int):
    global _server_sock, _client_conn, _gamepad, _server_running
    
    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _server_sock.bind((HOST, port))
        _server_sock.listen(1)
        print(f"[+] TCP server listening on {HOST}:{port}")
    except Exception as e:
        print(f"[-] Failed to bind TCP server on port {port}: {e}")
        stop_server_action()
        return

    while _server_running:
        try:
            conn, addr = _server_sock.accept()
            _client_conn = conn
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            print(f"[+] Client Connected: {addr[0]}:{addr[1]}")
            update_client_status(f"Connected (TCP: {addr[0]})", True)

            handle_client(conn, _gamepad)

            print("[-] Client Disconnected.")
            update_client_status("Disconnected", False)

            # Zero out gamepad on disconnect
            if _gamepad:
                _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                _gamepad.update()

        except OSError:
            break  # socket closed
        except Exception as e:
            print(f"[-] TCP loop error: {e}")
            break

def run_bluetooth_server_thread():
    global _bt_server_sock, _bt_client_conn, _gamepad, _server_running

    if not hasattr(socket, 'AF_BLUETOOTH') or not hasattr(socket, 'BTPROTO_RFCOMM'):
        update_bt_status("Disabled/No OS Support", 'disabled')
        return

    try:
        _bt_server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        _bt_server_sock.bind((socket.BDADDR_ANY, 4))  # Channel 4
        _bt_server_sock.listen(1)
        print("[+] Bluetooth RFCOMM server listening on channel 4")
        update_bt_status("Active", 'active')
    except Exception as e:
        print(f"[-] Bluetooth RFCOMM failed to start: {e}")
        update_bt_status("Disabled/No Adapter", 'disabled')
        if _bt_server_sock:
            try:
                _bt_server_sock.close()
            except Exception:
                pass
        return

    while _server_running:
        try:
            conn, addr = _bt_server_sock.accept()
            _bt_client_conn = conn
            print(f"[+] Bluetooth Client Connected: {addr[0]}")
            update_client_status("Connected (Bluetooth)", True)

            handle_client(conn, _gamepad)

            print("[-] Bluetooth Client Disconnected.")
            update_client_status("Disconnected", False)

            if _gamepad:
                _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                _gamepad.update()
        except OSError:
            break
        except Exception as e:
            print(f"[-] Bluetooth loop error: {e}")
            break

def run_udp_beacon_thread(port: int):
    global _udp_sock, _server_running
    _udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    beacon_data = json.dumps({
        "service": "AirSimController",
        "port": port
    }).encode('utf-8')

    while _server_running:
        try:
            _udp_sock.sendto(beacon_data, ('255.255.255.255', DISCOVERY_PORT))
        except OSError:
            break
        except Exception:
            pass
        time.sleep(1.0)

def run_adb_tunnel_thread(port: int):
    update_adb_status("Running...", 'checking')
    ok, msg = run_adb_reverse(port)
    update_adb_status(msg, 'active' if ok else 'failed')

# ── Server Actions ───────────────────────────────────────────────────────────

def start_server_action():
    global _server_running, _gamepad
    if _server_running:
        return

    try:
        port = int(port_var.get().strip())
        if not (1024 <= port <= 65535):
            raise ValueError()
    except ValueError:
        messagebox.showerror("Invalid Port", "Port must be an integer between 1024 and 65535.")
        return

    print(f"[*] Starting Falcon Controller Server on port {port}...")

    # Load virtual gamepad driver
    try:
        import vgamepad as vg
        _gamepad = vg.VX360Gamepad()
        update_driver_status("Active", 'active')
        print("[+] Virtual Xbox 360 Gamepad device created.")
    except Exception as e:
        update_driver_status("Not Found", 'failed')
        print(f"[-] Gamepad driver initialization failed: {e}")
        messagebox.showerror("Driver Missing",
                             "Failed to initialize virtual gamepad driver.\n\n"
                             "Please ensure the ViGEmBus gamepad driver is installed on this PC.")
        return

    _server_running = True
    update_button_states()

    # Update IP displays
    localhost_ip_var.set(f"127.0.0.1:{port}")
    wifi_ip = get_local_ip()
    wifi_ip_var.set(f"{wifi_ip}:{port}")

    # Launch threads
    threading.Thread(target=run_tcp_server_thread, args=(port,), daemon=True).start()
    threading.Thread(target=run_udp_beacon_thread, args=(port,), daemon=True).start()
    threading.Thread(target=run_bluetooth_server_thread, daemon=True).start()
    threading.Thread(target=run_adb_tunnel_thread, args=(port,), daemon=True).start()

def stop_server_action():
    global _server_running, _server_sock, _client_conn, _udp_sock, _bt_server_sock, _bt_client_conn, _gamepad
    if not _server_running:
        return

    print("[*] Stopping Falcon Controller Server...")
    _server_running = False

    # Close client sockets
    if _client_conn:
        try: _client_conn.close()
        except Exception: pass
        _client_conn = None

    if _bt_client_conn:
        try: _bt_client_conn.close()
        except Exception: pass
        _bt_client_conn = None

    # Close server sockets
    if _server_sock:
        try: _server_sock.close()
        except Exception: pass
        _server_sock = None

    if _udp_sock:
        try: _udp_sock.close()
        except Exception: pass
        _udp_sock = None

    if _bt_server_sock:
        try: _bt_server_sock.close()
        except Exception: pass
        _bt_server_sock = None

    # Clean up gamepad
    if _gamepad:
        try:
            _gamepad.left_joystick_float(0.0, 0.0)
            _gamepad.right_joystick_float(0.0, 0.0)
            _gamepad.update()
        except Exception: pass
        _gamepad = None

    update_button_states()
    update_client_status("Disconnected", False)
    update_adb_status("Inactive", 'disabled')
    update_bt_status("Inactive", 'disabled')
    print("[+] Server stopped successfully.")

def open_manual():
    # Look in script path or execution directory
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    manual_path = os.path.join(exe_dir, "INSTRUCTION_MANUAL.md")
    if not os.path.exists(manual_path):
        manual_path = "INSTRUCTION_MANUAL.md"

    if os.path.exists(manual_path):
        try:
            os.startfile(manual_path)
            print(f"[+] Opened instruction manual: {manual_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open instruction manual: {e}")
    else:
        messagebox.showerror("Error", "Instruction manual (INSTRUCTION_MANUAL.md) not found.")

# ── GUI Setup & Event Handling ───────────────────────────────────────────────

def create_accent_button(parent, text, command):
    btn = tk.Button(parent, text=text, command=command,
                    bg="#00E5FF", fg="#121212",
                    activebackground="#00D2EA", activeforeground="#121212",
                    font=("Helvetica", 9, "bold"), relief="flat", bd=0, cursor="hand2",
                    padx=12, pady=6)
    return btn

def update_button_states():
    if _server_running:
        start_btn.configure(state="disabled", bg="#2A2A2A", fg="#666666")
        stop_btn.configure(state="normal", bg="#FF5252", fg="#FFFFFF")
        port_entry.configure(state="disabled", bg="#1A1A1A", fg="#666666")
    else:
        start_btn.configure(state="normal", bg="#00E5FF", fg="#121212")
        stop_btn.configure(state="disabled", bg="#2A2A2A", fg="#666666")
        port_entry.configure(state="normal", bg="#1E1E1E", fg="#FFFFFF")

# Thread-safe UI update helpers
def update_status(var, val, fg_color, label_widget):
    def _update():
        var.set(val)
        if label_widget:
            label_widget.configure(fg=fg_color)
    root.after(0, _update)

def update_driver_status(val, status_type):
    # status_type: 'active', 'failed'
    color = "#00E676" if status_type == 'active' else "#FF5252"
    update_status(driver_status_var, val, color, driver_val_lbl)

def update_adb_status(val, status_type):
    # status_type: 'active', 'checking', 'failed', 'disabled'
    color = "#00E676" if status_type == 'active' else ("#00E5FF" if status_type == 'checking' else ("#888888" if status_type == 'disabled' else "#FF5252"))
    update_status(adb_status_var, val, color, adb_val_lbl)

def update_bt_status(val, status_type):
    # status_type: 'active', 'disabled'
    color = "#00E676" if status_type == 'active' else "#888888"
    update_status(bt_status_var, val, color, bt_val_lbl)

def update_client_status(val, connected):
    color = "#00E676" if connected else "#888888"
    update_status(client_status_var, val, color, client_val_lbl)

def on_enter_start(e):
    if start_btn["state"] == "normal":
        start_btn.configure(bg="#00E676")

def on_leave_start(e):
    if start_btn["state"] == "normal":
        start_btn.configure(bg="#00E5FF")

def on_enter_stop(e):
    if stop_btn["state"] == "normal":
        stop_btn.configure(bg="#FF7373")

def on_leave_stop(e):
    if stop_btn["state"] == "normal":
        stop_btn.configure(bg="#FF5252")

def on_close():
    if _server_running:
        if messagebox.askokcancel("Quit", "The server is running. Stop the server and exit?"):
            stop_server_action()
        else:
            return
    
    # Clean up redirector
    if _sys_redirector:
        _sys_redirector.stop()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    root.destroy()

# ── Main Entry Point ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Initialize main GUI window
    root = tk.Tk()
    root.title("FALCON Controller Server")
    root.geometry("640x550")
    root.minsize(640, 500)
    root.configure(bg="#121212")

    # Set Window Icon
    icon_name = "icon.ico"
    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, icon_name)
    else:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)
    
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    # GUI Variables
    port_var = tk.StringVar(value=str(DEFAULT_PORT))
    wifi_ip_var = tk.StringVar(value="Checking...")
    localhost_ip_var = tk.StringVar(value="127.0.0.1:9000")
    driver_status_var = tk.StringVar(value="Checking...")
    adb_status_var = tk.StringVar(value="Inactive")
    bt_status_var = tk.StringVar(value="Checking...")
    client_status_var = tk.StringVar(value="Disconnected")

    # Header Frame
    header_frame = tk.Frame(root, bg="#121212", pady=15)
    header_frame.pack(fill="x", padx=20)

    title_lbl = tk.Label(header_frame, text="FALCON CONTROLLER", bg="#121212", fg="#00E5FF", font=("Helvetica", 18, "bold"))
    title_lbl.pack(anchor="w")
    subtitle_lbl = tk.Label(header_frame, text="Xbox 360 Controller Emulation Bridge for Android Client", bg="#121212", fg="#888888", font=("Helvetica", 9, "italic"))
    subtitle_lbl.pack(anchor="w", pady=(2, 0))

    # Dashboard Grid Container
    dash_frame = tk.Frame(root, bg="#121212")
    dash_frame.pack(fill="x", padx=12, pady=5)
    
    dash_frame.columnconfigure(0, weight=1)
    dash_frame.columnconfigure(1, weight=1)

    # Card Constructor Helper
    def create_card(title, var, row, col):
        card = tk.Frame(dash_frame, bg="#1E1E1E", padx=12, pady=10, highlightbackground="#2A2A2A", highlightthickness=1)
        card.grid(row=row, column=col, padx=8, pady=6, sticky="nsew")
        
        lbl_title = tk.Label(card, text=title.upper(), bg="#1E1E1E", fg="#888888", font=("Helvetica", 8, "bold"))
        lbl_title.pack(anchor="w")
        
        lbl_val = tk.Label(card, textvariable=var, bg="#1E1E1E", fg="#FFFFFF", font=("Consolas", 10, "bold"))
        lbl_val.pack(anchor="w", pady=(4, 0))
        return lbl_val

    # Populate status dashboard cards
    wifi_ip_val_lbl = create_card("Local Wi-Fi IP", wifi_ip_var, 0, 0)
    localhost_val_lbl = create_card("Localhost IP (USB)", localhost_ip_var, 0, 1)
    driver_val_lbl = create_card("Gamepad Driver", driver_status_var, 1, 0)
    adb_val_lbl = create_card("ADB USB Tunnel", adb_status_var, 1, 1)
    bt_val_lbl = create_card("Bluetooth RFCOMM", bt_status_var, 2, 0)
    client_val_lbl = create_card("Client Connection", client_status_var, 2, 1)

    # Controls Row Frame
    ctrl_frame = tk.Frame(root, bg="#121212", pady=10)
    ctrl_frame.pack(fill="x", padx=20)

    start_btn = create_accent_button(ctrl_frame, "START SERVER", start_server_action)
    start_btn.bind("<Enter>", on_enter_start)
    start_btn.bind("<Leave>", on_leave_start)
    start_btn.pack(side="left", padx=(0, 10))

    stop_btn = tk.Button(ctrl_frame, text="STOP SERVER", command=stop_server_action,
                         bg="#FF5252", fg="#FFFFFF",
                         activebackground="#D32F2F", activeforeground="#FFFFFF",
                         font=("Helvetica", 9, "bold"), relief="flat", bd=0, cursor="hand2",
                         padx=12, pady=6)
    stop_btn.bind("<Enter>", on_enter_stop)
    stop_btn.bind("<Leave>", on_leave_stop)
    stop_btn.pack(side="left", padx=10)

    # Port config subframe
    port_subframe = tk.Frame(ctrl_frame, bg="#1E1E1E", padx=5, pady=2, highlightbackground="#2A2A2A", highlightthickness=1)
    port_subframe.pack(side="left", padx=10)

    port_lbl = tk.Label(port_subframe, text="PORT:", bg="#1E1E1E", fg="#888888", font=("Helvetica", 8, "bold"))
    port_lbl.pack(side="left", padx=(5, 5))

    port_entry = tk.Entry(port_subframe, textvariable=port_var, width=6, bg="#1E1E1E", fg="#FFFFFF",
                          insertbackground="#FFFFFF", relief="flat", font=("Consolas", 10, "bold"))
    port_entry.pack(side="left", padx=(0, 5))

    manual_btn = tk.Button(ctrl_frame, text="OPEN MANUAL", command=open_manual,
                           bg="#37474F", fg="#FFFFFF",
                           activebackground="#455A64", activeforeground="#FFFFFF",
                           font=("Helvetica", 9, "bold"), relief="flat", bd=0, cursor="hand2",
                           padx=12, pady=6)
    manual_btn.pack(side="right")

    # Console output frame
    log_frame = tk.Frame(root, bg="#121212")
    log_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))

    lbl_log = tk.Label(log_frame, text="CONSOLE LOGGER", bg="#121212", fg="#888888", font=("Helvetica", 8, "bold"))
    lbl_log.pack(anchor="w", pady=(0, 4))

    console_text = scrolledtext.ScrolledText(log_frame, bg="#0C0C0C", fg="#E0E0E0", insertbackground="#FFFFFF",
                                             relief="flat", font=("Consolas", 9), state="disabled", highlightbackground="#2A2A2A", highlightthickness=1)
    console_text.pack(fill="both", expand=True)

    # Redirect system streams to log window
    _sys_redirector = ConsoleRedirector(console_text)
    sys.stdout = _sys_redirector
    sys.stderr = _sys_redirector

    # Initialize Driver/IP info
    driver_installed = check_vgamepad_quietly()
    update_driver_status("Active" if driver_installed else "Not Found", 'active' if driver_installed else 'failed')
    
    wifi_ip = get_local_ip()
    wifi_ip_var.set(f"{wifi_ip}:{DEFAULT_PORT}")
    
    # Check Bluetooth availability
    if not hasattr(socket, 'AF_BLUETOOTH') or not hasattr(socket, 'BTPROTO_RFCOMM'):
        update_bt_status("Disabled/No OS Support", 'disabled')
    else:
        update_bt_status("Inactive", 'disabled')

    update_button_states()

    # Auto-start server on load
    root.after(300, start_server_action)

    # Bind Close Window event
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Run TK Main Loop
    root.mainloop()
