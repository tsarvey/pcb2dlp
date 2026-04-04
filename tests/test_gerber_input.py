"""Tests for Gerber input format."""

import tempfile
from pathlib import Path

from pcb2dlp.input_formats import get_format_for_file
from pcb2dlp.input_formats.gerber import GerberInput

# Minimal valid Gerber file
SIMPLE_GERBER = """\
G04 Test*
%FSLAX24Y24*%
%MOMM*%
%ADD10C,0.500*%
D10*
X00100000Y00100000D02*
X00500000Y00100000D01*
X00500000Y00500000D01*
X00100000Y00500000D01*
X00100000Y00100000D01*
M02*
"""


def _write_gerber(content: str = SIMPLE_GERBER, suffix: str = ".gbr") -> Path:
    path = Path(tempfile.mktemp(suffix=suffix))
    path.write_text(content)
    return path


class TestGerberInput:
    def test_load(self):
        path = _write_gerber()
        fmt = GerberInput()
        fmt.load(path)
        # Should not raise

    def test_to_svg(self):
        path = _write_gerber()
        fmt = GerberInput()
        fmt.load(path)
        svg = fmt.to_svg()
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_bounding_box(self):
        path = _write_gerber()
        fmt = GerberInput()
        fmt.load(path)
        x0, y0, x1, y1 = fmt.bounding_box_mm()
        assert x1 > x0
        assert y1 > y0

    def test_board_size(self):
        path = _write_gerber()
        fmt = GerberInput()
        fmt.load(path)
        w, h = fmt.board_size_mm()
        assert w > 0
        assert h > 0

    def test_format_detection_gbr(self):
        path = _write_gerber(suffix=".gbr")
        fmt = get_format_for_file(path)
        assert isinstance(fmt, GerberInput)

    def test_format_detection_gtl(self):
        path = _write_gerber(suffix=".gtl")
        fmt = get_format_for_file(path)
        assert isinstance(fmt, GerberInput)

    def test_unknown_extension(self):
        path = _write_gerber(suffix=".xyz")
        try:
            get_format_for_file(path)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_no_file_loaded_raises(self):
        fmt = GerberInput()
        try:
            fmt.to_svg()
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass
