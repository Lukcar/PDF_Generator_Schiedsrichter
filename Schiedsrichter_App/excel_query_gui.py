from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QWidget

class ExcelQueryWindow(QMainWindow):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager  # Speichere den DataManager
        self.setWindowTitle("Excel Abfrage")
        self.setGeometry(200, 200, 400, 300)

        # Beispiel-Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Excel-Abfragefenster"))

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
