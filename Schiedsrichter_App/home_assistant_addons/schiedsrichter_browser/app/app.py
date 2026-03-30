from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import os
import secrets
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, request, send_file, send_from_directory, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from browser_storage import AddonAppStorage
from excel_source import load_appointments_from_excel
from hw_client import PhoenixClient
from km_lookup import KmLookup
from models import Appointment, Profile, normalize_text, parse_match_datetime
from pdf_service import PDFService

DEFAULT_KM_RATE = 0.38
DEFAULT_WEEK_BONUS = 10.0
APPOINTMENT_CACHE: dict[str, list[dict[str, Any]]] = {}
UPLOAD_TARGETS = {
    "pdf_template": ("reisekosten_template.pdf", {".pdf"}),
    "km_table": ("km_tabelle.xlsx", {".xlsx"}),
}
APP_DIR = Path(__file__).resolve().parent
APP_STORAGE_DIR = Path(os.environ.get("APP_STORAGE_DIR", "/data")).resolve()


def parse_decimal_value(value: object, fallback: float | None = None) -> float:
    text = str(value).strip().replace(",", ".")
    if not text:
        if fallback is not None:
            return fallback
        raise ValueError("Wert fehlt.")

    try:
        parsed = float(text)
    except (TypeError, ValueError):
        if fallback is not None:
            return fallback
        raise ValueError("Ungueltiger Zahlenwert.") from None

    if parsed < 0:
        if fallback is not None:
            return fallback
        raise ValueError("Negative Werte sind nicht erlaubt.")

    return parsed


def format_decimal_input(value: object) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def load_secret_key(storage_dir: Path) -> str:
    secret_path = storage_dir / ".secret_key"
    storage_dir.mkdir(parents=True, exist_ok=True)
    if not secret_path.exists():
        secret_path.write_text(secrets.token_hex(32), encoding="utf-8")
    return secret_path.read_text(encoding="utf-8").strip()


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", load_secret_key(APP_STORAGE_DIR))
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


def get_storage() -> AddonAppStorage:
    return AddonAppStorage(APP_DIR, APP_STORAGE_DIR)


def get_session_bucket() -> str:
    bucket = session.get("appointment_bucket")
    if not bucket:
        bucket = uuid4().hex
        session["appointment_bucket"] = bucket
    return bucket


def set_session_appointments(appointments: list[Appointment]) -> None:
    APPOINTMENT_CACHE[get_session_bucket()] = [asdict(item) for item in appointments]


