import os
import sys
import shutil
import subprocess

def run_pyinstaller(root_dir):
    print("[*] Running PyInstaller build for src/main.py...")
    pyinstaller_exe = os.path.join(root_dir, "venv", "Scripts", "pyinstaller.exe")
    
    # Check if pyinstaller exists
    if not os.path.exists(pyinstaller_exe):
        print(f"[-] PyInstaller not found at {pyinstaller_exe}. Please run 'pip install pyinstaller'.")
        return False
        
    cmd = [
        pyinstaller_exe,
        "--noconsole",
        "--onefile",
        "--icon=" + os.path.join("assets", "icon.ico"),
        "--add-data", "assets/icon.ico;assets",
        "--name=server",
        os.path.join("src", "main.py")
    ]
    print(f"[*] Executing command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=root_dir)
    if result.returncode == 0:
        print("[+] PyInstaller build completed successfully.")
        return True
    else:
        print(f"[-] PyInstaller build failed with exit code: {result.returncode}")
        return False

def assemble_staging(root_dir):
    print("[*] Assembling installer staging directory (dist_bin)...")
    dist_bin = os.path.join(root_dir, "installer", "dist_bin")
    
    # Recreate clean dist_bin folder
    if os.path.exists(dist_bin):
        shutil.rmtree(dist_bin)
    os.makedirs(dist_bin, exist_ok=True)
    
    # Source file mappings
    files_to_copy = [
        # (source, name)
        (os.path.join(root_dir, "dist", "server.exe"), "server.exe"),
        (os.path.join(root_dir, "assets", "icon.ico"), "icon.ico"),
        (os.path.join(root_dir, "docs", "README.md"), "README.md"),
        (os.path.join(root_dir, "docs", "INSTRUCTION_MANUAL.md"), "INSTRUCTION_MANUAL.md"),
        (r"C:\Users\arjun\AppData\Local\Android\Sdk\platform-tools\adb.exe", "adb.exe"),
        (r"C:\Users\arjun\AppData\Local\Android\Sdk\platform-tools\AdbWinApi.dll", "AdbWinApi.dll"),
        (r"C:\Users\arjun\AppData\Local\Android\Sdk\platform-tools\AdbWinUsbApi.dll", "AdbWinUsbApi.dll"),
        (os.path.join(root_dir, "venv", "Lib", "site-packages", "vgamepad", "win", "vigem", "install", "x64", "ViGEmBusSetup_x64.msi"), "ViGEmBusSetup_x64.msi")
    ]
    
    for src, name in files_to_copy:
        dest = os.path.join(dist_bin, name)
        if os.path.exists(src):
            print(f"Copying {src} -> {dest}")
            shutil.copy2(src, dest)
        else:
            print(f"[-] ERROR: Source file does not exist: {src}")
            return False
            
    print("[+] Staging folder assembled successfully under installer/dist_bin/")
    return True

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, ".."))
    
    if run_pyinstaller(root_dir):
        if assemble_staging(root_dir):
            print("[+] Build and assembly completed successfully.")
            sys.exit(0)
    sys.exit(1)
