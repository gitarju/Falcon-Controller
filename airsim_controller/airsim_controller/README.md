# AirSim Drone Controller

Flutter Android app + Python PC server for controlling AirSim drone simulation.

## Architecture

```
Flutter App (Android)
  Two thumbsticks → TCP JSON @ 50Hz
        ↓ WiFi hotspot or USB tethering
  Python server (PC)
        ↓ vgamepad (virtual Xbox 360)
  AirSim → reads XInput gamepad
```

## Stick Mapping

| Flutter Stick | Axis | AirSim Action |
|---|---|---|
| Left X | lx | Yaw |
| Left Y | ly | Throttle |
| Right X | rx | Roll |
| Right Y | ry | Pitch |

---

## PC Setup

### 1. Install Python dependencies

```bash
pip install vgamepad
```

> vgamepad requires ViGEmBus driver on Windows.
> Download & install: https://github.com/nefarius/ViGEmBus/releases

### 2. Run the server

```bash
python server.py
```

Server listens on port `9000` by default.

### 3. AirSim settings.json

Make sure your `~/Documents/AirSim/settings.json` has:

```json
{
  "SettingsVersion": 1.2,
  "SimMode": "Multirotor"
}
```

AirSim auto-detects any connected XInput gamepad — no extra config needed.

---

## Android App Setup

### Prerequisites
- Flutter SDK 3.10+
- Android device (API 21+)

### Build & install

```bash
cd airsim_controller
flutter pub get
flutter run --release
```

Or build APK:
```bash
flutter build apk --release
# install: flutter install
```

---

## Connection

### Option A — WiFi Hotspot
1. Enable hotspot on Android
2. Connect PC to phone hotspot
3. PC IP is usually `192.168.43.1` (check with `ipconfig` on PC)
4. Enter that IP in app → CONNECT

### Option B — USB Tethering
1. Connect phone to PC via USB
2. Enable USB tethering in Android settings
3. PC IP is usually `192.168.42.1`
4. Enter that IP in app → CONNECT

> USB tethering = lower latency, recommended for drone control.

---

## Verify controller detected (Windows)

Run `joy.cpl` in Windows Run dialog → should show Xbox 360 Controller while server is running and app is connected.
