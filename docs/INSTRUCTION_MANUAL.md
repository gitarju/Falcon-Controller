# FALCON Controller - First-Time Setup & User Manual

Welcome to the **FALCON Controller** setup guide. This manual walks you through the steps required to configure your PC and mobile device for the very first launch.

---

## 🛠️ Step 1: PC Setup (First Time Only)

### Option A: Setup Wizard (Recommended for End-Users)
If you installed the application using the Windows Setup Wizard:
1. **Launch the Server**: Use the Desktop or Start Menu shortcut to launch the **FALCON Controller Server**.
2. **Driver Check**: The application will automatically verify if the virtual gamepad driver is running. (If you selected the task to install it during setup, the installer will have configured it for you, prompting a reboot if needed).
3. **Start**: The GUI console opens and the emulation bridge starts automatically.

### Option B: Developer Setup (Running from Source)
If you cloned the repository and want to run from source code:
1. **Install Python**:
   - Download and install Python 3.10+ from the official website: [python.org/downloads](https://www.python.org/downloads/)
   - **IMPORTANT**: During installation, check the box that says **"Add Python to PATH"**.

2. **Install the Virtual Gamepad Driver (ViGEmBus)**:
   - The server emulates an Xbox 360 controller using the ViGEmBus driver.
   - Download the latest installer from the official repository: [ViGEmBus Releases](https://github.com/nefarius/ViGEmBus/releases)
   - Run the `.msi` installer and complete the setup. Restart your PC if prompted.

3. **Launch the Server**:
   - Double-click **`setup_and_run.bat`** in the root folder.
   - The script will automatically configure a virtual environment, install package dependencies, verify the gamepad driver, and launch the PyQt6 application dashboard.

---

## 📱 Step 2: Phone Setup (First Time Only)

1. **Install the App (APK)**:
   - Copy **`FALCON-Controller-v1.0.0.apk`** to your Android phone.
   - Open your phone's file manager, tap the APK, and install it. (If prompted, allow installation from "Unknown Sources").

2. **Enable USB Debugging** (Required *only* if you want to connect via USB cable):
   - Go to **Settings** → **About Phone** on your phone.
   - Scroll down to find the **Build Number** and tap it **7 times** rapidly. You will see a notification: *"You are now a developer!"*.
   - Go back to the main Settings menu, search for **Developer Options** (usually under System/Additional Settings), and open it.
   - Scroll down and toggle **USB Debugging** to **ON**.
   - Plug your phone into the PC using a USB cable. When a popup appears on your phone asking *"Allow USB debugging?"*, check *"Always allow from this computer"* and tap **Allow**.

---

## 🔗 Step 3: Choose Your Connection Method

You can connect the phone app to the PC server using one of three options:

### Option A: USB Cable Connection (Recommended - Zero Lag)
1. Plug your phone into your PC via a USB cable.
2. Ensure **USB Debugging** is turned ON (see Step 2 above).
3. Run **`setup_and_run.bat`** on your PC. It will print:
   `√ ADB reverse tunnel established on port 9000`
4. Launch the **FALCON** app on your phone.
5. Keep the default IP set to **`127.0.0.1`** and Port **`9000`**.
6. Tap the cyan **CONNECT** button.

### Option B: Wi-Fi Connection (Wireless)
1. Ensure both your PC and phone are connected to the **same Wi-Fi router**.
2. Run **`setup_and_run.bat`** on your PC. It will display your PC's Wi-Fi IP address in the console, for example:
   `- Wi-Fi : IP 192.168.1.15 and Port 9000`
3. Launch the **FALCON** app on your phone.
4. Either:
   - Wait 1-2 seconds: the app's **Auto-Discovery** will find your PC and automatically fill in the IP.
   - Or, manually type the IP (e.g. `192.168.1.15`) and Port (`9000`) shown on the PC console.
5. Tap the cyan **CONNECT** button.
* *(Note: If it times out, allow Python through your Windows Defender Firewall).*

### Option C: Bluetooth Connection (Wireless & Offline)
1. Turn on Bluetooth on both your PC and your phone.
2. Go to Windows Bluetooth settings and **pair** your phone with your PC.
3. Run **`setup_and_run.bat`** on your PC. (It will output that the Bluetooth server is listening on channel 4).
4. Launch the **FALCON** app on your phone.
5. Tap the green **Bluetooth icon** in the top bar.
6. Grant the requested Bluetooth permissions, select your PC from the list, and it will connect.

---

## 🎛️ Step 4: Controller Calibration & Inversions

Once connected, tap the **Settings icon (gear)** in the top bar of the app to configure your controls:
* **Deadzone**: Filter out stick jitter.
* **Sensitivity Curve (Expo)**: Fine-tune control responsiveness (higher values give smoother controls around center sticks).
* **Invert Axes**: Toggle yaw, throttle, roll, or pitch inversion to match your flight preferences.
