"""Main application window."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import numpy as np

from ..input_formats import get_format_for_file, InputFormat
from ..output_formats import ExposureParams
from ..output_formats.goo import GooOutput
from ..printers import get_printer
from ..rasterizer import PlacementConfig, rasterize_svg
from ..test_pattern import generate_exposure_times, build_test_layers
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
        self._test_pattern_layers: list[tuple[np.ndarray, int]] | None = None
        self._test_pattern_base_time: float | None = None

        self._setup_button_styles()
        self._build_menu()
        self._build_layout()

    def _setup_button_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Primary.TButton",
            background="#4a9eff", foreground="white",
            font=("Helvetica", 12, "bold"), padding=(20, 8),
        )
        style.map("Primary.TButton",
                   background=[("active", "#3a8eef"), ("disabled", "#555")])
        style.configure(
            "Secondary.TButton",
            background="#555", foreground="white",
            font=("Helvetica", 11), padding=(15, 5),
        )
        style.map("Secondary.TButton",
                   background=[("active", "#666"), ("disabled", "#444")])

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Gerber...", command=self._open_file, accelerator="Cmd+O")
        file_menu.add_command(label="Generate Test Pattern", command=self._generate_test_pattern, accelerator="Cmd+T")
        file_menu.add_separator()
        file_menu.add_command(label="Export .goo...", command=self._export_file, accelerator="Cmd+E")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit, accelerator="Cmd+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        self.root.bind("<Command-o>", lambda _: self._open_file())
        self.root.bind("<Command-t>", lambda _: self._generate_test_pattern())
        self.root.bind("<Command-e>", lambda _: self._export_file())
        self.root.bind("<Command-q>", lambda _: self.root.quit())

    def _build_layout(self):
        profile = get_printer("Elegoo Mars 4 9K")

        # Controls on the right
        self.controls = ControlsPanel(self.root, on_change=self._on_settings_change)
        self.controls.pack(side=tk.RIGHT, fill=tk.Y)

        # Mode label + export button at bottom of controls
        self._mode_label = tk.Label(
            self.controls, text="No file loaded",
            bg="#2b2b2b", fg="#888", font=("Helvetica", 10),
            wraplength=220, justify="left",
        )
        self._mode_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 5))

        export_btn = ttk.Button(
            self.controls, text="Export .goo",
            command=self._export_file, style="Primary.TButton",
        )
        export_btn.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 15))

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
            self._test_pattern_layers = None
            self._input_fmt = get_format_for_file(Path(path))
            self._input_fmt.load(Path(path))
            self._svg = self._input_fmt.to_svg()
            self._board_size = self._input_fmt.board_size_mm()
            self.root.title(f"pcb2dlp - {Path(path).name}")
            self.controls.set_test_pattern_mode(False)
            self._mode_label.config(text="Gerber mode: sidebar controls apply")
            self._update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def _generate_test_pattern(self):
        profile = self.controls.get_profile()

        # Ask for board dimensions
        dialog = _TestPatternDialog(self.root, profile)
        self.root.wait_window(dialog)
        if not dialog.result:
            return

        base, multiplier, regions = dialog.result["base"], dialog.result["multiplier"], dialog.result["regions"]
        board_w, board_h = dialog.result["board_w"], dialog.result["board_h"]

        exposures = generate_exposure_times(base, multiplier, regions)

        layers, base_time, composite = build_test_layers(exposures, profile, board_w, board_h)

        self._test_pattern_layers = layers
        self._test_pattern_base_time = base_time
        self._bitmap = composite
        self._svg = None
        self._input_fmt = None
        self._board_size = None

        self.preview.update_bitmap(composite)
        self.controls.set_test_pattern_mode(True)
        total_layers = sum(count for _, count in layers)
        total_time_s = total_layers * (base_time + 4)  # ~4s lift overhead
        exp_str = ", ".join(f"{e}s" for e in exposures)
        self.root.title(f"pcb2dlp - Exposure Test ({exp_str})")
        self._mode_label.config(
            text=f"Test pattern mode: {regions} regions, {total_layers} layers\n"
                 f"Exposures: {exp_str}\n"
                 f"Est. time: {total_time_s / 60:.1f} min"
        )

    def _on_settings_change(self):
        if self._svg is not None:
            self._update_preview()
        elif self._test_pattern_layers is not None:
            self._update_test_pattern_preview()

    def _apply_mirror(self, bitmap: np.ndarray) -> np.ndarray:
        """Apply current mirror settings to a bitmap."""
        state = self.controls.state
        if state.mirror_x:
            bitmap = np.fliplr(bitmap)
        if state.mirror_y:
            bitmap = np.flipud(bitmap)
        return bitmap

    def _update_test_pattern_preview(self):
        """Re-render the test pattern composite with current mirror settings."""
        profile = self.controls.get_profile()
        composite = np.zeros((profile.y_pixels, profile.x_pixels), dtype=np.uint8)
        for layer_bitmap, _ in self._test_pattern_layers:
            composite = np.maximum(composite, layer_bitmap)
        self._bitmap = self._apply_mirror(composite)
        self.preview.update_bitmap(self._bitmap)

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
            messagebox.showwarning("No data", "Open a Gerber file or generate a test pattern first.")
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
            if self._test_pattern_layers is not None:
                test_params = ExposureParams(
                    exposure_time_s=self._test_pattern_base_time,
                    bottom_exposure_time_s=self._test_pattern_base_time,
                    light_pwm=state.pwm,
                )
                mirrored_layers = [
                    (self._apply_mirror(bm), count)
                    for bm, count in self._test_pattern_layers
                ]
                writer.write_multilayer(Path(path), mirrored_layers, profile, test_params)
            else:
                writer.write(Path(path), self._bitmap, profile, params)
            messagebox.showinfo("Success", f"Exported to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def run(self):
        self.root.mainloop()


class _TestPatternDialog(tk.Toplevel):
    """Dialog for configuring the exposure test pattern."""

    def __init__(self, parent, profile):
        super().__init__(parent)
        self.title("Exposure Test Pattern")
        self.configure(bg="#2b2b2b")
        self.resizable(False, False)
        self.result = None

        label_opts = {"bg": "#2b2b2b", "fg": "#ccc", "font": ("Helvetica", 11)}
        pad = {"padx": 10, "pady": 5}

        # Board size
        tk.Label(self, text="Board Size", bg="#2b2b2b", fg="#fff",
                 font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        tk.Label(self, text="Width (mm):", **label_opts).grid(row=1, column=0, sticky="w", **pad)
        self._width_var = tk.StringVar(value=str(min(100.0, profile.build_area_x_mm)))
        tk.Entry(self, textvariable=self._width_var, width=10).grid(row=1, column=1, **pad)

        tk.Label(self, text="Height (mm):", **label_opts).grid(row=2, column=0, sticky="w", **pad)
        self._height_var = tk.StringVar(value=str(min(70.0, profile.build_area_y_mm)))
        tk.Entry(self, textvariable=self._height_var, width=10).grid(row=2, column=1, **pad)

        # Exposure settings
        tk.Label(self, text="Exposure", bg="#2b2b2b", fg="#fff",
                 font=("Helvetica", 12, "bold")).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))

        tk.Label(self, text="Base time (s):", **label_opts).grid(row=4, column=0, sticky="w", **pad)
        self._base_var = tk.StringVar(value="5.0")
        tk.Entry(self, textvariable=self._base_var, width=10).grid(row=4, column=1, **pad)

        tk.Label(self, text="Multiplier:", **label_opts).grid(row=5, column=0, sticky="w", **pad)
        self._mult_var = tk.StringVar(value="2.0")
        tk.Entry(self, textvariable=self._mult_var, width=10).grid(row=5, column=1, **pad)

        tk.Label(self, text="Regions:", **label_opts).grid(row=6, column=0, sticky="w", **pad)
        self._regions_var = tk.StringVar(value="5")
        tk.Entry(self, textvariable=self._regions_var, width=10).grid(row=6, column=1, **pad)

        # Preview of exposure times
        self._preview_label = tk.Label(self, text="", bg="#2b2b2b", fg="#888",
                                       font=("Helvetica", 10), wraplength=250, justify="left")
        self._preview_label.grid(row=7, column=0, columnspan=2, sticky="w", **pad)
        self._update_preview()

        for var in [self._base_var, self._mult_var, self._regions_var]:
            var.trace_add("write", lambda *_: self._update_preview())

        # Buttons
        btn_frame = tk.Frame(self, bg="#2b2b2b")
        btn_frame.grid(row=8, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Generate", style="Primary.TButton",
                   command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", style="Secondary.TButton",
                   command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.transient(parent)
        self.grab_set()

    def _update_preview(self):
        try:
            base = float(self._base_var.get())
            mult = float(self._mult_var.get())
            regions = int(self._regions_var.get())
            exposures = generate_exposure_times(base, mult, regions)
            self._preview_label.config(text="Exposures: " + ", ".join(f"{e}s" for e in exposures))
        except (ValueError, TypeError):
            self._preview_label.config(text="")

    def _on_ok(self):
        try:
            self.result = {
                "board_w": float(self._width_var.get()),
                "board_h": float(self._height_var.get()),
                "base": float(self._base_var.get()),
                "multiplier": float(self._mult_var.get()),
                "regions": int(self._regions_var.get()),
            }
        except ValueError:
            return
        self.destroy()


def run_gui():
    app = App()
    app.run()
