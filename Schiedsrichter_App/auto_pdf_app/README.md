# Auto PDF Schiedsrichter

Diese Unterordner-App ist eine einfache, getrennte Lösung für:

- Spielaufträge direkt von `hw.it4sport.de` laden
- alternativ eine exportierte Excel-Datei als Fallback verwenden
- Schiedsrichter-Profile speichern
- Kilometer aus der vorhandenen `Km-Tabelle.xlsx` ziehen
- die vorhandene Reisekosten-PDF automatisch befüllen

## Start

```powershell
cd auto_pdf_app
python app.py
```

Oder per Doppelklick auf `run_app.bat`.

## Was die App erwartet

- `Google Chrome` muss installiert sein
- gültige Zugangsdaten für `hw.it4sport.de`
- die bestehenden Dateien aus dem Projektordner:
  - `Schiedsrichter-Reisekostenabrechnung.pdf`
  - `Km-Tabelle.xlsx`

Die Pfade sind beim ersten Start schon vorbelegt und können in der Oberfläche geändert werden.

## Bedienung

1. Zugangsdaten eingeben und optional speichern.
2. Entweder `Automatisch von Webseite laden` klicken oder `Manuell im Browser anmelden`.
3. Ein oder zwei Profile auswählen.
4. Einen Spielauftrag markieren.
5. `PDF für Auswahl erzeugen` klicken.

Die PDF landet automatisch im Unterordner `auto_pdf_app/output`.

## Hinweise

- Für die Webabfrage wird ein eigener Chrome-Profilordner im Unterordner verwendet. So bleiben Logins und Cookies getrennt von der alten App.
- Wenn der automatische Login scheitert, öffnet der manuelle Modus Chrome sichtbar. Nach deinem Login importiert die App die Spielaufträge automatisch weiter.
- Wenn der Webseitenabruf einmal nicht klappt, kann über `Excel-Fallback` weiterhin gearbeitet werden.
- Die Abfahrts- und Rückkehrzeiten werden automatisch aus Anwurfzeit plus Profilwerten berechnet.
