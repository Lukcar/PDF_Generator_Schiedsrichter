from __future__ import annotations

from pathlib import Path

import pandas as pd

from models import Appointment


def load_appointments_from_excel(excel_path: str) -> list[Appointment]:
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel-Datei nicht gefunden: {path}")

    dataframe = pd.read_excel(path)
    required = {"Datum", "Zeit", "Heimmannschaft", "Gastmannschaft"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Excel-Datei fehlt mindestens diese Spalten: {joined}")

    appointments = [Appointment.from_row(row.to_dict()) for _, row in dataframe.iterrows()]
    return [item for item in appointments if item.home_team or item.away_team]
