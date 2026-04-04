"""Elegoo Mars 4 9K printer profile."""

from . import PrinterProfile

MARS4_9K = PrinterProfile(
    name="Elegoo Mars 4 9K",
    x_pixels=8520,
    y_pixels=4320,
    pixel_size_um=18.0,
    build_area_x_mm=153.36,
    build_area_y_mm=77.76,
    build_area_z_mm=175.0,
    uv_wavelength_nm=405,
    default_exposure_s=60.0,
    default_bottom_exposure_s=60.0,
    default_pwm=255,
)
