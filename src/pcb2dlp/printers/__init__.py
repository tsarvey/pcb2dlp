"""Printer profile definitions and registry.

Profiles are loaded from TOML files in the ``profiles/`` subdirectory at
import time. To add a new printer, drop a ``<name>.toml`` file in that
directory — no Python edits required.
"""

from dataclasses import dataclass
from pathlib import Path
import tomllib

REGISTRY: dict[str, "PrinterProfile"] = {}

_PROFILES_DIR = Path(__file__).parent / "profiles"


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
    # Exposure defaults are empirical for PCB photoresist and must be tuned
    # per printer/resist/board. ``None`` means "no verified default — user
    # must supply a value." Only profiles whose values have been physically
    # tested should set these.
    default_exposure_s: float | None = None
    default_bottom_exposure_s: float | None = None
    default_pwm: int | None = None

    def __post_init__(self):
        REGISTRY[self.name] = self


def get_printer(name: str) -> PrinterProfile:
    return REGISTRY[name]


def list_printers() -> list[str]:
    return sorted(REGISTRY.keys())


def _load_profiles() -> None:
    for path in sorted(_PROFILES_DIR.glob("*.toml")):
        with path.open("rb") as f:
            data = tomllib.load(f)
        PrinterProfile(**data)


_load_profiles()
