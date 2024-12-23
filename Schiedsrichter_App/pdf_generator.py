import os
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from PyQt5.QtWidgets import QFileDialog
import pandas as pd

class PDFGenerator:
    def __init__(self, data_manager):
        self.data_manager = data_manager

    def create_overlay(self, data):
        """Erstellt ein PDF-Overlay mit den bereitgestellten Daten."""
        packet = BytesIO()
        c = canvas.Canvas(packet)

        c.setFont("Helvetica", 10)

        # Beispiel für einige Datenpunkte im PDF
        c.drawString(128, 740, f" {data.get('Sp.Nr', 'Unbekannt')}")
        c.drawString(68, 700, f" {data.get('Spielklasse', 'Unbekannt')}")
        c.drawString(315, 720, f" {data.get('Hallename', data.get('Hallenname_cleaned', 'Unbekannt'))}")
        c.drawString(68, 682, f" {data.get('Heimmannschaft', 'Unbekannt')}")
        c.drawString(326, 740, f" {data.get('Halle', 'Unbekannt')}")
        c.drawString(318, 700, f" {data.get('Datum', 'Unbekannt')}")
        c.drawString(435, 700, f" {data.get('Zeit', 'Unbekannt')}")
        c.drawString(343, 682, f" {data.get('Gastmannschaft', 'Unbekannt')}")

        # Linker Bereich
        c.drawString(25, 657, f" {data.get('Name_Links', 'Unbekannt')}")
        c.drawString(143, 657, f" {data.get('Vorname_Links', 'Unbekannt')}")
        c.drawString(25, 632, f" {data.get('PLZ_Wohnort_Links', 'Unbekannt')}")
        c.drawString(25, 607, f" {data.get('Strasse_Links', 'Unbekannt')}")
        c.drawString(25, 580, f" {data.get('Abfahrt_Links', 'Unbekannt')}")
        c.drawString(180, 580, f" {data.get('Rueckkehr_Links', 'Unbekannt')}")
        c.drawString(83, 525, f" {data.get('PKW_Links', 'Unbekannt')} km")
        c.drawString(250, 525, f" {data.get('PKW_Links_Summe', 'Unbekannt')} ")
        c.drawString(250, 365, f" {data.get('Spielentschaedigung_Links', 'Unbekannt')} ")
        c.drawString(250, 340, f" {data.get('Summe_Links', 'Unbekannt')} ")

        # Rechter Bereich
        c.drawString(305, 657, f" {data.get('Name_Rechts', 'Unbekannt')}")
        c.drawString(423, 657, f" {data.get('Vorname_Rechts', 'Unbekannt')}")
        c.drawString(305, 632, f" {data.get('PLZ_Wohnort_Rechts', 'Unbekannt')}")
        c.drawString(305, 607, f" {data.get('Strasse_Rechts', 'Unbekannt')}")
        c.drawString(305, 580, f" {data.get('Abfahrt_Rechts', 'Unbekannt')}")
        c.drawString(460, 580, f" {data.get('Rueckkehr_Rechts', 'Unbekannt')}")
        c.drawString(375, 525, f" {data.get('PKW_Rechts', 'Unbekannt')} km")
        c.drawString(530, 525, f" {data.get('PKW_Rechts_Summe', 'Unbekannt')} ")
        c.drawString(530, 365, f" {data.get('Spielentschaedigung_Rechts', 'Unbekannt')} ")
        c.drawString(530, 340, f" {data.get('Summe_Rechts', 'Unbekannt')} ")

        # Gesamtsumme
        c.setFont("Helvetica", 13)
        c.drawString(520, 257, f" {data.get('Summe_Gesammt', 'Unbekannt')} ")

        c.save()
        packet.seek(0)
        return packet

    def generate_pdf(self, template_path):
        """Generiert ein PDF basierend auf einem Template und den gespeicherten Daten."""
        try:
            # Dialogfenster zur Auswahl des Speicherorts
            output_path, _ = QFileDialog.getSaveFileName(None, "PDF speichern", "", "PDF Dateien (*.pdf)")
            if not output_path:
                print("Speichern abgebrochen.")
                return

            data = self.data_manager.get_data()

            # Erstellen des Overlays
            overlay_pdf = self.create_overlay(data)

            # Template laden
            reader = PdfReader(template_path)
            writer = PdfWriter()

            page = reader.pages[0]

            # Overlay anwenden
            page.merge_page(PdfReader(overlay_pdf).pages[0])

            writer.add_page(page)

            # Ausgabe speichern
            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            print(f"PDF wurde erfolgreich generiert: {output_path}")
            os.startfile(output_path)

        except Exception as e:
            print(f"Fehler beim Generieren des PDFs: {e}")

class ExcelspielauftraegeLaden:
    def __init__(self, game_dropdown, data_manager):
        self.game_dropdown = game_dropdown
        self.data_manager = data_manager
        self.excel_file_path = ""

    def set_excel_file_path(self, file_path):
        self.excel_file_path = file_path

    def load_games_into_dropdown(self):
        """Lädt die Spiele aus der Excel-Datei und speichert sie im DataManager."""
        if not self.excel_file_path:
            print("Bitte eine Excel-Datei auswählen!")
            return

        try:
            df = pd.read_excel(self.excel_file_path)

            required_columns = ['Sp.Nr', 'Datum', 'Heimmannschaft', 'Gastmannschaft', 'H.Nr', 'Hallename', 'Zeit']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                print(f"Die folgenden benötigten Spalten fehlen in der Excel-Datei: {', '.join(missing_columns)}")
                return

            games = []

            for _, row in df.iterrows():
                heimverein = row.get('Heimmannschaft', 'Nicht verfügbar')
                gastverein = row.get('Gastmannschaft', 'Nicht verfügbar')

                if '[' in heimverein and ']' in heimverein:
                    spielklasse = heimverein.split('[')[-1].split(']')[0]
                    heimverein = heimverein.split('[')[0].strip()
                else:
                    spielklasse = 'Nicht verfügbar'

                if '[' in gastverein and ']' in gastverein:
                    gastverein = gastverein.split('[')[0].strip()

                halle = row.get('H.Nr', 'Nicht verfügbar')
                hallenname = row.get('Hallename', 'Nicht verfügbar')
                hallenname_cleaned = ' '.join(hallenname.split(' ')[1:]) if hallenname != 'Nicht verfügbar' else hallenname

                game = {
                    "Sp.Nr": row.get('Sp.Nr', 'Nicht verfügbar'),
                    "Datum": row.get('Datum', 'Nicht verfügbar'),
                    "Spielklasse": spielklasse,
                    "Heimmannschaft": heimverein,
                    "Gastmannschaft": gastverein,
                    "Halle": halle,
                    "Hallenname_cleaned": hallenname_cleaned,
                    "Zeit": row.get('Zeit', 'Nicht verfügbar')
                }
                games.append(game)

            self.data_manager.set_games(games)
            print("Spiele erfolgreich geladen und in DataManager gespeichert.")
        except Exception as e:
            print(f"Fehler beim Laden der Spiele: {e}")
