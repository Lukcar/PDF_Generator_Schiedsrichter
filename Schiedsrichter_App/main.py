from data_manager import DataManager
from main_window import MainWindow
from PyQt5.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    data_manager = DataManager()
    main_window = MainWindow(data_manager)
    
    main_window.show()
    sys.exit(app.exec_())
