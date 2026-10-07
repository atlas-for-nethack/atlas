#!/usr/bin/env python3
"""Check transparent Lantern fixtures against retained art and shipped atlases.

Run with a Python environment containing Pillow. Current source, packing and
floor transparency checks do not depend on historical whole-atlas captures.
"""
import hashlib
import json
from pathlib import Path
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / 'assets/tiles'
LANTERN = TILES / 'lantern'
SOURCES = LANTERN / 'production-sources/transparent-fixtures'
EXPECTED = {872, 873, 874, 875, 1325, 1326, 1327, 1333}
BOWS = {872, 873, 874, 875}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tile(image, slot):
    x, y = slot % 40 * 64, slot // 40 * 64
    return image.crop((x, y, x + 64, y + 64))


def clear_fraction(image, bounds):
    alpha = image.getchannel('A').crop(bounds).tobytes()
    return alpha.count(0) / len(alpha)


class TransparentFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = read(SOURCES / 'sources.json')
        cls.records = cls.evidence['sources']
        cls.overrides = read(LANTERN / 'production-overrides.json')
        cls.catalog = {t['slot']: t for t in read(LANTERN / 'catalog.json')['tiles']}
        manifest = read(TILES / 'manifest.json')['tilesets']
        cls.entries = {t['id']: t for t in manifest if t['id'] in ('lantern', 'lantern-modern')}
        cls.images = {key: Image.open(TILES / entry['file']).convert('RGBA')
                      for key, entry in cls.entries.items()}

    def test_retained_sources_and_registered_overrides(self):
        slots = [slot for record in self.records for slot in record['slots']]
        self.assertEqual(set(slots), EXPECTED)
        self.assertEqual(len(slots), len(EXPECTED), 'Each repaired slot has one source record')
        self.assertEqual(self.evidence['license'], 'CC-BY-4.0')
        self.assertEqual(self.evidence['credit'], 'NetHack Atlas project')
        for record in self.records:
            with self.subTest(art_key=record['art_key']):
                for filename, sha in [('source', 'sourceSha256'), ('file', 'sha256')]:
                    path = SOURCES / record[filename]
                    self.assertTrue(path.resolve().is_relative_to(SOURCES.resolve()))
                    self.assertEqual(digest(path), record[sha], str(path))
                    with Image.open(path) as image:
                        image.verify()
                override = self.overrides[record['art_key']]
                self.assertEqual((LANTERN / override['file']).resolve(),
                                 (SOURCES / record['file']).resolve())
                self.assertEqual(override['sha256'], record['sha256'])
                for slot in record['slots']:
                    self.assertEqual(self.catalog[slot]['art_key'], record['art_key'])

    def test_repaired_pixels_are_shipped_identically_in_both_editions(self):
        for record in self.records:
            with Image.open(SOURCES / record['file']) as opened:
                self.assertEqual(opened.size, (64, 64))
                self.assertEqual(opened.mode, 'RGBA', record['file'])
                pixels = opened.tobytes()
            for slot in record['slots']:
                for edition, atlas in self.images.items():
                    with self.subTest(slot=slot, edition=edition):
                        self.assertEqual(tile(atlas, slot).tobytes(), pixels)
                        self.assertNotIn(str(slot), self.entries[edition]
                                         .get('projectedFrames', {}).get('frames', {}),
                                         'A projected frame must not bypass the corrected tile')

    def test_floor_can_show_through_without_losing_the_object(self):
        for slot in sorted(EXPECTED):
            with self.subTest(slot=slot):
                image = tile(self.images['lantern'], slot)
                alpha = image.getchannel('A').tobytes()
                # Transparent margins alone do not solve an opaque internal plate.
                # Old traps were almost solid inside this 48px square; the old
                # bow interiors were solid within the central 16px square.
                bounds = (24, 24, 40, 40) if slot in BOWS else (8, 8, 56, 56)
                self.assertGreater(clear_fraction(image, bounds), .20,
                                   'Floor remains obscured inside the former backing')
                self.assertGreater(sum(a >= 128 for a in alpha), 60,
                                   'An empty or nearly invisible sprite is not a repair')
                self.assertGreater(alpha.count(0), 512,
                                   'Fixture should expose surrounding floor')

    def test_current_floors_show_through_repaired_fixtures(self):
        # Historical before-* captures predate approved Mines walls and packed
        # regional additions. Their atlas dimensions/pixels cannot gate current
        # fixture transparency. Check the actual compositing invariant instead.
        for edition, atlas in self.images.items():
            floors = [1291, 1292, 1293, 1294]
            mines = self.entries[edition]['regionalMaterials']['mines']['tileMap']
            floors += [mines[str(slot)] for slot in floors]
            for floor_slot in set(floors):
                floor = tile(atlas, floor_slot)
                for slot in EXPECTED:
                    with self.subTest(edition=edition, floor=floor_slot, fixture=slot):
                        sprite = tile(atlas, slot)
                        composite = Image.alpha_composite(floor, sprite)
                        clear = [i for i, a in enumerate(sprite.getchannel('A').tobytes()) if a == 0]
                        self.assertGreater(len(clear), 512)
                        raw, displayed = floor.tobytes(), composite.tobytes()
                        self.assertTrue(all(raw[4*i:4*i+4] == displayed[4*i:4*i+4] for i in clear))
                        self.assertNotEqual(raw, displayed, 'Fixture remains visible on the floor')


if __name__ == '__main__':
    unittest.main()
