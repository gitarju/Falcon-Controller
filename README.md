# FALCON Controller - Setup and User Manual

FALCON Controller is a drone simulation interface linking an Android client app to an AirSim simulator server on Windows. The system emulates an Xbox 360 controller using the ViGEmBus driver to stream flight controls and custom calibration settings over USB, Wi-Fi, or Bluetooth.

### [📥 Download Windows PC Setup Wizard](https://github.com/gitarju/Falcon-Controller/raw/main/output/FALCON_Controller_Server_Setup.exe) | [📥 Download Android App APK (v1.0.0)](https://github.com/gitarju/Falcon-Controller/raw/main/FALCON-Controller-v1.0.0.apk)

---

## Features

* **Windows Setup Wizard**: Installs all required tools (ADB, Gamepad Driver, and executable Server) with a single, standalone installer.
* **Modern GUI Dashboard**: Includes a sleek dark-themed Tkinter GUI console showing live network configurations, driver states, connection logs, and active status cards.
* **Multi-Mode Connection**: Connect via USB debugging tunnel (ADB reverse), Local Wi-Fi (Auto-Discovery), or Classic Bluetooth (RFCOMM/SPP).
* **Xbox 360 Gamepad Emulation**: Emulates a physical controller using Windows ViGEmBus and the python-vgamepad driver.
* **Control Calibration**: In-app configurations for deadzone size, sensitivity curves (exponential scaling), and axis inversions (Yaw, Throttle, Roll, Pitch).
* **Real-time Failure Prediction (FALCON Project)**: Features a hidden HUD dialog detailing failure prediction and autonomous landing systems.

---

## Step 1: PC Setup (Using the Setup Wizard)

1. **Download and Run the Installer**:
   * Download the latest `FALCON_Controller_Server_Setup.exe`.
   * Double-click the installer and grant Administrator permissions (required to install the virtual gamepad driver).

2. **Smart Driver Installation**:
   * The installer automatically checks if the **ViGEmBus Virtual Gamepad Driver** is installed on your PC.
   * If the driver is missing, a checkbox task will appear to install the driver. Make sure this is checked and let the setup wizard install the gamepad driver.

3. **Launch the Server GUI**:
   * Launch **FALCON Controller Server** using the Desktop or Start Menu shortcut.
   * The dark-themed GUI will load and immediately auto-start the server.

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

## Step 3: Choose Your Connection Method

### Option A: USB Cable Connection (Recommended - Zero Lag)
1. Plug your phone into the PC using a USB cable.
2. Verify USB Debugging is ON.
3. Open the PC Server GUI (it will automatically run the ADB reverse tunnel). Look at the status cards to verify **ADB USB Tunnel** shows `Active`.
4. Launch the FALCON application on your phone.
5. Keep the default IP set to `127.0.0.1` and Port to `9000`.
6. Tap the cyan **CONNECT** button.

### Option B: Wi-Fi Connection (Wireless)
1. Ensure both your PC and phone are connected to the same Wi-Fi network.
2. Open the PC Server GUI. The dashboard will show your PC's IP address (under **Local Wi-Fi IP**, e.g., `192.168.1.15:9000`).
3. Launch the FALCON application. The app's auto-discovery will automatically detect and populate the IP, or you can manually enter the IP and Port.
4. Tap the cyan **CONNECT** button. (Note: Allow python/server through your Windows Defender Firewall if it fails to connect).

### Option C: Bluetooth Connection (Wireless & Offline)
1. Enable Bluetooth on both your PC and phone.
2. Pair your phone with your PC in the Windows Bluetooth settings.
3. Open the PC Server GUI (the status cards will show **Bluetooth RFCOMM** is `Active`).
4. Launch the FALCON application.
5. Tap the green **Bluetooth icon** in the top navigation bar, select your PC from the paired devices list, and connect.

---

## Step 4: Control Calibration

Once connected to the simulator, tap the **Gear icon** in the top bar of the application to access settings:
* **Deadzone**: Adjust to filter out analog stick jitter (0% to 25%).
* **Sensitivity Curve**: Adjust stick exponent scaling to fine-tune control response around the center points.
* **Invert Axes**: Toggle active inversion of Yaw, Throttle, Roll, or Pitch axes.

---

## Developer Setup (Running from Source)

If you are a developer and want to run or modify the python server from source:

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   ```
2. Run the developer launcher:
   ```bash
   .\setup_and_run.bat
   ```
   *This batch script prepares dependencies and launches the Tkinter GUI server from the virtual environment.*
3. To package the standalone executable and setup wizard:
   * Install packager dependencies:
     ```bash
     .\venv\Scripts\pip install pyinstaller Pillow
     ```
   * Convert icon png to ico:
     ```bash
     .\venv\Scripts\python convert_icon.py
     ```
   * Build executable and assemble staging directory:
     ```bash
     .\venv\Scripts\pyinstaller --noconsole --onefile --icon=icon.ico --name=server server.py
     .\venv\Scripts\python C:\Users\arjun\.gemini\antigravity\brain\178b2fea-0ae9-4145-b070-54efe50255a4\scratch\assemble_dist.py
     ```
   * Compile the setup wizard using Inno Setup 6:
     ```bash
     & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup_wizard.iss
     ```

---

## Developer Team

* Abhisudh k S
* Arjun A
* Muhammed Sijadh M P
* Sruthi E P
