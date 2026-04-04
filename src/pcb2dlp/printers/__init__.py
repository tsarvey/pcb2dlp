"""Printer profile definitions and registry."""

from dataclasses import dataclass

REGISTRY: dict[str, "PrinterProfile"] = {}


@dataclass(frozen=True)
class PrinterProfile:
    name: str
    x_pixels: int
    y_pixels: int
    pixel_size_um: float
    build_area_x_mm: float
    build_area_y_mm: float
    build_area_z_mm: float
    uv_wavelength_nm: int
    default_exposure_s: float
    default_bottom_exposure_s: float
    default_pwm: int

    def __post_init__(self):
        REGISTRY[self.name] = self


def get_printer(name: str) -> PrinterProfile:
    return REGISTRY[name]


def list_printers() -> list[str]:
    return list(REGISTRY.keys())


# Import printer modules to trigger registration
from . import mars4_9k  # noqa: E402, F401
