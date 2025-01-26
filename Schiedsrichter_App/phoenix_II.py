import tkinter as tk
from tkinter import messagebox
import configparser
import os
from selenium.webdriver import Edge, EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.remote.webelement import WebElement
from dataclasses import dataclass, InitVar
from datetime import datetime
from typing import List
import re


class Credentials:
    def __init__(self):
        project_dir = os.path.dirname(__file__)
        self.file_path = f"{project_dir}/credentials.ini"

        self.username, self.password = self.read_from_ini()
        if not self.username or not self.password:
            self.initialize_gui()

    def save_to_ini(self, username, password):
        config = configparser.ConfigParser()
        config['Account'] = {'Username': username, 'Password': password}
        with open(self.file_path, 'w') as ini_file:
            config.write(ini_file)
        messagebox.showinfo("Success", "Credentials saved successfully!")

    def read_from_ini(self) -> (str, str):
        if not os.path.isfile(self.file_path):
            return None, None
        config = configparser.ConfigParser()
        config.read(self.file_path)
        username = config.get('Account', 'Username')
        password = config.get('Account', 'Password')
        return username, password

    # TODO: create a better ui!!!
    def initialize_gui(self):
        root = tk.Tk()
        root.title("Login Form")
        root.geometry("300x150")

        # Username and Password Labels and Entries
        tk.Label(root, text="Username:").pack()
        username_entry = tk.Entry(root)
        username_entry.pack()

        tk.Label(root, text="Password:").pack()
        password_entry = tk.Entry(root, show="*")
        password_entry.pack()

        # Save Button
        def save():
            self.username = username_entry.get()
            self.password = password_entry.get()
            if self.username and self.password:
                self.save_to_ini(self.username, self.password)
                root.destroy()  # Close the window after saving
            else:
                messagebox.showwarning("Warning", "Username and Password are required.")

        tk.Button(root, text="Save", command=save).pack()

        root.mainloop()


@dataclass
class Match:
    id: int
    home: str
    guest: str
    league: str

    def __post_init__(self):
        self.id = int(self.id)

@dataclass
class Address:
    street: str
    street_nr: InitVar[int | None]
    city: str
    zip_code: int

    def __init__(self, *args):
        for arg in args:
            if isinstance(arg, str):
                arg += "\n\n"
                address_str, city_str, _ = arg.split("\n", 2)
                number_list = re.findall(r"\d+", address_str)
                if number_list:
                    self.street_nr = int(number_list[0])
                    self.street = address_str.rsplit(" ", 1)[0]
                else:
                    self.street_nr = None
                    self.street = address_str

                self.zip_code, self.city = city_str.split(" ", 1)
                self.zip_code = int(self.zip_code)

@dataclass
class Place:
    id: int
    name: str
    address: Address

    def __post_init__(self):
        self.id = int(self.id)

@dataclass
class MatchAppointment:
    date: datetime
    match: Match
    place: Place
    refery: List[str]

    def __init__(self, **kwargs):
        self.date = datetime.strptime(
            f"{kwargs.get('Datum', '01.01.2000')} {kwargs.get('Zeit', '00:00')}",
            "%d.%m.%Y %H:%M",
        )

        self.match = Match(
            id=kwargs.get("Sp.Nr", 0),
            home=kwargs.get("Heimmannschaft", "Home"),
            guest=kwargs.get("Gastmannschaft", "Guest"),
            league=kwargs.get("Staffel", "League"),
        )

        self.place = Place(
            id=kwargs.get("H.Nr", 0),
            name=kwargs.get("Hallename", "Name"),
            address=Address(kwargs.get("Halle Kontakt")),
        )

        self.refery = list(kwargs.get("Namen", "").split(" / "))


