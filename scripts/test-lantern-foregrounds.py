#!/usr/bin/env python3
"""Independent alpha-boundary checks for Lantern foreground extraction (Pillow)."""
import importlib.util
from pathlib import Path
import unittest
from PIL import Image, ImageDraw

path = Path(__file__).resolve().parents[1]/'assets/tiles/lantern/prepare_foregrounds.py'
spec = importlib.util.spec_from_file_location('lantern_foregrounds', path)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class ForegroundTests(unittest.TestCase):
    def test_only_exterior_studio_removed(self):
        image = Image.new('RGBA', (32, 32), (22, 34, 32, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 23, 23), fill=(0, 0, 0, 255))
        draw.rectangle((11, 11, 20, 20), fill=(22, 34, 32, 255))
        draw.rectangle((14, 14, 17, 17), fill=(120, 70, 25, 255))
        result, metrics = cleanup.clean_foreground(image, 'monster/test')
        self.assertEqual(result.getpixel((0, 0)), (22, 34, 32, 0))
        self.assertEqual(result.getpixel((8, 8)), (0, 0, 0, 255))
        self.assertEqual(result.getpixel((11, 11)), (22, 34, 32, 255))
        self.assertEqual(result.getpixel((15, 15)), (120, 70, 25, 255))
        self.assertGreater(metrics['enclosedCandidatePixels'], 0)

    def test_background_variation_not_black_gear(self):
        image = Image.new('RGBA', (32, 32), (22, 34, 32, 255))
        image.putpixel((0, 0), (23, 32, 33, 255))
        ImageDraw.Draw(image).rectangle((10, 0, 13, 25), fill=(3, 5, 4, 255))
        result, _ = cleanup.clean_foreground(image, 'object/test')
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((11, 0)), (3, 5, 4, 255))
        self.assertEqual(result.getpixel((11, 20)), (3, 5, 4, 255))

    def test_existing_alpha_and_color_preserved(self):
        image = Image.new('RGBA', (32, 32), (211, 90, 150, 0))
        image.putpixel((16, 16), (100, 80, 60, 128))
        image.putpixel((16, 17), (0, 0, 0, 255))
        result, _ = cleanup.clean_foreground(image, 'object/test')
        self.assertEqual(result.getpixel((0, 0)), (211, 90, 150, 0))
        self.assertEqual(result.getpixel((16, 16)), (100, 80, 60, 128))
        self.assertEqual(result.getpixel((16, 17)), (0, 0, 0, 255))

    def test_ground_and_walls_excluded(self):
        for key in ('monster/000-giant-ant', 'object/potion/ruby-potion',
                    'terrain/fountain', 'terrain/staircase-down', 'terrain/bear-trap'):
            self.assertTrue(cleanup.should_clean(key), key)
        for key in ('terrain/floor-of-a-room', 'terrain/water', 'terrain/main-walls-vertical',
                    'terrain/corridor', 'terrain/ice', 'effect/explosion-fiery'):
            self.assertFalse(cleanup.should_clean(key), key)


if __name__ == '__main__':
    unittest.main()
