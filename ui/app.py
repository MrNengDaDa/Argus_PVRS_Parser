#!/usr/bin/env python3
"""PVRS Editor GUI — 应用入口。"""

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PVRS Editor")
    app.setOrganizationName("Argus")

    window = MainWindow()
    window.resize(1200, 800)
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
