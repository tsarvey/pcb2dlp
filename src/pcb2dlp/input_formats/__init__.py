"""Input format definitions and registry."""

from abc import ABC, abstractmethod
from pathlib import Path

REGISTRY: dict[str, type["InputFormat"]] = {}


class InputFormat(ABC):
    name: str
    file_extensions: list[str]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name"):
            REGISTRY[cls.name] = cls

    @abstractmethod
    def load(self, path: Path) -> None:
        ...

    @abstractmethod
    def to_svg(self) -> str:
        ...

    @abstractmethod
    def bounding_box_mm(self) -> tuple[float, float, float, float]:
        """Return (min_x, min_y, max_x, max_y) in mm."""
        ...

    def board_size_mm(self) -> tuple[float, float]:
        """Return (width, height) in mm."""
        x0, y0, x1, y1 = self.bounding_box_mm()
        return (x1 - x0, y1 - y0)


def get_format_for_file(path: Path) -> "InputFormat":
    suffix = path.suffix.lower()
    for cls in REGISTRY.values():
        if suffix in cls.file_extensions:
            return cls()
    raise ValueError(f"No input format supports {suffix} files")


# Import format modules to trigger registration
from . import gerber  # noqa: E402, F401
