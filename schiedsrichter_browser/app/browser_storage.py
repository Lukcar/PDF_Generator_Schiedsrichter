from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

from models import Profile


class AddonAppStorage:
    def __init__(self, code_dir: Path, storage_dir: Path):
        self.code_dir = Path(code_dir)
        self.storage_dir = Path(storage_dir)
        self.assets_dir = self.code_dir / "assets"
        self.settings_path = self.storage_dir / "settings.json"
        self.profiles_path = self.storage_dir / "profiles.json"
        self.credentials_path = self.storage_dir / "credentials.ini"
        self.output_dir = self.storage_dir / "output"
        self.chrome_profile_dir = self.storage_dir / "chrome_profile"
        self.uploads_dir = self.storage_dir / "uploads"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chrome_profile_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def _bundled_or_uploaded_file(self, upload_name: str, asset_name: str) -> str:
        uploaded = self.uploads_dir / upload_name
        if uploaded.exists():
            return str(uploaded.resolve())

        bundled = self.assets_dir / asset_name
        if bundled.exists():
            return str(bundled.resolve())
        return ""

    def default_settings(self) -> dict[str, Any]:
        fallback_excel = self.uploads_dir / "spielauftraege_fallback.xlsx"
        return {
            "pdf_template": self._bundled_or_uploaded_file(
                "reisekosten_template.pdf",
                "Schiedsrichter-Reisekostenabrechnung.pdf",
            ),
            "km_table": self._bundled_or_uploaded_file("km_tabelle.xlsx", "Km-Tabelle.xlsx"),
            "last_excel": str(fallback_excel.resolve()) if fallback_excel.exists() else "",
            "output_dir": str(self.output_dir.resolve()),
            "chrome_profile_dir": str(self.chrome_profile_dir.resolve()),
            "show_browser": False,
            "default_km_rate": 0.38,
            "week_bonus_amount": 10.0,
        }

    def load_settings(self) -> dict[str, Any]:
        settings = self.default_settings()
        if self.settings_path.exists():
            try:
                payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                settings.update(payload)

        for key in ("output_dir", "chrome_profile_dir"):
            if settings.get(key):
                Path(settings[key]).mkdir(parents=True, exist_ok=True)

        self.save_settings(settings)
        return settings

    def save_settings(self, settings: dict[str, Any]) -> None:
        self.settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_profiles(self) -> dict[str, Profile]:
        if not self.profiles_path.exists():
            return {}

        try:
            payload = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        profiles: dict[str, Profile] = {}
        if isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                profile = Profile.from_dict(entry)
                if profile.profile_name:
                    profiles[profile.profile_name] = profile
        return dict(sorted(profiles.items()))

    def save_profiles(self, profiles: dict[str, Profile]) -> None:
        payload = [profile.to_dict() for _, profile in sorted(profiles.items())]
        self.profiles_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_credentials(self) -> tuple[str, str]:
        config = configparser.ConfigParser()
        if not self.credentials_path.exists():
            return "", ""

        config.read(self.credentials_path, encoding="utf-8")
        if not config.has_section("Account"):
            return "", ""

        return (
            config.get("Account", "Username", fallback=""),
            config.get("Account", "Password", fallback=""),
        )

    def save_credentials(self, username: str, password: str) -> None:
        config = configparser.ConfigParser()
        config["Account"] = {"Username": username, "Password": password}
        with self.credentials_path.open("w", encoding="utf-8") as handle:
            config.write(handle)
