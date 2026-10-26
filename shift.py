import datetime
import uuid

SHIFT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "telescopium.shift")

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class Shift:
    def __init__(self):
        self.name = ""
        self.location = ""
        self.shift: str | None = ""
        self.start: None | datetime.datetime = None
        self.end: None | datetime.datetime = None

    @property
    def id(self):
        return uuid.uuid5(SHIFT_NAMESPACE, self.uuid_name)

    @property
    def weekday(self):
        if self.start is None:
            return None

        return WEEKDAYS[self.start.weekday()]

    # The date is left out on purpose, so the same weekly shift keeps
    # the same id across every week of the schedule
    @property
    def uuid_name(self):
        return "|".join(
            [
                self.name,
                self.shift or "",
                self.weekday or "",
                self.format_time(self.start) or "",
                self.format_time(self.end) or "",
            ]
        )

    @staticmethod
    def format_time(value: None | datetime.datetime):
        if value is None:
            return None

        return value.strftime("%H:%M:%S")

    def __str__(self):
        return (
            f"{self.name}\n"
            f"\tShift: {self.shift}\n"
            f"\tStart: {self.start}\n"
            f"\tEnd: {self.end}\n"
            f"\tLocation: {self.location}\n"
        )

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "location": self.location,
            "shift": self.shift,
            "weekday": self.weekday,
            "start_time": self.format_time(self.start),
            "end_time": self.format_time(self.end),
        }
