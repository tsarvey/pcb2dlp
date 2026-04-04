"""Bitmap manipulation operations."""

import numpy as np
from PIL import Image


def downscale_for_preview(bitmap: np.ndarray, max_width: int = 800) -> Image.Image:
    """Downscale a full-resolution bitmap for GUI preview."""
    h, w = bitmap.shape
    if w <= max_width:
        return Image.fromarray(bitmap)
    scale = max_width / w
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = Image.fromarray(bitmap)
    return img.resize((new_w, new_h), Image.NEAREST)
