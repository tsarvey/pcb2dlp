"""Verify .goo file structural integrity by reading it back."""

import struct
from pathlib import Path

from .goo import (
    MAGIC_TAG,
    DELIMITER,
    ENDING_STRING,
    HEADER_SIZE,
    SMALL_PREVIEW_SIZE,
    BIG_PREVIEW_SIZE,
    RLE_MAGIC,
    _calculate_checksum,
)


class GooVerifyError(Exception):
    pass


def verify_goo(path: Path, expected_pixels: tuple[int, int] | None = None) -> dict:
    """Read and verify a .goo file. Returns parsed metadata.

    Args:
        path: Path to the .goo file.
        expected_pixels: Optional (x_pixels, y_pixels) to check resolution.

    Raises:
        GooVerifyError on any structural problem.
    """
    data = path.read_bytes()
    errors = []

    def check(condition: bool, msg: str):
        if not condition:
            errors.append(msg)

    # --- Header ---
    check(len(data) > HEADER_SIZE + len(ENDING_STRING),
          f"File too small: {len(data)} bytes (header alone is {HEADER_SIZE})")

    pos = 0

    # Version
    version = data[pos:pos + 4].rstrip(b"\x00").decode("ascii", errors="replace")
    check(version == "V3.0", f"Unexpected version: {version!r}")
    pos += 4

    # Magic
    check(data[pos:pos + 8] == MAGIC_TAG, "Magic tag mismatch")
    pos += 8

    # Software info, version, time, printer name, type, profile
    software = data[pos:pos + 32].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 32
    sw_version = data[pos:pos + 24].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 24
    file_time = data[pos:pos + 24].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 24
    printer_name = data[pos:pos + 32].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 32
    printer_type = data[pos:pos + 32].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 32
    profile_name = data[pos:pos + 32].rstrip(b"\x00").decode("ascii", errors="replace")
    pos += 32

    # AA, grey, blur
    aa, grey, blur = struct.unpack_from(">HHH", data, pos)
    pos += 6

    # Small preview
    pos += SMALL_PREVIEW_SIZE
    check(data[pos:pos + 2] == DELIMITER, f"Missing delimiter after small preview at {pos}")
    pos += 2

    # Big preview
    pos += BIG_PREVIEW_SIZE
    check(data[pos:pos + 2] == DELIMITER, f"Missing delimiter after big preview at {pos}")
    pos += 2

    # Total layers
    total_layers = struct.unpack_from(">I", data, pos)[0]
    check(total_layers >= 1, f"total_layers is {total_layers}, expected >= 1")
    pos += 4

    # Resolution
    x_res, y_res = struct.unpack_from(">HH", data, pos)
    pos += 4
    if expected_pixels:
        check(x_res == expected_pixels[0], f"x_res {x_res} != expected {expected_pixels[0]}")
        check(y_res == expected_pixels[1], f"y_res {y_res} != expected {expected_pixels[1]}")

    # Mirrors
    pos += 2

    # X/Y/Z size, layer thickness
    x_mm, y_mm, z_mm = struct.unpack_from(">fff", data, pos)
    pos += 12
    layer_thickness = struct.unpack_from(">f", data, pos)[0]
    pos += 4

    # Exposure time
    exposure_time = struct.unpack_from(">f", data, pos)[0]
    pos += 4

    # Exposure delay mode
    exposure_delay_mode = data[pos]
    pos += 1

    # Turn off time
    pos += 4

    # 6 timing floats (bottom_before/after_lift/retract, normal_before/after_lift/retract)
    pos += 24

    # Bottom exposure time, bottom layers
    bottom_exposure = struct.unpack_from(">f", data, pos)[0]
    pos += 4
    bottom_layers = struct.unpack_from(">I", data, pos)[0]
    pos += 4

    # 16 lift/retract floats
    pos += 64

    # PWM
    bottom_pwm, light_pwm = struct.unpack_from(">HH", data, pos)
    pos += 4

    # Advance mode
    pos += 1

    # Printing time
    pos += 4

    # Volume, weight, price
    pos += 12

    # Price unit
    pos += 8

    # Layer content offset
    layer_offset = struct.unpack_from(">I", data, pos)[0]
    check(layer_offset == HEADER_SIZE,
          f"Layer offset {layer_offset} != HEADER_SIZE {HEADER_SIZE}")
    pos += 4

    # Grey scale level, transition layers
    pos += 3

    check(pos == HEADER_SIZE,
          f"Header parse ended at {pos}, expected {HEADER_SIZE}")

    # --- Layers ---
    layer_info = []
    pos = HEADER_SIZE

    for layer_idx in range(total_layers):
        layer_start = pos
        check(pos + 60 < len(data), f"Layer {layer_idx}: truncated layer header at {pos}")
        if pos + 60 >= len(data):
            break

        # Pause flag (u16) + pause pos z (f32)
        pos += 6
        # Layer position Z
        layer_z = struct.unpack_from(">f", data, pos)[0]
        pos += 4
        # Exposure time
        layer_exposure = struct.unpack_from(">f", data, pos)[0]
        pos += 4
        # Layer off time
        pos += 4
        # 3 timing floats
        pos += 12
        # 4 lift/retract pairs (8 floats)
        pos += 32
        # PWM
        layer_pwm = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        # Delimiter
        check(data[pos:pos + 2] == DELIMITER,
              f"Layer {layer_idx}: missing delimiter at {pos}")
        pos += 2
        # Data length
        data_length = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        check(data_length >= 2, f"Layer {layer_idx}: data_length {data_length} < 2")

        # RLE magic
        check(data[pos] == RLE_MAGIC,
              f"Layer {layer_idx}: RLE magic {data[pos]:#x} != {RLE_MAGIC:#x}")
        pos += 1

        # RLE data + checksum
        rle_size = data_length - 2  # minus magic and checksum
        rle_data = data[pos:pos + rle_size]
        pos += rle_size

        # Checksum
        expected_checksum = _calculate_checksum(rle_data)
        actual_checksum = data[pos]
        check(actual_checksum == expected_checksum,
              f"Layer {layer_idx}: checksum {actual_checksum:#x} != expected {expected_checksum:#x}")
        pos += 1

        # Delimiter after layer
        check(data[pos:pos + 2] == DELIMITER,
              f"Layer {layer_idx}: missing trailing delimiter at {pos}")
        pos += 2

        layer_info.append({
            "index": layer_idx,
            "z_mm": layer_z,
            "exposure_s": layer_exposure,
            "pwm": layer_pwm,
            "rle_bytes": len(rle_data),
        })

    # Ending string
    check(data[pos:pos + len(ENDING_STRING)] == ENDING_STRING,
          f"Missing ending string at {pos}")
    check(pos + len(ENDING_STRING) == len(data),
          f"Extra data after ending string: {len(data) - pos - len(ENDING_STRING)} bytes")

    metadata = {
        "version": version,
        "software": software,
        "printer": printer_name,
        "resolution": (x_res, y_res),
        "build_area_mm": (x_mm, y_mm, z_mm),
        "layer_thickness_mm": layer_thickness,
        "exposure_time_s": exposure_time,
        "bottom_exposure_s": bottom_exposure,
        "bottom_layers": bottom_layers,
        "light_pwm": light_pwm,
        "total_layers": total_layers,
        "layers": layer_info,
    }

    if errors:
        raise GooVerifyError(
            f"{len(errors)} error(s) in {path.name}:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    return metadata
