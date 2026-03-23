import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.application import calculate_aspect_ratio_fit


class AspectRatioPolicyTests(unittest.TestCase):
    def test_fit_width_keeps_original_ratio(self) -> None:
        result = calculate_aspect_ratio_fit(1200, 800, mode="fit_width", viewport_width=600)

        self.assertEqual(result["width"], 600)
        self.assertEqual(result["height"], 400)
        self.assertEqual(result["aspect_ratio"], 1.5)

    def test_fit_height_keeps_original_ratio(self) -> None:
        result = calculate_aspect_ratio_fit(1200, 800, mode="fit_height", viewport_height=200)

        self.assertEqual(result["width"], 300)
        self.assertEqual(result["height"], 200)
        self.assertEqual(result["aspect_ratio"], 1.5)

    def test_percent_zoom_keeps_original_ratio(self) -> None:
        result = calculate_aspect_ratio_fit(640, 360, mode="200%")

        self.assertEqual(result["width"], 1280)
        self.assertEqual(result["height"], 720)
        self.assertEqual(result["aspect_ratio"], round(640 / 360, 6))


if __name__ == "__main__":
    unittest.main()
