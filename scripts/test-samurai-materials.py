#!/usr/bin/env python3
"""Check Samurai source fitting, all directional poses and unrelated art isolation.

Use --shipped after regeneration to compare all four original editions and the
retained pre-integration projection oracle. Tests never rewrite atlas files.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / 'assets/tiles'
SHIPPED = '--shipped' in sys.argv
if SHIPPED:
    sys.argv.remove('--shipped')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def pixels(image, pose):
    x, y, width, height = pose['source']
    return image.crop((x, y, x + width, y + height)).tobytes()


class SamuraiMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samurai = module('tested_samurai', TILES / 'samurai_material.py')
        cls.packer = module('samurai_test_packer', TILES / 'packing.py')
        cls.registry = json.loads((TILES / 'regions/samurai/sources.json').read_text())
        cls.entries = {entry['id']: entry for entry in
                       json.loads((TILES / 'manifest.json').read_text())['tilesets']}
        cls.examples = {}
        for family, ident in [('lantern', 'lantern'), ('soot-and-brass', 'soot-and-brass')]:
            entry = cls.entries[ident]
            source = Image.open(TILES / entry['file']).convert('RGBA')
            projection = copy.deepcopy(entry['projectedFrames'])
            architecture = copy.deepcopy(entry['lanternWalls'])
            original_projection = copy.deepcopy(projection)
            original_architecture = copy.deepcopy(architecture)
            built = cls.samurai.append(source, projection, family,
                                       cls.packer.append_projected, architecture)
            cls.examples[family] = (entry, source, built, projection, architecture,
                                    original_projection, original_architecture)

    def test_retained_source_and_prompt_hashes(self):
        folder = TILES / 'regions/samurai'
        prompt = self.registry['prompts']
        self.assertEqual(hashlib.sha256((folder / prompt['file']).read_bytes()).hexdigest(), prompt['sha256'])
        self.assertEqual(self.registry['license'], 'CC-BY-4.0')
        for record in self.registry['sources'].values():
            self.assertEqual(hashlib.sha256((folder / record['file']).read_bytes()).hexdigest(), record['sha256'])
            self.assertEqual(hashlib.sha256((folder / record['reference']).read_bytes()).hexdigest(), record['referenceSha256'])
            with Image.open(folder / record['file']) as source:
                self.assertEqual(list(source.size), record['size'])
                for piece in record['pieces'].values():
                    x, y, right, bottom = piece['bounds']
                    self.assertTrue(0 <= x < right <= source.width)
                    self.assertTrue(0 <= y < bottom <= source.height)

    def test_all_base_pixels_and_inputs_preserved(self):
        for family, (_, source, built, projection, architecture, old_projection, old_architecture) in self.examples.items():
            with self.subTest(family=family):
                output = built[0]
                self.assertEqual(output.crop((0, 0, *source.size)).tobytes(), source.tobytes())
                self.assertEqual(projection, old_projection)
                self.assertEqual(architecture, old_architecture)

    def test_all_wall_masks_and_existing_gate_masks_resolve(self):
        for family, (entry, _, built, _, _, _, _) in self.examples.items():
            output, projection, count, material, evidence, added = built
            for slot in range(1273, 1284):
                rule = material['wallTiles'][str(slot)]
                self.assertEqual(len(rule['variants']), 256)
                self.assertEqual(rule['topology'], entry['lanternWalls']['tiles'][str(slot)]['topology'])
                self.assertEqual(rule['connections'], entry['lanternWalls']['tiles'][str(slot)]['connections'])
                for mask, variant in enumerate(rule['variants']):
                    frame = projection['frames'][str(variant)]
                    original_variant = entry['lanternWalls']['tiles'][str(slot)]['variants'][mask]
                    original_frame = entry['projectedFrames']['frames'][str(original_variant)]
                    self.assertEqual(frame['offset'], original_frame['offset'], (family, slot, mask))
                    self.assertEqual(frame['source'][2:], original_frame['source'][2:], (family, slot, mask))
                    self.assertEqual(frame['depth'], 64)
                    self.assertIn(str(variant), added)
                    self.assertTrue(0 <= variant < count)
                    self.assertTrue(any(pixels(output, frame)[3::4]))
            for slot, _, _ in self.samurai.DOORS:
                original = entry['lanternWalls']['doors'][str(slot)]
                for mask, variant in enumerate(original['variants']):
                    frame = projection['frames'][str(material['tileMap'][str(variant)])]
                    old = entry['projectedFrames']['frames'][str(variant)]
                    self.assertEqual(frame['offset'], old['offset'], (family, slot, mask))
                    self.assertEqual(frame['source'][2:], old['source'][2:], (family, slot, mask))
                    self.assertEqual(frame['depth'], old['depth'])
            self.assertEqual(evidence['license'], 'CC-BY-4.0')

    def test_open_gates_keep_frames_and_show_clear_apertures(self):
        for family in self.examples:
            assembly, *_ = self.samurai.private_architecture(family)
            for vertical in (True, False):
                for mask in range(256):
                    opened, closed = assembly.door(vertical, True, mask), assembly.door(vertical, False, mask)
                    self.assertEqual(opened['offset'], closed['offset'])
                    self.assertEqual(opened['image'].size, closed['image'].size)
                    opened_alpha = opened['image'].getchannel('A')
                    closed_alpha = closed['image'].getchannel('A')
                    self.assertLess(sum(opened_alpha.tobytes()), sum(closed_alpha.tobytes()))
                    # Unmoving crown and outer jamb pixel positions stay identical.
                    self.assertEqual(opened['image'].crop((0, 0, opened['image'].width, 7)).tobytes(),
                                     closed['image'].crop((0, 0, closed['image'].width, 7)).tobytes())

    def test_no_floor_bar_object_or_creature_aliases(self):
        for family, (_, _, built, _, _, _, _) in self.examples.items():
            material = built[3]
            for slot in [0, 1056, 1266, 1284, 1289, *range(1291, 1469), 1469, 1470]:
                self.assertNotIn(str(slot), material['tileMap'], (family, slot))
            self.assertEqual(set(material['wallTiles']), {str(slot) for slot in range(1273, 1284)})

    def test_independent_instances_do_not_leak_changes(self):
        for family, (_, source, built, projection, architecture, _, _) in self.examples.items():
            again = self.samurai.append(source, projection, family, self.packer.append_projected, architecture)
            self.assertEqual(again[0].tobytes(), built[0].tobytes())
            self.assertEqual(again[1:4], built[1:4])
        with self.assertRaises(ValueError):
            self.samurai.private_architecture('official')

    @unittest.skipUnless(SHIPPED, 'requires regenerated shipped metadata')
    def test_shipped_classic_modern_parity_and_other_family_exclusion(self):
        originals = {'lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'}
        for classic, modern in [('lantern', 'lantern-modern'), ('soot-and-brass-classic', 'soot-and-brass')]:
            a, b = self.entries[classic], self.entries[modern]
            material = a['regionalMaterials']['samurai']
            self.assertEqual(material, b['regionalMaterials']['samurai'])
            with Image.open(TILES / a['file']) as ai, Image.open(TILES / b['file']) as bi:
                for target in {*material['tileMap'].values(), *(slot for rule in material['wallTiles'].values() for slot in rule['variants'])}:
                    af, bf = a['projectedFrames']['frames'][str(target)], b['projectedFrames']['frames'][str(target)]
                    self.assertEqual(af['offset'], bf['offset'])
                    for ap, bp in zip([af, *af.get('alternates', [])], [bf, *bf.get('alternates', [])]):
                        self.assertEqual(pixels(ai, ap), pixels(bi, bp))
        for ident, entry in self.entries.items():
            if ident not in originals:
                self.assertNotIn('samurai', entry.get('regionalMaterials', {}))

    @unittest.skipUnless(SHIPPED, 'requires regenerated shipped metadata')
    def test_preexisting_projection_pixels_and_rules_unchanged(self):
        baseline = ROOT / '.artifacts/samurai-before'
        if not (baseline / 'manifest.json').exists():
            self.skipTest('retained pre-integration oracle is unavailable')
        entries = json.loads((baseline / 'manifest.json').read_text())['tilesets']
        for before in entries:
            after = self.entries[before['id']]
            if before['id'] not in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
                for field in ('id', 'name', 'license', 'credit', 'description',
                              'tileWidth', 'tileHeight', 'columns', 'count', 'version'):
                    self.assertEqual(before.get(field), after.get(field), field)
                if (baseline / before['file']).exists():
                    with Image.open(baseline / before['file']) as old, Image.open(TILES / after['file']) as new:
                        self.assertEqual(old.size, new.size)
                        self.assertEqual(old.convert('RGBA').tobytes(), new.convert('RGBA').tobytes())
                continue
            with Image.open(baseline / before['file']) as old, Image.open(TILES / after['file']) as new:
                frame_cache, slot_cache = {}, {}
                def frame_signature(image, frame):
                    key = (id(image), id(frame))
                    if key not in frame_cache:
                        occupied = frame.get('occupiedSquares')
                        frame_cache[key] = (tuple(frame['source'][2:]), tuple(frame['offset']), frame.get('depth'),
                                            frame.get('kind'), None if occupied is None else tuple(map(tuple, occupied)),
                                            hashlib.sha256(pixels(image, frame)).hexdigest(),
                                            tuple(frame_signature(image, pose) for pose in frame.get('alternates', [])))
                    return frame_cache[key]

                def slot_signature(image, entry, slot):
                    key = (id(image), slot)
                    if key not in slot_cache:
                        x, y = slot % 40 * 64, slot // 40 * 64
                        pose = entry['projectedFrames']['frames'].get(str(slot))
                        slot_cache[key] = (hashlib.sha256(image.crop((x, y, x + 64, y + 64)).tobytes()).hexdigest(),
                                           frame_signature(image, pose) if pose else None)
                    return slot_cache[key]

                def lookup_signature(image, entry, value, field=None):
                    if isinstance(value, list):
                        if field == 'variants':
                            return [slot_signature(image, entry, slot) for slot in value]
                        return [lookup_signature(image, entry, item) for item in value]
                    if isinstance(value, dict):
                        if field == 'tileMap':
                            return sorted((str(key) if int(key) < 2304 else
                                           repr(slot_signature(image, entry, int(key))),
                                           slot_signature(image, entry, target))
                                          for key, target in value.items())
                        if field == 'wallTiles' or field == 'tiles':
                            return {key: lookup_signature(image, entry, item) for key, item in value.items()}
                        return {key: lookup_signature(image, entry, item, key)
                                for key, item in value.items() if key != 'variantStart'}
                    if field in ('tile', 'isolated') and isinstance(value, int):
                        return slot_signature(image, entry, value)
                    return value

                for key, region in before['regionalMaterials'].items():
                    self.assertEqual(lookup_signature(old, before, region),
                                     lookup_signature(new, after, after['regionalMaterials'][key]),
                                     (before['id'], key))
                self.assertEqual(lookup_signature(old, before, before['lanternWalls']),
                                 lookup_signature(new, after, after['lanternWalls']))
                # Every retained canonical pose and supplemental pose must retain
                # its exact pixels and geometry, even when packed coordinates move.
                new_signatures = {frame_signature(new, frame)
                                  for frame in after['projectedFrames']['frames'].values()}
                for key, old_frame in before['projectedFrames']['frames'].items():
                    signature = frame_signature(old, old_frame)
                    if int(key) < 2304:
                        self.assertEqual(signature, frame_signature(new, after['projectedFrames']['frames'][key]),
                                         (before['id'], key))
                    else:
                        self.assertIn(signature, new_signatures, (before['id'], key))


if __name__ == '__main__':
    unittest.main(verbosity=2)
