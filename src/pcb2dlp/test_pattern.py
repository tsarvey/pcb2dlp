"""Exposure test pattern generator.

Generates a multi-layer .goo file with different exposure times per region,
filled with SMD component footprints, trace widths, and text labels.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .printers import PrinterProfile
from .output_formats import ExposureParams
from .output_formats.goo import GooOutput


def mm_to_px(mm: float, profile: PrinterProfile) -> int:
    return round(mm * 1000 / profile.pixel_size_um)


def generate_exposure_times(
    base_s: float,
    multiplier: float,
    regions: int,
) -> list[float]:
    return [round(base_s * (multiplier ** i), 1) for i in range(regions)]


def _get_font(size_px: int):
    """Get a font at the given pixel size, with fallbacks."""
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size_px)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


class PatternDrawer:
    """Draws test patterns into a Pillow ImageDraw at printer resolution."""

    def __init__(self, draw: ImageDraw.Draw, profile: PrinterProfile):
        self.draw = draw
        self.profile = profile

    def px(self, mm: float) -> int:
        return mm_to_px(mm, self.profile)

    def rect(self, x: float, y: float, w: float, h: float):
        px, py = self.px(x), self.px(y)
        self.draw.rectangle([px, py, px + self.px(w), py + self.px(h)], fill=255)

    def pad(self, cx: float, cy: float, w: float, h: float):
        self.rect(cx - w / 2, cy - h / 2, w, h)

    def circle_pad(self, cx: float, cy: float, diameter: float):
        r = self.px(diameter / 2)
        pcx, pcy = self.px(cx), self.px(cy)
        self.draw.ellipse([pcx - r, pcy - r, pcx + r, pcy + r], fill=255)

    def trace(self, x1: float, y1: float, x2: float, y2: float, width: float):
        pw = max(1, self.px(width))
        self.draw.line(
            [(self.px(x1), self.px(y1)), (self.px(x2), self.px(y2))],
            fill=255, width=pw,
        )

    def text(self, x: float, y: float, text: str, size_mm: float):
        font = _get_font(self.px(size_mm))
        self.draw.text((self.px(x), self.px(y)), text, fill=255, font=font)

    # --- SMD Component Footprints ---

    def smd_2pad(self, x: float, y: float, pad_w: float, pad_h: float,
                 gap: float, label: str = ""):
        """2-pad component (resistor/cap). x,y = top-left of component area."""
        cy = y
        self.pad(x + pad_w / 2, cy, pad_w, pad_h)
        self.pad(x + pad_w + gap + pad_w / 2, cy, pad_w, pad_h)
        if label:
            self.text(x, y + pad_h / 2 + 0.3, label, 1.2)

    def soic8(self, x: float, y: float):
        pad_w, pad_h, pitch = 0.6, 1.5, 1.27
        span = 5.4
        for i in range(4):
            py = y + i * pitch
            self.pad(x + pad_h / 2, py, pad_h, pad_w)
            self.pad(x + span - pad_h / 2, py, pad_h, pad_w)
        self.text(x + 0.3, y + 4 * pitch + 0.3, "SOIC-8", 1.2)

    def sot23(self, x: float, y: float):
        pad_w, pad_h, pitch = 0.6, 1.0, 0.95
        self.pad(x + pad_h / 2, y, pad_h, pad_w)
        self.pad(x + pad_h / 2, y + pitch, pad_h, pad_w)
        self.pad(x + 2.2 + pad_h / 2, y + pitch / 2, pad_h, pad_w)
        self.text(x - 0.2, y + pitch + 0.8, "SOT-23", 1.2)

    def sot223(self, x: float, y: float):
        """SOT-223 — larger 4-pin package."""
        pad_w, pad_h = 0.7, 1.2
        tab_w, tab_h = 3.2, 1.8
        pitch = 2.3
        # 3 small pads on left
        for i in range(3):
            self.pad(x + pad_h / 2, y + i * pitch, pad_h, pad_w)
        # Large tab on right
        self.pad(x + 5.5, y + pitch, tab_h, tab_w)
        self.text(x - 0.2, y + 3 * pitch + 0.3, "SOT-223", 1.2)

    def qfp_pads(self, x: float, y: float, pitch: float = 0.5, count: int = 8):
        """Row of fine-pitch QFP pads."""
        pad_w = pitch * 0.55
        pad_h = 1.5
        for i in range(count):
            self.pad(x + i * pitch + pitch / 2, y, pad_w, pad_h)
        self.text(x, y + pad_h / 2 + 0.3, f"{pitch}mm pitch", 1.2)

    def qfn_pads(self, x: float, y: float):
        """QFN-16 style bottom pads with center ground pad."""
        pitch = 0.65
        pad_w, pad_h = 0.35, 0.8
        body = 4.0
        # 4 pads per side
        for i in range(4):
            offset = (i - 1.5) * pitch
            # Bottom row
            self.pad(x + body / 2 + offset, y + body - pad_h / 2, pad_w, pad_h)
            # Top row
            self.pad(x + body / 2 + offset, y + pad_h / 2, pad_w, pad_h)
            # Left column
            self.pad(x + pad_h / 2, y + body / 2 + offset, pad_h, pad_w)
            # Right column
            self.pad(x + body - pad_h / 2, y + body / 2 + offset, pad_h, pad_w)
        # Center pad
        self.pad(x + body / 2, y + body / 2, 2.0, 2.0)
        self.text(x, y + body + 0.3, "QFN-16", 1.2)

    def dip8(self, x: float, y: float):
        """DIP-8 / through-hole pads."""
        pitch = 2.54
        pad_d = 1.6
        row_spacing = 7.62
        for i in range(4):
            self.circle_pad(x, y + i * pitch, pad_d)
            self.circle_pad(x + row_spacing, y + i * pitch, pad_d)
        self.text(x - 0.5, y + 4 * pitch + 0.3, "DIP-8", 1.2)

    # --- Test Sections ---

    def trace_width_test(self, x: float, y: float, region_w: float):
        """Draw traces at various widths with labels."""
        widths = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.8, 1.0, 1.5, 2.0]
        spacing = 1.8
        length = min(region_w - 10, 12.0)

        self.text(x, y - 2.0, "Trace widths", 1.5)
        for i, w in enumerate(widths):
            ty = y + i * spacing
            self.trace(x, ty, x + length, ty, w)
            self.text(x + length + 0.5, ty - 0.5, f"{w}mm", 1.0)

    def via_test(self, x: float, y: float):
        """Draw circular pads at various sizes."""
        diameters = [0.3, 0.4, 0.5, 0.8, 1.0, 1.5, 2.0]
        self.text(x, y - 2.0, "Pad diameters", 1.5)
        cx = x
        for d in diameters:
            self.circle_pad(cx + d / 2, y + d / 2, d)
            self.text(cx, y + max(d, 1.0) + 0.5, f"{d}", 0.9)
            cx += max(d, 1.2) + 1.5

    def spacing_test(self, x: float, y: float):
        """Pairs of traces with decreasing gaps to test isolation."""
        spacings = [0.5, 0.3, 0.2, 0.15, 0.1]
        trace_w = 0.3
        trace_len = 5.0

        self.text(x, y - 2.0, "Trace spacing", 1.5)
        cy = y
        for gap in spacings:
            self.trace(x, cy, x + trace_len, cy, trace_w)
            self.trace(x, cy + trace_w + gap, x + trace_len, cy + trace_w + gap, trace_w)
            self.text(x + trace_len + 0.5, cy, f"{gap}mm gap", 0.9)
            cy += trace_w * 2 + gap + 1.5


def _draw_test_pattern(draw: ImageDraw.Draw, x: float, y: float,
                       region_w: float, region_h: float,
                       exposure_s: float, profile: PrinterProfile):
    """Draw the full test pattern for one region.

    Layout is designed to fit within region_h (typically 70mm).
    """
    d = PatternDrawer(draw, profile)
    margin = 1.5
    cx = x + margin
    content_w = region_w - margin * 2

    # Region border
    bw = 0.15
    d.rect(x + 0.3, y + 0.3, region_w - 0.6, bw)
    d.rect(x + 0.3, y + region_h - 0.3 - bw, region_w - 0.6, bw)
    d.rect(x + 0.3, y + 0.3, bw, region_h - 0.6)
    d.rect(x + region_w - 0.3 - bw, y + 0.3, bw, region_h - 0.6)

    # Cursor tracks vertical position
    cy = y + 1.0

    # --- Exposure time label at top ---
    d.text(cx, cy, f"{exposure_s}s", 2.5)
    cy += 4.5

    # --- SMD components ---
    d.text(cx, cy, "SMD Passives", 1.2)
    cy += 2.0
    d.smd_2pad(cx, cy, 0.2, 0.25, 0.15, "0201")
    d.smd_2pad(cx + 5, cy, 0.3, 0.4, 0.25, "0402")
    d.smd_2pad(cx + 10, cy, 0.45, 0.55, 0.4, "0603")
    cy += 2.8
    d.smd_2pad(cx, cy, 0.55, 0.75, 0.7, "0805")
    d.smd_2pad(cx + 5, cy, 0.75, 1.5, 0.9, "1206")
    d.smd_2pad(cx + 11, cy, 1.0, 2.5, 1.2, "2512")
    cy += 4.5

    # --- ICs ---
    d.text(cx, cy, "IC Packages", 1.2)
    cy += 2.0
    d.sot23(cx, cy)
    d.soic8(cx + 5, cy)
    d.qfn_pads(cx + 12, cy - 0.5)
    cy += 7.0
    d.qfp_pads(cx, cy, pitch=0.5, count=8)
    cy += 3.5
    d.qfp_pads(cx, cy, pitch=0.8, count=8)
    cy += 3.5

    # --- Trace widths ---
    d.text(cx, cy, "Trace widths", 1.2)
    cy += 2.0
    widths = [0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5]
    trace_len = min(content_w - 6, 8.0)
    for w in widths:
        d.trace(cx, cy, cx + trace_len, cy, w)
        d.text(cx + trace_len + 0.5, cy - 0.4, f"{w}", 0.8)
        cy += max(w, 0.3) + 0.8

    # --- Trace spacing ---
    cy += 0.5
    d.text(cx, cy, "Trace spacing", 1.2)
    cy += 2.0
    spacings = [0.3, 0.2, 0.15, 0.1]
    trace_w = 0.25
    trace_len2 = min(content_w - 6, 5.0)
    for gap in spacings:
        d.trace(cx, cy, cx + trace_len2, cy, trace_w)
        d.trace(cx, cy + trace_w + gap, cx + trace_len2, cy + trace_w + gap, trace_w)
        d.text(cx + trace_len2 + 0.5, cy - 0.2, f"{gap}mm", 0.8)
        cy += trace_w * 2 + gap + 1.0

    # --- Pad diameters ---
    cy += 0.5
    d.text(cx, cy, "Pads", 1.2)
    cy += 2.0
    diameters = [0.3, 0.5, 0.8, 1.0, 1.5]
    pad_x = cx
    for dia in diameters:
        d.circle_pad(pad_x + dia / 2, cy + dia / 2, dia)
        d.text(pad_x, cy + max(dia, 0.8) + 0.3, f"{dia}", 0.7)
        pad_x += max(dia, 0.8) + 1.0

    # --- Exposure label at bottom ---
    d.text(cx, y + region_h - 4.5, f"{exposure_s}s", 2.5)


def build_test_layers(
    exposures: list[float],
    profile: PrinterProfile,
    board_w: float,
    board_h: float,
) -> tuple[list[tuple[np.ndarray, int]], float, np.ndarray]:
    """Build cumulative test exposure layers.

    All regions that still need exposure are lit simultaneously.  Regions
    drop out one by one as they reach their target.  All layers use the
    same uniform exposure time.

    For exposures [5, 10, 20] with layer_time=5s:
      Layer 0 (1×): ██████  all 3 regions  -> region 0 done (5s)
      Layer 1 (1×): ░░████  regions 1,2    -> region 1 done (10s)
      Layer 2 (2×): ░░░░██  region 2 only  -> region 2 done (20s)
      Total: 4 layers (vs 7 sequential)

    Returns (layers, layer_time_s, composite).
    """
    regions = len(exposures)
    region_w = board_w / regions

    offset_x = (profile.build_area_x_mm - board_w) / 2
    offset_y = (profile.build_area_y_mm - board_h) / 2

    # Find the largest layer time that keeps rounding error under 5%
    # and total layer count under 200.
    max_layers_limit = 200
    layer_time = exposures[0]
    while layer_time >= 0.5:
        trial = [max(1, round(e / layer_time)) for e in exposures]
        if max(trial) > max_layers_limit:
            layer_time *= 2
            break
        max_err = max(
            abs(n * layer_time - e) / e
            for n, e in zip(trial, exposures) if e > 0
        )
        if max_err <= 0.05:
            break
        layer_time /= 2
    layers_needed = [max(1, round(e / layer_time)) for e in exposures]

    # Build unique bitmaps at each threshold where a region drops out
    layers: list[tuple[np.ndarray, int]] = []
    composite = np.zeros((profile.y_pixels, profile.x_pixels), dtype=np.uint8)

    sorted_thresholds = sorted(set(layers_needed))
    prev_count = 0

    for threshold in sorted_thresholds:
        bitmap = np.zeros((profile.y_pixels, profile.x_pixels), dtype=np.uint8)
        img = Image.fromarray(bitmap)
        draw = ImageDraw.Draw(img)

        # Draw all regions that still need exposure at this point
        for region_idx in range(regions):
            if layers_needed[region_idx] >= threshold:
                region_x = offset_x + region_idx * region_w
                _draw_test_pattern(
                    draw, region_x, offset_y, region_w, board_h,
                    exposures[region_idx], profile,
                )

        bitmap = np.array(img)
        repeat_count = threshold - prev_count
        layers.append((bitmap, repeat_count))
        composite = np.maximum(composite, bitmap)
        prev_count = threshold

    return layers, layer_time, composite


def generate_test_exposure(
    profile: PrinterProfile,
    output_path: Path,
    base_exposure_s: float = 8.0,
    multiplier: float = 1.7,
    regions: int = 6,
    pwm: int = 255,
    board_width_mm: float | None = None,
    board_height_mm: float | None = None,
    mirror_x: bool = True,
    mirror_y: bool = True,
) -> list[float]:
    """Generate a multi-layer exposure test .goo file.

    Args:
        board_width_mm: Width of the test pattern area. Defaults to full build plate.
        board_height_mm: Height of the test pattern area. Defaults to full build plate.

    Returns the list of exposure times used.
    """
    exposures = generate_exposure_times(base_exposure_s, multiplier, regions)

    board_w = board_width_mm or profile.build_area_x_mm
    board_h = board_height_mm or profile.build_area_y_mm

    layers, base_time, _ = build_test_layers(exposures, profile, board_w, board_h)

    if mirror_x or mirror_y:
        mirrored = []
        for bitmap, count in layers:
            if mirror_x:
                bitmap = np.fliplr(bitmap)
            if mirror_y:
                bitmap = np.flipud(bitmap)
            mirrored.append((bitmap, count))
        layers = mirrored

    params = ExposureParams(
        exposure_time_s=base_time,
        bottom_exposure_time_s=base_time,
        light_pwm=pwm,
    )

    writer = GooOutput()
    writer.write_multilayer(output_path, layers, profile, params)

    return exposures
