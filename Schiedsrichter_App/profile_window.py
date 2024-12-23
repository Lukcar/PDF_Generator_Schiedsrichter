from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QWidget, QMessageBox
)

class ProfileWindow(QMainWindow):
    def __init__(self, data_manager, refresh_callback):
        super().__init__()
        self.setWindowTitle("Profil-Manager")
        self.setGeometry(100, 100, 400, 400)

        self.data_manager = data_manager
        self.refresh_callback = refresh_callback

        # Hauptlayout
        layout = QVBoxLayout()

        # Formularlayout für Profildaten
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.vorname_input = QLineEdit()
        self.plz_input = QLineEdit()
        self.strasse_input = QLineEdit()

        # Dropdown für Start-Ort
        self.start_ort_dropdown = QComboBox()
        self.start_ort_dropdown.addItems(self.data_manager.get_start_ort_list())

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Vorname:", self.vorname_input)
        form_layout.addRow("PLZ + Wohnort:", self.plz_input)
        form_layout.addRow("Straße:", self.strasse_input)
        form_layout.addRow("Start-Ort:", self.start_ort_dropdown)

        layout.addLayout(form_layout)

        # Dropdown zum Auswählen eines bestehenden Profils
        self.profile_selector = QComboBox()
        self.profile_selector.addItem("-- Neues Profil --")
        self.update_profile_selector()
        self.profile_selector.currentIndexChanged.connect(self.load_profile)
        layout.addWidget(QLabel("Vorhandenes Profil auswählen:"))
        layout.addWidget(self.profile_selector)

        # Buttons
        self.save_button = QPushButton("Speichern")
        self.save_button.clicked.connect(self.save_profile)
        layout.addWidget(self.save_button)

        # Hauptcontainer
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_profile_selector(self):
        """Aktualisiert das Dropdown-Menü mit den vorhandenen Profilen."""
        self.profile_selector.clear()
        self.profile_selector.addItem("-- Neues Profil --")
        for profile_name in self.data_manager.get_all_profiles().keys():
            self.profile_selector.addItem(profile_name)

    def load_profile(self):
        """Lädt ein vorhandenes Profil in die Eingabefelder."""
        index = self.profile_selector.currentIndex() - 1
        if index >= 0:
            profile_name = list(self.data_manager.get_all_profiles().keys())[index]
            profile_data = self.data_manager.get_profile(profile_name)

            self.name_input.setText(profile_data.get("Name_Links", ""))
            self.vorname_input.setText(profile_data.get("Vorname_Links", ""))
            self.plz_input.setText(profile_data.get("PLZ_Wohnort_Links", ""))
            self.strasse_input.setText(profile_data.get("Strasse_Links", ""))
            self.start_ort_dropdown.setCurrentText(profile_data.get("Start_Ort", ""))
        else:
            self.clear_inputs()

    def save_profile(self):
        """Speichert die eingegebenen Profildaten in der DataManager-Klasse."""
        name = self.name_input.text().strip()
        vorname = self.vorname_input.text().strip()
        plz = self.plz_input.text().strip()
        strasse = self.strasse_input.text().strip()
        start_ort = self.start_ort_dropdown.currentText()

        if not name or not vorname:
            QMessageBox.warning(self, "Warnung", "Vor- und Nachname dürfen nicht leer sein!")
            return

        # Generiere Profilnamen aus Vor- und Nachnamen
        profile_name = f"{vorname} {name}"

        profile_data = {
            "Name_Links": name,
            "Vorname_Links": vorname,
            "PLZ_Wohnort_Links": plz,
            "Strasse_Links": strasse,
            "Start_Ort": start_ort
        }

        if self.data_manager.add_profile(profile_name, profile_data):
            QMessageBox.information(self, "Erfolg", "Profil wurde gespeichert!")
        elif self.data_manager.update_profile(profile_name, profile_data):
            QMessageBox.information(self, "Erfolg", "Profil wurde aktualisiert!")
        else:
            QMessageBox.critical(self, "Fehler", "Fehler beim Speichern des Profils.")

        # Aktualisiere das Dropdown-Menü direkt
        self.update_profile_selector()

        self.refresh_callback()

    def clear_inputs(self):
        """Leert alle Eingabefelder."""
        self.name_input.clear()
        self.vorname_input.clear()
        self.plz_input.clear()
        self.strasse_input.clear()
        self.start_ort_dropdown.setCurrentIndex(0)
