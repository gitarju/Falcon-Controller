import os
import sys
import socket
import shutil
import subprocess

def clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))

def get_local_ip() -> str:
    """Get the active local network IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
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

def open_manual_action():
    """Locate and open the instruction manual."""
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    # Check possible manual locations (docs/ relative to root, or in same dir if packaged)
    possible_paths = [
        os.path.join(exe_dir, "docs", "INSTRUCTION_MANUAL.md"),
        os.path.join(exe_dir, "INSTRUCTION_MANUAL.md"),
        os.path.join(os.getcwd(), "docs", "INSTRUCTION_MANUAL.md"),
        os.path.join(os.getcwd(), "INSTRUCTION_MANUAL.md")
    ]
    
    manual_path = ""
    for path in possible_paths:
        if os.path.exists(path):
            manual_path = path
            break
            
    if manual_path:
        try:
            os.startfile(manual_path)
            print(f"[+] Opened instruction manual: {manual_path}")
            return True, ""
        except Exception as e:
            return False, f"Could not open manual: {e}"
    else:
        return False, "Instruction manual (INSTRUCTION_MANUAL.md) not found."