def get_session_appointments() -> list[Appointment]:
    payload = APPOINTMENT_CACHE.get(get_session_bucket(), [])
    appointments: list[Appointment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        appointments.append(Appointment(**item))
    return appointments


def load_start_locations(km_path: str) -> list[str]:
    if not km_path:
        return []

    lookup = KmLookup(km_path)
    try:
        lookup.load()
    except Exception:
        return []
    return lookup.available_start_locations()


def suggest_profiles(appointment: Appointment, profiles: dict[str, Profile]) -> tuple[str, str]:
    if not appointment.referees:
        return "", ""

    referee_names = [normalize_text(name) for name in appointment.referees]
    matches = [name for name in sorted(profiles) if normalize_text(name) in referee_names]
    if not matches:
        return "", ""
    if len(matches) == 1:
        return matches[0], ""
    return matches[0], matches[1]


def split_appointments(
    appointments: list[Appointment],
    profiles: dict[str, Profile],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    upcoming: list[dict[str, Any]] = []
    past: list[dict[str, Any]] = []

    for index, appointment in enumerate(appointments):
        suggested_left, suggested_right = suggest_profiles(appointment, profiles)
        row = {
            "index": index,
            "appointment": appointment,
            "referees_text": " / ".join(appointment.referees),
            "suggested_left": suggested_left,
            "suggested_right": suggested_right,
        }
        match_dt = parse_match_datetime(appointment.date, appointment.time)
        if match_dt is None or match_dt >= datetime.now():
            upcoming.append(row)
        else:
            past.append(row)

    upcoming.sort(key=lambda row: parse_match_datetime(row["appointment"].date, row["appointment"].time) or datetime.max)
    past.sort(
        key=lambda row: parse_match_datetime(row["appointment"].date, row["appointment"].time) or datetime.min,
        reverse=True,
    )
    return upcoming, past


def save_uploaded_file(storage: AddonAppStorage, setting_key: str, uploaded_file) -> Path:
    target_name, extensions = UPLOAD_TARGETS[setting_key]
    original_name = uploaded_file.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in extensions:
        expected = ", ".join(sorted(extensions))
        raise ValueError(f"Dateityp nicht erlaubt. Erlaubt sind: {expected}")

    target_path = storage.uploads_dir / target_name
    uploaded_file.save(target_path)
    return target_path.resolve()


def list_output_files(output_dir: Path) -> list[dict[str, str]]:
    files = [path for path in output_dir.glob("*.pdf") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    results: list[dict[str, str]] = []
    for path in files[:10]:
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
        results.append({"name": path.name, "modified": modified})
    return results


def load_profile_form_data(request_form: Any, default_km_rate: float) -> Profile:
    return Profile(
        first_name=str(request_form.get("first_name", "")).strip(),
        last_name=str(request_form.get("last_name", "")).strip(),
        city_zip=str(request_form.get("city_zip", "")).strip(),
        street=str(request_form.get("street", "")).strip(),
        start_location=str(request_form.get("start_location", "")).strip(),
        minutes_before=int(float(request_form.get("minutes_before", 75) or 75)),
        minutes_after=int(float(request_form.get("minutes_after", 120) or 120)),
        match_fee=parse_decimal_value(request_form.get("match_fee", 25), 25.0),
        km_rate=parse_decimal_value(request_form.get("km_rate", default_km_rate), default_km_rate),
    )


def count_text(appointments: list[Appointment], profiles: dict[str, Profile]) -> str:
    upcoming, past = split_appointments(appointments, profiles)
    return f"{len(upcoming)} neue und {len(past)} alte Eintraege gefunden."


@app.get("/")
def index():
    storage = get_storage()
    settings = storage.load_settings()
    profiles = storage.load_profiles()
    username, password = storage.load_credentials()
    appointments = get_session_appointments()
    upcoming, past = split_appointments(appointments, profiles)
    edit_name = request.args.get("edit", "").strip()
    editing_profile = profiles.get(edit_name)

    return render_template(
        "index.html",
        settings=settings,
        username=username,
        password=password,
        profiles=profiles,
        profile_names=sorted(profiles),
        start_locations=load_start_locations(settings.get("km_table", "")),
        default_km_rate=format_decimal_input(settings.get("default_km_rate", DEFAULT_KM_RATE)),
        week_bonus_amount=format_decimal_input(settings.get("week_bonus_amount", DEFAULT_WEEK_BONUS)),
        upcoming_rows=upcoming,
        past_rows=past,
        output_files=list_output_files(storage.output_dir),
        editing_profile=editing_profile,
    )


@app.post("/settings/save")
def save_settings():
    storage = get_storage()
    settings = storage.load_settings()

    try:
        default_km_rate = parse_decimal_value(request.form.get("default_km_rate"), DEFAULT_KM_RATE)
        week_bonus_amount = parse_decimal_value(request.form.get("week_bonus_amount"), DEFAULT_WEEK_BONUS)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    username = str(request.form.get("username", "")).strip()
    password = str(request.form.get("password", ""))
    storage.save_credentials(username, password)

    settings.update(
        {
            "pdf_template": str(request.form.get("pdf_template", "")).strip(),
            "km_table": str(request.form.get("km_table", "")).strip(),
            "last_excel": str(request.form.get("last_excel", "")).strip(),
            "output_dir": settings.get("output_dir", str(storage.output_dir.resolve())),
            "chrome_profile_dir": settings.get("chrome_profile_dir", str(storage.chrome_profile_dir.resolve())),
            "show_browser": bool(request.form.get("show_browser")),
            "default_km_rate": default_km_rate,
            "week_bonus_amount": week_bonus_amount,
        }
    )
    storage.save_settings(settings)
    flash("Einstellungen gespeichert.", "success")
    return redirect(url_for("index"))


@app.post("/upload/<setting_key>")
def upload_file(setting_key: str):
    if setting_key not in UPLOAD_TARGETS:
        flash("Unbekannter Upload-Typ.", "error")
        return redirect(url_for("index"))

    storage = get_storage()
    settings = storage.load_settings()
    uploaded_file = request.files.get("uploaded_file")
    if uploaded_file is None or not uploaded_file.filename:
        flash("Bitte eine Datei auswaehlen.", "error")
        return redirect(url_for("index"))

    try:
        saved_path = save_uploaded_file(storage, setting_key, uploaded_file)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    settings[setting_key] = str(saved_path)
    storage.save_settings(settings)
    flash("Datei gespeichert.", "success")
    return redirect(url_for("index"))


@app.post("/profiles/save")
def save_profile():
    storage = get_storage()
    settings = storage.load_settings()
    profiles = storage.load_profiles()

    try:
        profile = load_profile_form_data(
            request.form,
            parse_decimal_value(settings.get("default_km_rate", DEFAULT_KM_RATE), DEFAULT_KM_RATE),
        )
    except ValueError:
        flash("Bitte alle Zahlenfelder korrekt ausfuellen.", "error")
        return redirect(url_for("index"))

    if not all([profile.first_name, profile.last_name, profile.city_zip, profile.street, profile.start_location]):
        flash("Bitte alle Profilfelder ausfuellen.", "error")
        return redirect(url_for("index"))

    original_name = str(request.form.get("original_name", "")).strip()
    if original_name and original_name != profile.profile_name:
        profiles.pop(original_name, None)

    profiles[profile.profile_name] = profile
    storage.save_profiles(profiles)
    flash(f"Profil '{profile.profile_name}' gespeichert.", "success")
    return redirect(url_for("index"))


@app.post("/profiles/delete/<path:profile_name>")
def delete_profile(profile_name: str):
    storage = get_storage()
    profiles = storage.load_profiles()
    removed = profiles.pop(profile_name, None)
    if removed is None:
        flash("Profil wurde nicht gefunden.", "error")
        return redirect(url_for("index"))

    storage.save_profiles(profiles)
    flash(f"Profil '{profile_name}' geloescht.", "success")
    return redirect(url_for("index"))


@app.post("/appointments/load-web")
def load_web_appointments():
    storage = get_storage()
    settings = storage.load_settings()
    username, password = storage.load_credentials()

    if not username or not password:
        flash("Bitte zuerst Zugangsdaten speichern.", "error")
        return redirect(url_for("index"))

    client = PhoenixClient(
        profile_dir=str(settings.get("chrome_profile_dir", "")).strip(),
        show_browser=bool(settings.get("show_browser", False)),
    )

    try:
        appointments = client.fetch_appointments(username=username, password=password)
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    set_session_appointments(appointments)
    flash(f"Spielauftraege von hw.it4sport.de geladen. {count_text(appointments, storage.load_profiles())}", "success")
    return redirect(url_for("index"))


@app.post("/appointments/load-excel")
def load_excel_appointments():
    storage = get_storage()
    settings = storage.load_settings()
    uploaded_file = request.files.get("excel_file")

    if uploaded_file is not None and uploaded_file.filename:
        suffix = Path(uploaded_file.filename).suffix.lower()
        if suffix != ".xlsx":
            flash("Bitte eine .xlsx-Datei hochladen.", "error")
            return redirect(url_for("index"))
        target_path = storage.uploads_dir / "spielauftraege_fallback.xlsx"
        uploaded_file.save(target_path)
        settings["last_excel"] = str(target_path.resolve())
        storage.save_settings(settings)

    excel_path = str(settings.get("last_excel", "")).strip()
    if not excel_path:
        flash("Bitte zuerst eine Excel-Datei hochladen oder einen Pfad speichern.", "error")
        return redirect(url_for("index"))

    try:
        appointments = load_appointments_from_excel(excel_path)
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    set_session_appointments(appointments)
    flash(f"Excel-Spielauftraege geladen. {count_text(appointments, storage.load_profiles())}", "success")
    return redirect(url_for("index"))


@app.post("/pdf/generate")
def generate_pdf():
    storage = get_storage()
    settings = storage.load_settings()
    profiles = storage.load_profiles()
    appointments = get_session_appointments()

    try:
        appointment_index = int(request.form.get("appointment_index", "-1"))
    except ValueError:
        flash("Spielauftrag konnte nicht gelesen werden.", "error")
        return redirect(url_for("index"))

    if appointment_index < 0 or appointment_index >= len(appointments):
        flash("Spielauftrag wurde nicht gefunden.", "error")
        return redirect(url_for("index"))

    left_name = str(request.form.get("left_profile", "")).strip()
    right_name = str(request.form.get("right_profile", "")).strip()
    left_profile = profiles.get(left_name)
    right_profile = profiles.get(right_name) if right_name else None

    if left_profile is None:
        flash("Bitte mindestens ein linkes Profil auswaehlen.", "error")
        return redirect(url_for("index"))

    try:
        week_bonus_amount = parse_decimal_value(
            request.form.get("week_bonus_amount"),
            parse_decimal_value(settings.get("week_bonus_amount", DEFAULT_WEEK_BONUS), DEFAULT_WEEK_BONUS),
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    settings["week_bonus_amount"] = week_bonus_amount
    storage.save_settings(settings)

    left_week_bonus = week_bonus_amount if bool(request.form.get("left_week_bonus")) else 0.0
    right_week_bonus = week_bonus_amount if right_profile is not None and bool(request.form.get("right_week_bonus")) else 0.0

    try:
        km_lookup = KmLookup(str(settings.get("km_table", "")).strip())
        km_lookup.load()
        pdf_service = PDFService(str(settings.get("pdf_template", "")).strip())
        output_path = pdf_service.generate(
            appointment=appointments[appointment_index],
            left_profile=left_profile,
            right_profile=right_profile,
            km_lookup=km_lookup,
            output_dir=str(settings.get("output_dir", "")).strip(),
            left_week_bonus=left_week_bonus,
            right_week_bonus=right_week_bonus,
        )
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    return send_file(output_path, as_attachment=True, download_name=output_path.name)


@app.get("/output/<path:filename>")
def download_output(filename: str):
    storage = get_storage()
    return send_from_directory(str(storage.output_dir), filename, as_attachment=True)


@app.get("/health")
def health() -> tuple[str, int]:
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
