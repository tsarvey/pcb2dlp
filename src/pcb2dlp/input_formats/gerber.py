"""Gerber (RS-274X) input format via gerbonara."""

from pathlib import Path

from gerbonara import GerberFile

from . import InputFormat


class GerberInput(InputFormat):
    name = "gerber"
    file_extensions = [".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".grb"]

    def __init__(self):
        self._file: GerberFile | None = None

    def load(self, path: Path) -> None:
        self._file = GerberFile.open(str(path))

    def to_svg(self) -> str:
        if self._file is None:
            raise RuntimeError("No file loaded")
        return str(self._file.to_svg(fg="white", bg="black"))

    def bounding_box_mm(self) -> tuple[float, float, float, float]:
        if self._file is None:
            raise RuntimeError("No file loaded")
        (min_x, min_y), (max_x, max_y) = self._file.bounding_box(unit="mm")
        return (float(min_x), float(min_y), float(max_x), float(max_y))
