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
from pcb2dlp.output_formats.goo_verify import verify_goo, GooVerifyError
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
            + 4 * 6  # timing floats
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


class TestGooVerify:
    """Verify .goo files are structurally valid by reading them back."""

    def _write_test_file(self, bitmap=None, exposure=60.0):
        if bitmap is None:
            bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        params = ExposureParams(exposure_time_s=exposure, bottom_exposure_time_s=exposure)
        path = Path(tempfile.mktemp(suffix=".goo"))
        GooOutput().write(path, bitmap, PROFILE, params)
        return path

    def test_verify_single_layer(self):
        path = self._write_test_file()
        meta = verify_goo(path, expected_pixels=(PROFILE.x_pixels, PROFILE.y_pixels))
        assert meta["total_layers"] == 1
        assert meta["resolution"] == (PROFILE.x_pixels, PROFILE.y_pixels)
        assert meta["printer"] == PROFILE.name
        assert len(meta["layers"]) == 1

    def test_verify_multilayer(self):
        bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        bitmap[100:200, 100:200] = 255
        # (bitmap, repeat_count) — all layers use params.exposure_time_s
        layers = [(bitmap, 1), (bitmap, 2), (bitmap, 4)]
        params = ExposureParams(exposure_time_s=5.0, bottom_exposure_time_s=5.0)
        path = Path(tempfile.mktemp(suffix=".goo"))
        GooOutput().write_multilayer(path, layers, PROFILE, params)
        meta = verify_goo(path, expected_pixels=(PROFILE.x_pixels, PROFILE.y_pixels))
        assert meta["total_layers"] == 7  # 1 + 2 + 4
        assert len(meta["layers"]) == 7
        # All layers should have the same exposure time
        for layer in meta["layers"]:
            assert layer["exposure_s"] == 5.0

    def test_verify_layer_z_increments(self):
        """Layers should start low and increment slightly to trigger LCD refresh."""
        bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        layers = [(bitmap, 1), (bitmap, 2), (bitmap, 1)]
        params = ExposureParams(exposure_time_s=5.0, bottom_exposure_time_s=5.0)
        path = Path(tempfile.mktemp(suffix=".goo"))
        writer = GooOutput()
        writer.write_multilayer(path, layers, PROFILE, params)
        meta = verify_goo(path)
        z_values = [l["z_mm"] for l in meta["layers"]]
        assert len(z_values) == 4  # 1 + 2 + 1
        assert z_values[0] < z_values[1] < z_values[2] < z_values[3]
        assert z_values[0] == pytest.approx(writer.LAYER_Z_MM)
        assert z_values[-1] < writer.LAYER_Z_MM + 1.0

    def test_verify_checksums(self):
        bitmap = np.zeros((PROFILE.y_pixels, PROFILE.x_pixels), dtype=np.uint8)
        bitmap[::3, ::5] = 255  # pattern to exercise RLE
        path = self._write_test_file(bitmap=bitmap)
        # verify_goo checks checksums internally — no error means they're correct
        verify_goo(path)

    def test_verify_detects_corruption(self):
        """Corrupt a byte in the header magic — verifier should catch it."""
        path = self._write_test_file()
        data = bytearray(path.read_bytes())
        data[5] ^= 0xFF  # corrupt magic tag
        path.write_bytes(data)
        with pytest.raises(GooVerifyError):
            verify_goo(path)
