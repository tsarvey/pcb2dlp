"""Tests for printer profiles."""

from pcb2dlp.printers import get_printer, list_printers, PrinterProfile


class TestPrinterRegistry:
    def test_mars4_9k_registered(self):
        assert "Elegoo Mars 4 9K" in list_printers()

    def test_get_mars4_9k(self):
        profile = get_printer("Elegoo Mars 4 9K")
        assert isinstance(profile, PrinterProfile)

    def test_mars4_9k_specs(self):
        p = get_printer("Elegoo Mars 4 9K")
        assert p.x_pixels == 8520
        assert p.y_pixels == 4320
        assert p.pixel_size_um == 18.0
        assert p.uv_wavelength_nm == 405

    def test_build_area_matches_resolution(self):
        p = get_printer("Elegoo Mars 4 9K")
        expected_x = p.x_pixels * p.pixel_size_um / 1000
        expected_y = p.y_pixels * p.pixel_size_um / 1000
        assert abs(p.build_area_x_mm - expected_x) < 0.1
        assert abs(p.build_area_y_mm - expected_y) < 0.1

    def test_unknown_printer_raises(self):
        try:
            get_printer("Nonexistent Printer")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass
