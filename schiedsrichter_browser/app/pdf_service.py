from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from km_lookup import KmLookup
from models import Appointment, Profile, calculate_time_window


def format_money(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def format_km(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".replace(".", ",")


def format_km_rate(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + " \u20ac"


def safe_filename(value: str) -> str:
    value = re.sub(r"[<>:\"/\\\\|?*]+", "-", value)
    value = re.sub(r"\s+", "_", value.strip())
    return value[:120] or "abrechnung"


def extract_match_place(appointment: Appointment) -> str:
    hall_address = (appointment.hall_address or "").strip()
    if hall_address:
        match = re.search(r"\d{5}\s*([^\d]+)$", hall_address)
        if match:
            return match.group(1).strip()

    hall_name = (appointment.hall_name or "").strip()
    if hall_name:
        return hall_name

    return ""


def should_render_footer(profile: Profile | None) -> bool:
    return profile is not None


def build_place_date(place: str, created_on: str) -> str:
    place = (place or "").strip()
    return f"{place}, {created_on}" if place else created_on


class PDFService:
    def __init__(self, template_path: str):
        self.template_path = Path(template_path)

    def generate(
        self,
        appointment: Appointment,
        left_profile: Profile,
        right_profile: Profile | None,
        km_lookup: KmLookup,
        output_dir: str,
        left_week_bonus: float = 0.0,
        right_week_bonus: float = 0.0,
    ) -> Path:
        if not self.template_path.exists():
            raise FileNotFoundError(f"PDF-Vorlage nicht gefunden: {self.template_path}")

        output_folder = Path(output_dir)
        output_folder.mkdir(parents=True, exist_ok=True)
        created_on = datetime.now().strftime("%d.%m.%Y")

        shared_match_fee = left_profile.match_fee
        left_side = self._build_side_data(
            appointment,
            left_profile,
            km_lookup,
            match_fee=shared_match_fee,
            gets_travel_money=True,
            week_bonus=left_week_bonus,
        )
        right_side = (
            self._build_side_data(
                appointment,
                right_profile,
                km_lookup,
                match_fee=shared_match_fee,
                gets_travel_money=False,
                week_bonus=right_week_bonus,
            )
            if right_profile
            else None
        )
        place_date = build_place_date(extract_match_place(appointment), created_on)
        left_footer = self._build_footer_data(should_render_footer(left_profile), place_date)
        right_footer = self._build_footer_data(should_render_footer(right_profile), place_date)

        output_name = safe_filename(
            f"{appointment.date}_{appointment.match_id}_{appointment.home_team}_vs_{appointment.away_team}.pdf"
        )
        output_path = output_folder / output_name

        overlay_stream = self._create_overlay(appointment, left_side, right_side, left_footer, right_footer)
        reader = PdfReader(str(self.template_path))
        writer = PdfWriter()

        page = reader.pages[0]
        page.merge_page(PdfReader(overlay_stream).pages[0])
        writer.add_page(page)

        with output_path.open("wb") as handle:
            writer.write(handle)

        return output_path

    def _build_side_data(
        self,
        appointment: Appointment,
        profile: Profile | None,
        km_lookup: KmLookup,
        match_fee: float | None = None,
        gets_travel_money: bool = True,
        week_bonus: float = 0.0,
    ) -> dict[str, str]:
        if profile is None:
            return {
                "last_name": "",
                "first_name": "",
                "city_zip": "",
                "street": "",
                "departure": "",
                "return_trip": "",
                "km": "",
                "km_rate": "",
                "travel_cost": "",
                "week_bonus": "",
                "match_fee": "",
                "total": "",
            }

        effective_match_fee = profile.match_fee if match_fee is None else match_fee
        distance = km_lookup.get_distance(profile.start_location, appointment.hall_id) if gets_travel_money else None
        departure, return_trip = calculate_time_window(
            appointment.date,
            appointment.time,
            profile.minutes_before,
            profile.minutes_after,
        )
        travel_cost = round((distance or 0.0) * profile.km_rate, 2) if gets_travel_money else 0.0
        total = round(travel_cost + week_bonus + effective_match_fee, 2)

        return {
            "last_name": profile.last_name,
            "first_name": profile.first_name,
            "city_zip": profile.city_zip,
            "street": profile.street,
            "departure": departure,
            "return_trip": return_trip,
            "km": format_km(distance) if distance is not None else "",
            "km_rate": format_km_rate(profile.km_rate),
            "travel_cost": format_money(travel_cost) if gets_travel_money else "",
            "week_bonus": format_money(week_bonus) if week_bonus else "",
            "match_fee": format_money(effective_match_fee),
            "total": format_money(total),
        }

    def _build_footer_data(self, should_render: bool, place_date: str) -> dict[str, str]:
        if not should_render:
            return {"place_date": ""}
        return {"place_date": place_date}

    def _create_overlay(
        self,
        appointment: Appointment,
        left_side: dict[str, str],
        right_side: dict[str, str] | None,
        left_footer: dict[str, str],
        right_footer: dict[str, str] | None,
    ) -> BytesIO:
        right_side = right_side or self._build_side_data(appointment, None, KmLookup(""))
        right_footer = right_footer or {"place_date": ""}
        total_sum = 0.0
        for side in (left_side, right_side):
            total_text = side.get("total", "").replace(",", ".")
            if total_text:
                total_sum += float(total_text)

        packet = BytesIO()
        pdf_canvas = canvas.Canvas(packet, pagesize=(595.2, 841.68))
        pdf_canvas.setFont("Helvetica", 10)

        self._draw_top_section(pdf_canvas, appointment)
        self._draw_side(pdf_canvas, left_side, left=True)
        self._draw_side(pdf_canvas, right_side, left=False)
        self._draw_footer(pdf_canvas, left_footer, left=True)
        self._draw_footer(pdf_canvas, right_footer, left=False)

        pdf_canvas.setFont("Helvetica-Bold", 12)
        pdf_canvas.drawString(523, 255, format_money(total_sum))

        pdf_canvas.save()
        packet.seek(0)
        return packet

    def _draw_top_section(self, pdf_canvas: canvas.Canvas, appointment: Appointment) -> None:
        pdf_canvas.drawString(128, 740, f" {appointment.match_id or ''}")
        pdf_canvas.drawString(326, 740, f" {appointment.hall_code or appointment.hall_id or ''}")
        pdf_canvas.drawString(68, 700, f" {appointment.league or ''}")
        pdf_canvas.drawString(315, 720, f" {appointment.hall_name or ''}")
        pdf_canvas.drawString(68, 682, f" {appointment.home_team or ''}")
        pdf_canvas.drawString(318, 700, f" {appointment.date or ''}")
        pdf_canvas.drawString(436, 700, f" {appointment.time or ''}")
        pdf_canvas.drawString(343, 682, f" {appointment.away_team or ''}")

    def _draw_side(self, pdf_canvas: canvas.Canvas, data: dict[str, str], left: bool) -> None:
        x_offset = 0 if left else 280

        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.drawString(25 + x_offset, 657, data.get("last_name", ""))
        pdf_canvas.drawString(143 + x_offset, 657, data.get("first_name", ""))
        pdf_canvas.drawString(25 + x_offset, 632, data.get("city_zip", ""))
        pdf_canvas.drawString(25 + x_offset, 607, data.get("street", ""))

        pdf_canvas.setFont("Helvetica", 9)
        pdf_canvas.drawString(25 + x_offset, 580, data.get("departure", ""))
        pdf_canvas.drawString(180 + x_offset, 580, data.get("return_trip", ""))

        pdf_canvas.setFont("Helvetica", 10)
        km_text = data.get("km", "")
        if km_text:
            pdf_canvas.drawString(84 + x_offset, 525, km_text)
        self._draw_km_rate(pdf_canvas, data.get("km_rate", ""), left)
        pdf_canvas.drawRightString(274 + x_offset, 525, data.get("travel_cost", ""))
        pdf_canvas.drawRightString(274 + x_offset, 416, data.get("week_bonus", ""))
        pdf_canvas.drawRightString(274 + x_offset, 365, data.get("match_fee", ""))
        pdf_canvas.drawRightString(274 + x_offset, 340, data.get("total", ""))

    def _draw_footer(self, pdf_canvas: canvas.Canvas, data: dict[str, str], left: bool) -> None:
        place_date = data.get("place_date", "")
        if not place_date:
            return

        center_x = 159 if left else 440
        pdf_canvas.setFont("Helvetica", 8.25)
        pdf_canvas.drawCentredString(center_x, 171, place_date)

    def _draw_km_rate(self, pdf_canvas: canvas.Canvas, text: str, left: bool) -> None:
        x_offset = 0 if left else 280
        rect_x = 152 + x_offset
        center_x = 183 + x_offset

        pdf_canvas.saveState()
        pdf_canvas.setFillColorRGB(1, 1, 1)
        pdf_canvas.rect(rect_x, 523, 62, 11, fill=1, stroke=0)
        pdf_canvas.setFillColorRGB(0, 0, 0)
        pdf_canvas.setFont("Helvetica", 9)
        if text:
            pdf_canvas.drawCentredString(center_x, 524.5, text)
        pdf_canvas.restoreState()
