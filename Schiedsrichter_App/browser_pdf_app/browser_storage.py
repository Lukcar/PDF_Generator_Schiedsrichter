from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any
import sys

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DESKTOP_APP_DIR = ROOT_DIR / "auto_pdf_app"

if str(DESKTOP_APP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_APP_DIR))

from models import Profile
from storage import AppStorage


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _load_profiles_file(path: Path) -> dict[str, Profile]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    profiles: dict[str, Profile] = {}
    if not isinstance(payload, list):
        return profiles

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        profile = Profile.from_dict(entry)
        if profile.profile_name:
            profiles[profile.profile_name] = profile
    return dict(sorted(profiles.items()))


class BrowserAppStorage(AppStorage):
    def __init__(self, app_dir: Path):
        super().__init__(app_dir)
        self.uploads_dir = self.app_dir / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self.desktop_app_dir = self.project_dir / "auto_pdf_app"
        self.desktop_settings_path = self.desktop_app_dir / "settings.json"
        self.desktop_profiles_path = self.desktop_app_dir / "profiles.json"
        self.desktop_credentials_path = self.desktop_app_dir / "credentials.ini"

    def default_settings(self) -> dict[str, Any]:
        settings = super().default_settings()

        uploaded_template = self.uploads_dir / "reisekosten_template.pdf"
        uploaded_km_table = self.uploads_dir / "km_tabelle.xlsx"
        uploaded_excel = self.uploads_dir / "spielauftraege_fallback.xlsx"

        if uploaded_template.exists():
            settings["pdf_template"] = str(uploaded_template.resolve())
        if uploaded_km_table.exists():
            settings["km_table"] = str(uploaded_km_table.resolve())
        if uploaded_excel.exists():
            settings["last_excel"] = str(uploaded_excel.resolve())

        settings["output_dir"] = str(self.output_dir.resolve())
        settings["chrome_profile_dir"] = str(self.chrome_profile_dir.resolve())
        return settings

    def load_settings(self) -> dict[str, Any]:
        settings = self.default_settings()

        if self.settings_path.exists():
            settings.update(_load_json_dict(self.settings_path))
        else:
            desktop_settings = _load_json_dict(self.desktop_settings_path)
            if desktop_settings:
                settings.update(desktop_settings)
                settings["output_dir"] = str(self.output_dir.resolve())
                settings["chrome_profile_dir"] = str(self.chrome_profile_dir.resolve())

        for key in ("output_dir", "chrome_profile_dir"):
            if settings.get(key):
                Path(settings[key]).mkdir(parents=True, exist_ok=True)

        self.save_settings(settings)
        return settings

    def load_profiles(self) -> dict[str, Profile]:
        profiles = _load_profiles_file(self.profiles_path)
        if profiles:
            return profiles
        return _load_profiles_file(self.desktop_profiles_path)

    def load_credentials(self) -> tuple[str, str]:
        config = configparser.ConfigParser()
        preferred_files = [
            self.credentials_path,
            self.project_dir / "credentials.ini",
            self.desktop_credentials_path,
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
