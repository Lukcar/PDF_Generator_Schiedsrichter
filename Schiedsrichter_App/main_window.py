import os
from PyQt5.QtWidgets import (
    QMainWindow, QGridLayout, QLabel, QComboBox, QPushButton, QWidget, QMessageBox, QFileDialog, QMenuBar, QAction
)
from data_manager import DataManager
from pdf_generator import PDFGenerator
from excel_game_loader import ExcelspielauftraegeLaden

class MainWindow(QMainWindow):
    def __init__(self, data_manager):
        super().__init__()
        self.setWindowTitle("Profil-Manager und PDF-Generator")
        self.setGeometry(100, 100, 500, 400)

        self.data_manager = data_manager
        self.pdf_generator = PDFGenerator(data_manager)

        # Initialisiere Excel-Spiel-Lader
        self.excel_loader = ExcelspielauftraegeLaden(None, data_manager)
        self.excel_loader.set_excel_file_path(self.data_manager.get_excel_file_path())

        # Hauptlayout
        layout = QGridLayout()

        # Menüleiste erstellen
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        # Menü für Profile
        profile_menu = self.menu_bar.addMenu("Menü")
        manage_profiles_action = QAction("Profile verwalten", self)
        manage_profiles_action.triggered.connect(self.open_profile_manager)
        profile_menu.addAction(manage_profiles_action)

        # Dropdown-Menü für Profil Links
        layout.addWidget(QLabel("Profil Links:"), 0, 0)
        self.profile_dropdown_links = QComboBox()
        self.profile_dropdown_links.addItem("-- Profil Links auswählen --")
        layout.addWidget(self.profile_dropdown_links, 0, 1)

        # Dropdown-Menü für Profil Rechts
        layout.addWidget(QLabel("Profil Rechts:"), 1, 0)
        self.profile_dropdown_rechts = QComboBox()
        self.profile_dropdown_rechts.addItem("-- Profil Rechts auswählen --")
        layout.addWidget(self.profile_dropdown_rechts, 1, 1)

        # Spiel auswählen
        layout.addWidget(QLabel("Spiel auswählen:"), 2, 0)
        self.game_dropdown = QComboBox()
        self.game_dropdown.addItem("-- Spiel auswählen --")
        self.excel_loader.game_dropdown = self.game_dropdown  # Verbinde Dropdown mit Excel-Lader
        layout.addWidget(self.game_dropdown, 2, 1)

        # PDF-Datei auswählen
        self.pdf_file_button = QPushButton("PDF-Datei auswählen")
        layout.addWidget(self.pdf_file_button, 3, 0, 1, 2)

        # Excel-Datei auswählen
        self.file_button = QPushButton("Excel-Datei auswählen")
        layout.addWidget(self.file_button, 4, 0, 1, 2)

        # PDF generieren
        self.generate_pdf_button = QPushButton("PDF generieren")
        layout.addWidget(self.generate_pdf_button, 5, 0, 1, 2)

        # Hauptcontainer
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Event-Handlers
        self.file_button.clicked.connect(self.select_excel_file)
        self.pdf_file_button.clicked.connect(self.select_pdf_file)
        self.generate_pdf_button.clicked.connect(self.generate_pdf)

        # Initialisierung
        self.refresh_profile_dropdowns()

        # Standard-Dateien laden
        self.load_default_files()

    def load_default_files(self):
        """Lädt die Standard-Excel- und PDF-Dateien."""
        if os.path.exists(self.data_manager.get_excel_file_path()):
            self.excel_loader.load_games_into_dropdown()
        else:
            QMessageBox.warning(self, "Warnung", f"Standard-Excel-Datei nicht gefunden: {self.data_manager.get_excel_file_path()}")

        if not os.path.exists(self.data_manager.get_pdf_file_path()):
            QMessageBox.warning(self, "Warnung", f"Standard-PDF-Datei nicht gefunden: {self.data_manager.get_pdf_file_path()}")

    def open_profile_manager(self):
        """Öffnet das Fenster zum Verwalten von Profilen."""
        # ProfileWindow wird hier definiert (Nicht im Code enthalten)
        pass

    def refresh_profile_dropdowns(self):
        """Aktualisiert die Dropdown-Menüs für Profile."""
        self.profile_dropdown_links.clear()
        self.profile_dropdown_rechts.clear()

        self.profile_dropdown_links.addItem("-- Profil Links auswählen --")
        self.profile_dropdown_rechts.addItem("-- Profil Rechts auswählen --")

        for profile_name in self.data_manager.get_all_profiles().keys():
            self.profile_dropdown_links.addItem(profile_name)
            self.profile_dropdown_rechts.addItem(profile_name)

    def select_excel_file(self):
        """Öffnet einen Dialog zum Auswählen der Excel-Datei."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Excel-Datei auswählen", "", "Excel Dateien (*.xlsx)")
        if file_path:
            self.excel_loader.set_excel_file_path(file_path)
            self.excel_loader.load_games_into_dropdown()

    def select_pdf_file(self):
        """Öffnet einen Dialog zum Auswählen der PDF-Datei."""
        file_path, _ = QFileDialog.getOpenFileName(self, "PDF-Datei auswählen", "", "PDF Dateien (*.pdf)")
        if file_path:
            self.data_manager.default_pdf_file_path = file_path

    def generate_pdf(self):
        """Generiert ein PDF basierend auf den ausgewählten Profilen."""
        try:
            # Profil-Daten und ausgewähltes Spiel laden
            profile_links_name = self.profile_dropdown_links.currentText()
            profile_rechts_name = self.profile_dropdown_rechts.currentText()
    
            if profile_links_name == "-- Profil Links auswählen --" or profile_rechts_name == "-- Profil Rechts auswählen --":
                QMessageBox.warning(self, "Warnung", "Bitte Profile für Links und Rechts auswählen!")
                return
    
            selected_game_index = self.game_dropdown.currentIndex() - 1
            if selected_game_index < 0:
                QMessageBox.warning(self, "Warnung", "Bitte ein Spiel auswählen!")
                return
    
            selected_game = self.data_manager.get_game(selected_game_index)
            if not selected_game:
                QMessageBox.critical(self, "Fehler", "Ungültiges Spiel ausgewählt!")
                return
    
            profile_links = self.data_manager.get_profile(profile_links_name)
            profile_rechts = self.data_manager.get_profile(profile_rechts_name)
    
            # Daten kombinieren
            pdf_data = {
                **selected_game,
                **profile_links,
                **{key.replace('_Links', '_Rechts'): value for key, value in profile_rechts.items()}
            }
    
            self.data_manager.load_from_dict(pdf_data)

        
    
            # PDF generieren
            self.pdf_generator.generate_pdf(self.data_manager.get_pdf_file_path())
            print(self)

    
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Generieren des PDFs: {e}")
    