"""Sidebar controls for exposure settings and transformations."""

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Callable

from ..printers import PrinterProfile, list_printers, get_printer


@dataclass
class ControlState:
    printer_name: str = "Elegoo Mars 4 9K"
    exposure_s: float = 60.0
    pwm: int = 255
    invert: bool = False
    mirror_x: bool = True
    mirror_y: bool = False
    rotation: int = 0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0


class ControlsPanel(tk.Frame):
    """Right sidebar with exposure and transform controls."""

    def __init__(
        self,
        parent: tk.Widget,
        on_change: Callable[[], None],
        **kwargs,
    ):
        super().__init__(parent, bg="#2b2b2b", **kwargs)
        self._on_change = on_change
        self.state = ControlState()

        # Tkinter variables
        self._printer_var = tk.StringVar(value=self.state.printer_name)
        self._exposure_var = tk.StringVar(value=str(self.state.exposure_s))
        self._pwm_var = tk.IntVar(value=self.state.pwm)
        self._invert_var = tk.BooleanVar(value=self.state.invert)
        self._mirror_x_var = tk.BooleanVar(value=self.state.mirror_x)
        self._mirror_y_var = tk.BooleanVar(value=self.state.mirror_y)
        self._rotation_var = tk.IntVar(value=self.state.rotation)
        self._offset_x_var = tk.StringVar(value=str(self.state.offset_x_mm))
        self._offset_y_var = tk.StringVar(value=str(self.state.offset_y_mm))

        self._gerber_widgets: list[tk.Widget] = []
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 3}
        section_pad = {"padx": 10, "pady": (15, 3)}
        label_opts = {"bg": "#2b2b2b", "fg": "#ccc", "anchor": "w", "font": ("Helvetica", 11)}
        header_opts = {"bg": "#2b2b2b", "fg": "#fff", "anchor": "w", "font": ("Helvetica", 12, "bold")}

        # Printer (always active)
        tk.Label(self, text="Printer", **header_opts).pack(fill=tk.X, **section_pad)
        printer_menu = ttk.Combobox(
            self, textvariable=self._printer_var,
            values=list_printers(), state="readonly", width=22,
        )
        printer_menu.pack(fill=tk.X, **pad)
        printer_menu.bind("<<ComboboxSelected>>", lambda _: self._notify())

        # --- Gerber-only controls (disabled in test pattern mode) ---

        # Exposure
        lbl = tk.Label(self, text="Exposure", **header_opts)
        lbl.pack(fill=tk.X, **section_pad)
        self._gerber_widgets.append(lbl)

        row = tk.Frame(self, bg="#2b2b2b")
        row.pack(fill=tk.X, **pad)
        lbl2 = tk.Label(row, text="Time (s):", **label_opts)
        lbl2.pack(side=tk.LEFT)
        exp_entry = tk.Entry(row, textvariable=self._exposure_var, width=8, justify=tk.RIGHT)
        exp_entry.pack(side=tk.RIGHT)
        exp_entry.bind("<Return>", lambda _: self._notify())
        exp_entry.bind("<FocusOut>", lambda _: self._notify())
        self._gerber_widgets.extend([lbl2, exp_entry])

        row2 = tk.Frame(self, bg="#2b2b2b")
        row2.pack(fill=tk.X, **pad)
        lbl3 = tk.Label(row2, text="PWM:", **label_opts)
        lbl3.pack(side=tk.LEFT)
        pwm_scale = tk.Scale(
            row2, from_=0, to=255, orient=tk.HORIZONTAL,
            variable=self._pwm_var, bg="#2b2b2b", fg="#ccc",
            highlightthickness=0, length=140,
            command=lambda _: self._notify(),
        )
        pwm_scale.pack(side=tk.RIGHT)
        self._gerber_widgets.extend([lbl3, pwm_scale])

        # Polarity
        lbl4 = tk.Label(self, text="Polarity", **header_opts)
        lbl4.pack(fill=tk.X, **section_pad)
        invert_cb = tk.Checkbutton(
            self, text="Invert (positive resist)",
            variable=self._invert_var, bg="#2b2b2b", fg="#ccc",
            selectcolor="#444", activebackground="#2b2b2b",
            command=self._notify,
        )
        invert_cb.pack(fill=tk.X, **pad)
        self._gerber_widgets.extend([lbl4, invert_cb])

        # Mirror
        lbl5 = tk.Label(self, text="Mirror", **header_opts)
        lbl5.pack(fill=tk.X, **section_pad)
        mirror_x_cb = tk.Checkbutton(
            self, text="Mirror X (horizontal)",
            variable=self._mirror_x_var, bg="#2b2b2b", fg="#ccc",
            selectcolor="#444", activebackground="#2b2b2b",
            command=self._notify,
        )
        mirror_x_cb.pack(fill=tk.X, **pad)
        mirror_y_cb = tk.Checkbutton(
            self, text="Mirror Y (vertical)",
            variable=self._mirror_y_var, bg="#2b2b2b", fg="#ccc",
            selectcolor="#444", activebackground="#2b2b2b",
            command=self._notify,
        )
        mirror_y_cb.pack(fill=tk.X, **pad)
        self._gerber_widgets.extend([lbl5, mirror_x_cb, mirror_y_cb])

        # Rotation
        lbl6 = tk.Label(self, text="Rotation", **header_opts)
        lbl6.pack(fill=tk.X, **section_pad)
        rot_frame = tk.Frame(self, bg="#2b2b2b")
        rot_frame.pack(fill=tk.X, **pad)
        self._gerber_widgets.append(lbl6)
        for deg in [0, 90, 180, 270]:
            rb = tk.Radiobutton(
                rot_frame, text=f"{deg}\u00b0",
                variable=self._rotation_var, value=deg,
                bg="#2b2b2b", fg="#ccc", selectcolor="#444",
                activebackground="#2b2b2b",
                command=self._notify,
            )
            rb.pack(side=tk.LEFT, padx=5)
            self._gerber_widgets.append(rb)

        # Offset
        lbl7 = tk.Label(self, text="Offset (mm)", **header_opts)
        lbl7.pack(fill=tk.X, **section_pad)
        self._gerber_widgets.append(lbl7)
        for label, var in [("X:", self._offset_x_var), ("Y:", self._offset_y_var)]:
            row = tk.Frame(self, bg="#2b2b2b")
            row.pack(fill=tk.X, **pad)
            lbl_xy = tk.Label(row, text=label, **label_opts)
            lbl_xy.pack(side=tk.LEFT)
            entry = tk.Entry(row, textvariable=var, width=8, justify=tk.RIGHT)
            entry.pack(side=tk.RIGHT)
            entry.bind("<Return>", lambda _: self._notify())
            entry.bind("<FocusOut>", lambda _: self._notify())
            self._gerber_widgets.extend([lbl_xy, entry])

    def _notify(self):
        """Read all variables into state and notify the callback."""
        try:
            self.state.printer_name = self._printer_var.get()
            self.state.exposure_s = float(self._exposure_var.get())
            self.state.pwm = self._pwm_var.get()
            self.state.invert = self._invert_var.get()
            self.state.mirror_x = self._mirror_x_var.get()
            self.state.mirror_y = self._mirror_y_var.get()
            self.state.rotation = self._rotation_var.get()
            self.state.offset_x_mm = float(self._offset_x_var.get())
            self.state.offset_y_mm = float(self._offset_y_var.get())
        except ValueError:
            return  # ignore invalid input while typing
        self._on_change()

    def set_test_pattern_mode(self, enabled: bool):
        """Disable gerber-only controls in test pattern mode, re-enable otherwise."""
        state = "disabled" if enabled else "normal"
        for widget in self._gerber_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass  # some widgets (e.g. Frame) don't support state

    def get_profile(self) -> PrinterProfile:
        return get_printer(self.state.printer_name)
