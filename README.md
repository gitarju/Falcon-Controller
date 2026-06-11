# FALCON Controller - Setup and User Manual

FALCON Controller is a drone simulation interface linking an Android client app to an AirSim simulator server on Windows. The system emulates an Xbox 360 controller using the ViGEmBus driver to stream flight controls and custom calibration settings over USB, Wi-Fi, or Bluetooth.

The PC server is implemented as a professional desktop console using **PyQt6** and packaged into a native Windows installer.

### [📥 Download Windows PC Setup Wizard](https://github.com/gitarju/Falcon-Controller/raw/main/output/FALCON_Controller_Server_Setup.exe) | [📥 Download Android App APK (v1.0.0)](https://github.com/gitarju/Falcon-Controller/raw/main/FALCON-Controller-v1.0.0.apk)

---

## Repository Structure

The project directory is structured cleanly for easy cloning and development:
```
├── .gitignore
├── requirements.txt         # Package dependencies (PyQt6, vgamepad, pyinstaller, Pillow)
├── setup_and_run.bat        # One-click developer build and execution script
├── src/                     # PyQt6 Application Python source code
│   ├── main.py              # Application entry point
│   ├── gui.py               # PyQt6 windows, layouts, stylesheets, and custom signals
│   ├── server_core.py       # TCP, UDP discovery, and Bluetooth RFCOMM server threads
│   └── utils.py             # File system, IP, ADB, and manual helper methods
├── assets/                  # Graphics and icons (icon.png, icon.ico)
├── docs/                    # Offline documentation (README, Instruction Manual)
├── installer/               # Installer assets and configurations
│   ├── setup_wizard.iss     # Inno Setup 6 packaging script
│   └── dist_bin/            # Temporary build staging directory
└── output/                  # Final compiled Windows Setup Wizard (.exe)
```

---

## Features

* **PyQt6 GUI Console**: A dark-themed, high-performance desktop application interface with real-time status indicators (Wi-Fi, Bluetooth, ADB, Driver, Client).
* **Smart Installer**: An installation wizard that automatically checks the system registry to see if the **ViGEmBus Gamepad Driver** is installed, offering to run the installer silently if missing.
* **USB Cable Connection (ADB)**: Establishes a zero-lag connection by running a reverse TCP tunnel automatically on server startup.
* **Wi-Fi Auto-Discovery**: Broadcasts UDP beacons on port 9001 so the Android app auto-detects the PC IP address on local networks.
* **Bluetooth RFCOMM Link**: Back-up offline wireless link using Classic Bluetooth SPP (Serial Port Profile).
* **Monospace Log Viewer**: Real-time console logs are redirected thread-safely directly inside the PyQt6 dashboard.

---

## Step 1: PC Installation

1. **Run the Installer**:
   * Download the latest [FALCON_Controller_Server_Setup.exe](https://github.com/gitarju/Falcon-Controller/raw/main/output/FALCON_Controller_Server_Setup.exe).
   * Double-click to run the setup wizard (grant Administrator permissions so it can configure registry keys and gamepad drivers).
2. **Setup Wizard Steps**:
   * The setup wizard will analyze your system for the virtual gamepad driver.
   * If missing, check the **Install ViGEmBus Virtual Gamepad Driver** checkbox during the tasks stage.
3. **Launch**:
   * Use the Desktop or Start Menu shortcut to launch the **FALCON Controller Server**. It will load and immediately auto-start the server.

---

## Step 2: Phone Setup (First Time Only)

1. **Install the App (APK)**:
   * Copy `FALCON-Controller-v1.0.0.apk` to your Android device and install it (allow installations from "Unknown Sources" if prompted).
2. **Enable USB Debugging (Only required for USB Cable connections)**:
   * Go to **Settings** -> **About Phone** on your Android device.
   * Find the **Build Number** and tap it 7 times until you see the notification: *"You are now a developer!"*.
   * Go back to the main Settings menu, open **Developer Options**, and toggle **USB Debugging** to **ON**.
   * Connect your phone to your PC via a USB cable. When prompted with *"Allow USB debugging?"*, check *"Always allow from this computer"* and tap **Allow**.

---

## Step 3: Connection Guide

### Option A: USB Cable Connection (Recommended - Zero Lag)
1. Plug your phone into the PC using a USB cable.
2. Verify USB Debugging is ON.
3. Open the PC Server. The status card **ADB USB Tunnel** will change to `Active` (indicating port forwarding is set up).
4. Launch the Android application, keep the default IP set to `127.0.0.1` and Port to `9000`.
5. Tap the cyan **CONNECT** button.

### Option B: Wi-Fi Connection (Wireless)
1. Ensure both your PC and phone are connected to the same Wi-Fi network.
2. Open the PC Server. The card **Local Wi-Fi IP** will show your PC's IP address (e.g. `192.168.1.15:9000`).
3. Launch the Android application. The app's auto-discovery will automatically detect and populate the IP.
4. Tap the cyan **CONNECT** button.

### Option C: Bluetooth Connection (Wireless & Offline)
1. Enable Bluetooth on both your PC and phone.
2. Pair your phone with your PC in the Windows Bluetooth settings.
3. Open the PC Server. Verify **Bluetooth RFCOMM** is `Active`.
4. Launch the Android application.
5. Tap the green **Bluetooth icon** in the top navigation bar, select your PC from the paired devices list, and connect.

---

## Developer Guide (Running and Compiling from Source)

### Prerequisites
1. Python 3.10+ (make sure it's added to your PATH).
2. Inno Setup 6 (to compile the setup wizard).

### Run from Source
1. Double-click `setup_and_run.bat` in the root directory.
   *This batch file will automatically configure a python virtual environment, install package dependencies from `requirements.txt`, check the gamepad driver, and launch the PyQt6 application console.*

### Compile and Package Standalone Binary
To compile the source code into a standalone `.exe` and assemble the installer staging folder:
1. Run the build script using the virtual environment:
   ```bash
   .\venv\Scripts\python.exe build_scripts\build_exe.py
   ```
   *This will run PyInstaller to bundle the PyQt6 application into `dist/server.exe`, compile `assets/icon.ico` from `assets/icon.png`, and assemble all binaries and manuals in `installer/dist_bin/`.*

### Compile Setup Wizard Installer
1. Open PowerShell and run the Inno Setup compiler:
   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer/setup_wizard.iss
   ```
   *The resulting installer `FALCON_Controller_Server_Setup.exe` will be generated under the root `output/` directory.*

---

## Developer Team

* Abhisudh k S
* Arjun A
* Muhammed Sijadh M P
* Sruthi E P
