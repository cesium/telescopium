import math
import re
from datetime import datetime, timedelta
from time import sleep

import bs4
import requests
from bs4 import BeautifulSoup

from shift import Shift

SCHEDULE_URL = "https://alunos.uminho.pt/PT/estudantes/Paginas/InfoUteisHorarios.aspx"
STATE = lambda course, course_id: (
    f'{{"logEntries":[],"value":"{course_id}","text":"{course}","enabled":true,'
    f'"checkedIndices":[],"checkedItemsTextOverflows":false}}'
)
TIME_SLOT_SIZE_PX = 60

class Scraper:
    course_name = None
    year = ""
    form_id = None
    plan_name = None

    shifts: list[Shift] = []
    classes: list[str] = []

    def __init__(self, config: dict):
        weeks = self.get_weeks_between(config["week"]["start"], config["week"]["end"])
        if "classes" in config.keys() and type(config["classes"]) is list:
            self.classes = config["classes"]

        self.course_name = config["course_name"]
        self.year = str(config["year"])

        res = requests.get(SCHEDULE_URL)
        soup = BeautifulSoup(res.text, features="lxml")
        self.form_id = self.get_form_id(soup)

        res = requests.post(SCHEDULE_URL, headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }, data={
            **self.parse_hidden_inputs(soup),
            f"{self.form_id}dataCurso": self.course_name,
            f"{self.get_client_state_input_name(soup)}": STATE(self.course_name, self.get_course_id(soup, self.course_name))
        })

        print(f"Scraping {self.course_name} shifts...")

        if "Mostrar horário expandido" not in res.text:
            plan_soup = BeautifulSoup(res.text, features="lxml")
            plan_info = self._detect_plan_dropdown(plan_soup)

            if plan_info:
                plan_name, plan_id = plan_info
                self.plan_name = plan_name
                client_state_prefix = self.form_id.replace('$', '_')
                print(f"Course has variant plan, selecting: {plan_name}...")

                res = requests.post(SCHEDULE_URL, headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }, data={
                    **self.parse_hidden_inputs(plan_soup),
                    '__EVENTTARGET': f'{self.form_id}dataPlano',
                    '__EVENTARGUMENT': '{"Command":"Select","Index":0}',
                    f'{self.form_id}dataCurso': self.course_name,
                    f'{client_state_prefix}dataCurso_ClientState': '',
                    f'{self.form_id}dataPlano': plan_name,
                    f'{client_state_prefix}dataPlano_ClientState': STATE(plan_name, plan_id),
                })

            if "Mostrar horário expandido" not in res.text:
                print("\nCouldn't get course data. Stopping...")
                exit(-1)

        soup = BeautifulSoup(res.text, features="lxml")

        for i, week in enumerate(weeks):
            state = f'{{"enabled":true,"emptyMessage":"","validationText":"{week}-00-00-00","valueAsString":"{week}-00-00-00","minDateStr":"2025-09-15-00-00-00","maxDateStr":"2026-06-21-00-00-00","lastSetTextBoxValue":"20-10-2025"}}'

            plan_fields = {}
            if self.plan_name:
                plan_fields[f"{self.form_id}dataPlano"] = self.plan_name

            res = requests.post(SCHEDULE_URL, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0"
            }, data={
                **self.parse_hidden_inputs(soup),
                **plan_fields,
                f"{self.form_id}dataCurso": self.course_name,
                f"{self.form_id}dataAnoCurricular": self.year,
                f"{self.form_id}dataWeekSelect": week,
                f"{self.form_id}dataWeekSelect$dateInput": "-".join(reversed(week.split("-"))),
                f"{self.form_id}chkMostraExpandido": "on",
                f"{self.form_id.replace('$', '_')}dataWeekSelect_dateInput_ClientState": state
            })

            self.parse_schedule(res.text)

            if i != len(weeks) - 1:
                sleep(config["timeout"])


    def parse_schedule(self, raw_schedule_data: str):
        soup = BeautifulSoup(raw_schedule_data, features="lxml")
        table = soup.select_one(".rsContent > table:nth-child(1)")

        days = [th.find("a").attrs["href"][1:] for th in table.select(".rsHorizontalHeaderTable th")]
        earliest_hour = self.parse_earliest_hour(table)
        n_time_slots = self.get_number_of_time_slots(table)


        for day_index, day in enumerate(days):
            time = earliest_hour

            for time_slot in range(1, n_time_slots + 1):
                schedule_slots = table.select(
                    f".rsContentTable > tr:nth-child({time_slot}) > td:nth-child({day_index + 1}) > .rsWrap > div")

                for schedule_slot in schedule_slots:
                    if schedule_slot.text.strip():
                        # if class names specified in config, only keep classes specified
                        if len(self.classes) == 0 or any(class_name in schedule_slot.text for class_name in self.classes):
                            self.shifts.append(self.parse_shift(schedule_slot, time, day))

                time += timedelta(minutes=30)

    def _detect_plan_dropdown(self, soup: BeautifulSoup) -> tuple[str, str] | None:
        #Check if a dataPlano dropdown exists and return (first_plan_name, first_plan_value).
        text = soup.decode()

        if 'dataPlano' not in text:
            return None

        # Find the plan RadComboBox by its ID containing 'dataPlano'
        plan_combo = soup.find('div', class_='RadComboBox', id=lambda i: i and 'dataPlano' in i)
        if not plan_combo:
            return None

        # Get plan option names from list items within this combo
        items = plan_combo.select('li.rcbItem')
        if not items:
            return None

        first_name = items[0].get_text(strip=True)

        # Find all itemData blocks on the page; the second one is for the plan dropdown
        matches = list(re.finditer(r'"itemData"\s*:\s*\[(.*?)]', text, flags=re.S))
        if len(matches) >= 2:
            plan_data = matches[1].group(1)
            values = re.findall(r'"value"\s*:\s*"([^"]+)"', plan_data)
            if values:
                return (first_name, values[0])

        return None

    @staticmethod
    def parse_hidden_inputs(soup: BeautifulSoup):
        return {
            _input.get("name"): _input.get("value")
            for _input in soup.select("input[type='hidden']")
        }

    @staticmethod
    def get_course_id(soup: BeautifulSoup, course_name: str) -> str | None:
        names = [li.get_text(strip=True) for li in soup.select("li.rcbItem")]

        text = soup.decode()
        match = re.search(r'"itemData"\s*:\s*\[(.*?)]', text, flags=re.S)
        if not match:
            return None

        ids = re.findall(r'["\']?value["\']?\s*:\s*["\'](\d+)["\']', match.group(1))
        if len(ids) != len(names):
            return None

        course_map = dict(zip(names, ids))
        return course_map.get(course_name)

    @staticmethod
    def get_client_state_input_name(soup: BeautifulSoup):
        return soup.select_one(".RadComboBox > input").get("name")

    @staticmethod
    def get_form_id(soup: BeautifulSoup):
        return soup.select_one(".rcbInput").get("name")[:-9]

    @staticmethod
    def parse_earliest_hour(table: BeautifulSoup) -> datetime:
        return datetime.strptime(table.select_one(
            ".rsVerticalHeaderTable > tr:nth-child(1) > th:nth-child(1) > div:nth-child(1)").text.strip(), "%H:%M")

    @staticmethod
    def get_number_of_time_slots(table: BeautifulSoup) -> int:
        return len(table.select_one(".rsContentTable").select("table > tr"))

    @staticmethod
    def parse_shift(slot: bs4.Tag, start: datetime, date: str) -> Shift:
        new_shift = Shift()

        new_shift_date = datetime.strptime(date, "%Y-%m-%d").date()
        new_shift.start = start.replace(year=new_shift_date.year, month=new_shift_date.month,
                                         day=new_shift_date.day)

        match = re.search(r'height:\s*([\d.]+)(px|%)?', slot.get("style"))
        if match:
            height_value = int(match.group(1))
            time = math.ceil(height_value / TIME_SLOT_SIZE_PX)
        else:
            time = 1

        new_shift.end = new_shift.start + timedelta(minutes=time * 30)

        metadata = slot.select_one(".rsAptOut > .rsAptMid > .rsAptIn > .rsAptContent")
        new_shift.name = metadata.contents[0].get_text(strip=True)
        new_shift.location = metadata.find('span').get_text(strip=True).strip('[]')
        new_shift.shift = metadata.contents[3].get_text(strip=True)

        return new_shift

    @staticmethod
    def get_weeks_between(start_date: str, end_date: str):
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        days_since_monday = start.weekday()
        first_monday = start - timedelta(days=days_since_monday)

        mondays = []
        current = first_monday
        while current <= end:
            mondays.append(current.strftime("%Y-%m-%d"))
            current += timedelta(weeks=1)

        return mondays