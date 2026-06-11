import sys
import os

# Configure stdout/stderr to use UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Enable ANSI escape processing
os.system('')

from PyQt6.QtWidgets import QApplication
from src.gui import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        import src.server_core as server_core
        server_core.stop_server()

if __name__ == "__main__":
    main()
