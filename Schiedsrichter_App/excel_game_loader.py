import pandas as pd
from PyQt5.QtWidgets import QMessageBox


class ExcelspielauftraegeLaden:
    def __init__(self, game_dropdown, data_manager):
        """Initialisiert die Klasse mit dem Dropdown-Menü und DataManager."""
        self.game_dropdown = game_dropdown
        self.data_manager = data_manager
        self.excel_file_path = ""

    def set_excel_file_path(self, file_path):
        """Setzt den Pfad zur Excel-Datei."""
        self.excel_file_path = file_path

    def load_games_into_dropdown(self):
        """Lädt die Spiele aus der Excel-Datei und speichert sie im DataManager."""
        if not self.excel_file_path:
            QMessageBox.warning(None, "Warnung", "Bitte eine Excel-Datei auswählen!")
            return
    
        try:
            # Excel-Daten lesen
            df = pd.read_excel(self.excel_file_path)
    
            # Prüfen, ob die erwarteten Spalten vorhanden sind
            required_columns = ['Datum', 'Heimmannschaft', 'Gastmannschaft', 'Staffel', 'Hallename', 'Zeit']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                QMessageBox.critical(
                    None,
                    "Fehler",
                    f"Die folgenden benötigten Spalten fehlen in der Excel-Datei: {', '.join(missing_columns)}"
                )
                return
    
            # Dropdown-Menü für Spiele leeren
            self.game_dropdown.clear()
            self.game_dropdown.addItem("-- Spiel auswählen --")
    
            # Spiele hinzufügen und im DataManager speichern
            games = []
            for _, row in df.iterrows():
                datum = row.get('Datum', 'Unbekannt')
                if isinstance(datum, str):
                    try:
                        datum = pd.to_datetime(datum, dayfirst=True).strftime('%d.%m.%Y')
                    except Exception:
                        datum = 'Unbekannt'
                elif pd.notnull(datum):
                    datum = datum.strftime('%d.%m.%Y')
                else:
                    datum = 'Unbekannt'
    
                # Weitere Daten
                spiel = {
                    "Datum": datum,
                    "Heimmannschaft": row.get('Heimmannschaft', 'Unbekannt'),
                    "Gastmannschaft": row.get('Gastmannschaft', 'Unbekannt'),
                    "Spielklasse": row.get('Staffel', 'Unbekannt'),
                    "Halle": row.get('Halle', 'Unbekannt'),
                    "Hallenname_cleaned": row.get('Hallename', 'Unbekannt'),
                    "Zeit": row.get('Zeit', 'Unbekannt')
                }
                games.append(spiel)
    
                # Eintrag für Dropdown-Menü
                spiel_text = f"{spiel['Datum']} | {spiel['Spielklasse']}: {spiel['Heimmannschaft']} vs {spiel['Gastmannschaft']}"
                self.game_dropdown.addItem(spiel_text)
    
            # Spiele im DataManager speichern
            self.data_manager.set_games(games)
            print("Spiele an DataManager übergeben:")  # Debugging-Ausgabe
            QMessageBox.information(None, "Erfolg", "Spiele erfolgreich geladen!")
    
        except Exception as e:
            QMessageBox.critical(None, "Fehler", f"Fehler beim Einlesen der Excel-Datei: {e}")
    
        