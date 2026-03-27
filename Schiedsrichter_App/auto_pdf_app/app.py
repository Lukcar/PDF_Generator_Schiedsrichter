from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from excel_source import load_appointments_from_excel
from hw_client import PhoenixClient
from km_lookup import KmLookup
from models import Appointment, Profile, normalize_text, parse_match_datetime
from pdf_service import PDFService
from storage import AppStorage


LEFT_PLACEHOLDER = "-- Linkes Profil wählen --"
RIGHT_PLACEHOLDER = "-- Kein zweites Profil --"
DEFAULT_KM_RATE = 0.38
DEFAULT_WEEK_BONUS = 10.0


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


def format_decimal_value(value: float) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text or "0"


class ProfileEditor(tk.Toplevel):
    def __init__(
        self,
        master: "AutoPdfApp",
        profiles: dict[str, Profile],
        start_locations: list[str],
        default_km_rate: float,
        on_save,
    ):
        super().__init__(master)
        self.title("Profile verwalten")
        self.geometry("760x470")
        self.resizable(False, False)

        self.on_save = on_save
        self.profiles = dict(profiles)
        self.start_locations = start_locations
        self.default_km_rate = default_km_rate
        self.selected_name: str | None = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(self, padding=12)
        list_frame.grid(row=0, column=0, sticky="ns")

        form_frame = ttk.Frame(self, padding=12)
        form_frame.grid(row=0, column=1, sticky="nsew")
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(list_frame, text="Gespeicherte Profile").pack(anchor="w")
        self.profile_list = tk.Listbox(list_frame, width=28, height=18)
        self.profile_list.pack(fill="y", pady=(6, 12))
        self.profile_list.bind("<<ListboxSelect>>", self._on_profile_select)

        ttk.Button(list_frame, text="Neues Profil", command=self._new_profile).pack(fill="x")
        ttk.Button(list_frame, text="Profil löschen", command=self._delete_profile).pack(fill="x", pady=(8, 0))

        self.first_name_var = tk.StringVar()
        self.last_name_var = tk.StringVar()
        self.city_zip_var = tk.StringVar()
        self.street_var = tk.StringVar()
        self.start_location_var = tk.StringVar()
        self.minutes_before_var = tk.StringVar(value="75")
        self.minutes_after_var = tk.StringVar(value="120")
        self.match_fee_var = tk.StringVar(value="25")
        self.km_rate_var = tk.StringVar(value=format_decimal_value(default_km_rate))

        fields = [
            ("Vorname", ttk.Entry(form_frame, textvariable=self.first_name_var)),
            ("Nachname", ttk.Entry(form_frame, textvariable=self.last_name_var)),
            ("PLZ + Ort", ttk.Entry(form_frame, textvariable=self.city_zip_var)),
            ("Straße", ttk.Entry(form_frame, textvariable=self.street_var)),
            (
                "Start-Ort",
                ttk.Combobox(
                    form_frame,
                    textvariable=self.start_location_var,
                    values=start_locations,
                    state="readonly" if start_locations else "normal",
                ),
            ),
            ("Minuten vor Anwurf", ttk.Entry(form_frame, textvariable=self.minutes_before_var)),
            ("Minuten nach Spiel", ttk.Entry(form_frame, textvariable=self.minutes_after_var)),
            ("Spielleitung in EUR", ttk.Entry(form_frame, textvariable=self.match_fee_var)),
            ("KM-Pauschale in EUR/km", ttk.Entry(form_frame, textvariable=self.km_rate_var)),
        ]

        for row, (label, widget) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
            widget.grid(row=row, column=1, sticky="ew", pady=6)

        ttk.Button(form_frame, text="Speichern", command=self._save_profile).grid(
            row=len(fields),
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(18, 0),
        )

        self._refresh_list()
        self._new_profile()

    def _refresh_list(self) -> None:
        self.profile_list.delete(0, tk.END)
        for name in sorted(self.profiles):
            self.profile_list.insert(tk.END, name)

    def _new_profile(self) -> None:
        self.selected_name = None
        self.first_name_var.set("")
        self.last_name_var.set("")
        self.city_zip_var.set("")
        self.street_var.set("")
        self.start_location_var.set(self.start_locations[0] if self.start_locations else "")
        self.minutes_before_var.set("75")
        self.minutes_after_var.set("120")
        self.match_fee_var.set("25")
        self.km_rate_var.set(format_decimal_value(self.default_km_rate))
        self.profile_list.selection_clear(0, tk.END)

    def _on_profile_select(self, _event=None) -> None:
        selection = self.profile_list.curselection()
        if not selection:
            return
        profile_name = self.profile_list.get(selection[0])
        profile = self.profiles[profile_name]
        self.selected_name = profile_name
        self.first_name_var.set(profile.first_name)
        self.last_name_var.set(profile.last_name)
        self.city_zip_var.set(profile.city_zip)
        self.street_var.set(profile.street)
        self.start_location_var.set(profile.start_location)
        self.minutes_before_var.set(str(profile.minutes_before))
        self.minutes_after_var.set(str(profile.minutes_after))
        self.match_fee_var.set(format_decimal_value(profile.match_fee))
        self.km_rate_var.set(format_decimal_value(profile.km_rate))

    def _delete_profile(self) -> None:
        if not self.selected_name:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Profil auswählen.")
            return
        if not messagebox.askyesno("Profil löschen", f"Soll '{self.selected_name}' gelöscht werden?"):
            return
        self.profiles.pop(self.selected_name, None)
        self.selected_name = None
        self._refresh_list()
        self._new_profile()
        self.on_save(self.profiles)

    def _save_profile(self) -> None:
        try:
            profile = Profile(
                first_name=self.first_name_var.get().strip(),
                last_name=self.last_name_var.get().strip(),
                city_zip=self.city_zip_var.get().strip(),
                street=self.street_var.get().strip(),
                start_location=self.start_location_var.get().strip(),
                minutes_before=int(self.minutes_before_var.get().strip()),
                minutes_after=int(self.minutes_after_var.get().strip()),
                match_fee=parse_decimal_value(self.match_fee_var.get()),
                km_rate=parse_decimal_value(self.km_rate_var.get()),
            )
        except ValueError:
            messagebox.showerror("Fehler", "Bitte Zahlenfelder korrekt ausfüllen.")
            return

        if not all([profile.first_name, profile.last_name, profile.city_zip, profile.street, profile.start_location]):
            messagebox.showerror("Fehler", "Bitte alle Felder ausfüllen.")
            return

        if self.selected_name and self.selected_name != profile.profile_name:
            self.profiles.pop(self.selected_name, None)

        self.profiles[profile.profile_name] = profile
        self.selected_name = profile.profile_name
        self._refresh_list()
        self.on_save(self.profiles)
        messagebox.showinfo("Erfolg", f"Profil '{profile.profile_name}' gespeichert.")


class AutoPdfApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto PDF Schiedsrichter")
        self.geometry("1180x720")
        self.minsize(1100, 680)

        self.base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        self.storage = AppStorage(self.base_dir)
        self.settings = self.storage.load_settings()
        self.profiles = self.storage.load_profiles()
        self.appointments: list[Appointment] = []
        self._ui_queue: Queue = Queue()
        self.upcoming_lookup: dict[str, Appointment] = {}
        self.past_lookup: dict[str, Appointment] = {}
        self.busy = False

        username, password = self.storage.load_credentials()

        self.username_var = tk.StringVar(value=username)
        self.password_var = tk.StringVar(value=password)
        self.template_var = tk.StringVar(value=self.settings.get("pdf_template", ""))
        self.km_var = tk.StringVar(value=self.settings.get("km_table", ""))
        self.output_var = tk.StringVar(value=self.settings.get("output_dir", ""))
        self.excel_var = tk.StringVar(value=self.settings.get("last_excel", ""))
        self.show_browser_var = tk.BooleanVar(value=bool(self.settings.get("show_browser", False)))
        self.default_km_rate_var = tk.StringVar(
            value=format_decimal_value(
                parse_decimal_value(self.settings.get("default_km_rate", DEFAULT_KM_RATE), DEFAULT_KM_RATE)
            )
        )
        self.week_bonus_amount_var = tk.StringVar(
            value=format_decimal_value(
                parse_decimal_value(self.settings.get("week_bonus_amount", DEFAULT_WEEK_BONUS), DEFAULT_WEEK_BONUS)
            )
        )
        self.left_week_bonus_var = tk.BooleanVar(value=False)
        self.right_week_bonus_var = tk.BooleanVar(value=False)
        self.left_profile_var = tk.StringVar(value=LEFT_PLACEHOLDER)
        self.right_profile_var = tk.StringVar(value=RIGHT_PLACEHOLDER)
        self.status_var = tk.StringVar(value="Bereit.")

        self._build_ui()
        self._refresh_profile_boxes()
        self.after(100, self._process_ui_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        source_frame = ttk.LabelFrame(self, text="Quelle und Dateien", padding=12)
        source_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        source_frame.columnconfigure(1, weight=1)

        ttk.Label(source_frame, text="Benutzername").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(source_frame, textvariable=self.username_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(source_frame, text="Passwort").grid(row=0, column=2, sticky="w", pady=4, padx=(16, 10))
        ttk.Entry(source_frame, textvariable=self.password_var, show="*").grid(row=0, column=3, sticky="ew", pady=4)
        ttk.Button(source_frame, text="Zugang speichern", command=self._save_credentials).grid(row=0, column=4, padx=(12, 0))

        self._add_path_row(source_frame, 1, "PDF-Vorlage", self.template_var, self._browse_pdf)
        self._add_path_row(source_frame, 2, "KM-Tabelle", self.km_var, self._browse_km)
        self._add_path_row(source_frame, 3, "Excel-Fallback", self.excel_var, self._browse_excel)
        self._add_path_row(source_frame, 4, "Ausgabeordner", self.output_var, self._browse_output)

        ttk.Checkbutton(
            source_frame,
            text="Browser sichtbar öffnen",
            variable=self.show_browser_var,
            command=self._persist_settings,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        button_row = ttk.Frame(source_frame)
        button_row.grid(row=5, column=2, columnspan=3, sticky="e", pady=(8, 0))
        self.web_button = ttk.Button(button_row, text="Automatisch von Webseite laden", command=self._load_from_website)
        self.web_button.pack(side="left")
        self.manual_web_button = ttk.Button(
            button_row,
            text="Manuell im Browser anmelden",
            command=self._load_from_website_manual,
        )
        self.manual_web_button.pack(side="left", padx=(10, 0))
        self.excel_button = ttk.Button(button_row, text="Aus Excel laden", command=self._load_from_excel)
        self.excel_button.pack(side="left", padx=(10, 0))

        profile_frame = ttk.LabelFrame(self, text="Profile", padding=12)
        profile_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        profile_frame.columnconfigure(1, weight=1)
        profile_frame.columnconfigure(3, weight=1)

        ttk.Label(profile_frame, text="Links").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.left_profile_box = ttk.Combobox(profile_frame, textvariable=self.left_profile_var, state="readonly")
        self.left_profile_box.grid(row=0, column=1, sticky="ew")

        ttk.Label(profile_frame, text="Rechts").grid(row=0, column=2, sticky="w", padx=(18, 10))
        self.right_profile_box = ttk.Combobox(profile_frame, textvariable=self.right_profile_var, state="readonly")
        self.right_profile_box.grid(row=0, column=3, sticky="ew")

        ttk.Button(profile_frame, text="Profile verwalten", command=self._open_profile_editor).grid(
            row=0,
            column=4,
            padx=(14, 0),
        )

        ttk.Label(profile_frame, text="Standard KM in EUR/km").grid(row=1, column=0, sticky="w", pady=(10, 0), padx=(0, 10))
        default_km_entry = ttk.Entry(profile_frame, textvariable=self.default_km_rate_var)
        default_km_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        default_km_entry.bind("<FocusOut>", lambda _event: self._persist_settings())

        ttk.Label(profile_frame, text="Wochenzuschlag in EUR").grid(row=1, column=2, sticky="w", pady=(10, 0), padx=(18, 10))
        week_bonus_entry = ttk.Entry(profile_frame, textvariable=self.week_bonus_amount_var)
        week_bonus_entry.grid(row=1, column=3, sticky="ew", pady=(10, 0))
        week_bonus_entry.bind("<FocusOut>", lambda _event: self._persist_settings())

        ttk.Checkbutton(profile_frame, text="Wochenzuschlag links", variable=self.left_week_bonus_var).grid(
            row=2,
            column=1,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Checkbutton(profile_frame, text="Wochenzuschlag rechts", variable=self.right_week_bonus_var).grid(
            row=2,
            column=3,
            sticky="w",
            pady=(8, 0),
        )

        table_frame = ttk.LabelFrame(self, text="Spielaufträge", padding=12)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=3)
        table_frame.rowconfigure(1, weight=2)

        self.upcoming_frame = ttk.LabelFrame(table_frame, text="Neue Spiele", padding=8)
        self.upcoming_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.upcoming_frame.columnconfigure(0, weight=1)
        self.upcoming_frame.rowconfigure(0, weight=1)

        self.past_frame = ttk.LabelFrame(table_frame, text="Alte Spiele", padding=8)
        self.past_frame.grid(row=1, column=0, sticky="nsew")
        self.past_frame.columnconfigure(0, weight=1)
        self.past_frame.rowconfigure(0, weight=1)

        self.upcoming_tree = self._create_appointments_tree(self.upcoming_frame)
        self.past_tree = self._create_appointments_tree(self.past_frame)

        bottom_frame = ttk.Frame(self, padding=(12, 4, 12, 12))
        bottom_frame.grid(row=3, column=0, sticky="ew")
        bottom_frame.columnconfigure(0, weight=1)

        ttk.Label(bottom_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.generate_button = ttk.Button(bottom_frame, text="PDF für Auswahl erzeugen", command=self._generate_selected_pdf)
        self.generate_button.grid(row=0, column=1, sticky="e")

    def _create_appointments_tree(self, parent) -> ttk.Treeview:
        columns = ("date", "time", "league", "home", "away", "hall", "refs")
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        headings = {
            "date": "Datum",
            "time": "Zeit",
            "league": "Liga",
            "home": "Heim",
            "away": "Gast",
            "hall": "Halle",
            "refs": "SR",
        }
        widths = {"date": 90, "time": 60, "league": 100, "home": 220, "away": 220, "hall": 170, "refs": 180}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], anchor="w")

        tree.grid(row=0, column=0, sticky="nsew")
        tree.bind("<<TreeviewSelect>>", self._on_appointment_selected)

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def _add_path_row(self, frame, row: int, label: str, variable: tk.StringVar, browse_command) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        entry.bind("<FocusOut>", lambda _event: self._persist_settings())
        ttk.Button(frame, text="...", width=4, command=browse_command).grid(row=row, column=4, padx=(12, 0))

    def _browse_pdf(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.template_var.set(path)
            self._persist_settings()

    def _browse_km(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.km_var.set(path)
            self._persist_settings()

    def _browse_excel(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.excel_var.set(path)
            self._persist_settings()

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)
            self._persist_settings()

    def _persist_settings(self) -> None:
        default_km_rate = parse_decimal_value(
            self.default_km_rate_var.get(),
            parse_decimal_value(self.settings.get("default_km_rate", DEFAULT_KM_RATE), DEFAULT_KM_RATE),
        )
        week_bonus_amount = parse_decimal_value(
            self.week_bonus_amount_var.get(),
            parse_decimal_value(self.settings.get("week_bonus_amount", DEFAULT_WEEK_BONUS), DEFAULT_WEEK_BONUS),
        )
        self.settings.update(
            {
                "pdf_template": self.template_var.get().strip(),
                "km_table": self.km_var.get().strip(),
                "last_excel": self.excel_var.get().strip(),
                "output_dir": self.output_var.get().strip(),
                "show_browser": bool(self.show_browser_var.get()),
                "default_km_rate": default_km_rate,
                "week_bonus_amount": week_bonus_amount,
            }
        )
        self.storage.save_settings(self.settings)

    def _save_credentials(self) -> None:
        self.storage.save_credentials(self.username_var.get().strip(), self.password_var.get())
        self.status_var.set("Zugangsdaten im Unterordner gespeichert.")

    def _get_start_locations(self) -> list[str]:
        km_path = self.km_var.get().strip()
        if not km_path:
            return []
        lookup = KmLookup(km_path)
        try:
            lookup.load()
        except Exception:
            return []
        return lookup.available_start_locations()

    def _open_profile_editor(self) -> None:
        start_locations = self._get_start_locations()
        ProfileEditor(
            self,
            self.profiles,
            start_locations,
            parse_decimal_value(self.default_km_rate_var.get(), DEFAULT_KM_RATE),
            self._save_profiles,
        )

    def _save_profiles(self, profiles: dict[str, Profile]) -> None:
        self.profiles = dict(sorted(profiles.items()))
        self.storage.save_profiles(self.profiles)
        self._refresh_profile_boxes()

    def _refresh_profile_boxes(self) -> None:
        names = sorted(self.profiles)
        self.left_profile_box["values"] = [LEFT_PLACEHOLDER, *names]
        self.right_profile_box["values"] = [RIGHT_PLACEHOLDER, *names]

        if self.left_profile_var.get() not in self.left_profile_box["values"]:
            self.left_profile_var.set(LEFT_PLACEHOLDER)
        if self.right_profile_var.get() not in self.right_profile_box["values"]:
            self.right_profile_var.set(RIGHT_PLACEHOLDER)

    def _set_busy(self, busy: bool, status_text: str | None = None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.web_button, self.manual_web_button, self.excel_button, self.generate_button):
            button.configure(state=state)
        if status_text is not None:
            self.status_var.set(status_text)

    def _run_background(self, worker, on_success) -> None:
        def task():
            try:
                result = worker()
            except Exception as exc:
                self._ui_queue.put(("error", exc))
                return
            self._ui_queue.put(("success", on_success, result))

        threading.Thread(target=task, daemon=True).start()

    def _process_ui_queue(self) -> None:
        while True:
            try:
                item = self._ui_queue.get_nowait()
            except Empty:
                break

            kind = item[0]
            if kind == "error":
                self._handle_background_error(item[1])
            elif kind == "success":
                callback = item[1]
                value = item[2]
                callback(value)

        self.after(100, self._process_ui_queue)

    def _handle_background_error(self, exc: Exception) -> None:
        self._set_busy(False, "Aktion fehlgeschlagen.")
        message = str(exc)
        if "Login" in message or "Passwort" in message or "Benutzer" in message:
            message = f"{message}\n\nAlternativ kannst du 'Manuell im Browser anmelden' verwenden."
        messagebox.showerror("Fehler", message)

    def _load_from_website(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        self._persist_settings()
        self._set_busy(True, "Lade Spielaufträge von hw.it4sport.de ...")

        def worker():
            client = PhoenixClient(
                profile_dir=self.settings.get("chrome_profile_dir", ""),
                show_browser=bool(self.show_browser_var.get()),
            )
            return client.fetch_appointments(username, password)

        def on_success(appointments: list[Appointment]) -> None:
            self._set_busy(False)
            self.storage.save_credentials(username, password)
            self._load_appointments_into_table(appointments, "Spielaufträge erfolgreich geladen.")

        self._run_background(worker, on_success)

    def _load_from_website_manual(self) -> None:
        self._persist_settings()
        self._set_busy(
            True,
            "Chrome wird geöffnet. Bitte auf hw.it4sport.de anmelden, danach importiert die App automatisch.",
        )

        def worker():
            client = PhoenixClient(
                profile_dir=self.settings.get("chrome_profile_dir", ""),
                show_browser=True,
                timeout=300,
            )
            return client.fetch_appointments(
                role="Schiedsrichter",
                page_name="Spielaufträge",
                manual_login=True,
            )

        def on_success(appointments: list[Appointment]) -> None:
            self._set_busy(False)
            self._load_appointments_into_table(appointments, "Spielaufträge nach manuellem Login geladen.")

        self._run_background(worker, on_success)

    def _load_from_excel(self) -> None:
        excel_path = self.excel_var.get().strip()
        if not excel_path:
            messagebox.showinfo("Hinweis", "Bitte zuerst eine Excel-Datei auswählen.")
            return

        self._persist_settings()
        self._set_busy(True, "Lade Spielaufträge aus Excel ...")

        def worker():
            return load_appointments_from_excel(excel_path)

        def on_success(appointments: list[Appointment]) -> None:
            self._set_busy(False)
            self._load_appointments_into_table(appointments, "Excel-Spielaufträge geladen.")

        self._run_background(worker, on_success)

    def _load_appointments_into_table(self, appointments: list[Appointment], status_prefix: str) -> None:
        self.appointments = appointments
        upcoming, past = self._split_appointments(appointments)

        self.upcoming_lookup.clear()
        self.past_lookup.clear()
        self.upcoming_tree.delete(*self.upcoming_tree.get_children())
        self.past_tree.delete(*self.past_tree.get_children())

        for index, appointment in enumerate(upcoming):
            item_id = f"new-{index}"
            self.upcoming_lookup[item_id] = appointment
            self.upcoming_tree.insert("", "end", iid=item_id, values=self._appointment_values(appointment))

        for index, appointment in enumerate(past):
            item_id = f"old-{index}"
            self.past_lookup[item_id] = appointment
            self.past_tree.insert("", "end", iid=item_id, values=self._appointment_values(appointment))

        self.upcoming_frame.configure(text=f"Neue Spiele ({len(upcoming)})")
        self.past_frame.configure(text=f"Alte Spiele ({len(past)})")
        self.status_var.set(f"{status_prefix} {len(upcoming)} neue und {len(past)} alte Einträge gefunden.")

    def _appointment_values(self, appointment: Appointment) -> tuple[str, str, str, str, str, str, str]:
        return (
            appointment.date,
            appointment.time,
            appointment.league,
            appointment.home_team,
            appointment.away_team,
            appointment.hall_name,
            " / ".join(appointment.referees),
        )

    def _split_appointments(self, appointments: list[Appointment]) -> tuple[list[Appointment], list[Appointment]]:
        now = datetime.now()
        upcoming: list[Appointment] = []
        past: list[Appointment] = []

        for appointment in appointments:
            match_dt = parse_match_datetime(appointment.date, appointment.time)
            if match_dt is None or match_dt >= now:
                upcoming.append(appointment)
            else:
                past.append(appointment)

        upcoming.sort(key=lambda item: parse_match_datetime(item.date, item.time) or datetime.max)
        past.sort(key=lambda item: parse_match_datetime(item.date, item.time) or datetime.min, reverse=True)
        return upcoming, past

    def _on_appointment_selected(self, event=None) -> None:
        if event is not None:
            if event.widget is self.upcoming_tree:
                self.past_tree.selection_remove(self.past_tree.selection())
            elif event.widget is self.past_tree:
                self.upcoming_tree.selection_remove(self.upcoming_tree.selection())

        appointment = self._get_selected_appointment()
        if appointment is None or not appointment.referees:
            return

        referee_names = [normalize_text(name) for name in appointment.referees]
        matches = [name for name in sorted(self.profiles) if normalize_text(name) in referee_names]

        if matches:
            self.left_profile_var.set(matches[0])
        if len(matches) > 1:
            self.right_profile_var.set(matches[1])

    def _get_selected_appointment(self) -> Appointment | None:
        upcoming_selection = self.upcoming_tree.selection()
        if upcoming_selection:
            return self.upcoming_lookup.get(upcoming_selection[0])

        past_selection = self.past_tree.selection()
        if past_selection:
            return self.past_lookup.get(past_selection[0])

        return None

    def _generate_selected_pdf(self) -> None:
        appointment = self._get_selected_appointment()
        if appointment is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Spielauftrag auswählen.")
            return

        left_name = self.left_profile_var.get()
        right_name = self.right_profile_var.get()
        if left_name == LEFT_PLACEHOLDER:
            messagebox.showinfo("Hinweis", "Bitte mindestens ein linkes Profil auswählen.")
            return

        left_profile = self.profiles.get(left_name)
        right_profile = self.profiles.get(right_name) if right_name != RIGHT_PLACEHOLDER else None
        if left_profile is None:
            messagebox.showerror("Fehler", "Linkes Profil konnte nicht geladen werden.")
            return

        try:
            week_bonus_amount = parse_decimal_value(self.week_bonus_amount_var.get())
        except ValueError:
            messagebox.showerror("Fehler", "Bitte den Wochenzuschlag korrekt eintragen.")
            return

        left_week_bonus = week_bonus_amount if self.left_week_bonus_var.get() else 0.0
        right_week_bonus = week_bonus_amount if right_profile is not None and self.right_week_bonus_var.get() else 0.0

        self._persist_settings()
        self._set_busy(True, "Erzeuge PDF ...")

        def worker():
            km_lookup = KmLookup(self.km_var.get().strip())
            km_lookup.load()
            service = PDFService(self.template_var.get().strip())
            return service.generate(
                appointment=appointment,
                left_profile=left_profile,
                right_profile=right_profile,
                km_lookup=km_lookup,
                output_dir=self.output_var.get().strip(),
                left_week_bonus=left_week_bonus,
                right_week_bonus=right_week_bonus,
            )

        def on_success(output_path: Path) -> None:
            self._set_busy(False, f"PDF erzeugt: {output_path.name}")
            try:
                os.startfile(output_path)
            except OSError:
                pass

        self._run_background(worker, on_success)


if __name__ == "__main__":
    app = AutoPdfApp()
    app.mainloop()
