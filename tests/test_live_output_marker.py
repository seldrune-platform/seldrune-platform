"""Marker placement and pixel checks for the outbound WebRTC video boundary."""

import unittest

from PIL import Image

from services.live_media.output_marker import MarkerPosition, burn_marker, marker_bounds


class OutputMarkerTests(unittest.TestCase):
    def test_position_is_bounded_and_session_value_is_immutable(self):
        top_right = MarkerPosition(1, 0)
        bottom_left = MarkerPosition(0, 1)
        self.assertEqual(marker_bounds(1280, 720, top_right), (925, 9, 1271, 46))
        self.assertEqual(marker_bounds(1280, 720, bottom_left), (9, 674, 355, 711))
        with self.assertRaises(ValueError):
            MarkerPosition(1.01, 0)
        with self.assertRaises(ValueError):
            MarkerPosition(float("nan"), 0)
        with self.assertRaises(Exception):
            top_right.x = 0

    def test_marker_is_in_returned_pixels_and_source_stays_unmodified(self):
        original = Image.new("RGB", (1280, 720), (70, 90, 110))
        position = MarkerPosition(0.4, 0.6)
        returned = burn_marker(original, position)
        left, top, right, bottom = marker_bounds(*returned.size, position)
        self.assertEqual(original.getpixel((left + 10, top + 10)), (70, 90, 110))
        self.assertNotEqual(returned.getpixel((left + 10, top + 10)), (70, 90, 110))
        self.assertEqual(returned.getpixel((0, 0)), (70, 90, 110))
        self.assertLess(right, returned.width)
        self.assertLess(bottom, returned.height)


if __name__ == "__main__":
    unittest.main()
