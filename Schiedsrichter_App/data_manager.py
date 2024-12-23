class DataManager:
    def __init__(self):
        # Standardpfade für Dateien
        self.default_excel_file_path = "C:\\Users\\lukas\\Desktop\\Schiedsrichter_App\\spielaufträge-export_2024-12-21_20-08_8HPe.xlsx"
        self.default_pdf_file_path = "C:\\Users\\lukas\\Desktop\\Schiedsrichter_App\\Schiedsrichter-Reisekostenabrechnung.pdf"
        
        # Initialisiere die Standarddaten
        self.default_data = {
            "Sp.Nr": "",
            "Spielklasse": "",
            "Heimmannschaft": "",
            "Gastmannschaft": "",
            "Datum": "",
            "Halle": "Sporthalle",
            "Hallenname_cleaned": "",
            "Zeit": "",
            "Name_Links": "",
            "Vorname_Links": "",
            "PLZ_Wohnort_Links": "",
            "Strasse_Links": "",
            "Start_Ort": "",
            "Abfahrt_Links": "",
            "Rueckkehr_Links": "",
            "PKW_Links": "13",
            "PKW_Links_Summe": "",
            "Anrechenbare_Kosten_Links": "",
            "Spielentschaedigung_Links": "25",
            "Summe_Links": "",
            "Ort_Links": "",
            "Name_Rechts": "",
            "Vorname_Rechts": "",
            "PLZ_Wohnort_Rechts": "",
            "Strasse_Rechts": "",
            "Abfahrt_Rechts": "",
            "Rueckkehr_Rechts": "",
            "PKW_Rechts": "",
            "PKW_Rechts_Summe": "",
            "Anrechenbare_Kosten_Rechts": "0",
            "Spielentschaedigung_Rechts": "25",
            "Summe_Rechts": "",
            "Summe_Gesammt": "",
            "Ort_Rechts": "",
        }

        # Start-Ort-Liste
        self.start_ort_list = [
            "Bockhorst", "Borgholzhausen", "Brockhagen", "Delbrück",
            "Dissen", "Geseke", "Greffen", "Gütersloh", "Halle",
            "Harsewinkel", "Herzebrock", "Hesselteich", "Hörste",
            "Isselhorst", "Langenberg", "Lippstadt", "Loxten",
            "Mastholte", "Neuenkirchen", "Oelde", "Rheda", "Rietberg",
            "Spexard", "Steinhagen", "Varensell", "Verl", "Versmold",
            "Werther", "Wiedenbrück"
        ]

        # Speicher für Profile
        self.profiles = {}

        # Standardspiele
        self.games = []

        # Standardprofil initialisieren
        self.initialize_default_profile()

    def initialize_default_profile(self):
        """Fügt ein vorinitialisiertes Standardprofil hinzu."""
        default_profile_name = "Default User"
        default_profile_data = {
            "Name_Links": "Max",
            "Vorname_Links": "Mustermann",
            "PLZ_Wohnort_Links": "12345 Musterstadt",
            "Strasse_Links": "Musterstraße 1",
            "Start_Ort": "Musterort",
            "Abfahrt_Links": "08:00",
            "Rueckkehr_Links": "18:00",
            "PKW_Links": "100",
            "Anrechenbare_Kosten_Links": "30.00",
            "Spielentschaedigung_Links": "25",
        }
        self.profiles[default_profile_name] = default_profile_data

    def get_excel_file_path(self):
        """Gibt den Standardpfad zur Excel-Datei zurück."""
        return self.default_excel_file_path

    def get_pdf_file_path(self):
        """Gibt den Standardpfad zur PDF-Datei zurück."""
        return self.default_pdf_file_path

    def get_data(self):
        """Gibt die aktuellen Daten zurück."""
        return self.default_data

    def update_data(self, key, value):
        """Aktualisiert einen bestimmten Wert in den Daten."""
        if key in self.default_data:
            self.default_data[key] = value
        else:
            raise KeyError(f"Key '{key}' existiert nicht in den Daten.")

    def reset_data(self):
        """Setzt die Daten auf die Standardwerte zurück."""
        for key in self.default_data.keys():
            self.default_data[key] = ""

    def load_from_dict(self, data_dict):
        """Lädt Daten aus einem Dictionary."""
        for key, value in data_dict.items():
            if key in self.default_data:
                self.default_data[key] = value

    def to_dict(self):
        """Gibt die Daten als Dictionary zurück."""
        return self.default_data

    def get_start_ort_list(self):
        """Gibt die Liste der Start-Orte zurück."""
        return self.start_ort_list

    # Profile-Management-Methoden
    def get_all_profiles(self):
        """Gibt alle gespeicherten Profile zurück."""
        return self.profiles

    def add_profile(self, profile_name, profile_data):
        """Fügt ein neues Profil hinzu."""
        if profile_name in self.profiles:
            return False  # Profil existiert bereits
        self.profiles[profile_name] = profile_data
        return True

    def update_profile(self, profile_name, profile_data):
        """Aktualisiert ein vorhandenes Profil."""
        if profile_name in self.profiles:
            self.profiles[profile_name] = profile_data
            return True
        return False

    def get_profile(self, profile_name):
        """Lädt ein bestimmtes Profil."""
        return self.profiles.get(profile_name)

    def delete_profile(self, profile_name):
        """Löscht ein bestimmtes Profil."""
        if profile_name in self.profiles:
            del self.profiles[profile_name]
            return True
        return False

    def set_games(self, games):
        """Speichert die Spiele im DataManager."""
        self.games = []
        for game in games:
            # Validierung und Standardwerte setzen
            valid_game = {
                "Datum": game.get("Datum", "Unbekannt"),
                "Spielklasse": game.get("Staffel", "Unbekannt"),
                "Heimmannschaft": game.get("Heimmannschaft", "Unbekannt"),
                "Gastmannschaft": game.get("Gastmannschaft", "Unbekannt"),
                "Halle": game.get("Halle", "Unbekannt"),
                "Hallenname_cleaned": game.get("Hallenname_cleaned", ""),
                "Zeit": game.get("Zeit", "")
            }
            self.games.append(valid_game)
        # print("Spiele gespeichert:", self.games)  # Debugging-Ausgabe

    def get_game(self, index):
        """Gibt ein Spiel basierend auf dem Index zurück."""
        if 0 <= index < len(self.games):
            print(f"Spiel gefunden für Index {index}: {self.games[index]}")  # Debugging-Ausgabe
            return self.games[index]
        #print(f"Ungültiger Index {index}. Spiele-Liste: {self.games}")  # Debugging-Ausgabe
        return None
