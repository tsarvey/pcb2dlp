"""Tests for the .goo file writer."""

import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest

from pcb2dlp.output_formats import ExposureParams
from pcb2dlp.output_formats.goo import (
    GooOutput,
    MAGIC_TAG,
    ENDING_STRING,
    HEADER_SIZE,
)
from pcb2dlp.printers import get_printer

PROFILE = get_printer("Elegoo Mars 4 9K")


class TestGooFile:
    def _write_test_file(self, bitmap=None, exposure=60.0):
        if bitmap is None:
            bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        params = ExposureParams(exposure_time_s=exposure, bottom_exposure_time_s=exposure)
        path = Path(tempfile.mktemp(suffix=".goo"))
        GooOutput().write(path, bitmap, PROFILE, params)
        return path

    def test_magic_bytes(self):
        path = self._write_test_file()
        with open(path, "rb") as f:
            f.read(4)  # skip version
            assert f.read(8) == MAGIC_TAG

    def test_ending_string(self):
        path = self._write_test_file()
        with open(path, "rb") as f:
            data = f.read()
            assert data[-11:] == ENDING_STRING

    def test_version(self):
        path = self._write_test_file()
        with open(path, "rb") as f:
            version = f.read(4)
            assert version == b"V3.0"

    def test_resolution_in_header(self):
        path = self._write_test_file()
        with open(path, "rb") as f:
            data = f.read()
        # Find resolution after the big preview delimiter
        # The header has a known structure, so we can find total_layers then x/y res
        offset = HEADER_SIZE - (
            4 + 4 + 4 + 4  # x/y/z size, layer_thickness
            + 4 + 1 + 4  # exposure_time, exposure_delay_mode, turn_off_time
            + 4 * 7  # timing floats
            + 4 + 4  # bottom_exposure_time, bottom_layers
            + 4 * 16  # lift/retract
            + 2 + 2 + 1  # pwm, advance_mode
            + 4 + 4 + 4 + 4  # printing_time, volume, weight, price
            + 8  # price_unit
            + 4 + 1 + 2  # offset, grey_scale, transition
            + 1 + 1  # mirrors
            + 2 + 2  # x_res, y_res
        )
        x_res = struct.unpack_from(">H", data, offset)[0]
        y_res = struct.unpack_from(">H", data, offset + 2)[0]
        assert x_res == PROFILE.x_pixels
        assert y_res == PROFILE.y_pixels

    def test_file_not_empty(self):
        path = self._write_test_file()
        assert path.stat().st_size > HEADER_SIZE + 11  # header + ending

    def test_exposure_time_roundtrip(self):
        """Verify exposure time is written somewhere in the layer content."""
        path = self._write_test_file(exposure=42.5)
        with open(path, "rb") as f:
            data = f.read()
        # Scan the layer content region for the exposure time value
        target = struct.pack(">f", 42.5)
        layer_data = data[HEADER_SIZE:]
        assert target in layer_data

    def test_all_black_small_file(self):
        """All-black bitmap should compress very small."""
        path = self._write_test_file()
        size = path.stat().st_size
        # Header is ~195K, layer data for all-black should be tiny
        assert size < HEADER_SIZE + 200

    def test_pattern_larger_file(self):
        """Bitmap with a pattern should produce a larger file than all-black."""
        bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        bitmap[::2, :] = 255  # alternating rows
        path = self._write_test_file(bitmap=bitmap)
        black_path = self._write_test_file()
        assert path.stat().st_size > black_path.stat().st_size
