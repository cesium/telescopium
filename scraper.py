import math
import re
from datetime import date, datetime, timedelta
from time import sleep
import json

import bs4
import requests
from bs4 import BeautifulSoup
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from shift import Shift

SCHEDULE_URL = "https://alunos.uminho.pt/PT/estudantes/Paginas/InfoUteisHorarios.aspx"
# The upstream server currently omits its intermediate certificate. Re-enable TLS
# verification as soon as its certificate chain is fixed.
VERIFY_TLS = False

if not VERIFY_TLS:
    disable_warnings(InsecureRequestWarning)

STATE = lambda course, course_id: (
    f'{{"logEntries":[],"value":"{course_id}","text":"{course}","enabled":true,'
    f'"checkedIndices":[],"checkedItemsTextOverflows":false}}'
)
TIME_SLOT_SIZE_PX = 60


class Scraper:
    def __init__(self, config: dict):
        self.course_name = None
        self.years = None
        self.form_id = None
        self.plan_name = None
        self.shifts: list[Shift] = []
        self.classes: list[str] = []

        weeks = self.get_weeks_between(config["week"]["start"], config["week"]["end"])
        if "classes" in config.keys() and type(config["classes"]) is list:
            self.classes = config["classes"]

        self.course_name = config["course_name"]
        year_config = config["year"]
        self.years = [str(year) for year in year_config]

        res = requests.get(SCHEDULE_URL, verify=VERIFY_TLS)
        soup = BeautifulSoup(res.text, features="lxml")
        self.form_id = self.get_form_id(soup)

        res = requests.post(
            SCHEDULE_URL,
            verify=VERIFY_TLS,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                **self.parse_hidden_inputs(soup),
                f"{self.form_id}dataCurso": self.course_name,
                f"{self.get_client_state_input_name(soup)}": STATE(
                    self.course_name, self.get_course_id(soup, self.course_name)
                ),
            },
        )

        print(f"Scraping {self.course_name} shifts...")

        if "Mostrar horário expandido" not in res.text:
            plan_soup = BeautifulSoup(res.text, features="lxml")
            plan_info = self._detect_plan_dropdown(plan_soup)

            if plan_info:
                plan_name, plan_id = plan_info
                self.plan_name = plan_name
                client_state_prefix = self.form_id.replace("$", "_")
                print(f"Course has variant plan, selecting: {plan_name}...")

                res = requests.post(
                    SCHEDULE_URL,
                    verify=VERIFY_TLS,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        **self.parse_hidden_inputs(plan_soup),
                        "__EVENTTARGET": f"{self.form_id}dataPlano",
                        "__EVENTARGUMENT": '{"Command":"Select","Index":0}',
                        f"{self.form_id}dataCurso": self.course_name,
                        f"{client_state_prefix}dataCurso_ClientState": "",
                        f"{self.form_id}dataPlano": plan_name,
                        f"{client_state_prefix}dataPlano_ClientState": STATE(
                            plan_name, plan_id
                        ),
                    },
                )

            if "Mostrar horário expandido" not in res.text:
                print("\nCouldn't get course data. Stopping...")
                exit(-1)

        soup = BeautifulSoup(res.text, features="lxml")
        week_select_range = self.get_week_select_range(soup)

        for year in self.years:
            for i, week in enumerate(weeks):
                state = self.get_week_select_date_input_state(week, week_select_range)

                plan_fields = {}
                if self.plan_name:
                    plan_fields[f"{self.form_id}dataPlano"] = self.plan_name

                res = requests.post(
                    SCHEDULE_URL,
                    verify=VERIFY_TLS,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0",
                    },
                    data={
                        **self.parse_hidden_inputs(soup),
                        **plan_fields,
                        f"{self.form_id}dataCurso": self.course_name,
                        f"{self.form_id}dataAnoCurricular": year,
                        f"{self.form_id}dataWeekSelect": week,
                        f"{self.form_id}dataWeekSelect$dateInput": "-".join(
                            reversed(week.split("-"))
                        ),
                        f"{self.form_id}chkMostraExpandido": "on",
                        f"{self.form_id.replace('$', '_')}dataWeekSelect_dateInput_ClientState": state,
                    },
                )

                self.parse_schedule(res.text)

                if i != len(weeks) - 1 or year != self.years[-1]:
                    sleep(config["timeout"])

    def parse_schedule(self, raw_schedule_data: str):
        soup = BeautifulSoup(raw_schedule_data, features="lxml")
        table = soup.select_one(".rsContent > table:nth-child(1)")
        if table is None:
            raise ValueError(
                "Schedule table was not found in the UMinho response. "
                "The selected week/year may have no published schedule, or the requested week is outside the available academic calendar."
            )

        days = [
            th.find("a").attrs["href"][1:]
            for th in table.select(".rsHorizontalHeaderTable th")
        ]
        earliest_hour = self.parse_earliest_hour(table)
        n_time_slots = self.get_number_of_time_slots(table)

        for day_index, day in enumerate(days):
            time = earliest_hour

            for time_slot in range(1, n_time_slots + 1):
                schedule_slots = table.select(
                    f".rsContentTable > tr:nth-child({time_slot}) > td:nth-child({day_index + 1}) > .rsWrap > div"
                )

                for schedule_slot in schedule_slots:
                    if schedule_slot.text.strip():
                        # if class names specified in config, only keep classes specified
                        if len(self.classes) == 0 or any(
                            class_name in schedule_slot.text
                            for class_name in self.classes
                        ):
                            self.shifts.append(
                                self.parse_shift(schedule_slot, time, day)
                            )

                time += timedelta(minutes=30)

    def _detect_plan_dropdown(self, soup: BeautifulSoup) -> tuple[str, str] | None:
        # Check if a dataPlano dropdown exists and return (first_plan_name, first_plan_value).
        text = soup.decode()

        if "dataPlano" not in text:
            return None

        # Find the plan RadComboBox by its ID containing 'dataPlano'
        plan_combo = soup.find(
            "div", class_="RadComboBox", id=lambda i: i and "dataPlano" in i
        )
        if not plan_combo:
            return None

        # Get plan option names from list items within this combo
        items = plan_combo.select("li.rcbItem")
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
    def get_week_select_range(soup: BeautifulSoup) -> tuple[date, date]:
        field = soup.select_one("input[name*='dataWeekSelect_calendar_AD']")
        if field is None:
            raise ValueError(
                "Could not find the schedule date range in the UMinho response."
            )

        available_dates = json.loads(field.get("value"))
        if len(available_dates) < 2:
            raise ValueError("UMinho returned an invalid schedule date range.")

        min_year, min_month, min_day = available_dates[0]
        max_year, max_month, max_day = available_dates[1]
        return (
            datetime(min_year, min_month, min_day).date(),
            datetime(max_year, max_month, max_day).date(),
        )

    @staticmethod
    def get_week_select_date_input_state(
        week: str, week_select_range: tuple[date, date]
    ) -> str:
        selected_date = datetime.strptime(week, "%Y-%m-%d").date()
        min_date, max_date = week_select_range

        if selected_date < min_date or selected_date > max_date:
            raise ValueError(
                f"Requested week {week} is outside the available schedule range "
                f"{min_date.isoformat()} to {max_date.isoformat()}."
            )

        return json.dumps(
            {
                "enabled": True,
                "emptyMessage": "",
                "validationText": f"{week}-00-00-00",
                "valueAsString": f"{week}-00-00-00",
                "minDateStr": f"{min_date.isoformat()}-00-00-00",
                "maxDateStr": f"{max_date.isoformat()}-00-00-00",
                "lastSetTextBoxValue": selected_date.strftime("%d-%m-%Y"),
            },
            separators=(",", ":"),
        )

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
        return datetime.strptime(
            table.select_one(
                ".rsVerticalHeaderTable > tr:nth-child(1) > th:nth-child(1) > div:nth-child(1)"
            ).text.strip(),
            "%H:%M",
        )

    @staticmethod
    def get_number_of_time_slots(table: BeautifulSoup) -> int:
        return len(table.select_one(".rsContentTable").select("table > tr"))

    @staticmethod
    def parse_shift(slot: bs4.Tag, start: datetime, date: str) -> Shift:
        new_shift = Shift()

        new_shift_date = datetime.strptime(date, "%Y-%m-%d").date()
        new_shift.start = start.replace(
            year=new_shift_date.year, month=new_shift_date.month, day=new_shift_date.day
        )

        match = re.search(r"height:\s*([\d.]+)(px|%)?", slot.get("style"))
        if match:
            height_value = int(match.group(1))
            time = math.ceil(height_value / TIME_SLOT_SIZE_PX)
        else:
            time = 1

        new_shift.end = new_shift.start + timedelta(minutes=time * 30)

        metadata = slot.select_one(".rsAptOut > .rsAptMid > .rsAptIn > .rsAptContent")
        new_shift.name = metadata.contents[0].get_text(strip=True)
        new_shift.location = metadata.find("span").get_text(strip=True).strip("[]")

        shift = metadata.contents[3].get_text(strip=True)
        new_shift.shift = shift if re.fullmatch(r"(?:T|TP|PL)\d+", shift) else None

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
