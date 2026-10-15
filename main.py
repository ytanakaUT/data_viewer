"""起動用ファイル。各機能は viewer/ 以下のモジュールに分離。"""
import sys
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg
from viewer.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Measurement Viewer")
    pg.setConfigOptions(antialias=False, background="w", foreground="k")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
