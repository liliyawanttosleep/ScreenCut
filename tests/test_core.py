import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from screencut.core import Stitcher, load_settings, save_settings
from screencut.i18n import LANGUAGES, ROWS
from screencut.native import parse_hotkey

class CoreTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.page = rng.integers(0, 256, (2400, 500, 3), dtype=np.uint8)

    def test_scroll_exact_reconstruction(self):
        stitch = Stitcher(self.page[:600])
        for offset in (150, 330, 600, 850, 1100, 1400, 1700, 1800):
            status, shift = stitch.append(self.page[offset:offset+600])
            self.assertEqual(status, "added")
        np.testing.assert_array_equal(stitch.image(), self.page)

    def test_duplicate_rejected(self):
        stitch = Stitcher(self.page[:600])
        self.assertEqual(stitch.append(self.page[:600]), ("unchanged", 0))

    def test_jump_and_reverse_rejected(self):
        stitch = Stitcher(self.page[300:900])
        self.assertNotEqual(stitch.append(self.page[100:700])[0], "added")
        self.assertNotEqual(stitch.append(self.page[1500:2100])[0], "added")
        self.assertEqual(stitch.height, 600)

    def test_size_cap(self):
        stitch = Stitcher(self.page[:600], max_pixels=600*500)
        self.assertEqual(stitch.append(self.page[100:700])[0], "limit")

    def test_repeated_content_is_ambiguous(self):
        tile = self.page[:60]
        page = np.tile(tile, (20, 1, 1))
        stitch = Stitcher(page[:600])
        self.assertEqual(stitch.append(page[30:630])[0], "ambiguous")

    def test_text_document(self):
        page = np.full((2400, 700, 3), 248, dtype=np.uint8)
        for i in range(55):
            cv2.putText(page, f"Row {i:02d}: ScreenCut sample {i*i+17}", (25, 40+i*42),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, (30, 40, 50), 1, cv2.LINE_AA)
        stitch = Stitcher(page[:600])
        self.assertEqual(stitch.append(page[180:780])[0], "added")
        np.testing.assert_array_equal(stitch.image(), page[:780])

    def test_settings_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings = load_settings(path)
            settings["language"] = "ja"
            settings["hotkeys"]["copy"] = "Ctrl+Shift+C"
            save_settings(settings, path)
            self.assertEqual(load_settings(path), settings)
            path.write_text("broken", encoding="utf-8")
            self.assertEqual(load_settings(path)["language"], "zh")

    def test_translations(self):
        for key, values in ROWS.items():
            self.assertEqual(len(values), len(LANGUAGES), key)
            self.assertTrue(all(values), key)

    def test_hotkey_validation(self):
        self.assertEqual(parse_hotkey("Alt+C"), (1, 67))
        self.assertEqual(parse_hotkey("Ctrl+Shift+F8"), (6, 119))
        self.assertIsNone(parse_hotkey(""))
        for text in ("C", "Ctrl+F12", "Alt+Space", "Ctrl+!"):
            with self.assertRaises(ValueError):
                parse_hotkey(text)

if __name__ == "__main__":
    unittest.main()
