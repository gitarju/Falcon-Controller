import socket
import json
import threading
import time
import sys
import atexit
from PyQt6.QtCore import QObject, pyqtSignal
from src.utils import clamp, get_local_ip, check_vgamepad_quietly, run_adb_reverse

class ServerSignals(QObject):
    client_status_changed = pyqtSignal(str, bool)
    driver_status_changed = pyqtSignal(str, str)
    adb_status_changed = pyqtSignal(str, str)
    bt_status_changed = pyqtSignal(str, str)
    server_stopped_signal = pyqtSignal()

# Shared constants
UDP_DISCOVERY_PORT = 9001

# Global variables for socket references and state
_gamepad = None
_server_sock = None
_client_conn = None
_udp_sock = None
_bt_server_sock = None
_bt_client_conn = None

_server_running = False
signals = ServerSignals()

# Synchronization locks
_gamepad_lock = threading.Lock()
_state_lock = threading.Lock()

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
                with _gamepad_lock:
                    if _gamepad:
                        _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                        _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                        _gamepad.update()

                consecutive_timeouts += 1
                if consecutive_timeouts >= 5:
                    print("[-] Connection timed out (no heartbeat for 2.5s)")
                    break
                continue

            if not data:
                break

            consecutive_timeouts = 0
            buffer += data.decode('utf-8', errors='ignore')

            # Issue 35: DoS Protection - limit buffer size
            if len(buffer) > 4096:
                print("[-] Warning: Client buffer exceeded size limit (4KB). Disconnecting.")
                break

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

                    with _gamepad_lock:
                        if _gamepad:
                            _gamepad.left_joystick_float(x_value_float=lx, y_value_float=ly)
                            _gamepad.right_joystick_float(x_value_float=rx, y_value_float=ry)
                            _gamepad.update()

                except (json.JSONDecodeError, ValueError, KeyError):
                    pass  # skip malformed packets

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_tcp_server_thread(port: int):
    global _server_sock, _client_conn, _gamepad, _server_running
    
    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _server_sock.bind(('0.0.0.0', port))
        _server_sock.listen(1)
        print(f"[+] TCP server listening on 0.0.0.0:{port}")
        # Issue 33: Log security warning
        print("[!] Security Warning: Server is bound to 0.0.0.0 (all network interfaces) with no authentication.")
        print("[!] Any device on your local Wi-Fi network can connect and emulate inputs.")
    except Exception as e:
        print(f"[-] Failed to bind TCP server on port {port}: {e}")
        stop_server()
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
            signals.client_status_changed.emit(f"Connected (TCP: {addr[0]})", True)

            handle_client(conn, _gamepad)

            print("[-] Client Disconnected.")
            signals.client_status_changed.emit("Disconnected", False)

            with _gamepad_lock:
                if _gamepad:
                    _gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                    _gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                    _gamepad.update()

        except OSError:
            break  # socket closed on stop
        except Exception as e:
            print(f"[-] TCP loop error: {e}")
            break


def run_bluetooth_server_thread():
    global _bt_server_sock, _bt_client_conn, _gamepad, _server_running

    if not hasattr(socket, 'AF_BLUETOOTH') or not hasattr(socket, 'BTPROTO_RFCOMM'):
        signals.bt_status_changed.emit("Disabled/No OS Support", 'disabled')
        return

    try:
        _bt_server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        # Issue 36: Guard BDADDR_ANY
        bdaddr = getattr(socket, 'BDADDR_ANY', '00:00:00:00:00:00')
        _bt_server_sock.bind((bdaddr, 4))  # Channel 4
        _bt_server_sock.listen(1)
        print("[+] Bluetooth RFCOMM server listening on channel 4")
        signals.bt_status_changed.emit("Active", 'active')
    except Exception as e:
        print(f"[-] Bluetooth RFCOMM failed to start: {e}")
        signals.bt_status_changed.emit("Disabled/No Adapter", 'disabled')
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
            signals.client_status_changed.emit("Connected (Bluetooth)", True)

            handle_client(conn, _gamepad)

            print("[-] Bluetooth Client Disconnected.")
            signals.client_status_changed.emit("Disconnected", False)

            with _gamepad_lock:
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
            _udp_sock.sendto(beacon_data, ('255.255.255.255', UDP_DISCOVERY_PORT))
        except OSError:
            break
        except Exception:
            pass
        time.sleep(1.0)


def run_adb_tunnel_thread(port: int):
    signals.adb_status_changed.emit("Running...", 'checking')
    ok, msg = run_adb_reverse(port)
    signals.adb_status_changed.emit(msg, 'active' if ok else 'failed')


def start_server(port: int):
    global _server_running, _gamepad
    with _state_lock:
        if _server_running:
            return True

        print(f"[*] Starting Falcon Controller Server on port {port}...")

        # Load virtual gamepad driver
        try:
            import vgamepad as vg
            with _gamepad_lock:
                _gamepad = vg.VX360Gamepad()
            signals.driver_status_changed.emit("Active", 'active')
            print("[+] Virtual Xbox 360 Gamepad device created.")
        except Exception as e:
            signals.driver_status_changed.emit("Not Found", 'failed')
            print(f"[-] Gamepad driver initialization failed: {e}")
            return False

        _server_running = True

    # Launch threads (outside of state lock to avoid blocking UI)
    threading.Thread(target=run_tcp_server_thread, args=(port,), daemon=True).start()
    threading.Thread(target=run_udp_beacon_thread, args=(port,), daemon=True).start()
    threading.Thread(target=run_bluetooth_server_thread, daemon=True).start()
    threading.Thread(target=run_adb_tunnel_thread, args=(port,), daemon=True).start()
    
    return True


def stop_server():
    global _server_running, _server_sock, _client_conn, _udp_sock, _bt_server_sock, _bt_client_conn, _gamepad
    with _state_lock:
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
        with _gamepad_lock:
            if _gamepad:
                try:
                    _gamepad.left_joystick_float(0.0, 0.0)
                    _gamepad.right_joystick_float(0.0, 0.0)
                    _gamepad.update()
                except Exception: pass
                _gamepad = None

        signals.client_status_changed.emit("Disconnected", False)
        signals.adb_status_changed.emit("Inactive", 'disabled')
        signals.bt_status_changed.emit("Inactive", 'disabled')
        signals.server_stopped_signal.emit()
        print("[+] Server stopped successfully.")


def is_running():
    return _server_running

# Issue 34: Register atexit handler to ensure phantom gamepad device is deleted on exit
atexit.register(stop_server)
