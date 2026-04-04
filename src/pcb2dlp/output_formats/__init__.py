"""Output format definitions and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..printers import PrinterProfile

REGISTRY: dict[str, type["OutputFormat"]] = {}


@dataclass
class ExposureParams:
    exposure_time_s: float = 60.0
    bottom_exposure_time_s: float = 60.0
    light_pwm: int = 255
    layer_thickness_mm: float = 0.05


class OutputFormat(ABC):
    name: str
    file_extension: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name"):
            REGISTRY[cls.name] = cls

    @abstractmethod
    def write(
        self,
        path: Path,
        bitmap: np.ndarray,
        profile: PrinterProfile,
        params: ExposureParams,
    ) -> None:
        ...


def get_format(name: str) -> "OutputFormat":
    return REGISTRY[name]()


# Import format modules to trigger registration
from . import goo  # noqa: E402, F401
