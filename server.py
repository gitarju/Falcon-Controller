"""
AirSim Controller - PC Server
Receives joystick data from Flutter app → drives virtual Xbox 360 controller

Install deps:
    pip install -r requirements.txt

Run:
    python server.py [--port PORT]

Default port: 9000
"""

import socket
import json
import threading
import time
import sys
import signal
import argparse

# ── ANSI color codes ─────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

HOST = '0.0.0.0'

# ── Axis mapping ─────────────────────────────────────────────────────────────
#
#  Flutter left stick:
#    lx = Yaw        → Xbox right trigger axis  (mapped to left stick X)
#    ly = Throttle   → Xbox left stick Y
#
#  Flutter right stick:
#    rx = Roll       → Xbox right stick X
#    ry = Pitch      → Xbox right stick Y
#
#  AirSim default Xbox binding:
#    Left stick X  = Yaw
#    Left stick Y  = Throttle
#    Right stick X = Roll
#    Right stick Y = Pitch
# ─────────────────────────────────────────────────────────────────────────────

# Global references for graceful shutdown
_gamepad = None
_server_sock = None


def clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# ── Startup self-checks ──────────────────────────────────────────────────────

def check_vgamepad():
    """Verify that vgamepad can be imported (ViGEmBus driver must be installed)."""
    try:
        import vgamepad  # noqa: F401
        print(f"  {GREEN}✓{RESET} vgamepad module loaded successfully")
        return True
    except ImportError:
        print(f"  {RED}✗ vgamepad is not installed!{RESET}")
        print(f"    Run: {CYAN}pip install vgamepad{RESET}")
        print(f"    Also make sure the ViGEmBus driver is installed:")
        print(f"    {CYAN}https://github.com/nefarius/ViGEmBus/releases{RESET}")
        return False


def check_port_free(port: int):
    """Verify the TCP port is available before starting the server."""
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.bind((HOST, port))
        test_sock.close()
        print(f"  {GREEN}✓{RESET} Port {port} is available")
        return True
    except OSError:
        print(f"  {RED}✗ Port {port} is already in use!{RESET}")
        print(f"    Another instance may be running, or another program is using this port.")
        print(f"    Close the other program or use {CYAN}--port{RESET} to pick a different port.")
        return False


def run_self_checks(port: int):
    """Run all startup checks. Returns True if all pass."""
    print(f"\n{BOLD}Running startup checks...{RESET}")
    ok = True
    if not check_vgamepad():
        ok = False
    if not check_port_free(port):
        ok = False
    if ok:
        print(f"  {GREEN}All checks passed!{RESET}\n")
    else:
        print(f"\n  {RED}Some checks failed. Please fix the issues above.{RESET}")
    return ok


# ── Signal handling ──────────────────────────────────────────────────────────

def _shutdown_handler(signum, frame):
    """Handle Ctrl+C gracefully: reset gamepad, close sockets, exit."""
    global _gamepad, _server_sock
    print(f"\n\n{YELLOW}[AirSim Controller]{RESET} Ctrl+C received — shutting down gracefully...")

    # Reset gamepad to neutral
    if _gamepad is not None:
        try:
            _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
            _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
            _gamepad.update()
            print(f"  {GREEN}✓{RESET} Virtual gamepad reset to zero")
        except Exception:
            pass

    # Close server socket
    if _server_sock is not None:
        try:
            _server_sock.close()
            print(f"  {GREEN}✓{RESET} Server socket closed")
        except Exception:
            pass

    print(f"{GREEN}[AirSim Controller]{RESET} Goodbye!\n")
    sys.exit(0)


# ── UDP discovery beacon ─────────────────────────────────────────────────────

def broadcast_beacon(server_port: int):
    """Broadcast a UDP beacon so the Flutter app can auto-discover this server."""
    beacon_port = 9001  # Fixed discovery port
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    beacon_data = json.dumps({
        "service": "AirSimController",
        "port": server_port
    }).encode('utf-8')
    while True:
        try:
            udp_sock.sendto(beacon_data, ('255.255.255.255', beacon_port))
        except Exception:
            pass
        time.sleep(1.0)


# ── Client handler ───────────────────────────────────────────────────────────

def handle_client(conn: socket.socket, gamepad):
    """Read newline-delimited JSON from the client and update the virtual gamepad."""
    buffer = ""
    conn.settimeout(0.5)  # 500ms timeout for safety heartbeat
    consecutive_timeouts = 0
    try:
        while True:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                # Timeout: client might have disconnected or is lagging.
                # Center joysticks for safety.
                gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                gamepad.update()
                
                consecutive_timeouts += 1
                if consecutive_timeouts >= 5:
                    print(f"  {RED}✗ Connection timed out (no heartbeat for 2.5s){RESET}")
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

                    # Map to Xbox sticks
                    # Left stick: X = Yaw, Y = Throttle
                    gamepad.left_joystick_float(
                        x_value_float=lx,
                        y_value_float=ly
                    )
                    # Right stick: X = Roll, Y = Pitch
                    gamepad.right_joystick_float(
                        x_value_float=rx,
                        y_value_float=ry
                    )
                    gamepad.update()

                except (json.JSONDecodeError, ValueError, KeyError):
                    pass  # skip malformed packets

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        conn.close()