class Session:
    def __init__(self, username: str, password: str, debug = False):
        self.debug = debug
        if self.debug:
            print("__init__")

        self.username = username
        self.password = password
        self.url = "https://hw.it4sport.de/"

        self.roles = []
        self.role = None

    def __enter__(self):
        if self.debug:
            print("__enter__")

        project_dir = os.path.dirname(__file__)

        options = EdgeOptions()
        options.use_chromium = True
        options.add_argument("headless")
        options.add_argument("disable-gpu")
        options.add_argument(f"user-data-dir={project_dir}/selenium")
        self.driver = Edge(options=options)
        self.__login__(self.username, self.password)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.debug:
            print("__exit__")
        self.driver.close()

    def __del__(self):
        if self.debug:
            print("__del__")
        try:
            self.driver.close()
        except Exception:
            print("Driver was still closed!")

    def __login__(self, username: str, password: str):
        if self.debug:
            print("command: login")

        self.driver.get(f"{self.url}")

        # if not logged in
        if self.driver.current_url != self.url:
            loginform_email = self.driver.find_element(By.ID, "std-field-0")
            loginform_email.send_keys(username)

            loginform_password = self.driver.find_element(By.ID, "std-field-1")
            loginform_password.send_keys(password)

            button = self.driver.find_element(By.ID, "doLogin")
            button.click()
        else:
            print("Already logged in!")

    @staticmethod
    def __get_children__(element: WebElement, first: bool = False) -> (WebElement, List[WebElement], None):
        children = element.find_elements(By.XPATH, "./child::*")
        if children:
            if first:
                return children[0]
            else:
                return children
        else:
            return None

    def __role__(self) -> Select:
        return Select(self.driver.find_element(By.NAME, "FORMDATA[PHOENIXBASE.BASE.PAGES.PHOENIXSTARTPAGE.TOPAREA.USERROLES]"))

    def get_allowed_user_roles(self) -> List[str]:
        self.roles = []
        for option in self.__role__().options:
            self.roles.append(option.text)
        return self.roles

    def set_user_role(self, role: str):
        if role in self.get_allowed_user_roles():
            self.__role__().select_by_visible_text(role)
            self.role = role
        else:
            raise ValueError(f"Role '{role}' is not allowed!")

    def __sub_pages__(self) -> List[WebElement]:
        nav_bar = self.driver.find_element(By.ID, "bs-example-navbar-collapse-1")
        nav_bar_sub = self.__get_children__(nav_bar, first=True)
        return self.__get_children__(nav_bar_sub)

    def get_sub_pages(self) -> List[str]:
        sub_pages = []
        nav_bar_elements = self.__sub_pages__()
        for element in nav_bar_elements:
            if isinstance(element, WebElement):
                sub_pages.append(element.text)
        return sub_pages

    def select_sub_page(self, page_name: str):
        success = False
        nav_bar_elements = self.__sub_pages__()
        for element in nav_bar_elements:
            if isinstance(element, WebElement) and page_name == element.text:
                element.click()
                success = True
                break
        if not success:
            raise ValueError(f"SubPage '{role}' is not allowed!")

    def __extract_table__(self, table_element: WebElement) -> List[dict]:
        table = []
        tbody = self.__get_children__(table_element, first=True)
        tr_list = self.__get_children__(tbody)
        key_list = []
        for idx, tr in enumerate(tr_list):
            value_list = []
            child_list = self.__get_children__(tr)
            for child in child_list:
                if isinstance(child, WebElement):
                    value_list.append(child.text)
            if idx == 0:
                key_list = value_list
            else:
                table.append(dict(zip(key_list, value_list)))
        return table

    def get_appointments(self) -> List[MatchAppointment]:
        appointment_list = []
        table_list = self.driver.find_elements(By.CLASS_NAME, "table-responsive")
        for table in table_list:
            table_element = None
            if isinstance(table, WebElement):
                table_element = self.__get_children__(table, first=True)
            if isinstance(table_element, WebElement) and table_element.tag_name == "table":
                parsed_table_list = self.__extract_table__(table_element)
                for parsed_table in parsed_table_list:
                    appointment_list.append(MatchAppointment(**parsed_table))
        return appointment_list


if __name__ == "__main__":
    credentials = Credentials()
    with Session(credentials.username, credentials.password) as session:
        role = "Schiedsrichter" # TODO --> Enum
        if session.role != role:
            session.set_user_role(role)
        sub_page = "Spielaufträge"
        if sub_page in session.get_sub_pages():
            session.select_sub_page(sub_page)

        appointment_list = session.get_appointments()
        print(len(appointment_list), appointment_list)

