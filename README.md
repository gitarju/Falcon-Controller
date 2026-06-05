# FALCON Controller - Setup and User Manual

FALCON Controller is a drone simulation interface linking an Android client app to an AirSim simulator server on Windows. The system emulates an Xbox 360 controller using the ViGEmBus driver to stream flight controls and custom calibration settings over USB, Wi-Fi, or Bluetooth.

### [📥 Download Release APK (v1.0.0)](https://github.com/gitarju/Falcon-Controller/raw/main/FALCON-Controller-v1.0.0.apk)

---

## Features

* **Multi-Mode Connection**: Connect via USB debugging tunnel (ADB reverse), Local Wi-Fi (Auto-Discovery), or Classic Bluetooth (RFCOMM/SPP).
* **Xbox 360 Gamepad Emulation**: Emulates a physical controller using Windows ViGEmBus and the python-vgamepad driver.
* **Control Calibration**: In-app configurations for deadzone size, sensitivity curves (exponential scaling), and axis inversions (Yaw, Throttle, Roll, Pitch).
* **Real-time Failure Prediction (FALCON Project)**: Features a hidden HUD dialog detailing failure prediction and autonomous landing systems.

---

## Step 1: PC Setup (First Time Only)

1. **Install Python**:
   * Download and install Python 3.10+ from the official download site (python.org).
   * Important: During installation, make sure to check the box that says "Add Python to PATH".

2. **Install the Virtual Gamepad Driver (ViGEmBus)**:
   * The server emulates an Xbox 360 controller using the ViGEmBus driver.
   * Download the latest installer from the official repository: [ViGEmBus Releases](https://github.com/nefarius/ViGEmBus/releases).
   * Run the `.msi` installer, complete the setup, and restart your PC if prompted.

3. **Launch the Server**:
   * Double-click `setup_and_run.bat` in the project root.
   * The script will automatically check/create a Python virtual environment, install dependencies, verify your virtual gamepad driver, establish the ADB port-forwarding tunnel, and start the TCP/UDP and Bluetooth listeners.

---

## Step 2: Phone Setup (First Time Only)

1. **Install the App (APK)**:
   * Copy `FALCON-Controller-v1.0.0.apk` to your Android device and install it (allow installations from "Unknown Sources" if prompted).

2. **Enable USB Debugging (Only required for USB Cable connections)**:
   * Go to Settings -> About Phone on your Android device.
   * Find the Build Number and tap it 7 times until you see the notification: "You are now a developer!".
   * Go back to the main Settings menu, open Developer Options, and toggle USB Debugging to ON.
   * Connect your phone to your PC via a USB cable. When prompted with "Allow USB debugging?", check "Always allow from this computer" and tap Allow.

---

## Step 3: Choose Your Connection Method

### Option A: USB Cable Connection (Recommended - Zero Lag)
1. Plug your phone into the PC using a USB cable.
2. Verify USB Debugging is ON.
3. Run `setup_and_run.bat` on your PC. It will output: `√ ADB reverse tunnel established on port 9000`.
4. Launch the FALCON application on your phone.
5. Keep the default IP set to `127.0.0.1` and Port to `9000`.
6. Tap the cyan CONNECT button.

### Option B: Wi-Fi Connection (Wireless)
1. Ensure both your PC and phone are connected to the same Wi-Fi network.
2. Run `setup_and_run.bat` on your PC. The console will display your PC's IP address (e.g., `- Wi-Fi : IP 192.168.1.15 and Port 9000`).
3. Launch the FALCON application. The app's auto-discovery will automatically detect and populate the IP, or you can manually enter the IP and Port.
4. Tap the cyan CONNECT button. (Note: Allow Python through your Windows Defender Firewall if it fails to connect).

### Option C: Bluetooth Connection (Wireless & Offline)
1. Enable Bluetooth on both your PC and phone.
2. Pair your phone with your PC in the Windows Bluetooth settings.
3. Run `setup_and_run.bat` on your PC (the console will output that the Bluetooth server is listening on channel 4).
4. Launch the FALCON application.
5. Tap the green Bluetooth icon in the top navigation bar, select your PC from the paired devices list, and connect.

---

## Step 4: Control Calibration

Once connected to the simulator, tap the Gear icon in the top bar of the application to access settings:
* **Deadzone**: Adjust to filter out analog stick jitter (0% to 25%).
* **Sensitivity Curve**: Adjust stick exponent scaling to fine-tune control response around the center points.
* **Invert Axes**: Toggle active inversion of Yaw, Throttle, Roll, or Pitch axes.

---

## Developer Team

* Abhisudh k S
* Arjun A
* Muhammed Sijadh M P
* Sruthi E P
