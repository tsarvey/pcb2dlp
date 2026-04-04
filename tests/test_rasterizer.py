"""Tests for the SVG rasterizer."""

import numpy as np
import pytest

from pcb2dlp.printers import get_printer
from pcb2dlp.rasterizer import PlacementConfig, rasterize_svg

PROFILE = get_printer("Elegoo Mars 4 9K")

# Minimal SVG: 10mm x 10mm white rectangle on black background
SIMPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="10mm" height="10mm">
  <rect x="0" y="0" width="10" height="10" fill="black"/>
  <rect x="2" y="2" width="6" height="6" fill="white"/>
</svg>"""


class TestRasterize:
    def test_output_shape(self):
        bitmap = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        assert bitmap.shape == (PROFILE.y_pixels, PROFILE.x_pixels)

    def test_output_dtype(self):
        bitmap = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        assert bitmap.dtype == np.uint8

    def test_binary_values(self):
        bitmap = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        unique = set(np.unique(bitmap))
        assert unique.issubset({0, 255})

    def test_has_white_pixels(self):
        bitmap = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        assert (bitmap == 255).sum() > 0

    def test_centered(self):
        bitmap = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        # White pixels should be roughly centered
        white_coords = np.argwhere(bitmap == 255)
        center_y = white_coords[:, 0].mean()
        center_x = white_coords[:, 1].mean()
        assert abs(center_y - PROFILE.y_pixels / 2) < 50
        assert abs(center_x - PROFILE.x_pixels / 2) < 50

    def test_invert(self):
        normal = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        inverted = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig(invert=True))
        # Center of the board region should be opposite
        cy, cx = PROFILE.y_pixels // 2, PROFILE.x_pixels // 2
        assert normal[cy, cx] != inverted[cy, cx]

    def test_mirror_x(self):
        normal = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        mirrored = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig(mirror_x=True))
        # Symmetric SVG, so mirrored should still be centered but flipped
        assert normal.shape == mirrored.shape
        assert (normal == 255).sum() == (mirrored == 255).sum()

    def test_offset(self):
        centered = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig())
        shifted = rasterize_svg(SIMPLE_SVG, (10.0, 10.0), PROFILE, PlacementConfig(offset_x_mm=10.0))
        # White pixel center should shift right
        centered_cx = np.argwhere(centered == 255)[:, 1].mean()
        shifted_cx = np.argwhere(shifted == 255)[:, 1].mean()
        expected_shift_px = 10.0 * 1000 / PROFILE.pixel_size_um
        assert shifted_cx - centered_cx == pytest.approx(expected_shift_px, abs=5)
