from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

from models import Profile


class AppStorage:
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.project_dir = self.app_dir.parent
        self.assets_dir = self.app_dir / "assets"
        self.settings_path = self.app_dir / "settings.json"
        self.profiles_path = self.app_dir / "profiles.json"
        self.credentials_path = self.app_dir / "credentials.ini"
        self.output_dir = self.app_dir / "output"
        self.chrome_profile_dir = self.app_dir / "chrome_profile"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chrome_profile_dir.mkdir(parents=True, exist_ok=True)

    def _find_project_file(self, pattern: str) -> str:
        matches = sorted(self.project_dir.glob(pattern))
        return str(matches[0].resolve()) if matches else ""

    def _bundled_or_project_file(self, filename: str) -> str:
        bundled = self.assets_dir / filename
        if bundled.exists():
            return str(bundled.resolve())
        return str((self.project_dir / filename).resolve())

    def default_settings(self) -> dict[str, Any]:
        return {
            "pdf_template": self._bundled_or_project_file("Schiedsrichter-Reisekostenabrechnung.pdf"),
            "km_table": self._bundled_or_project_file("Km-Tabelle.xlsx"),
            "last_excel": self._find_project_file("spielaufträge-export*.xlsx"),
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
                loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    settings.update(loaded)
            except json.JSONDecodeError:
                pass

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
            loaded = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        profiles: dict[str, Profile] = {}
        if isinstance(loaded, list):
            for entry in loaded:
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
        preferred_files = [
            self.credentials_path,
            self.project_dir / "credentials.ini",
        ]

        for file_path in preferred_files:
            if not file_path.exists():
                continue
            config.read(file_path, encoding="utf-8")
            if config.has_section("Account"):
                return (
                    config.get("Account", "Username", fallback=""),
                    config.get("Account", "Password", fallback=""),
                )
        return "", ""

    def save_credentials(self, username: str, password: str) -> None:
        config = configparser.ConfigParser()
        config["Account"] = {"Username": username, "Password": password}
        with self.credentials_path.open("w", encoding="utf-8") as handle:
            config.write(handle)