def run_bluetooth_server(gamepad):
    """Start a background Bluetooth RFCOMM server for the Flutter client."""
    # Check if Bluetooth socket support is available in Python
    if not hasattr(socket, 'AF_BLUETOOTH') or not hasattr(socket, 'BTPROTO_RFCOMM'):
        print(f"{YELLOW}[AirSim Controller] Bluetooth is not supported by this Python environment.{RESET}")
        return

    bt_server_sock = None
    try:
        bt_server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        bt_server_sock.bind((socket.BDADDR_ANY, 4))  # Channel 4
        bt_server_sock.listen(1)
        print(f"{CYAN}[AirSim Controller]{RESET} Bluetooth RFCOMM server listening on channel 4")
    except Exception:
        print(f"{YELLOW}[AirSim Controller] Bluetooth server failed to start (disabled or no adapter).{RESET}")
        if bt_server_sock:
            try:
                bt_server_sock.close()
            except Exception:
                pass
        return

    while True:
        try:
            conn, addr = bt_server_sock.accept()
            print(f"{GREEN}[+] Bluetooth Connected:{RESET} {addr[0]}")
            handle_client(conn, gamepad)
            print(f"{YELLOW}[-] Bluetooth Disconnected.{RESET} Waiting for Bluetooth connection...\n")
            
            # Zero out controller on disconnect
            gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
            gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
            gamepad.update()
        except OSError:
            break
        except Exception:
            pass


# ── Main server loop ─────────────────────────────────────────────────────────

def run_server(port: int):
    """Start the TCP server, create the virtual gamepad, and accept connections."""
    global _gamepad, _server_sock

    import vgamepad as vg

    _gamepad = vg.VX360Gamepad()
    print(f"{GREEN}[AirSim Controller]{RESET} Virtual Xbox 360 gamepad created.")

    # Start UDP broadcast beacon thread
    beacon_port = 9001  # Fixed discovery port
    udp_thread = threading.Thread(target=broadcast_beacon, args=(port,), daemon=True)
    udp_thread.start()
    print(f"{CYAN}[AirSim Controller]{RESET} UDP discovery beacon broadcasting on port {beacon_port}.")

    # Start Bluetooth server thread
    bt_thread = threading.Thread(target=run_bluetooth_server, args=(_gamepad,), daemon=True)
    bt_thread.start()

    # Bind TCP server
    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_sock.bind((HOST, port))
    _server_sock.listen(1)

    print(f"{CYAN}[AirSim Controller]{RESET} TCP server listening on {HOST}:{port}")
    print(f"{YELLOW}[AirSim Controller]{RESET} Waiting for Flutter app connection...\n")

    # Register Ctrl+C handler
    signal.signal(signal.SIGINT, _shutdown_handler)

    while True:
        try:
            conn, addr = _server_sock.accept()
            if conn.family == socket.AF_INET:
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass
            print(f"{GREEN}[+] Connected:{RESET} {addr[0]}:{addr[1]}")
            handle_client(conn, _gamepad)
            print(f"{YELLOW}[-] Disconnected.{RESET} Waiting for new connection...\n")

            # Zero out controller on disconnect
            _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
            _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
            _gamepad.update()

        except OSError:
            # Socket was closed (e.g. during shutdown)
            break

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


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Configure stdout/stderr to use UTF-8 on Windows to prevent UnicodeEncodeError when printing ✓/✗
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    # Enable ANSI escape codes on Windows 10+
    import os
    os.system('')  # enables ANSI processing in Windows terminal

    parser = argparse.ArgumentParser(
        description="AirSim Controller Server — virtual Xbox gamepad bridge"
    )
    parser.add_argument(
        '--port', type=int, default=9000,
        help='TCP port to listen on (default: 9000). UDP beacon uses port 9001.'
    )
    args = parser.parse_args()

    local_ip = get_local_ip()
    print(f"\n{BOLD}{'=' * 52}{RESET}")
    print(f"{BOLD}   AirSim Controller Server{RESET}")
    print(f"{BOLD}{'=' * 52}{RESET}")
    print(f"  TCP port   : {CYAN}{args.port}{RESET}")
    print(f"  UDP beacon : {CYAN}9001{RESET}")
    print(f"\n{BOLD}  To connect from the Flutter app:{RESET}")
    print(f"  - USB (ADB) : IP {GREEN}127.0.0.1{RESET} and Port {GREEN}{args.port}{RESET}")
    print(f"  - Wi-Fi     : IP {GREEN}{local_ip}{RESET} and Port {GREEN}{args.port}{RESET}")
    print(f"                (Or wait for Auto-Discovery to find it)")
    print(f"{BOLD}{'=' * 52}{RESET}")

    if not run_self_checks(args.port):
        sys.exit(1)

    run_server(args.port)
