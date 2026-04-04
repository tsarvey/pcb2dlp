"""Elegoo .goo file format writer with RLE encoder."""

import struct
import time
from pathlib import Path

import numpy as np

from ..printers import PrinterProfile
from . import ExposureParams, OutputFormat

# Constants from the reference implementation
MAGIC_TAG = bytes([0x07, 0x00, 0x00, 0x00, 0x44, 0x4C, 0x50, 0x00])
DELIMITER = bytes([0x0D, 0x0A])
ENDING_STRING = bytes([0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x44, 0x4C, 0x50, 0x00])
RLE_MAGIC = 0x55

# Preview image sizes (RGB565, 2 bytes per pixel)
SMALL_PREVIEW_SIZE = 116 * 116 * 2  # 26912 bytes
BIG_PREVIEW_SIZE = 290 * 290 * 2  # 168200 bytes

# Header size (fixed) - computed from the struct layout
# version(4) + magic(8) + software_info(32) + software_version(24) + file_time(24) +
# printer_name(32) + printer_type(32) + profile_name(32) +
# anti_aliasing(2) + grey_level(2) + blur_level(2) +
# small_preview(26912) + delimiter(2) + big_preview(168200) + delimiter(2) +
# total_layers(4) + x_res(2) + y_res(2) + x_mirror(1) + y_mirror(1) +
# x_size(4) + y_size(4) + z_size(4) + layer_thickness(4) +
# exposure_time(4) + exposure_delay_mode(1) + turn_off_time(4) +
# 7 floats(28) + bottom_exposure_time(4) + bottom_layers(4) +
# 16 floats(64) +
# bottom_light_pwm(2) + light_pwm(2) + advance_mode(1) +
# printing_time(4) + total_volume(4) + total_weight(4) + total_price(4) +
# price_unit(8) + offset_of_layer_content(4) + grey_scale_level(1) + transition_layers(2)
HEADER_SIZE = (
    4 + 8 + 32 + 24 + 24 + 32 + 32 + 32  # strings
    + 2 + 2 + 2  # u16 fields
    + SMALL_PREVIEW_SIZE + 2  # small preview + delimiter
    + BIG_PREVIEW_SIZE + 2  # big preview + delimiter
    + 4 + 2 + 2 + 1 + 1  # total_layers, resolutions, mirrors
    + 4 + 4 + 4 + 4  # x/y/z size, layer_thickness
    + 4 + 1 + 4  # exposure_time, exposure_delay_mode, turn_off_time
    + 4 * 7  # bottom_before_lift_time through after_retract_time
    + 4 + 4  # bottom_exposure_time, bottom_layers
    + 4 * 16  # lift/retract distances and speeds
    + 2 + 2 + 1  # pwm values, advance_mode
    + 4 + 4 + 4 + 4  # printing_time, volume, weight, price
    + 8  # price_unit
    + 4 + 1 + 2  # offset_of_layer_content, grey_scale_level, transition_layers
)


def _sized_string(s: str, size: int) -> bytes:
    """Encode a string into a fixed-size null-padded byte field."""
    encoded = s.encode("utf-8")[:size]
    return encoded.ljust(size, b"\x00")


def rle_encode(bitmap: np.ndarray) -> bytes:
    """RLE-encode a bitmap for the .goo format."""
    flat = bitmap.flatten()
    data = bytearray()
    i = 0
    total = len(flat)

    while i < total:
        value = flat[i]
        run_start = i
        while i < total and flat[i] == value:
            i += 1
        length = i - run_start

        if value == 0x00:
            chunk_type = 0b00
        elif value == 0xFF:
            chunk_type = 0b11
        else:
            chunk_type = 0b01

        while length > 0:
            run = min(length, 0xFFFFFFF)
            length -= run
            _encode_run(data, chunk_type, run, value)

    return bytes(data)


def _encode_run(data: bytearray, chunk_type: int, length: int, value: int) -> None:
    """Encode a single RLE run. Matches the Rust reference encoder exactly."""
    # Determine how many extra bytes needed for the length
    if length <= 0xF:
        length_size = 0b00
    elif length <= 0xFFF:
        length_size = 0b01
    elif length <= 0xFFFFF:
        length_size = 0b10
    else:
        length_size = 0b11

    # Header byte: chunk_type(2) | length_size(2) | base_length(4)
    header = (chunk_type << 6) | (length_size << 4) | (length & 0x0F)
    data.append(header)

    # Gray value byte follows header for type 0b01
    if chunk_type == 0b01:
        data.append(value)

    # Extra length bytes, written HIGH to LOW matching the Rust encoder:
    # size 1: [(length >> 4)]
    # size 2: [(length >> 12), (length >> 4)]
    # size 3: [(length >> 20), (length >> 12), (length >> 4)]
    if length_size == 0b01:
        data.append((length >> 4) & 0xFF)
    elif length_size == 0b10:
        data.append((length >> 12) & 0xFF)
        data.append((length >> 4) & 0xFF)
    elif length_size == 0b11:
        data.append((length >> 20) & 0xFF)
        data.append((length >> 12) & 0xFF)
        data.append((length >> 4) & 0xFF)


def _calculate_checksum(data: bytes) -> int:
    """Calculate the .goo RLE checksum: bitwise NOT of the wrapping byte sum."""
    total = 0
    for b in data:
        total = (total + b) & 0xFF
    return (~total) & 0xFF


