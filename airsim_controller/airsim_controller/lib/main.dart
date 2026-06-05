import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_joystick/flutter_joystick.dart';
import 'package:flutter_bluetooth_serial/flutter_bluetooth_serial.dart';
import 'package:permission_handler/permission_handler.dart';

// ── Design Tokens ────────────────────────────────────────────────────────────

const Color kBackground = Color(0xFF0A0E1A);
const Color kSurface = Color(0xFF0D1525);
const Color kGridBg = Color(0xFF0D1830);
const Color kPrimaryCyan = Color(0xFF00D4FF);
const Color kSecondaryGreen = Color(0xFF00FF88);
const Color kAccentOrange = Color(0xFFFFAA00);
const Color kDanger = Color(0xFFFF4455);
const Color kTextPrimary = Color(0xFFCCDDFF);
const Color kTextMuted = Color(0xFF8899BB);
const Color kTextDark = Color(0xFF556688);
const Color kBorder = Color(0xFF1A2D50);
const Color kBarBorder = Color(0xFF1A2540);
const Color kInactiveDot = Color(0xFF444466);
const Color kSwitchInactive = Color(0xFF445577);

const String kAppVersion = '1.0.0';

// ── Entry Point ──────────────────────────────────────────────────────────────

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  runApp(const AirSimControllerApp());
}

class AirSimControllerApp extends StatelessWidget {
  const AirSimControllerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FALCON Controller',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: kBackground,
        colorScheme: const ColorScheme.dark(
          primary: kPrimaryCyan,
          secondary: kSecondaryGreen,
        ),
      ),
      home: const ControllerScreen(),
    );
  }
}

// ── Main Screen ──────────────────────────────────────────────────────────────

class ControllerScreen extends StatefulWidget {
  const ControllerScreen({super.key});

  @override
  State<ControllerScreen> createState() => _ControllerScreenState();
}

