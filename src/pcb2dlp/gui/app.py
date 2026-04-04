"""Main application window."""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import numpy as np

from ..input_formats import get_format_for_file, InputFormat
from ..output_formats import ExposureParams
from ..output_formats.goo import GooOutput
from ..printers import get_printer
from ..rasterizer import PlacementConfig, rasterize_svg
from .controls import ControlsPanel
from .preview import PreviewCanvas


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("pcb2dlp")
        self.root.configure(bg="#2b2b2b")
        self.root.geometry("1050x620")

        self._input_fmt: InputFormat | None = None
        self._svg: str | None = None
        self._board_size: tuple[float, float] | None = None
        self._bitmap: np.ndarray | None = None

        self._build_menu()
        self._build_layout()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Gerber...", command=self._open_file, accelerator="Cmd+O")
        file_menu.add_command(label="Export .goo...", command=self._export_file, accelerator="Cmd+E")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit, accelerator="Cmd+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        self.root.bind("<Command-o>", lambda _: self._open_file())
        self.root.bind("<Command-e>", lambda _: self._export_file())
        self.root.bind("<Command-q>", lambda _: self.root.quit())

    def _build_layout(self):
        profile = get_printer("Elegoo Mars 4 9K")

        # Controls on the right
        self.controls = ControlsPanel(self.root, on_change=self._on_settings_change)
        self.controls.pack(side=tk.RIGHT, fill=tk.Y)

        # Export button at bottom of controls
        export_btn = tk.Button(
            self.controls, text="Export .goo",
            command=self._export_file,
            bg="#4a9eff", fg="white", font=("Helvetica", 12, "bold"),
            padx=20, pady=8,
        )
        export_btn.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=15)

        # Preview in the center
        self.preview = PreviewCanvas(self.root, profile, bg="#2b2b2b")
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Gerber File",
            filetypes=[
                ("Gerber files", "*.gbr *.ger *.gtl *.gbl *.gts *.gbs *.grb"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            self._input_fmt = get_format_for_file(Path(path))
            self._input_fmt.load(Path(path))
            self._svg = self._input_fmt.to_svg()
            self._board_size = self._input_fmt.board_size_mm()
            self.root.title(f"pcb2dlp - {Path(path).name}")
            self._update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def _on_settings_change(self):
        if self._svg is not None:
            self._update_preview()

    def _update_preview(self):
        if self._svg is None or self._board_size is None:
            return

        state = self.controls.state
        profile = self.controls.get_profile()

        placement = PlacementConfig(
            offset_x_mm=state.offset_x_mm,
            offset_y_mm=state.offset_y_mm,
            rotation_deg=state.rotation,
            mirror_x=state.mirror_x,
            mirror_y=state.mirror_y,
            invert=state.invert,
        )

        try:
            self._bitmap = rasterize_svg(self._svg, self._board_size, profile, placement)
            self.preview.update_bitmap(self._bitmap)
        except Exception as e:
            messagebox.showerror("Error", f"Rasterization failed:\n{e}")

    def _export_file(self):
        if self._bitmap is None:
            messagebox.showwarning("No data", "Open a Gerber file first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export .goo File",
            defaultextension=".goo",
            filetypes=[("GOO files", "*.goo")],
        )
        if not path:
            return

        state = self.controls.state
        profile = self.controls.get_profile()
        params = ExposureParams(
            exposure_time_s=state.exposure_s,
            bottom_exposure_time_s=state.exposure_s,
            light_pwm=state.pwm,
        )

        try:
            writer = GooOutput()
            writer.write(Path(path), self._bitmap, profile, params)
            messagebox.showinfo("Success", f"Exported to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def run(self):
        self.root.mainloop()


def run_gui():
    app = App()
    app.run()