def _write_header(
    f,
    profile: PrinterProfile,
    params: ExposureParams,
    total_layers: int = 1,
) -> None:
    """Write the .goo file header."""
    # Version
    f.write(_sized_string("V3.0", 4))
    # Magic
    f.write(MAGIC_TAG)
    # Software info
    f.write(_sized_string("pcb2dlp", 32))
    # Software version
    f.write(_sized_string("0.1.0", 24))
    # File time
    f.write(_sized_string(time.strftime("%Y-%m-%d %H:%M:%S"), 24))
    # Printer name
    f.write(_sized_string(profile.name, 32))
    # Printer type
    f.write(_sized_string(profile.name, 32))
    # Profile name
    f.write(_sized_string("PCB Exposure", 32))
    # Anti-aliasing, grey level, blur level
    f.write(struct.pack(">HHH", 1, 0, 0))
    # Small preview (black)
    f.write(b"\x00" * SMALL_PREVIEW_SIZE)
    # Delimiter
    f.write(DELIMITER)
    # Big preview (black)
    f.write(b"\x00" * BIG_PREVIEW_SIZE)
    # Delimiter
    f.write(DELIMITER)
    # Total layers
    f.write(struct.pack(">I", total_layers))
    # X/Y resolution
    f.write(struct.pack(">HH", profile.x_pixels, profile.y_pixels))
    # X/Y mirror (bools as u8)
    f.write(struct.pack(">BB", 0, 0))
    # X/Y/Z size in mm
    f.write(struct.pack(">fff", profile.build_area_x_mm, profile.build_area_y_mm, profile.build_area_z_mm))
    # Layer thickness
    f.write(struct.pack(">f", params.layer_thickness_mm))
    # Common exposure time
    f.write(struct.pack(">f", params.exposure_time_s))
    # Exposure delay mode
    f.write(struct.pack(">B", 0))
    # Turn off time
    f.write(struct.pack(">f", 0.0))
    # bottom_before_lift_time, bottom_after_lift_time, bottom_after_retract_time
    f.write(struct.pack(">fff", 0.0, 0.0, 0.0))
    # before_lift_time, after_lift_time, after_retract_time
    f.write(struct.pack(">fff", 0.0, 0.0, 0.0))
    # Bottom exposure time
    f.write(struct.pack(">f", params.bottom_exposure_time_s))
    # Bottom layers
    f.write(struct.pack(">I", 1))
    # bottom_lift_distance, bottom_lift_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # lift_distance, lift_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # bottom_retract_distance, bottom_retract_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # retract_distance, retract_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # bottom_second_lift_distance, bottom_second_lift_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # second_lift_distance, second_lift_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # bottom_second_retract_distance, bottom_second_retract_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # second_retract_distance, second_retract_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # Bottom light PWM, light PWM
    f.write(struct.pack(">HH", params.light_pwm, params.light_pwm))
    # Advance mode
    f.write(struct.pack(">B", 0))
    # Printing time (seconds)
    f.write(struct.pack(">I", int(params.exposure_time_s * total_layers)))
    # Total volume, weight, price
    f.write(struct.pack(">fff", 0.0, 0.0, 0.0))
    # Price unit
    f.write(_sized_string("$", 8))
    # Offset of layer content (= header size)
    f.write(struct.pack(">I", HEADER_SIZE))
    # Grey scale level
    f.write(struct.pack(">B", 0))
    # Transition layers
    f.write(struct.pack(">H", 0))


def _write_layer(
    f,
    rle_data: bytes,
    params: ExposureParams,
    layer_pos_z: float = 0.05,
) -> None:
    """Write a single layer content block."""
    # Pause flag
    f.write(struct.pack(">H", 0))
    # Pause position Z
    f.write(struct.pack(">f", 0.0))
    # Layer position Z
    f.write(struct.pack(">f", layer_pos_z))
    # Layer exposure time
    f.write(struct.pack(">f", params.exposure_time_s))
    # Layer off time
    f.write(struct.pack(">f", 0.0))
    # before_lift_time, after_lift_time, after_retract_time
    f.write(struct.pack(">fff", 0.0, 0.0, 0.0))
    # lift_distance, lift_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # second_lift_distance, second_lift_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # retract_distance, retract_speed
    f.write(struct.pack(">ff", 5.0, 3.0))
    # second_retract_distance, second_retract_speed
    f.write(struct.pack(">ff", 0.0, 0.0))
    # Light PWM
    f.write(struct.pack(">H", params.light_pwm))
    # Delimiter
    f.write(DELIMITER)
    # Data length (magic byte + rle data + checksum byte = len + 2)
    f.write(struct.pack(">I", len(rle_data) + 2))
    # RLE magic byte
    f.write(bytes([RLE_MAGIC]))
    # RLE encoded data
    f.write(rle_data)
    # Checksum
    f.write(bytes([_calculate_checksum(rle_data)]))
    # Delimiter
    f.write(DELIMITER)


class GooOutput(OutputFormat):
    name = "goo"
    file_extension = ".goo"

    def write(
        self,
        path: Path,
        bitmap: np.ndarray,
        profile: PrinterProfile,
        params: ExposureParams,
    ) -> None:
        rle_data = rle_encode(bitmap)

        with open(path, "wb") as f:
            _write_header(f, profile, params, total_layers=1)
            _write_layer(f, rle_data, params)
            f.write(ENDING_STRING)