class _ControllerScreenState extends State<ControllerScreen>
    with TickerProviderStateMixin {
  // Connection state
  Socket? _socket;
  BluetoothConnection? _btConnection;
  bool _connected = false;
  bool _connecting = false;
  bool _isBluetooth = false;
  String _statusMsg = 'Disconnected';

  // IP / port fields
  final TextEditingController _ipController =
      TextEditingController(text: '127.0.0.1');
  final TextEditingController _portController =
      TextEditingController(text: '9000');

  // Joystick values  (left = throttle/yaw, right = pitch/roll)
  double _lx = 0, _ly = 0, _rx = 0, _ry = 0;

  // Throttle for send rate
  Timer? _sendTimer;

  // Animations
  late AnimationController _pulseCtrl;
  late Animation<double> _pulse;
  late AnimationController _radarCtrl;
  late Animation<double> _radarPulse;

  // UDP Auto-Discovery Socket
  RawDatagramSocket? _udpSocket;

  // Calibration settings
  double _deadzone = 0.05;
  double _expo = 1.0;
  bool _invertYaw = false;
  bool _invertThrottle = false;
  bool _invertRoll = false;
  bool _invertPitch = false;

  // Easter egg tap state
  int _tapCount = 0;
  Timer? _tapResetTimer;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _pulse = Tween(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );

    _radarCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    )..repeat();
    _radarPulse = Tween(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _radarCtrl, curve: Curves.easeOut),
    );

    _startUdpDiscovery();
  }

  @override
  void dispose() {
    _sendTimer?.cancel();
    _socket?.destroy();
    _udpSocket?.close();
    _ipController.dispose();
    _portController.dispose();
    _pulseCtrl.dispose();
    _radarCtrl.dispose();
    super.dispose();
  }

  void _startUdpDiscovery() async {
    try {
      _udpSocket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 9001);
      _udpSocket!.listen((RawSocketEvent event) {
        if (event == RawSocketEvent.read) {
          final datagram = _udpSocket!.receive();
          if (datagram != null) {
            try {
              final message = utf8.decode(datagram.data);
              final payload = jsonDecode(message);
              if (payload['service'] == 'AirSimController') {
                final discoveredIp = datagram.address.address;
                final discoveredPort = payload['port']?.toString() ?? '9000';
                if (!_connected && !_connecting) {
                  setState(() {
                    _ipController.text = discoveredIp;
                    _portController.text = discoveredPort;
                  });
                }
              }
            } catch (_) {}
          }
        }
      });
    } catch (_) {}
  }

  double _transformAxis(double rawValue, bool invert) {
    if (rawValue.abs() < _deadzone) return 0.0;
    // Scale linear value above deadzone to range [0.0, 1.0]
    final double scaled = (rawValue.abs() - _deadzone) / (1.0 - _deadzone);
    // Apply expo curve
    final double expoVal = math.pow(scaled, _expo).toDouble();
    // Restore sign and apply inversion
    final double result = rawValue.sign * expoVal;
    return invert ? -result : result;
  }

  // ── Toast Notification ─────────────────────────────────────────────────────

  void _showToast(String message, Color color) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              color == kSecondaryGreen ? Icons.check_circle : Icons.info_outline,
              color: color,
              size: 16,
            ),
            const SizedBox(width: 8),
            Text(
              message,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: color,
                letterSpacing: 1,
              ),
            ),
          ],
        ),
        backgroundColor: kBackground.withOpacity(0.95),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(color: color.withOpacity(0.4)),
        ),
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.only(bottom: 16, left: 80, right: 80),
      ),
    );
  }

  // ── User-friendly error parsing ────────────────────────────────────────────

  String _friendlyError(dynamic error) {
    final msg = error.toString();
    if (msg.contains('Connection refused')) return 'Server not running';
    if (msg.contains('Connection timed out') || msg.contains('TimeoutException')) {
      return 'Connection timed out';
    }
    if (msg.contains('Network is unreachable')) return 'Network unreachable';
    if (msg.contains('No route to host')) return 'Host not found';
    if (msg.contains('SocketException')) {
      final match = RegExp(r'OS Error: (.+?),').firstMatch(msg);
      if (match != null) return match.group(1)!;
    }
    return 'Connection failed';
  }

  // ── Network ────────────────────────────────────────────────────────────────

  Future<void> _connect() async {
    if (_connecting || _connected) return;
    setState(() {
      _connecting = true;
      _statusMsg = 'Connecting…';
    });

    final ip = _ipController.text.trim();
    final port = int.tryParse(_portController.text.trim()) ?? 9000;

    try {
      _socket = await Socket.connect(ip, port,
          timeout: const Duration(seconds: 5));
      _socket!.setOption(SocketOption.tcpNoDelay, true);

      // Listen for errors / disconnect
      _socket!.handleError((_) => _disconnect());
      _socket!.listen(
        (_) {}, // no data expected from server
        onError: (_) => _disconnect(),
        onDone: () => _disconnect(),
      );

      // Start 50 Hz send loop
      _sendTimer =
          Timer.periodic(const Duration(milliseconds: 20), (_) => _sendData());

      setState(() {
        _connected = true;
        _connecting = false;
        _isBluetooth = false;
        _statusMsg = 'Connected  $ip:$port';
      });

      HapticFeedback.mediumImpact();
      _showToast('Connected to server', kSecondaryGreen);
    } catch (e) {
      setState(() {
        _connecting = false;
        _statusMsg = _friendlyError(e);
      });
      HapticFeedback.heavyImpact();
      _showToast(_friendlyError(e), kDanger);
    }
  }

  void _disconnect() {
    _sendTimer?.cancel();
    _sendTimer = null;

    if (_isBluetooth) {
      _btConnection?.dispose();
      _btConnection = null;
    } else {
      _socket?.destroy();
      _socket = null;
    }

    if (mounted) {
      setState(() {
        _connected = false;
        _connecting = false;
        _isBluetooth = false;
        _statusMsg = 'Disconnected';
        _lx = 0;
        _ly = 0;
        _rx = 0;
        _ry = 0;
      });
      HapticFeedback.lightImpact();
      _showToast('Disconnected', kTextMuted);
    }
  }

  void _sendData() {
    final payload = jsonEncode({
      'lx': double.parse(_lx.toStringAsFixed(4)),
      'ly': double.parse(_ly.toStringAsFixed(4)),
      'rx': double.parse(_rx.toStringAsFixed(4)),
      'ry': double.parse(_ry.toStringAsFixed(4)),
    });

    if (_isBluetooth) {
      if (_btConnection == null) return;
      try {
        _btConnection!.output.add(Uint8List.fromList(utf8.encode('$payload\n')));
      } catch (_) {
        _disconnect();
      }
    } else {
      if (_socket == null) return;
      try {
        _socket!.write('$payload\n');
      } catch (_) {
        _disconnect();
      }
    }
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final stickSize = size.height * 0.55;

    return Scaffold(
      body: Stack(
        children: [
          // Background grid
          CustomPaint(
            painter: _GridPainter(),
            size: Size.infinite,
          ),

          // Gradient overlay for depth
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  kBackground.withOpacity(0.5),
                  Colors.transparent,
                  kBackground.withOpacity(0.3),
                ],
                stops: const [0.0, 0.5, 1.0],
              ),
            ),
          ),

          // Main layout
          SafeArea(
            child: Column(
              children: [
              // Top bar
              _buildTopBar(),

              // Joystick area
              Expanded(
                child: Row(
                  children: [
                    // LEFT stick — Throttle (Y) / Yaw (X)
                    Expanded(
                      child: _buildStickPanel(
                        label: 'THROTTLE / YAW',
                        sublabelY: 'Throttle ↕',
                        sublabelX: 'Yaw ↔',
                        color: kPrimaryCyan,
                        size: stickSize,
                        onMove: (x, y) => setState(() {
                          _lx = _transformAxis(x, _invertYaw);
                          _ly = _transformAxis(-y, _invertThrottle);
                        }),
                        onRelease: () => setState(() {
                          _lx = 0;
                          _ly = 0;
                        }),
                        xVal: _lx,
                        yVal: _ly,
                      ),
                    ),

                    // Center info
                    SizedBox(
                      width: size.width * 0.18,
                      child: _buildCenterInfo(),
                    ),

                    // RIGHT stick — Pitch (Y) / Roll (X)
                    Expanded(
                      child: _buildStickPanel(
                        label: 'PITCH / ROLL',
                        sublabelY: 'Pitch ↕',
                        sublabelX: 'Roll ↔',
                        color: kSecondaryGreen,
                        size: stickSize,
                        onMove: (x, y) => setState(() {
                          _rx = _transformAxis(x, _invertRoll);
                          _ry = _transformAxis(-y, _invertPitch);
                        }),
                        onRelease: () => setState(() {
                          _rx = 0;
                          _ry = 0;
                        }),
                        xVal: _rx,
                        yVal: _ry,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          ),
        ],
      ),
    );
  }

  // ── Top Bar ────────────────────────────────────────────────────────────────

  Widget _buildTopBar() {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.black.withOpacity(0.7),
            Colors.black.withOpacity(0.5),
          ],
        ),
        border: const Border(
          bottom: BorderSide(color: kBarBorder, width: 1),
        ),
      ),
      child: Row(
        children: [
          // FALCON brand
          ShaderMask(
            shaderCallback: (bounds) => const LinearGradient(
              colors: [kPrimaryCyan, kSecondaryGreen],
            ).createShader(bounds),
            child: const Text(
              'FALCON',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Colors.white,
                letterSpacing: 3,
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Vertical divider
          Container(
            width: 1,
            height: 20,
            color: kBorder,
          ),
          const SizedBox(width: 10),

          // Status dot
          AnimatedBuilder(
            animation: _pulse,
            builder: (_, __) => Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _connected
                    ? Color.lerp(
                        kSecondaryGreen,
                        Colors.white,
                        _pulse.value)!
                    : (_connecting
                        ? Color.lerp(
                            kAccentOrange,
                            Colors.white,
                            _pulse.value)!
                        : kInactiveDot),
                boxShadow: _connected
                    ? [
                        BoxShadow(
                          color: kSecondaryGreen
                              .withOpacity(_pulse.value * 0.8),
                          blurRadius: 8,
                          spreadRadius: 2,
                        )
                      ]
                    : (_connecting
                        ? [
                            BoxShadow(
                              color: kAccentOrange
                                  .withOpacity(_pulse.value * 0.5),
                              blurRadius: 6,
                              spreadRadius: 1,
                            )
                          ]
                        : null),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // Status text
          AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 300),
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 11,
              color: _connected
                  ? kSecondaryGreen
                  : (_connecting ? kAccentOrange : kTextMuted),
              letterSpacing: 1.2,
            ),
            child: Text(_statusMsg),
          ),

          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              reverse: true,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  // IP field
                  SizedBox(
                    width: 130,
                    height: 28,
                    child: TextField(
                      controller: _ipController,
                      enabled: !_connected,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                        color: kTextPrimary,
                      ),
                      decoration: InputDecoration(
                        labelText: 'IP',
                        labelStyle: const TextStyle(
                            fontSize: 10, color: kTextDark),
                        contentPadding:
                            const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        isDense: true,
                        filled: true,
                        fillColor: kSurface,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kBorder),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kBorder),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kPrimaryCyan, width: 1.5),
                        ),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 6),

                  // Port field
                  SizedBox(
                    width: 68,
                    height: 28,
                    child: TextField(
                      controller: _portController,
                      enabled: !_connected,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                        color: kTextPrimary,
                      ),
                      decoration: InputDecoration(
                        labelText: 'PORT',
                        labelStyle: const TextStyle(
                            fontSize: 10, color: kTextDark),
                        contentPadding:
                            const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        isDense: true,
                        filled: true,
                        fillColor: kSurface,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kBorder),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kBorder),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                          borderSide: const BorderSide(color: kPrimaryCyan, width: 1.5),
                        ),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Connect / Disconnect button
                  Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: _connected ? _disconnect : _connect,
                      borderRadius: BorderRadius.circular(6),
                      splashColor: (_connected ? kDanger : kPrimaryCyan)
                          .withOpacity(0.3),
                      highlightColor: (_connected ? kDanger : kPrimaryCyan)
                          .withOpacity(0.1),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        padding:
                            const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        decoration: BoxDecoration(
                          color: _connected
                              ? kDanger.withOpacity(0.1)
                              : kPrimaryCyan.withOpacity(0.1),
                          border: Border.all(
                            color: _connected ? kDanger : kPrimaryCyan,
                            width: 1,
                          ),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (_connecting) ...[
                              const SizedBox(
                                width: 12,
                                height: 12,
                                child: CircularProgressIndicator(
                                  strokeWidth: 1.5,
                                  color: kPrimaryCyan,
                                ),
                              ),
                              const SizedBox(width: 8),
                            ],
                            Text(
                              _connected
                                  ? 'DISCONNECT'
                                  : (_connecting ? 'CONNECTING' : 'CONNECT'),
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: _connected ? kDanger : kPrimaryCyan,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Bluetooth Connect button
                  Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: _connected ? _disconnect : _connectBluetooth,
                      borderRadius: BorderRadius.circular(6),
                      splashColor: kSecondaryGreen.withOpacity(0.3),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: _connected && _isBluetooth
                              ? kSecondaryGreen.withOpacity(0.1)
                              : kSurface,
                          border: Border.all(
                            color: _connected && _isBluetooth ? kSecondaryGreen : kBorder,
                            width: 1,
                          ),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.bluetooth,
                              size: 14,
                              color: kSecondaryGreen,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Settings button
                  Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: _showSettingsDialog,
                      borderRadius: BorderRadius.circular(6),
                      splashColor: kPrimaryCyan.withOpacity(0.3),
                      child: Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: kSurface,
                          border: Border.all(color: kBorder, width: 1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Icon(
                          Icons.tune,
                          size: 16,
                          color: kTextPrimary,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Joystick Panel ─────────────────────────────────────────────────────────

  Widget _buildStickPanel({
    required String label,
    required String sublabelY,
    required String sublabelX,
    required Color color,
    required double size,
    required void Function(double x, double y) onMove,
    required VoidCallback onRelease,
    required double xVal,
    required double yVal,
  }) {
    final stickRadius = (size * 0.42).clamp(60.0, 160.0);
    final isActive = xVal.abs() > 0.01 || yVal.abs() > 0.01;

    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Label
        Text(
          label,
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 10,
            fontWeight: FontWeight.bold,
            color: color.withOpacity(0.7),
            letterSpacing: 2,
          ),
        ),
        const SizedBox(height: 12),

        // Joystick
        Joystick(
          mode: JoystickMode.all,
          base: Container(
            width: stickRadius * 2,
            height: stickRadius * 2,
            decoration: BoxDecoration(
              color: color.withOpacity(0.07),
              shape: BoxShape.circle,
              border: Border.all(
                color: color.withOpacity(isActive ? 0.45 : 0.25),
                width: isActive ? 2.0 : 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: color.withOpacity(isActive ? 0.25 : 0.15),
                  blurRadius: isActive ? 18 : 10,
                  spreadRadius: isActive ? 4 : 2,
                ),
              ],
            ),
          ),
          stick: AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            width: stickRadius * 0.76,
            height: stickRadius * 0.76,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  color.withOpacity(1.0),
                  color.withOpacity(0.75),
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: color.withOpacity(isActive ? 0.7 : 0.5),
                  blurRadius: isActive ? 16 : 10,
                  spreadRadius: isActive ? 4 : 2,
                ),
              ],
            ),
          ),
          listener: (details) {
            onMove(details.x, details.y);
            // Haptic feedback on edge boundaries
            final dist = math.sqrt(details.x * details.x + details.y * details.y);
            if (dist > 0.95) {
              HapticFeedback.selectionClick();
            }
          },
          onStickDragEnd: onRelease,
        ),

        const SizedBox(height: 12),

        // Live values
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _valueChip(sublabelX, xVal, color),
            const SizedBox(width: 8),
            _valueChip(sublabelY, yVal, color),
          ],
        ),
      ],
    );
  }

  Widget _valueChip(String label, double val, Color color) {
    final magnitude = val.abs();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06 + magnitude * 0.08),
        border: Border.all(
          color: color.withOpacity(0.2 + magnitude * 0.3),
          width: 0.5,
        ),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '${label.split(' ').first} ${val >= 0 ? '+' : ''}${val.toStringAsFixed(2)}',
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 11,
          color: color.withOpacity(0.7 + magnitude * 0.3),
          letterSpacing: 0.8,
          fontWeight: magnitude > 0.5 ? FontWeight.bold : FontWeight.normal,
        ),
      ),
    );
  }

  // ── Center Info Panel ──────────────────────────────────────────────────────

  Widget _buildCenterInfo() {
    return AnimatedBuilder(
      animation: _radarPulse,
      builder: (_, __) => Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Animated radar ring
          GestureDetector(
            onTap: _handleCenterTap,
            behavior: HitTestBehavior.opaque,
            child: SizedBox(
              width: 60,
              height: 60,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Outer pulse ring
                  if (_connected)
                    Transform.scale(
                      scale: 0.5 + _radarPulse.value * 0.5,
                      child: Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: kSecondaryGreen
                                .withOpacity(0.4 * (1 - _radarPulse.value)),
                            width: 1.5,
                          ),
                        ),
                      ),
                    ),
                  // Inner static ring
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: (_connected ? kSecondaryGreen : kPrimaryCyan)
                            .withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Center(
                      child: Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _connected
                              ? kSecondaryGreen.withOpacity(0.8)
                              : kPrimaryCyan.withOpacity(0.4),
                          boxShadow: _connected
                              ? [
                                  BoxShadow(
                                    color: kSecondaryGreen.withOpacity(0.5),
                                    blurRadius: 6,
                                  )
                                ]
                              : null,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 10),

          // Brand title
          ShaderMask(
            shaderCallback: (bounds) => LinearGradient(
              colors: [
                kPrimaryCyan.withOpacity(0.8),
                kPrimaryCyan.withOpacity(0.5),
              ],
            ).createShader(bounds),
            child: const Text(
              'AIRSIM DRONE',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: Colors.white,
                letterSpacing: 2,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'created for FALCON Project',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 7,
              color: kSecondaryGreen.withOpacity(0.7),
              letterSpacing: 0.5,
            ),
          ),

          const SizedBox(height: 12),

          // Send rate indicator
          if (_connected)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: kSecondaryGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: kSecondaryGreen.withOpacity(0.3),
                  width: 0.5,
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: kSecondaryGreen.withOpacity(_pulse.value),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '50Hz',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 9,
                      fontWeight: FontWeight.bold,
                      color: kSecondaryGreen.withOpacity(0.8),
                      letterSpacing: 1,
                    ),
                  ),
                ],
              ),
            ),

          const SizedBox(height: 8),

          // Version
          Text(
            'v$kAppVersion',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 7,
              color: kTextMuted.withOpacity(0.4),
              letterSpacing: 1,
            ),
          ),
        ],
      ),
    );
  }

  // ── Settings Dialog ────────────────────────────────────────────────────────

  void _showSettingsDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return BackdropFilter(
              filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
              child: AlertDialog(
                backgroundColor: kBackground.withOpacity(0.92),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(
                    color: kPrimaryCyan.withOpacity(0.6),
                    width: 1.5,
                  ),
                ),
                title: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: kPrimaryCyan.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.tune, color: kPrimaryCyan, size: 20),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        'CONTROLLER CALIBRATION',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
                content: Container(
                  constraints: const BoxConstraints(maxWidth: 450),
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 4),

                        // Deadzone section
                        _sectionHeader('DEADZONE', kPrimaryCyan),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Expanded(
                              child: SliderTheme(
                                data: SliderTheme.of(context).copyWith(
                                  activeTrackColor: kPrimaryCyan,
                                  inactiveTrackColor: kSurface,
                                  thumbColor: kPrimaryCyan,
                                  overlayColor: kPrimaryCyan.withOpacity(0.2),
                                  trackHeight: 3,
                                  thumbShape: const RoundSliderThumbShape(
                                    enabledThumbRadius: 7,
                                  ),
                                ),
                                child: Slider(
                                  value: _deadzone,
                                  min: 0.0,
                                  max: 0.25,
                                  divisions: 25,
                                  onChanged: (val) {
                                    setDialogState(() {
                                      _deadzone = val;
                                    });
                                    setState(() {});
                                  },
                                ),
                              ),
                            ),
                            Container(
                              width: 50,
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: kPrimaryCyan.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                '${(_deadzone * 100).toStringAsFixed(0)}%',
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  color: kPrimaryCyan,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Expo section
                        _sectionHeader('SENSITIVITY CURVE', kSecondaryGreen),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Expanded(
                              child: SliderTheme(
                                data: SliderTheme.of(context).copyWith(
                                  activeTrackColor: kSecondaryGreen,
                                  inactiveTrackColor: kSurface,
                                  thumbColor: kSecondaryGreen,
                                  overlayColor:
                                      kSecondaryGreen.withOpacity(0.2),
                                  trackHeight: 3,
                                  thumbShape: const RoundSliderThumbShape(
                                    enabledThumbRadius: 7,
                                  ),
                                ),
                                child: Slider(
                                  value: _expo,
                                  min: 1.0,
                                  max: 2.5,
                                  divisions: 15,
                                  onChanged: (val) {
                                    setDialogState(() {
                                      _expo = val;
                                    });
                                    setState(() {});
                                  },
                                ),
                              ),
                            ),
                            Container(
                              width: 50,
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: kSecondaryGreen.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                _expo.toStringAsFixed(1),
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  color: kSecondaryGreen,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Divider(color: kBorder.withOpacity(0.5), height: 1),
                        const SizedBox(height: 16),

                        // Inversion switches
                        _sectionHeader('INVERT AXES', kTextMuted),
                        const SizedBox(height: 10),
                        GridView.count(
                          crossAxisCount: 2,
                          shrinkWrap: true,
                          childAspectRatio: 3.2,
                          physics: const NeverScrollableScrollPhysics(),
                          children: [
                            _buildInvertSwitch(
                              label: 'Yaw',
                              value: _invertYaw,
                              onChanged: (val) {
                                setDialogState(() => _invertYaw = val);
                                setState(() {});
                              },
                            ),
                            _buildInvertSwitch(
                              label: 'Throttle',
                              value: _invertThrottle,
                              onChanged: (val) {
                                setDialogState(() => _invertThrottle = val);
                                setState(() {});
                              },
                            ),
                            _buildInvertSwitch(
                              label: 'Roll',
                              value: _invertRoll,
                              onChanged: (val) {
                                setDialogState(() => _invertRoll = val);
                                setState(() {});
                              },
                            ),
                            _buildInvertSwitch(
                              label: 'Pitch',
                              value: _invertPitch,
                              onChanged: (val) {
                                setDialogState(() => _invertPitch = val);
                                setState(() {});
                              },
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                actions: [
                  // Reset button
                  TextButton.icon(
                    onPressed: () {
                      setDialogState(() {
                        _deadzone = 0.05;
                        _expo = 1.0;
                        _invertYaw = false;
                        _invertThrottle = false;
                        _invertRoll = false;
                        _invertPitch = false;
                      });
                      setState(() {});
                      HapticFeedback.lightImpact();
                    },
                    icon: Icon(Icons.restart_alt,
                        size: 16, color: kAccentOrange.withOpacity(0.8)),
                    label: Text(
                      'RESET',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: kAccentOrange.withOpacity(0.8),
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text(
                      'CLOSE',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: kPrimaryCyan,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _sectionHeader(String text, Color color) {
    return Text(
      text,
      style: TextStyle(
        fontFamily: 'monospace',
        fontSize: 11,
        fontWeight: FontWeight.bold,
        color: color.withOpacity(0.8),
        letterSpacing: 1.5,
      ),
    );
  }

  Widget _buildInvertSwitch({
    required String label,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 11,
            color: kTextPrimary,
          ),
        ),
        Switch(
          value: value,
          onChanged: onChanged,
          activeColor: kPrimaryCyan,
          activeTrackColor: kPrimaryCyan.withOpacity(0.3),
          inactiveThumbColor: kSwitchInactive,
          inactiveTrackColor: kSurface,
        ),
      ],
    );
  }

  // ── Bluetooth Connection & Easter Egg Helpers ──────────────────────────────

  void _handleCenterTap() {
    _tapResetTimer?.cancel();
    setState(() {
      _tapCount++;
    });
    if (_tapCount >= 5) {
      _tapCount = 0;
      _showEasterEggDialog();
    } else {
      _tapResetTimer = Timer(const Duration(seconds: 2), () {
        setState(() {
          _tapCount = 0;
        });
      });
    }
  }

  void _showEasterEggDialog() {
    HapticFeedback.heavyImpact();
    showDialog(
      context: context,
      builder: (context) {
        return BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: AlertDialog(
            backgroundColor: kBackground.withOpacity(0.95),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: const BorderSide(color: kSecondaryGreen, width: 2),
            ),
            title: Row(
              children: [
                ShaderMask(
                  shaderCallback: (bounds) => const LinearGradient(
                    colors: [kSecondaryGreen, kPrimaryCyan],
                  ).createShader(bounds),
                  child: const Icon(Icons.security, color: Colors.white, size: 24),
                ),
                const SizedBox(width: 12),
                const Text(
                  'FALCON DIVISION',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    letterSpacing: 3,
                  ),
                ),
              ],
            ),
            content: Container(
              constraints: const BoxConstraints(maxWidth: 550),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'FLIGHT ANALYTICS FOR LIVE CONDITION OPTIMIZATION AND NAVIGATION',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: kPrimaryCyan,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'An AI-powered autonomous drone safety system designed to predict potential drone failures in real time and perform intelligent emergency landings in the safest possible location.',
                      style: TextStyle(fontSize: 11, color: kTextPrimary, height: 1.4),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'The project continuously analyzes live sensor data to detect abnormal behavior, hardware issues, or possible system failures (such as motor, circuit, or battery issues) before they become critical. When a threat is identified, the drone immediately activates an emergency landing protocol that searches for a safe landing zone while avoiding humans, animals, water bodies, buildings, vehicles, trees, and other hazardous environments.',
                      style: TextStyle(fontSize: 11, color: kTextMuted, height: 1.4),
                    ),
                    const SizedBox(height: 16),
                    _sectionHeader('MINIMIZING DAMAGE TO', kSecondaryGreen),
                    const SizedBox(height: 6),
                    _bulletItem('People and living beings nearby'),
                    _bulletItem('Property and surrounding infrastructure'),
                    _bulletItem('The drone itself'),
                    const SizedBox(height: 16),
                    _sectionHeader('POSSIBLE TECHNOLOGIES', kPrimaryCyan),
                    const SizedBox(height: 6),
                    const Text(
                      'Python • AirSim / Gazebo • OpenCV • YOLO / Deep Learning • Sensor Fusion • Reinforcement Learning • ROS • Streamlit Dashboard',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        color: kTextPrimary,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Divider(color: kBorder, height: 1),
                    const SizedBox(height: 16),
                    _sectionHeader('👥  TEAM MEMBERS', kAccentOrange),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(child: _teamMemberChip('Abhisudh k S')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(child: _teamMemberChip('Arjun A')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(child: _teamMemberChip('Muhammed Sijadh M P')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(child: _teamMemberChip('Sruthi E P')),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text(
                  'DISMISS',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    color: kSecondaryGreen,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 2,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _bulletItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4, left: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('• ', style: TextStyle(color: kSecondaryGreen, fontWeight: FontWeight.bold)),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 11, color: kTextPrimary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _teamMemberChip(String name) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: kBorder, width: 1),
      ),
      child: Row(
        children: [
          const Icon(Icons.person, size: 12, color: kTextMuted),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              name,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 10,
                color: kTextPrimary,
                fontWeight: FontWeight.bold,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _connectBluetooth() async {
    if (_connecting || _connected) return;

    setState(() {
      _connecting = true;
      _statusMsg = 'Checking Permissions…';
    });

    try {
      Map<Permission, PermissionStatus> statuses = await [
        Permission.bluetoothScan,
        Permission.bluetoothConnect,
        Permission.location,
      ].request();

      if (statuses[Permission.bluetoothConnect] != PermissionStatus.granted) {
        setState(() {
          _connecting = false;
          _statusMsg = 'Bluetooth Denied';
        });
        _showToast('Bluetooth permission required', kDanger);
        return;
      }

      bool? isEnabled = await FlutterBluetoothSerial.instance.isEnabled;
      if (isEnabled != true) {
        await FlutterBluetoothSerial.instance.requestEnable();
      }

      setState(() {
        _statusMsg = 'Scanning Paired Devices…';
      });
      List<BluetoothDevice> devices = await FlutterBluetoothSerial.instance.getBondedDevices();

      if (!mounted) return;
      setState(() {
        _connecting = false;
        _statusMsg = 'Disconnected';
      });

      _showBluetoothDevicesDialog(devices);

    } catch (e) {
      setState(() {
        _connecting = false;
        _statusMsg = 'BT Init Failed';
      });
      _showToast('Bluetooth initialization failed', kDanger);
    }
  }

  void _showBluetoothDevicesDialog(List<BluetoothDevice> devices) {
    showDialog(
      context: context,
      builder: (context) {
        return BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: AlertDialog(
            backgroundColor: kBackground.withOpacity(0.92),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: const BorderSide(color: kPrimaryCyan, width: 1.5),
            ),
            title: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: kPrimaryCyan.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.bluetooth, color: kPrimaryCyan, size: 20),
                ),
                const SizedBox(width: 12),
                const Text(
                  'SELECT PC BLUETOOTH',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 2,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
            content: SizedBox(
              width: 320,
              height: 250,
              child: devices.isEmpty
                  ? const Center(
                      child: Text(
                        'No paired Bluetooth devices found.\nPlease pair your phone and PC first in settings.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 11, color: kTextMuted, height: 1.4),
                      ),
                    )
                  : ListView.builder(
                      itemCount: devices.length,
                      itemBuilder: (context, index) {
                        final d = devices[index];
                        return Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          decoration: BoxDecoration(
                            color: kSurface,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: kBorder, width: 1),
                          ),
                          child: ListTile(
                            dense: true,
                            title: Text(
                              d.name ?? 'Unknown Device',
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                color: kTextPrimary,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            subtitle: Text(
                              d.address,
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                color: kTextMuted,
                                fontSize: 10,
                              ),
                            ),
                            trailing: const Icon(Icons.chevron_right, size: 16, color: kPrimaryCyan),
                            onTap: () {
                              Navigator.of(context).pop();
                              _connectToBluetoothDevice(d);
                            },
                          ),
                        );
                      },
                    ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text(
                  'CANCEL',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    color: kTextMuted,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _connectToBluetoothDevice(BluetoothDevice device) async {
    setState(() {
      _connecting = true;
      _statusMsg = 'Connecting to ${device.name}…';
    });

    try {
      _btConnection = await BluetoothConnection.toAddress(device.address);
      
      _btConnection!.input!.listen((_) {}).onDone(() {
        _disconnect();
      });

      _sendTimer = Timer.periodic(const Duration(milliseconds: 20), (_) => _sendData());

      setState(() {
        _connected = true;
        _isBluetooth = true;
        _connecting = false;
        _statusMsg = 'Bluetooth: ${device.name}';
      });

      HapticFeedback.mediumImpact();
      _showToast('Connected to Bluetooth', kSecondaryGreen);
    } catch (e) {
      setState(() {
        _connecting = false;
        _statusMsg = 'BT Connection Failed';
      });
      HapticFeedback.heavyImpact();
      _showToast('Bluetooth connection failed', kDanger);
    }
  }
}

// ── Background Grid Painter ──────────────────────────────────────────────────

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = kGridBg.withOpacity(0.8)
      ..style = PaintingStyle.fill;
    canvas.drawRect(Offset.zero & size, paint);

    final gridPaint = Paint()
      ..color = kPrimaryCyan.withOpacity(0.04)
      ..strokeWidth = 0.5;

    const step = 40.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
