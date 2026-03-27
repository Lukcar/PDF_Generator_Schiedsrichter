from __future__ import annotations

from pathlib import Path
import re
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from models import Appointment


class LoginError(RuntimeError):
    pass


class PhoenixClient:
    BASE_URL = "https://hw.it4sport.de/"
    ROLE_SELECT_NAMES = (
        "FORMDATA[PHOENIXBASE.BASE.PAGES.PHOENIXSTARTPAGE.MAINNAVIGATION.USERROLES]",
        "FORMDATA[PHOENIXBASE.BASE.PAGES.PHOENIXSTARTPAGE.TOPAREA.USERROLES]",
    )

    def __init__(self, profile_dir: str, show_browser: bool = False, timeout: int = 30):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.show_browser = show_browser
        self.timeout = timeout

    def fetch_appointments(
        self,
        username: str = "",
        password: str = "",
        role: str = "Schiedsrichter",
        page_name: str = "Spielaufträge",
        manual_login: bool = False,
    ) -> list[Appointment]:
        driver = self._build_driver()
        try:
            wait = WebDriverWait(driver, self.timeout)
            driver.get(self.BASE_URL)
            self._login_if_needed(driver, wait, username, password, manual_login=manual_login)
            self._select_role(driver, wait, role)
            self._open_sub_page(driver, wait, page_name)
            return self._extract_appointments(driver)
        finally:
            driver.quit()

    def _build_driver(self) -> Chrome:
        options = Options()
        if not self.show_browser:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,1200")
        options.add_argument("--log-level=3")
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        driver = Chrome(options=options)
        driver.set_page_load_timeout(60)
        return driver

    def _login_if_needed(
        self,
        driver: Chrome,
        wait: WebDriverWait,
        username: str,
        password: str,
        manual_login: bool = False,
    ) -> None:
        if "auth/login" not in driver.current_url and not driver.find_elements(By.ID, "login-form"):
            return

        if manual_login:
            self._wait_for_manual_login(driver, wait)
            return

        if not username or not password:
            raise LoginError("Bitte Benutzername und Passwort eingeben.")

        username_input = wait.until(EC.visibility_of_element_located((By.NAME, "username")))
        password_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))

        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        def login_finished(current_driver: Chrome) -> bool:
            if "auth/login" not in current_driver.current_url:
                return True
            return bool(current_driver.find_elements(By.CSS_SELECTOR, ".alert-danger"))

        wait.until(login_finished)
        if "auth/login" in driver.current_url:
            message = "Login fehlgeschlagen. Bitte Zugangsdaten prüfen."
            errors = driver.find_elements(By.CSS_SELECTOR, ".alert-danger")
            if errors:
                error_text = errors[0].text.strip()
                if error_text:
                    message = error_text
            raise LoginError(message)

    def _wait_for_manual_login(self, driver: Chrome, wait: WebDriverWait) -> None:
        def login_finished(current_driver: Chrome) -> bool:
            if "auth/login" not in current_driver.current_url:
                return True
            return bool(
                current_driver.find_elements(
                    By.NAME,
                    "FORMDATA[PHOENIXBASE.BASE.PAGES.PHOENIXSTARTPAGE.TOPAREA.USERROLES]",
                )
            )

        try:
            wait.until(login_finished)
        except TimeoutException as exc:
            raise LoginError(
                "Manueller Login wurde nicht abgeschlossen. Bitte Browser sichtbar öffnen und anmelden."
            ) from exc

    def _select_role(self, driver: Chrome, wait: WebDriverWait, role: str) -> None:
        role_select = self._find_role_select(driver, wait)
        if role_select is None:
            return

        options = [item.text.strip() for item in role_select.options]
        if role not in options:
            return

        if role_select.first_selected_option.text.strip() != role:
            role_select.select_by_visible_text(role)
            self._wait_for_role_navigation(driver, role)

    def _open_sub_page(self, driver: Chrome, wait: WebDriverWait, page_name: str) -> None:
        if driver.find_elements(By.CLASS_NAME, "table-responsive"):
            return

        page_url = self._extract_sub_page_url(driver, page_name)
        if not page_url:
            raise RuntimeError(f"Unterseite '{page_name}' wurde nicht gefunden.")

        driver.get(page_url)
        self._wait_for_appointments_page(driver, wait)

    def _extract_appointments(self, driver: Chrome) -> list[Appointment]:
        appointments: list[Appointment] = []
        tables = driver.find_elements(By.CSS_SELECTOR, ".table-responsive table")
        if not tables:
            tables = driver.find_elements(By.CSS_SELECTOR, "table")

        for table in tables:
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
            if len(rows) < 2:
                continue

            headers = self._extract_row_text(rows[0], "th,td")
            if not headers or "Datum" not in headers:
                continue

            for row in rows[1:]:
                values = self._extract_row_text(row, "td")
                if not values:
                    continue
                row_data = dict(zip(headers, values))
                appointment = Appointment.from_row(row_data)
                if appointment.home_team or appointment.away_team:
                    appointments.append(appointment)

        return appointments

    @staticmethod
    def _extract_row_text(row, selector: str) -> list[str]:
        return [cell.text.strip() for cell in row.find_elements(By.CSS_SELECTOR, selector)]

    def _find_role_select(self, driver: Chrome, wait: WebDriverWait) -> Select | None:
        for select_name in self.ROLE_SELECT_NAMES:
            try:
                wait.until(EC.presence_of_element_located((By.NAME, select_name)))
                return Select(driver.find_element(By.NAME, select_name))
            except TimeoutException:
                continue
        return None

    def _wait_for_role_navigation(self, driver: Chrome, role: str) -> None:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            role_select = self._find_role_select(driver, WebDriverWait(driver, 2))
            if role_select is not None and role_select.first_selected_option.text.strip() == role:
                page_texts = [item.text.strip() for item in driver.find_elements(By.CSS_SELECTOR, "#main-nav a.nav-link")]
                if role == "Schiedsrichter" and "Spielaufträge" in page_texts:
                    return
                if role in driver.page_source:
                    return
            time.sleep(1)
        raise TimeoutException(f"Rollenwechsel auf '{role}' wurde nicht abgeschlossen.")

    def _extract_sub_page_url(self, driver: Chrome, page_name: str) -> str:
        for element in driver.find_elements(By.CSS_SELECTOR, "#main-nav a.nav-link"):
            if element.text.strip() != page_name:
                continue

            onclick = element.get_attribute("onclick") or ""
            match = re.search(r"location\.href = '([^']+)'", onclick)
            if match:
                return self._absolute_url(match.group(1))

            href = element.get_attribute("href") or ""
            if href:
                return self._absolute_url(href)

        if page_name == "Spielaufträge":
            html = driver.page_source
            patterns = (
                r"(index\.php\?phoenix=handball4all\.sre\.pages\.SRSpielauftraegePage[^'\" ]+)",
                r"(index\.php\?phoenix=handball4all\.sre\.pages\.SRSpielauftraegePage[^<]+)",
            )
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    return self._absolute_url(match.group(1).replace("&amp;", "&"))

        old_nav_items = driver.find_elements(
            By.XPATH,
            "//*[@id='bs-example-navbar-collapse-1']//*[self::a or self::button or self::li]",
        )
        for element in old_nav_items:
            if element.text.strip() == page_name:
                href = element.get_attribute("href") or ""
                if href:
                    return self._absolute_url(href)

        return ""

    def _wait_for_appointments_page(self, driver: Chrome, wait: WebDriverWait) -> None:
        def has_table(current_driver: Chrome) -> bool:
            return len(current_driver.find_elements(By.CSS_SELECTOR, "table tr")) > 1

        wait.until(has_table)

    def _absolute_url(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"{self.BASE_URL}{url.lstrip('/')}"
