import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QPlainTextEdit, QFrame, QGridLayout, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QIntValidator
import src.server_core as server_core
from src.utils import get_local_ip, check_vgamepad_quietly, open_manual_action

class WriteStream(QObject):
    message_written = pyqtSignal(str)

    def write(self, text):
        self.message_written.emit(str(text))
        if sys.__stdout__ is not None:
            sys.__stdout__.write(text)
            sys.__stdout__.flush()

    def flush(self):
        if sys.__stdout__ is not None:
            sys.__stdout__.flush()

class StatusCard(QFrame):
    def __init__(self, title, default_val="Checking...", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        # Elegant Dark Panel QSS
        self.setStyleSheet("""
            StatusCard {
                background-color: #1E1E1E;
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(self.title_lbl)
        
        self.val_lbl = QLabel(default_val)
        self.val_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        layout.addWidget(self.val_lbl)

    def set_value(self, val, color="#FFFFFF"):
        self.val_lbl.setText(val)
        self.val_lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FALCON Controller Server")
        self.resize(650, 560)
        self.setMinimumSize(650, 500)
        self.setStyleSheet("background-color: #121212;")

        # Set Window Icon
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, "assets", "icon.ico")
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(script_dir, "..", "assets", "icon.ico")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Main Central Widget Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 1. Header Frame
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)
        
        title_lbl = QLabel("FALCON CONTROLLER")
        title_lbl.setStyleSheet("color: #00E5FF; font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title_lbl)
        
        subtitle_lbl = QLabel("Xbox 360 Controller Emulation Bridge for Android Client")
        subtitle_lbl.setStyleSheet("color: #888888; font-size: 11px; font-style: italic;")
        header_layout.addWidget(subtitle_lbl)
        
        main_layout.addWidget(header_widget)

        # 2. Dashboard Status Grid
        dash_widget = QWidget()
        dash_grid = QGridLayout(dash_widget)
        dash_grid.setContentsMargins(0, 0, 0, 0)
        dash_grid.setSpacing(10)
        
        self.wifi_card = StatusCard("Local Wi-Fi IP")
        self.local_card = StatusCard("Localhost IP (USB)")
        self.driver_card = StatusCard("Gamepad Driver")
        self.adb_card = StatusCard("ADB USB Tunnel")
        self.bt_card = StatusCard("Bluetooth RFCOMM")
        self.client_card = StatusCard("Client Connection")
        
        dash_grid.addWidget(self.wifi_card, 0, 0)
        dash_grid.addWidget(self.local_card, 0, 1)
        dash_grid.addWidget(self.driver_card, 1, 0)
        dash_grid.addWidget(self.adb_card, 1, 1)
        dash_grid.addWidget(self.bt_card, 2, 0)
        dash_grid.addWidget(self.client_card, 2, 1)
        
        main_layout.addWidget(dash_widget)

        # 3. Control Panel Row
        ctrl_widget = QWidget()
        ctrl_layout = QHBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(0, 5, 0, 5)
        ctrl_layout.setSpacing(10)

        # Start Button
        self.start_btn = QPushButton("START SERVER")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00E5FF;
                color: #121212;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #00E676;
            }
            QPushButton:disabled {
                background-color: #2A2A2A;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self.start_server_clicked)
        ctrl_layout.addWidget(self.start_btn)

        # Stop Button
        self.stop_btn = QPushButton("STOP SERVER")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5252;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #FF7373;
            }
            QPushButton:disabled {
                background-color: #2A2A2A;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_server_clicked)
        ctrl_layout.addWidget(self.stop_btn)

        # Port Configuration Card
        port_frame = QFrame()
        port_frame.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }
        """)
        port_layout = QHBoxLayout(port_frame)
        port_layout.setContentsMargins(8, 2, 8, 2)
        port_layout.setSpacing(5)
        
        port_lbl = QLabel("PORT:")
        port_lbl.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold; border: none;")
        port_layout.addWidget(port_lbl)
        
        self.port_entry = QLineEdit("9000")
        self.port_entry.setValidator(QIntValidator(1024, 65535))
        self.port_entry.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.port_entry.setMaximumWidth(60)
        self.port_entry.setStyleSheet("background: transparent; color: #FFFFFF; border: none; padding: 2px;")
        port_layout.addWidget(self.port_entry)
        
        ctrl_layout.addWidget(port_frame)
        
        # Spacer
        ctrl_layout.addStretch()

        # Open Manual Button
        self.manual_btn = QPushButton("OPEN MANUAL")
        self.manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_btn.setStyleSheet("""
            QPushButton {
                background-color: #37474F;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
        self.manual_btn.clicked.connect(self.open_manual_clicked)
        ctrl_layout.addWidget(self.manual_btn)

        main_layout.addWidget(ctrl_widget)

        # 4. Logger Terminal View
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 5, 0, 0)
        log_layout.setSpacing(4)
        
        log_lbl = QLabel("CONSOLE LOGGER")
        log_lbl.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        log_layout.addWidget(log_lbl)
        
        self.console_text = QPlainTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setFont(QFont("Consolas", 9))
        self.console_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0C0C0C;
                color: #E0E0E0;
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }
        """)
        log_layout.addWidget(self.console_text)
        
        main_layout.addWidget(log_widget)

        # Redirect standard stdout & stderr to text area
        self.stream_redirector = WriteStream()
        self.stream_redirector.message_written.connect(self.append_log)
        sys.stdout = self.stream_redirector
        sys.stderr = self.stream_redirector

        # Connect Core Signals
        server_core.signals.client_status_changed.connect(self.update_client_status)
        server_core.signals.driver_status_changed.connect(self.update_driver_status)
        server_core.signals.adb_status_changed.connect(self.update_adb_status)
        server_core.signals.bt_status_changed.connect(self.update_bt_status)
        server_core.signals.server_stopped_signal.connect(self.on_server_stopped)

        # Initialize indicators
        self.init_indicators()
        
        # Auto-start server shortly after UI mounts
        QTimer.singleShot(300, self.start_server_clicked)

    def append_log(self, text):
        self.console_text.insertPlainText(text)
        # Scroll to bottom
        self.console_text.ensureCursorVisible()

    def init_indicators(self):
        # 1. Driver check
        driver_installed = check_vgamepad_quietly()
        self.update_driver_status(
            "Active" if driver_installed else "Not Found", 
            'active' if driver_installed else 'failed'
        )

        # 2. Network IP Info
        wifi_ip = get_local_ip()
        port = self.port_entry.text().strip()
        self.wifi_card.set_value(f"{wifi_ip}:{port}", "#00E5FF")
        self.local_card.set_value(f"127.0.0.1:{port}", "#FFFFFF")

        # 3. Default state for tunnel & bluetooth
        self.adb_card.set_value("Inactive", "#888888")
        self.bt_card.set_value("Inactive", "#888888")
        self.client_card.set_value("Disconnected", "#888888")
        
        self.update_button_states()

    def update_button_states(self):
        running = server_core.is_running()
        self.start_btn.setDisabled(running)
        self.stop_btn.setEnabled(running)
        self.port_entry.setDisabled(running)

    # Signal slots for dashboard cards
    def update_client_status(self, val, connected):
        color = "#00E676" if connected else "#888888"
        self.client_card.set_value(val, color)

    def update_driver_status(self, val, status_type):
        color = "#00E676" if status_type == 'active' else "#FF5252"
        self.driver_card.set_value(val, color)

    def update_adb_status(self, val, status_type):
        if status_type == 'active':
            color = "#00E676"
        elif status_type == 'checking':
            color = "#00E5FF"
        elif status_type == 'disabled':
            color = "#888888"
        else:
            color = "#FF5252"
        self.adb_card.set_value(val, color)

    def update_bt_status(self, val, status_type):
        color = "#00E676" if status_type == 'active' else "#888888"
        self.bt_card.set_value(val, color)

    # Core Action slots
    def start_server_clicked(self):
        try:
            port = int(self.port_entry.text().strip())
            if not (1024 <= port <= 65535):
                raise ValueError()
        except ValueError:
            QMessageBox.critical(self, "Invalid Port", "Port must be an integer between 1024 and 65535.")
            return

        # Refresh network details with customized port
        self.wifi_card.set_value(f"{get_local_ip()}:{port}", "#00E5FF")
        self.local_card.set_value(f"127.0.0.1:{port}", "#FFFFFF")

        success = server_core.start_server(port)
        if success:
            self.update_button_states()
        else:
            QMessageBox.critical(self, "Driver Missing", 
                                 "Failed to initialize virtual gamepad driver.\n\n"
                                 "Please ensure the ViGEmBus driver is installed on this PC.")

    def stop_server_clicked(self):
        server_core.stop_server()

    def on_server_stopped(self):
        self.update_button_states()

    def open_manual_clicked(self):
        ok, err = open_manual_action()
        if not ok:
            QMessageBox.warning(self, "Manual Error", err)

    def closeEvent(self, event):
        if server_core.is_running():
            reply = QMessageBox.question(self, 'Quit Application',
                                         "Server is still running. Stop server and exit?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                server_core.stop_server()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
