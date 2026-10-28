from pathlib import Path

from shift import Shift


class BaseExportModule:
    def __init__(self):
        Path("./export").mkdir(parents=True, exist_ok=True)

    def export(self, shifts: list[Shift]):
        pass
