#!/usr/bin/env python3
"""Audit reviewed Lantern crop repairs against retained source and shipped pixels.

The exact sprite fingerprints freeze visually reviewed output; source checks
independently prove visible colors/alpha came from the retained source frame.
Requires Pillow only for development.
"""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'assets/tiles/lantern'
EXPECTED = {
    838: 'a53b3a23dc8f276fbf3c8e6dedc18cb6050c57e686e602d2d07fb56c5b7837c3',
    839: '213e3df44e6684acfc09e963aed546ee19bb3d6558824973a111bf934be70e77',
    843: 'c583ddf361609b88301077367c81879b2eeb9763fdfdce92f7318ee73d5c60b7',
    844: '2a398fdb448f6d574b40b25cb51ff7fbed52fd2d114b47621bf5a65c9e9df0e9',
    1234: '0c7e0a5fd7839a4cb46dab1a6a5e9802cfb73d6763053313ebcfb2b26b16a74d',
    1235: 'f4ae65908af18c5e803f1da973e6a82d36d112f1cc0eacd9e3778b47679696c5',
    1386: '42eb545264b699f11aa8c40f78953678f7b19fb502f90f7ea83512bae1a5e5d6',
    1387: '70790f35fb3f81566675ff2aa37f235181ae26cc7e6b594e410c88aff780dc01',
    1388: '9e8d2b4fd97707a9c557882f73c00621621e68de414c41f689a7eb720b89e49a',
    1389: '6ab76f49f39c59af4e09ef1c7aab481b858b2186622b77f5b8f5a67771a9713f',
}


def read(path):
    return json.loads(path.read_text())


def tile(atlas, slot):
    x, y = slot % 40 * 64, slot // 40 * 64
    return atlas.crop((x, y, x + 64, y + 64))


class CropRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read(HERE / 'sources.json')
        cls.catalog = read(HERE / 'catalog.json')['tiles']
        cls.sheets = {s['id']: s for s in cls.registry['sheets']}
        cls.entries = {t['id']: t for t in read(HERE.parent / 'manifest.json')['tilesets']
                       if t['id'] in ('lantern', 'lantern-modern')}
        cls.atlases = {key: Image.open(HERE.parent / e['file']).convert('RGBA')
                       for key, e in cls.entries.items()}

    def test_reviewed_pixels_and_shared_appearance_aliases(self):
        repaired_keys = {self.catalog[slot]['art_key'] for slot in EXPECTED}
        recorded_keys = {key for key, a in self.registry['art'].items() if a.get('extraction')}
        self.assertEqual(recorded_keys, repaired_keys)
        for reviewed_slot, sha in EXPECTED.items():
            key = self.catalog[reviewed_slot]['art_key']
            # Blue/black gem appearances also serve glass and stone appearances.
            for item in (t for t in self.catalog if t['art_key'] == key):
                for edition, atlas in self.atlases.items():
                    with self.subTest(edition=edition, slot=item['slot']):
                        sprite = tile(atlas, item['slot'])
                        self.assertEqual(hashlib.sha256(sprite.tobytes()).hexdigest(), sha)
                        self.assertNotIn(str(item['slot']),
                                         self.entries[edition]['projectedFrames']['frames'])

    def test_retained_source_frame_and_visible_pixels(self):
        for slot in EXPECTED:
            with self.subTest(slot=slot):
                assignment = self.registry['art'][self.catalog[slot]['art_key']]
                sheet = self.sheets[assignment['sheet']]
                path = HERE / sheet['file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sheet['sha256'])
                source = Image.open(path).convert('RGBA')
                x, y = assignment['column'], assignment['row']
                bounds = assignment['extraction'].get('sourceBounds',
                         [round(x*source.width/sheet['columns']), round(y*source.height/sheet['rows']),
                          round((x+1)*source.width/sheet['columns']), round((y+1)*source.height/sheet['rows'])])
                self.assertTrue(0 <= bounds[0] < bounds[2] <= source.width)
                self.assertTrue(0 <= bounds[1] < bounds[3] <= source.height)
                original = source.crop(bounds).resize((64, 64), Image.Resampling.NEAREST)
                sprite = tile(self.atlases['lantern'], slot)
                for py in range(64):
                    for px in range(64):
                        retained = sprite.getpixel((px, py))
                        if retained[3]:
                            self.assertEqual(retained, original.getpixel((px, py)),
                                             'Visible pixels must retain exact source RGBA')
                self.assertGreater(sum(a > 128 for a in sprite.getchannel('A').tobytes()), 500)
                # All confirmed lower-row fragments and shield backing are gone.
                self.assertIsNone(sprite.getchannel('A').crop((0, 58, 64, 64)).getbbox())
                if slot >= 1386:
                    alpha = sprite.getchannel('A')
                    for box in [(0, 0, 6, 64), (58, 0, 64, 64), (0, 0, 64, 3)]:
                        self.assertIsNone(alpha.crop(box).getbbox())
                    self.assertTrue(any(32 < a < 255 for a in alpha.tobytes()),
                                    'Original translucent shield detail remains')
                elif slot == 844:
                    self.assertLess(bounds[1], 940, 'Source frame must recover the original tip')
                    self.assertEqual(bounds[2] - bounds[0], bounds[3] - bounds[1],
                                     'Square extraction preserves the source sword proportions')
                    self.assertGreater(sprite.getchannel('A').crop((40, 0, 60, 7)).getbbox()[2], 0)


if __name__ == '__main__':
    unittest.main()
