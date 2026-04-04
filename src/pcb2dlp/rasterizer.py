"""Rasterize SVG to numpy bitmap at exact printer pixel resolution."""

from dataclasses import dataclass

import cairosvg
import numpy as np
from PIL import Image
import io

from .printers import PrinterProfile


@dataclass
class PlacementConfig:
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    rotation_deg: int = 0  # 0, 90, 180, 270
    mirror_x: bool = False
    mirror_y: bool = False
    invert: bool = False


def rasterize_svg(
    svg_string: str,
    board_size_mm: tuple[float, float],
    profile: PrinterProfile,
    placement: PlacementConfig,
) -> np.ndarray:
    """Rasterize an SVG string to a full build-plate bitmap.

    Returns a numpy array of shape (y_pixels, x_pixels) with values 0 or 255.
    """
    board_w_mm, board_h_mm = board_size_mm

    # Compute pixel dimensions for the board area
    board_w_px = round(board_w_mm * 1000 / profile.pixel_size_um)
    board_h_px = round(board_h_mm * 1000 / profile.pixel_size_um)

    # Rasterize SVG to PNG bytes at exact pixel dimensions
    png_bytes = cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        output_width=board_w_px,
        output_height=board_h_px,
    )

    # Load into Pillow and convert to grayscale
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    bitmap = np.array(img)

    # Threshold to pure black/white
    bitmap = np.where(bitmap > 127, 255, 0).astype(np.uint8)

    # Apply transformations
    if placement.invert:
        bitmap = 255 - bitmap

    if placement.mirror_x:
        bitmap = np.fliplr(bitmap)

    if placement.mirror_y:
        bitmap = np.flipud(bitmap)

    if placement.rotation_deg:
        k = placement.rotation_deg // 90
        bitmap = np.rot90(bitmap, k=-k)  # negative because rot90 is CCW

    # Place on full build plate (centered + offset)
    plate = np.zeros((profile.y_pixels, profile.x_pixels), dtype=np.uint8)
    bh, bw = bitmap.shape

    # Center position + offset in pixels
    offset_x_px = round(placement.offset_x_mm * 1000 / profile.pixel_size_um)
    offset_y_px = round(placement.offset_y_mm * 1000 / profile.pixel_size_um)
    cx = (profile.x_pixels - bw) // 2 + offset_x_px
    cy = (profile.y_pixels - bh) // 2 + offset_y_px

    # Clip to build plate bounds
    src_x0 = max(0, -cx)
    src_y0 = max(0, -cy)
    src_x1 = min(bw, profile.x_pixels - cx)
    src_y1 = min(bh, profile.y_pixels - cy)

    dst_x0 = max(0, cx)
    dst_y0 = max(0, cy)
    dst_x1 = dst_x0 + (src_x1 - src_x0)
    dst_y1 = dst_y0 + (src_y1 - src_y0)

    if src_x1 > src_x0 and src_y1 > src_y0:
        plate[dst_y0:dst_y1, dst_x0:dst_x1] = bitmap[src_y0:src_y1, src_x0:src_x1]

    return plate
