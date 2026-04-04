"""Tests for the .goo RLE encoder."""

import numpy as np
import pytest

from pcb2dlp.output_formats.goo import rle_encode, _calculate_checksum


def decode_rle(data: bytes) -> list[tuple[int, int]]:
    """Decode RLE data back to (length, value) runs for verification."""
    runs = []
    i = 0
    color = 0

    while i < len(data):
        head = data[i]
        chunk_type = head >> 6
        length_size = (head >> 4) & 0x03
        i += 1

        if chunk_type == 0b00:
            color = 0x00
        elif chunk_type == 0b11:
            color = 0xFF
        elif chunk_type == 0b01:
            color = data[i]
            i += 1
        elif chunk_type == 0b10:
            diff_sign = (head >> 5) & 1
            has_length = (head >> 4) & 1
            diff_value = head & 0x0F
            if diff_sign:
                color -= diff_value
            else:
                color += diff_value
            if has_length:
                length = data[i]
                i += 1
            else:
                length = 1
            runs.append((length, color))
            continue

        base = head & 0x0F
        length = base
        if length_size == 0b01:
            length += data[i] << 4
            i += 1
        elif length_size == 0b10:
            length += data[i] << 12
            i += 1
            length += data[i] << 4
            i += 1
        elif length_size == 0b11:
            length += data[i] << 20
            i += 1
            length += data[i] << 12
            i += 1
            length += data[i] << 4
            i += 1

        runs.append((length, color))

    return runs


def total_pixels(runs: list[tuple[int, int]]) -> int:
    return sum(length for length, _ in runs)


def reconstruct_bitmap(runs: list[tuple[int, int]], shape: tuple[int, int]) -> np.ndarray:
    """Reconstruct a bitmap from decoded RLE runs."""
    flat = []
    for length, value in runs:
        flat.extend([value] * length)
    return np.array(flat, dtype=np.uint8).reshape(shape)


class TestRLEEncode:
    def test_all_black(self):
        bitmap = np.zeros((10, 20), dtype=np.uint8)
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 200
        assert all(v == 0 for _, v in runs)

    def test_all_white(self):
        bitmap = np.full((10, 20), 255, dtype=np.uint8)
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 200
        assert all(v == 255 for _, v in runs)

    def test_alternating(self):
        bitmap = np.zeros((1, 10), dtype=np.uint8)
        bitmap[0, ::2] = 255  # [255, 0, 255, 0, ...]
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 10

    def test_roundtrip_simple(self):
        bitmap = np.zeros((20, 30), dtype=np.uint8)
        bitmap[5:15, 10:20] = 255  # white rectangle
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        result = reconstruct_bitmap(runs, bitmap.shape)
        np.testing.assert_array_equal(bitmap, result)

    def test_roundtrip_full_plate(self):
        """Test with full Mars 4 9K resolution."""
        bitmap = np.zeros((4320, 8520), dtype=np.uint8)
        bitmap[2000:2200, 4000:4500] = 255
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 4320 * 8520

    def test_small_runs(self):
        """Runs of length 1-15 should use 4-bit encoding (1 byte total)."""
        bitmap = np.zeros((1, 5), dtype=np.uint8)
        data = rle_encode(bitmap)
        # 5 black pixels: header byte only, no extra length bytes
        assert len(data) == 1
        assert data[0] == 0x05  # type=00, size=00, length=5

    def test_medium_runs(self):
        """Runs of length 16-4095 should use 12-bit encoding."""
        bitmap = np.zeros((1, 100), dtype=np.uint8)
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 100

    def test_large_runs(self):
        """Runs > 4095 should use 20-bit or 28-bit encoding."""
        bitmap = np.zeros((1, 100000), dtype=np.uint8)
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 100000

    def test_gray_value(self):
        bitmap = np.full((1, 10), 128, dtype=np.uint8)
        data = rle_encode(bitmap)
        runs = decode_rle(data)
        assert total_pixels(runs) == 10
        assert runs[0][1] == 128


class TestChecksum:
    def test_empty(self):
        assert _calculate_checksum(b"") == 0xFF

    def test_single_byte(self):
        assert _calculate_checksum(bytes([0x01])) == 0xFE

    def test_overflow(self):
        # Sum wraps: 0xFF + 0x01 = 0x00, ~0x00 = 0xFF
        assert _calculate_checksum(bytes([0xFF, 0x01])) == 0xFF

    def test_known_value(self):
        data = bytes([0x10, 0x20, 0x30])
        # sum = 0x60, ~0x60 = 0x9F
        assert _calculate_checksum(data) == 0x9F
