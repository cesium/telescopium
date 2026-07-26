import datetime
import uuid

SHIFT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "telescopium.shift")


class Shift:
    def __init__(self):
        self.name = ""
        self.location = ""
        self.shift = ""
        self.start: None | datetime.datetime = None
        self.end: None | datetime.datetime = None

    @property
    def id(self):
        return uuid.uuid5(SHIFT_NAMESPACE, self.uuid_name)

    @property
    def uuid_name(self):
        return "|".join(
            [
                self.name,
                self.shift,
                self.format_datetime(self.start) or "",
                self.format_datetime(self.end) or "",
            ]
        )

    @staticmethod
    def format_datetime(value: None | datetime.datetime):
        if value is None:
            return None

        return value.strftime("%Y-%m-%d %H:%M:%S")

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
            "start_time": self.format_datetime(self.start),
            "end_time": self.format_datetime(self.end),
        }
