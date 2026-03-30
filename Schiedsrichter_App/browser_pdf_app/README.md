# Browser-App fuer den Raspberry Pi

Dieser Ordner enthaelt eine Browser-Version deiner Schiedsrichter-App.

Die Web-App kann:

- Zugangsdaten speichern
- Spielauftraege direkt von `hw.it4sport.de` laden
- alternativ eine Excel-Datei hochladen oder als Fallback nutzen
- Profile im Browser pflegen
- PDFs erzeugen und direkt herunterladen
- auf dem Raspberry Pi im Netzwerk unter einer festen URL laufen

## Start lokal

```powershell
cd browser_pdf_app
python -m pip install -r requirements.txt
python app.py
```

Danach ist die App unter `http://localhost:5000` erreichbar.

## Raspberry Pi

1. Python 3 installieren.
2. Chromium fuer Selenium installieren.
3. Projekt auf den Raspberry kopieren.
4. In `browser_pdf_app` die Abhaengigkeiten installieren.
5. `python app.py` starten.

Die App lauscht auf `0.0.0.0:5000`, also im Heimnetz zum Beispiel unter:

```text
http://raspberrypi.local:5000
```

oder

```text
http://192.168.x.x:5000
```

## Immer erreichbar machen

Am saubersten ist ein `systemd`-Dienst auf dem Raspberry. Beispiel:

```ini
[Unit]
Description=Schiedsrichter Browser App
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Schiedsrichter_App/browser_pdf_app
ExecStart=/usr/bin/python3 /home/pi/Schiedsrichter_App/browser_pdf_app/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Danach:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now schiedsrichter-browser-app
```

## Hinweise

- Die Browser-App uebernimmt beim ersten Start vorhandene Profile und Einstellungen aus `auto_pdf_app`, falls dort schon Daten liegen.
- Hochgeladene Dateien landen in `browser_pdf_app/uploads`.
- Erzeugte PDFs landen in `browser_pdf_app/output`.
- Fuer Raspberry/Linux ist es sinnvoll, Chromium installiert zu haben. Der Selenium-Start wurde so vorbereitet, dass gaengige Chromium-Pfade erkannt werden.
