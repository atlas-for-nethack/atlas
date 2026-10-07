#!/usr/bin/env python3
"""Verify approved regional art, preserved canonical surfaces and edition parity."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image, ImageDraw, ImageEnhance, ImageStat

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / 'assets/tiles'
REGIONS = {'mines': 1471, 'gehennom': 1482}
FAMILIES = [('lantern', 'lantern', 'lantern-modern'),
            ('soot-and-brass', 'soot-and-brass-classic', 'soot-and-brass')]
# Captured before the approved canonical Mines wall replacement, October 1.
# Floors, main walls and Gehennom walls must retain their existing pixels.
BASELINE_SLOTS = [1284, *range(1291, 1297), *range(1273, 1284), *range(1482, 1493)]
BASELINE_HASHES = {
    'lantern': '18e51b72a4bf7c50422ef700ee4b11244e94c98eb6394888c150144c8a111908',
    'soot-and-brass': '8abaf1a3b8453ea907adf5ceb59510e80cb9e4dfb393565d9f2b37b0b067c212',
}


def read(path):
    return json.loads(path.read_text())


class RegionalMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlases = {a['id']: a for a in read(TILES / 'manifest.json')['tilesets']}
        cls.images = {}

    def image(self, atlas):
        if atlas['file'] not in self.images:
            with Image.open(TILES / atlas['file']) as image:
                self.images[atlas['file']] = image.convert('RGBA')
        return self.images[atlas['file']]

    def pixels(self, atlas, slot):
        x, y = slot % 40 * 64, slot // 40 * 64
        return self.image(atlas).crop((x, y, x + 64, y + 64)).tobytes()

    def frame_pixels(self, atlas, frame):
        x, y, w, h = frame['source']
        return self.image(atlas).crop((x, y, x + w, y + h)).tobytes()

    def source(self, family, region):
        sources = read(TILES / 'regions' / region / 'sources.json')
        record = sources['sources'][family]
        path = TILES / 'regions' / region / record['file']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['sha256'])
        with Image.open(path) as image:
            return image.convert('RGBA')

    def test_approved_floors_and_visible_engraving(self):
        for family, classic, _ in FAMILIES:
            atlas = self.atlases[classic]
            floors = {}
            for region in REGIONS:
                with self.subTest(family=family, region=region):
                    mapping = atlas['regionalMaterials'][region]['tileMap']
                    floor = self.source(family, region).crop((521, 217, 606, 288)).resize(
                        (64, 64), Image.Resampling.NEAREST)
                    shade = tuple(int(c * .45) for c in ImageStat.Stat(floor.convert('RGB')).mean) + (255,)
                    ImageDraw.Draw(floor).rectangle((0, 0, 63, 63), outline=shade, width=1)
                    dark = ImageEnhance.Brightness(floor).enhance(.66 if family == 'lantern' else .47)
                    for slot in (1291, 1295):
                        self.assertEqual(self.pixels(atlas, mapping[str(slot)]), floor.tobytes())
                    for slot in (1292, 1294):
                        self.assertEqual(self.pixels(atlas, mapping[str(slot)]), dark.tobytes())
                    self.assertNotEqual(self.pixels(atlas, 1291), floor.tobytes())
                    self.assertNotEqual(self.pixels(atlas, mapping['1293']), floor.tobytes())
                    self.assertNotEqual(self.pixels(atlas, mapping['1296']), dark.tobytes())
                    if family == 'lantern':
                        self.assertEqual(self.pixels(atlas, mapping['1284']), floor.tobytes())
                    floors[region] = floor.tobytes()
            self.assertNotEqual(floors['mines'], floors['gehennom'])

    def test_approved_gehennom_horizontal_wall_crops(self):
        for family, classic, _ in FAMILIES:
            atlas = self.atlases[classic]
            material = atlas['regionalMaterials']['gehennom']
            source = self.source(family, 'gehennom')
            crops = ((425, 105, 515, 211), (518, 105, 614, 211)) if family == 'lantern' else (
                (728, 105, 824, 211), (666, 105, 762, 211))
            slot = next(slot for slot, wall in material['wallTiles'].items() if wall['topology'] == 'horizontal')
            frame = atlas['projectedFrames']['frames'][str(material['tileMap'][slot])]
            plain, connector = [source.crop(crop).resize((64, 71), Image.Resampling.NEAREST).tobytes()
                                for crop in crops]
            self.assertEqual(self.frame_pixels(atlas, frame), plain)
            self.assertEqual([self.frame_pixels(atlas, f) for f in frame['alternates']],
                             [plain, plain, connector])

    def test_material_scope_and_separate_allocations(self):
        for family, classic, _ in FAMILIES:
            atlas = self.atlases[classic]
            allocations = []
            for region, start in REGIONS.items():
                material = atlas['regionalMaterials'][region]
                expected = {str(slot) for slot in (*range(1291, 1297), *range(start, start + 11))}
                if family == 'lantern':
                    expected.add('1284')
                self.assertEqual(set(material['tileMap']), expected)
                self.assertEqual(set(material['wallTiles']), {str(slot) for slot in range(start, start + 11)})
                # Bars, unknown/solid rock, pools, ice, lava and wall-of-lava stay canonical.
                for slot in (1272, 1289, 1469, 1470, 1314, 1315, 1316, 1317, 1324):
                    self.assertNotIn(str(slot), material['tileMap'])
                ids = set(material['tileMap'].values())
                ids.update(i for wall in material['wallTiles'].values() for i in wall['variants'])
                allocations.append(ids)
            self.assertTrue(allocations[0].isdisjoint(allocations[1]))

    def test_canonical_baseline_unchanged(self):
        for family, classic, modern in FAMILIES:
            for identifier in (classic, modern):
                digest = hashlib.sha256(b''.join(self.pixels(self.atlases[identifier], slot)
                                               for slot in BASELINE_SLOTS)).hexdigest()
                self.assertEqual(digest, BASELINE_HASHES[family], identifier)

    def test_canonical_mines_walls_use_approved_excavation_art(self):
        # Canonical branch art also retains these walls without a regional tag.
        # Fallback, directional topology and projected poses must all match
        # the approved random-cave art, without replacing canonical floors.
        for _, classic, modern in FAMILIES:
            for identifier in (classic, modern):
                atlas = self.atlases[identifier]
                material = atlas['regionalMaterials']['mines']
                for slot in range(1471, 1482):
                    key = str(slot)
                    target = material['tileMap'][key]
                    self.assertEqual(self.pixels(atlas, slot), self.pixels(atlas, target))
                    self.assertEqual(atlas['lanternWalls']['tiles'][key], material['wallTiles'][key])
                    first = atlas['projectedFrames']['frames'][key]
                    second = atlas['projectedFrames']['frames'][str(target)]
                    self.assert_frame_equal(atlas, first, atlas, second)

    def assert_frame_equal(self, a, first, b, second):
        for field in ('offset', 'depth', 'occupiedSquares', 'kind'):
            self.assertEqual(first.get(field), second.get(field), field)
        self.assertEqual(first['source'][2:], second['source'][2:])
        self.assertEqual(self.frame_pixels(a, first), self.frame_pixels(b, second))
        self.assertEqual(len(first.get('alternates', [])), len(second.get('alternates', [])))
        for first_alt, second_alt in zip(first.get('alternates', []), second.get('alternates', [])):
            self.assert_frame_equal(a, first_alt, b, second_alt)
        for atlas, frame in ((a, first), (b, second)):
            x, y, w, h = frame['source']
            width, height = self.image(atlas).size
            self.assertTrue(0 <= x < x + w <= width)
            self.assertTrue(0 <= y < y + h <= height)

    def test_classic_modern_parity_and_regional_frame_bounds(self):
        for _, classic, modern in FAMILIES:
            a, b = self.atlases[classic], self.atlases[modern]
            self.assertEqual(set(a['regionalMaterials']), set(b['regionalMaterials']))
            for region in REGIONS:
                material_a = a['regionalMaterials'][region]
                material_b = b['regionalMaterials'][region]
                self.assertEqual(set(material_a['tileMap']), set(material_b['tileMap']))
                pairs = list(zip(material_a['tileMap'].values(), material_b['tileMap'].values()))
                self.assertEqual(set(material_a['wallTiles']), set(material_b['wallTiles']))
                for key, wall_a in material_a['wallTiles'].items():
                    wall_b = material_b['wallTiles'][key]
                    self.assertEqual({k: v for k, v in wall_a.items() if k != 'variants'},
                                     {k: v for k, v in wall_b.items() if k != 'variants'})
                    self.assertEqual(len(wall_a['variants']), len(wall_b['variants']))
                    pairs.extend(zip(wall_a['variants'], wall_b['variants']))
                for first, second in set(pairs):
                    for atlas, slot in ((a, first), (b, second)):
                        self.assertTrue(2304 <= slot < atlas['count'])
                    self.assertEqual(self.pixels(a, first), self.pixels(b, second))
                    frame_a = a['projectedFrames']['frames'].get(str(first))
                    frame_b = b['projectedFrames']['frames'].get(str(second))
                    if frame_a is None:
                        self.assertIsNone(frame_b)
                    else:
                        self.assertIsNotNone(frame_b)
                        self.assert_frame_equal(a, frame_a, b, frame_b)

    def test_unrelated_atlases_do_not_opt_in(self):
        for key, atlas in self.atlases.items():
            if key not in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
                self.assertNotIn('regionalMaterials', atlas)


if __name__ == '__main__':
    unittest.main()
