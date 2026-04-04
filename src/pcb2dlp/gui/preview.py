"""Build plate preview canvas."""

import tkinter as tk

import numpy as np
from PIL import Image, ImageTk

from ..printers import PrinterProfile


class PreviewCanvas(tk.Frame):
    """Canvas widget showing the PCB pattern on the build plate."""

    def __init__(self, parent: tk.Widget, profile: PrinterProfile, **kwargs):
        super().__init__(parent, **kwargs)
        self.profile = profile
        self._photo: ImageTk.PhotoImage | None = None

        # Compute canvas size maintaining aspect ratio
        aspect = profile.x_pixels / profile.y_pixels
        self.canvas_width = 700
        self.canvas_height = int(self.canvas_width / aspect)

        self.canvas = tk.Canvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#1a1a1a",
            highlightthickness=1,
            highlightbackground="#444",
        )
        self.canvas.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Info label
        self.info_label = tk.Label(
            self,
            text=f"Build plate: {profile.build_area_x_mm:.1f} x {profile.build_area_y_mm:.1f} mm "
            f"({profile.x_pixels} x {profile.y_pixels} px, {profile.pixel_size_um}um)",
            fg="#888",
            bg="#2b2b2b",
            font=("Helvetica", 10),
        )
        self.info_label.pack(side=tk.BOTTOM, fill=tk.X)

        self._draw_empty_plate()

    def _draw_empty_plate(self):
        """Draw an empty build plate outline."""
        self.canvas.delete("all")
        pad = 10
        self.canvas.create_rectangle(
            pad, pad,
            self.canvas_width - pad, self.canvas_height - pad,
            outline="#555", width=1, dash=(4, 4),
        )
        self.canvas.create_text(
            self.canvas_width // 2, self.canvas_height // 2,
            text="Open a Gerber file to preview",
            fill="#666", font=("Helvetica", 14),
        )

    def update_bitmap(self, bitmap: np.ndarray | None):
        """Update the preview with a new bitmap (full build plate resolution)."""
        if bitmap is None:
            self._draw_empty_plate()
            return

        self.canvas.delete("all")

        # Downscale to canvas size
        img = Image.fromarray(bitmap)
        img = img.resize((self.canvas_width, self.canvas_height), Image.NEAREST)

        self._photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)
