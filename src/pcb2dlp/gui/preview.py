"""Build plate preview canvas with zoom and pan."""

import tkinter as tk

import numpy as np
from PIL import Image, ImageTk

from ..printers import PrinterProfile

# Maximum cached image dimension (full res is 8520px — keep it for sharp zoom)
MAX_RENDER_PX = 8520


class PreviewCanvas(tk.Frame):
    """Canvas widget showing the PCB pattern on the build plate with zoom/pan."""

    def __init__(self, parent: tk.Widget, profile: PrinterProfile, **kwargs):
        super().__init__(parent, **kwargs)
        self.profile = profile
        self._photo: ImageTk.PhotoImage | None = None
        self._full_img: Image.Image | None = None  # full-res PIL image

        # Zoom / pan state
        self._zoom = 1.0  # 1.0 = fit entire plate in canvas
        self._pan_x = 0.0  # pan offset in image coords (0..1)
        self._pan_y = 0.0
        self._drag_start: tuple[int, int] | None = None

        # Container that keeps the canvas at the printer's aspect ratio
        self._canvas_holder = tk.Frame(self, bg="#2b2b2b")
        self._canvas_holder.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        self._canvas_holder.bind("<Configure>", self._on_holder_resize)

        self._aspect = profile.x_pixels / profile.y_pixels
        self.canvas = tk.Canvas(
            self._canvas_holder, bg="#1a1a1a",
            highlightthickness=1, highlightbackground="#444",
        )
        self.canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=10, height=10)

        # Info label
        self.info_label = tk.Label(
            self,
            text=f"Build plate: {profile.build_area_x_mm:.1f} x {profile.build_area_y_mm:.1f} mm "
            f"({profile.x_pixels} x {profile.y_pixels} px, {profile.pixel_size_um}um)",
            fg="#888", bg="#2b2b2b", font=("Helvetica", 10),
        )
        self.info_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind events
        self.canvas.bind("<MouseWheel>", self._on_scroll)          # macOS / Windows
        self.canvas.bind("<Button-4>", self._on_scroll_linux_up)   # Linux
        self.canvas.bind("<Button-5>", self._on_scroll_linux_down)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Configure>", self._on_resize)

        self._draw_empty_plate()

    def _draw_empty_plate(self):
        """Draw an empty build plate outline."""
        self._full_img = None
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() or 700
        ch = self.canvas.winfo_height() or 354
        pad = 10
        self.canvas.create_rectangle(
            pad, pad, cw - pad, ch - pad,
            outline="#555", width=1, dash=(4, 4),
        )
        self.canvas.create_text(
            cw // 2, ch // 2,
            text="Open a Gerber file to preview",
            fill="#666", font=("Helvetica", 14),
        )

    def set_profile(self, profile: PrinterProfile):
        """Switch to a different printer profile, updating aspect & info text."""
        if profile is self.profile:
            return
        self.profile = profile
        self._aspect = profile.x_pixels / profile.y_pixels
        self.info_label.config(
            text=f"Build plate: {profile.build_area_x_mm:.1f} x {profile.build_area_y_mm:.1f} mm "
            f"({profile.x_pixels} x {profile.y_pixels} px, {profile.pixel_size_um}um)"
        )
        # Re-fit the canvas to the new aspect using current holder size
        holder_w = self._canvas_holder.winfo_width()
        holder_h = self._canvas_holder.winfo_height()
        if holder_w > 1 and holder_h > 1:
            avail_w = max(1, holder_w - 2)
            avail_h = max(1, holder_h - 2)
            if avail_w / avail_h > self._aspect:
                h = avail_h
                w = int(h * self._aspect)
            else:
                w = avail_w
                h = int(w / self._aspect)
            self.canvas.place_configure(width=w, height=h)
        # Bitmap is sized for the old profile — drop it; caller will re-render.
        self._full_img = None
        self._draw_empty_plate()

    def update_bitmap(self, bitmap: np.ndarray | None):
        """Update the preview with a new bitmap (full build plate resolution)."""
        if bitmap is None:
            self._draw_empty_plate()
            return

        self._full_img = Image.fromarray(bitmap)
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._render()

    def _render(self):
        """Render the current view (zoom + pan) to the canvas."""
        if self._full_img is None:
            return

        self.canvas.delete("all")

        cw = self.canvas.winfo_width() or 700
        ch = self.canvas.winfo_height() or 354
        img_w, img_h = self._full_img.size

        # At zoom=1 the full image fits in the canvas.
        # At higher zoom we show a cropped region.
        # Compute the region of the source image visible at this zoom.
        view_w = img_w / self._zoom
        view_h = img_h / self._zoom

        # Centre the view around the pan point, clamping to image bounds
        cx = self._pan_x * img_w
        cy = self._pan_y * img_h
        left = max(0, cx - view_w / 2)
        top = max(0, cy - view_h / 2)
        if left + view_w > img_w:
            left = max(0, img_w - view_w)
        if top + view_h > img_h:
            top = max(0, img_h - view_h)

        right = min(img_w, left + view_w)
        bottom = min(img_h, top + view_h)

        # Crop and resize to canvas, preserving aspect ratio (letterbox)
        cropped = self._full_img.crop((int(left), int(top), int(right), int(bottom)))
        crop_w, crop_h = cropped.size
        scale = min(cw / crop_w, ch / crop_h)
        render_w = max(1, int(crop_w * scale))
        render_h = max(1, int(crop_h * scale))
        resized = cropped.resize((render_w, render_h), Image.LANCZOS)

        # Center on canvas — store offset/scale for coordinate mapping
        self._render_ox = (cw - render_w) // 2
        self._render_oy = (ch - render_h) // 2
        self._render_w = render_w
        self._render_h = render_h

        self._photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(self._render_ox, self._render_oy, anchor=tk.NW, image=self._photo)

        # Show zoom level indicator if zoomed in
        if self._zoom > 1.05:
            self.canvas.create_text(
                cw - 10, 10, anchor=tk.NE,
                text=f"{self._zoom:.1f}x", fill="#888",
                font=("Helvetica", 11, "bold"),
            )

    def _on_scroll(self, event):
        if self._full_img is None:
            return
        # macOS sends delta in multiples of 1, Windows in multiples of 120
        delta = event.delta
        if abs(delta) > 10:
            delta = delta // abs(delta)  # normalize to +/-1

        factor = 1.2 if delta > 0 else 1 / 1.2
        new_zoom = max(1.0, min(20.0, self._zoom * factor))

        # Zoom towards the cursor position
        if new_zoom != self._zoom:
            self._zoom_towards(event.x, event.y, new_zoom)

    def _on_scroll_linux_up(self, event):
        event.delta = 1
        self._on_scroll(event)

    def _on_scroll_linux_down(self, event):
        event.delta = -1
        self._on_scroll(event)

    def _zoom_towards(self, canvas_x: int, canvas_y: int, new_zoom: float):
        """Zoom so the point under the cursor stays fixed."""
        img_w, img_h = self._full_img.size
        rw = getattr(self, "_render_w", img_w)
        rh = getattr(self, "_render_h", img_h)
        ox = getattr(self, "_render_ox", 0)
        oy = getattr(self, "_render_oy", 0)

        # Map canvas coords to fraction within the rendered image
        fx = (canvas_x - ox) / rw
        fy = (canvas_y - oy) / rh
        fx = max(0.0, min(1.0, fx))
        fy = max(0.0, min(1.0, fy))

        # Current view bounds
        view_w = img_w / self._zoom
        view_h = img_h / self._zoom
        cx = self._pan_x * img_w
        cy = self._pan_y * img_h
        left = max(0, cx - view_w / 2)
        top = max(0, cy - view_h / 2)
        if left + view_w > img_w:
            left = max(0, img_w - view_w)
        if top + view_h > img_h:
            top = max(0, img_h - view_h)

        # Image coordinate under cursor
        img_x = left + fx * view_w
        img_y = top + fy * view_h

        # New view size
        new_view_w = img_w / new_zoom
        new_view_h = img_h / new_zoom

        # New center so that img_x,img_y stays at the same screen fraction
        new_left = img_x - fx * new_view_w
        new_top = img_y - fy * new_view_h
        new_cx = new_left + new_view_w / 2
        new_cy = new_top + new_view_h / 2

        self._zoom = new_zoom
        self._pan_x = max(0.0, min(1.0, new_cx / img_w))
        self._pan_y = max(0.0, min(1.0, new_cy / img_h))
        self._render()

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        if self._drag_start is None or self._full_img is None or self._zoom <= 1.0:
            return

        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)

        rw = getattr(self, "_render_w", 700)
        rh = getattr(self, "_render_h", 354)

        # Convert pixel drag to pan offset (fraction of image)
        self._pan_x -= dx / rw / self._zoom
        self._pan_y -= dy / rh / self._zoom
        self._pan_x = max(0.0, min(1.0, self._pan_x))
        self._pan_y = max(0.0, min(1.0, self._pan_y))
        self._render()

    def _on_resize(self, event):
        """Re-render when the canvas is resized."""
        if self._full_img is not None:
            self._render()
        else:
            self._draw_empty_plate()

    def _on_holder_resize(self, event):
        """Resize the canvas to fit the holder while preserving printer aspect."""
        avail_w = max(1, event.width - 2)
        avail_h = max(1, event.height - 2)
        if avail_w / avail_h > self._aspect:
            h = avail_h
            w = int(h * self._aspect)
        else:
            w = avail_w
            h = int(w / self._aspect)
        self.canvas.place_configure(width=w, height=h)
