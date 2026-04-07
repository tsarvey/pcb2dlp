# pcb2dlp

Convert PCB Gerber exports to DLP/MSLA 3D printer formats for single-layer photoresist exposure.

Currently supports:
- **Input:** Gerber (RS-274X) files
- **Output:** `.goo` format (Elegoo Mars series)
- **Printer:** Elegoo Mars 4 9K (8520×4320, 18µm pixel pitch, 405nm UV)

## Install

Requires Python 3.10+.

```bash
pip install -e .
```

If you get an error about Cairo when running, you need the Cairo C library (used for SVG rasterization):

```bash
brew install cairo              # macOS
sudo apt install libcairo2-dev  # Debian/Ubuntu
```

## Usage

### CLI

```bash
pcb2dlp convert input.gbr -o output.goo --exposure 45
```

Options:
| Flag | Default | Description |
|------|---------|-------------|
| `--exposure` | 60 | Exposure time in seconds |
| `--pwm` | 255 | UV LED power (0–255) |
| `--mirror-x` | **on** | Mirror horizontally (use `--no-mirror-x` to disable) |
| `--mirror-y` | **on** | Mirror vertically (use `--no-mirror-y` to disable) |
| `--invert` | off | Invert polarity (for positive photoresist) |
| `--rotation` | 0 | Rotate 0/90/180/270° |
| `--offset-x` | 0 | X offset from center (mm) |
| `--offset-y` | 0 | Y offset from center (mm) |
| `--printer` | Elegoo Mars 4 9K | Printer profile |

### GUI

```bash
pcb2dlp gui
```

Open a Gerber file, adjust exposure/mirror/rotation settings with live preview, then export to `.goo`.

## Workflow

1. Design your PCB in KiCAD
2. Export the copper layer as a Gerber file (File → Fabrication Outputs → Gerbers)
3. Convert to `.goo` with this tool
4. Load the `.goo` onto your printer via USB and expose your photoresist-coated board

## Adding printer support

Drop a `<printer>.toml` file into `src/pcb2dlp/printers/profiles/`. It is auto-discovered at import time — no Python edits required. See [elegoo_mars_4_9k.toml](src/pcb2dlp/printers/profiles/elegoo_mars_4_9k.toml) for the field list.

Only the Elegoo Mars 4 9K has exposure values verified for PCB photoresist. All other shipped profiles contain hardware specs only — `default_exposure_s`, `default_bottom_exposure_s`, and `default_pwm` are `None` and must be supplied at the CLI/GUI until you've calibrated them on your hardware. If you tune values for a printer, please contribute them back by editing the relevant TOML file.
