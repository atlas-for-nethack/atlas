#!/usr/bin/env python3
"""Check Astral source isolation, directional geometry and shipped edition parity."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / 'assets/tiles'
SHIPPED = '--shipped' in sys.argv
if SHIPPED:
    sys.argv.remove('--shipped')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def crop(image, pose):
    x, y, width, height = pose['source']
    return image.crop((x, y, x+width, y+height))


class AstralMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = module('tested_astral', TILES / 'astral_material.py')
        cls.packer = module('astral_test_packer', TILES / 'packing.py')
        cls.entries = {entry['id']: entry for entry in json.loads((TILES / 'manifest.json').read_text())['tilesets']}
        cls.examples = {}
        for family in ('lantern', 'soot-and-brass'):
            entry = cls.entries[family]
            source = Image.open(TILES / entry['file']).convert('RGBA')
            projection, architecture = copy.deepcopy(entry['projectedFrames']), copy.deepcopy(entry['lanternWalls'])
            old_projection, old_architecture = copy.deepcopy(projection), copy.deepcopy(architecture)
            built = cls.generator.append(source, projection, family, cls.packer.append_projected, architecture)
            cls.examples[family] = (entry, source, built, projection, architecture, old_projection, old_architecture)

    def assert_pose(self, original_image, original, output, new):
        self.assertEqual(original['offset'], new['offset'])
        self.assertEqual(original['source'][2:], new['source'][2:])
        self.assertEqual(original.get('depth'), new.get('depth'))
        self.assertEqual(original.get('kind'), new.get('kind'))
        self.assertEqual(original.get('occupiedSquares'), new.get('occupiedSquares'))
        self.assertEqual(crop(original_image, original).getchannel('A').tobytes(), crop(output, new).getchannel('A').tobytes())
        self.assertEqual(len(original.get('alternates', [])), len(new.get('alternates', [])))
        for old_alternate, new_alternate in zip(original.get('alternates', []), new.get('alternates', [])):
            self.assert_pose(original_image, old_alternate, output, new_alternate)

    def test_all_inputs_and_preexisting_pixels_preserved(self):
        for family, (entry, source, built, projection, architecture, old_projection, old_architecture) in self.examples.items():
            with self.subTest(family=family):
                output, result_projection, *_ = built
                self.assertEqual(output.crop((0, 0, *source.size)).tobytes(), source.tobytes())
                self.assertEqual(projection, old_projection)
                self.assertEqual(architecture, old_architecture)
                for key, frame in old_projection['frames'].items():
                    self.assertEqual(result_projection['frames'][key], frame)

    def test_all_wall_masks_door_aliases_and_alternates_preserve_geometry(self):
        for family, (entry, source, built, _, _, _, _) in self.examples.items():
            output, projection, count, material, _, added = built
            for alias, source_slot in zip(range(1273, 1284), range(1504, 1515)):
                old_rule = entry['lanternWalls']['tiles'][str(source_slot)]
                new_rule = material['wallTiles'][str(alias)]
                self.assertEqual(len(new_rule['variants']), 256)
                for field in ('topology', 'connections'):
                    self.assertEqual(new_rule[field], old_rule[field])
                canonical = material['tileMap'][str(alias)]
                self.assert_pose(source, entry['projectedFrames']['frames'][str(source_slot)], output, projection['frames'][str(canonical)])
                for old_variant, new_variant in zip(old_rule['variants'], new_rule['variants']):
                    self.assertEqual(new_variant, material['tileMap'][str(old_variant)])
                    self.assertTrue(new_variant < count)
                    self.assertIn(str(new_variant), added)
                    self.assert_pose(source, entry['projectedFrames']['frames'][str(old_variant)], output, projection['frames'][str(new_variant)])
            for slot, rule in entry['lanternWalls']['doors'].items():
                for old_variant in [int(slot), *rule['variants']]:
                    new_variant = material['tileMap'][str(old_variant)]
                    self.assert_pose(source, entry['projectedFrames']['frames'][str(old_variant)], output, projection['frames'][str(new_variant)])

    def test_only_architecture_and_ordinary_ground_are_selected(self):
        for family, (entry, _, built, _, _, _, _) in self.examples.items():
            selected = set(map(int, built[3]['tileMap']))
            expected = set(range(1273, 1284)) | set(range(1291, 1297))
            if family == 'lantern':
                expected.add(1284)
            for slot in range(1504, 1515):
                expected.update(entry['lanternWalls']['tiles'][str(slot)]['variants'])
            for slot, rule in entry['lanternWalls']['doors'].items():
                expected.add(int(slot))
                expected.update(rule['variants'])
            self.assertEqual(selected, expected)
            for unmodified in (0, 1056, 1266, 1289, 1290, 1309, 1310, 1320, 1469, 1470):
                self.assertNotIn(unmodified, selected)
            self.assertEqual(set(built[3]['wallTiles']), set(map(str, range(1273, 1284))))

    def test_repeat_build_is_deterministic(self):
        for family, (_, source, built, projection, architecture, _, _) in self.examples.items():
            repeated = self.generator.append(source, projection, family, self.packer.append_projected, architecture)
            self.assertEqual(repeated[0].tobytes(), built[0].tobytes())
            self.assertEqual(repeated[1:], built[1:])

    def test_light_floor_dark_floor_and_engraving_remain_distinct(self):
        for family, (entry, source, built, _, _, _, _) in self.examples.items():
            output, projection, _, material, *_ = built
            def tile(image, slot):
                x, y = slot % 40*64, slot // 40*64
                return image.crop((x, y, x+64, y+64))
            mean = lambda image: sum(ImageStat.Stat(image.convert('RGB')).mean)/3
            floor = tile(output, material['tileMap']['1291'])
            dark = tile(output, material['tileMap']['1292'])
            engraved = tile(output, material['tileMap']['1293'])
            self.assertGreater(mean(floor), mean(tile(source, 1291))+20)
            self.assertGreater(mean(floor), mean(dark)+5)
            self.assertNotEqual(floor.tobytes(), engraved.tobytes())
            # Existing grid keeps a darker border than the quieter floor interior.
            self.assertLess(mean(floor.crop((0, 0, 64, 1))), mean(floor.crop((8, 8, 56, 56))))

    def test_remembered_dark_floor_is_quieter_without_interior_black_speckles(self):
        entry, source, built, *_ = self.examples['soot-and-brass']
        output, _, _, material, *_ = built
        def interior(image, slot):
            x, y = slot % 40*64, slot // 40*64
            return image.crop((x+4, y+4, x+60, y+60)).convert('L')
        for slot in (1291, 1292):
            old, new = interior(source, slot), interior(output, material['tileMap'][str(slot)])
            old_stat, new_stat = ImageStat.Stat(old), ImageStat.Stat(new)
            self.assertLess(new_stat.stddev[0], old_stat.stddev[0]*.75)
            # The whole dark interior stays in the pale material range. Grain
            # cannot enter the low-value joint branch and create black flecks.
            self.assertGreater(min(new.getdata()), 65)
            self.assertLess(max(new.getdata())-min(new.getdata()), max(old.getdata())-min(old.getdata())*.8)
        recipe = json.loads(self.generator.RECIPE.read_text())
        flat_dark = Image.new('RGBA', (9, 9), (10, 10, 10, 255))
        changed = self.generator.recolor(flat_dark, 'floor', 'soot-and-brass', recipe)
        self.assertGreater(changed.getpixel((4, 4))[0], changed.getpixel((0, 0))[0]+30)
        self.assertEqual(changed.getchannel('A').tobytes(), flat_dark.getchannel('A').tobytes())

    def test_engraving_detail_masks_only_retain_existing_source_strokes(self):
        recipe = json.loads(self.generator.RECIPE.read_text())
        for family, (_, source, built, _, _, _, _) in self.examples.items():
            def tile(slot):
                x, y = slot % 40*64, slot // 40*64
                return source.crop((x, y, x+64, y+64))
            for engraved_slot, plain_slot in ((1293, 1291), (1296, 1292)):
                engraved, plain = tile(engraved_slot), tile(plain_slot)
                mask = self.generator.engraving_mask(engraved, plain, recipe)
                self.assertTrue(any(mask.getdata()))
                grayscale = engraved.convert('L')
                from PIL import ImageFilter, ImageChops
                local = grayscale.filter(ImageFilter.MedianFilter(7))
                difference = ImageChops.difference(engraved.convert('RGB'), plain.convert('RGB')).convert('L')
                for index, (selected, value, background, delta) in enumerate(zip(mask.getdata(), grayscale.getdata(), local.getdata(), difference.getdata())):
                    if selected:
                        self.assertGreater(delta, 10)
                        self.assertGreater(abs(value-background), 8)
                changed = self.generator.recolor(engraved, 'floor', family, recipe, mask)
                self.assertEqual(changed.getchannel('A').tobytes(), engraved.getchannel('A').tobytes())

    def test_selective_palette_and_license(self):
        recipe = json.loads(self.generator.RECIPE.read_text())
        fixture = Image.new('RGBA', (4, 1))
        fixture.putdata([(100, 100, 100, 255), (65, 40, 20, 255), (180, 140, 60, 123), (1, 2, 3, 0)])
        for family, (_, source, built, _, _, _, _) in self.examples.items():
            changed = list(self.generator.recolor(fixture, 'architecture', family, recipe).getdata())
            self.assertNotEqual(changed[0], list(fixture.getdata())[0])
            self.assertEqual(changed[1], list(fixture.getdata())[1])
            self.assertGreater(changed[2][0], 180)
            self.assertEqual(changed[2][3], 123)
            self.assertEqual(changed[3], (1, 2, 3, 0))
            evidence = built[4]
            self.assertEqual(evidence['license'], 'CC-BY-4.0')
            self.assertEqual(evidence['credit'], 'NetHack Atlas project')
            self.assertEqual(evidence['sourcePixelSha256'], hashlib.sha256(source.tobytes()).hexdigest())
            self.assertEqual(evidence['recipeSha256'], hashlib.sha256(self.generator.RECIPE.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            self.generator.append(None, None, 'official', None, None)

    @unittest.skipUnless(SHIPPED, 'requires regenerated shipped materials')
    def test_shipped_classic_modern_parity_and_community_exclusion(self):
        originals = {'lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'}
        for classic, modern in [('lantern', 'lantern-modern'), ('soot-and-brass-classic', 'soot-and-brass')]:
            a, b = self.entries[classic], self.entries[modern]
            material = a['regionalMaterials']['astral']
            self.assertEqual(material, b['regionalMaterials']['astral'])
            selected = set(material['tileMap'].values())
            selected.update(slot for rule in material['wallTiles'].values() for slot in rule['variants'])
            with Image.open(TILES / a['file']) as ai, Image.open(TILES / b['file']) as bi:
                for slot in selected:
                    af, bf = a['projectedFrames']['frames'].get(str(slot)), b['projectedFrames']['frames'].get(str(slot))
                    if af:
                        self.assert_pose(ai, af, bi, bf)
                        for ap, bp in zip([af, *af.get('alternates', [])], [bf, *bf.get('alternates', [])]):
                            self.assertEqual(crop(ai, ap).tobytes(), crop(bi, bp).tobytes())
                    else:
                        x, y = slot % 40*64, slot // 40*64
                        self.assertEqual(ai.crop((x, y, x+64, y+64)).tobytes(), bi.crop((x, y, x+64, y+64)).tobytes())
        for ident, entry in self.entries.items():
            if ident not in originals:
                self.assertNotIn('astral', entry.get('regionalMaterials', {}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
