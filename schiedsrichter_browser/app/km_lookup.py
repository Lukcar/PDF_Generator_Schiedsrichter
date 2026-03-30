from __future__ import annotations

from pathlib import Path
from typing import Any
import re

import pandas as pd

from models import normalize_text


class KmLookup:
    def __init__(self, workbook_path: str):
        self.workbook_path = Path(workbook_path)
        self._matrix: dict[str, dict[str, float]] = {}
        self._display_names: dict[str, str] = {}

    def load(self) -> None:
        if not self.workbook_path.exists():
            raise FileNotFoundError(f"Kilometer-Datei nicht gefunden: {self.workbook_path}")

        dataframe = pd.read_excel(self.workbook_path)
        if dataframe.empty:
            raise ValueError("Kilometer-Datei ist leer.")

        start_col = dataframe.columns[0]
        self._matrix.clear()
        self._display_names.clear()

        for _, row in dataframe.iterrows():
            start_location = str(row[start_col]).strip()
            if not start_location or start_location.lower() == "nan":
                continue

            normalized_start = normalize_text(start_location)
            self._display_names[normalized_start] = start_location
            hall_distances: dict[str, float] = {}

            for column in dataframe.columns[1:]:
                value = row.get(column)
                if pd.isna(value):
                    continue
                hall_code = self._normalize_hall_code(column)
                if not hall_code:
                    continue
                hall_distances[hall_code] = float(value)

            self._matrix[normalized_start] = hall_distances

    @staticmethod
    def _normalize_hall_code(value: Any) -> str:
        digits = re.findall(r"\d+", str(value or ""))
        if not digits:
            return ""
        return digits[-1][-3:]

    def available_start_locations(self) -> list[str]:
        return [self._display_names[key] for key in sorted(self._display_names)]

    def get_distance(self, start_location: str, hall_id: str) -> float | None:
        if not self._matrix:
            self.load()

        normalized_start = normalize_text(start_location)
        hall_code = self._normalize_hall_code(hall_id)
        if not normalized_start or not hall_code:
            return None

        return self._matrix.get(normalized_start, {}).get(hall_code)
