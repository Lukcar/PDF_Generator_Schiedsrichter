# Schiedsrichter Browser fuer Home Assistant

Dieses Add-on startet die Browser-Version deiner Schiedsrichter-App direkt innerhalb von Home Assistant.

## Funktionen

- Spielauftraege von `hw.it4sport.de` laden
- Excel-Import als Fallback
- Profile im Browser pflegen
- Reisekosten-PDFs direkt erzeugen und herunterladen
- Zugriff ueber Home Assistant Ingress

## Wichtige Daten

- Persistente Daten liegen in `/data`
- Die Web-App hoert intern auf Port `5000`
- Die App wird ueber Home Assistant Ingress geoeffnet

## Hinweise

- Die erste PDF-Vorlage und KM-Tabelle werden aus den mitgelieferten Assets vorbelegt.
- Spaetere Uploads landen persistent in `/data/uploads`.
- Erzeugte PDFs landen in `/data/output`.
