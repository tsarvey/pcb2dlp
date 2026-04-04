"""CLI and GUI entry point for pcb2dlp."""

import argparse
import sys
from pathlib import Path

from .input_formats import get_format_for_file
from .output_formats import ExposureParams
from .output_formats.goo import GooOutput
from .printers import get_printer, list_printers
from .rasterizer import PlacementConfig, rasterize_svg


def cli_convert(args: argparse.Namespace) -> None:
    """Run the CLI conversion pipeline."""
    input_path = Path(args.input)
    output_path = Path(args.output)
    profile = get_printer(args.printer)

    print(f"Loading {input_path.name}...")
    fmt = get_format_for_file(input_path)
    fmt.load(input_path)

    board_size = fmt.board_size_mm()
    print(f"Board size: {board_size[0]:.2f} x {board_size[1]:.2f} mm")

    placement = PlacementConfig(
        offset_x_mm=args.offset_x,
        offset_y_mm=args.offset_y,
        rotation_deg=args.rotation,
        mirror_x=args.mirror_x,
        mirror_y=args.mirror_y,
        invert=args.invert,
    )

    print("Rasterizing...")
    svg = fmt.to_svg()
    bitmap = rasterize_svg(svg, board_size, profile, placement)

    white_pixels = (bitmap == 255).sum()
    total_pixels = bitmap.size
    print(f"Exposure area: {white_pixels / total_pixels * 100:.1f}% of build plate")

    params = ExposureParams(
        exposure_time_s=args.exposure,
        bottom_exposure_time_s=args.exposure,
        light_pwm=args.pwm,
    )

    print(f"Writing {output_path.name}...")
    writer = GooOutput()
    writer.write(output_path, bitmap, profile, params)
    print(f"Done. Exposure time: {args.exposure}s, PWM: {args.pwm}")


def main():
    parser = argparse.ArgumentParser(
        prog="pcb2dlp",
        description="Convert PCB Gerber files to MSLA 3D printer formats for photoresist exposure",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Convert command
    convert = subparsers.add_parser("convert", help="Convert a Gerber file to .goo")
    convert.add_argument("input", help="Input Gerber file path")
    convert.add_argument("-o", "--output", required=True, help="Output .goo file path")
    convert.add_argument("--printer", default="Elegoo Mars 4 9K", choices=list_printers(), help="Printer profile")
    convert.add_argument("--exposure", type=float, default=60.0, help="Exposure time in seconds (default: 60)")
    convert.add_argument("--pwm", type=int, default=255, help="Light PWM 0-255 (default: 255)")
    convert.add_argument("--mirror-x", action="store_true", help="Mirror horizontally")
    convert.add_argument("--mirror-y", action="store_true", help="Mirror vertically")
    convert.add_argument("--invert", action="store_true", help="Invert polarity (for positive photoresist)")
    convert.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, 270], help="Rotation in degrees")
    convert.add_argument("--offset-x", type=float, default=0.0, help="X offset from center in mm")
    convert.add_argument("--offset-y", type=float, default=0.0, help="Y offset from center in mm")

    # GUI command
    subparsers.add_parser("gui", help="Launch the graphical interface")

    args = parser.parse_args()

    if args.command == "convert":
        cli_convert(args)
    elif args.command == "gui":
        from .gui.app import run_gui
        run_gui()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
