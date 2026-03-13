import datetime
import uuid


class Shift:
    def __init__(self):
        self.id = uuid.uuid4()
        self.name = ""
        self.location = ""
        self.shift = ""
        self.start: None | datetime.datetime = None
        self.end: None | datetime.datetime = None

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
            "start": self.start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": self.end.strftime("%Y-%m-%d %H:%M:%S"),
        }
