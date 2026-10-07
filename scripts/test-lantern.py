#!/usr/bin/env python3
"""Focused assembler tests with disposable synthetic art, never player data.

Requires Pillow. These fixtures test assembly, not the quality or completeness
of the production artwork. Run with a development Python that has Pillow.
"""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'lantern_builder', ROOT / 'assets/tiles/lantern/build_atlas.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atlas-lantern-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sources').mkdir()
        (self.root / 'PROMPTS.md').write_text('Synthetic test fixture, not production artwork.\n')
        image = Image.new('RGBA', (128, 64), (20, 40, 80, 255))
        image.paste((200, 120, 30, 255), (64, 0, 128, 64))
        self.source = self.root / 'sources/synthetic.png'
        image.save(self.source)
        self.catalog = {
            'schema': 1, 'engineVersion': '5.0.0', 'requiredTileCount': 2304,
            'tiles': [{'slot': slot, 'label': f'Appearance {slot}',
                       'category': 'object', 'art_key': 'appearance/blue'}
                      for slot in range(2304)],
        }
        self.catalog['tiles'][1]['art_key'] = 'appearance/gold'
        self.catalog['tiles'][2303]['transform'] = 'statue'
        self.sources = {
            'schema': 1,
            'artwork': {'origin': 'original-ai-generated', 'tool': 'image_gen',
                        'prompt_file': 'PROMPTS.md'},
            'sheets': [{'id': 'synthetic', 'file': 'sources/synthetic.png',
                        'columns': 2, 'rows': 1,
                        'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}],
            'art': {'appearance/blue': {'sheet': 'synthetic', 'column': 0, 'row': 0},
                    'appearance/gold': {'sheet': 'synthetic', 'column': 1, 'row': 0}},
        }

    def build(self):
        (self.root / 'catalog.json').write_text(json.dumps(self.catalog))
        (self.root / 'sources.json').write_text(json.dumps(self.sources))
        return builder.prepare(self.root)

    def test_shared_appearances_and_slot_placement(self):
        prepared = self.build()
        report = prepared['evidence']
        image = prepared['image']
        with image:
            self.assertEqual(image.size, (1280, 1856))
            self.assertEqual(image.getpixel((0, 0)), (20, 40, 80, 255))
            self.assertEqual(image.getpixel((32, 0)), (200, 120, 30, 255))
            # Slot 40 is the first tile in the second row, sharing the blue art.
            self.assertEqual(image.getpixel((0, 32)), (20, 40, 80, 255))
            # Final canonical slot has a stone rendition, unused padding is clear.
            self.assertNotEqual(image.getpixel((23 * 32, 57 * 32)), (20, 40, 80, 255))
            self.assertEqual(image.getpixel((24 * 32, 57 * 32))[3], 0)
        self.assertEqual(report['assignedSlots'], 2304)
        self.assertEqual(report['uniqueArtKeys'], 2)
        self.assertEqual(report['statueSlots'], 1)
        self.assertEqual(prepared['metadata']['canonicalCount'], 2304)
        self.assertNotIn('output', report)
        self.assertEqual({p.name for p in self.root.iterdir()},
                         {'sources', 'PROMPTS.md', 'catalog.json', 'sources.json'})

    def test_missing_and_duplicate_slot_coverage(self):
        original = deepcopy(self.catalog)
        for mutation in ('missing', 'duplicate', 'out_of_range'):
            with self.subTest(mutation=mutation):
                self.catalog = deepcopy(original)
                if mutation == 'missing':
                    self.catalog['tiles'].pop()
                elif mutation == 'duplicate':
                    self.catalog['tiles'][-1]['slot'] = 0
                else:
                    self.catalog['tiles'][-1]['slot'] = 2304
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse((self.root / 'out.png').exists())

    def test_missing_art_never_uses_a_fallback(self):
        del self.sources['art']['appearance/gold']
        with self.assertRaisesRegex(ValueError, 'Missing art assignments'):
            self.build()

    def test_grid_and_cell_bounds(self):
        original = deepcopy(self.sources)
        for mutation in ('bad_grid', 'row', 'column', 'negative'):
            with self.subTest(mutation=mutation):
                self.sources = deepcopy(original)
                if mutation == 'bad_grid':
                    self.sources['sheets'][0]['columns'] = 3
                elif mutation == 'row':
                    self.sources['art']['appearance/blue']['row'] = 1
                elif mutation == 'column':
                    self.sources['art']['appearance/blue']['column'] = 2
                else:
                    self.sources['art']['appearance/blue']['row'] = -1
                with self.assertRaises(ValueError):
                    self.build()

    def test_required_provenance_and_input_hash(self):
        original = deepcopy(self.sources)
        for mutation in ('origin', 'tool', 'prompt', 'hash'):
            with self.subTest(mutation=mutation):
                self.sources = deepcopy(original)
                if mutation == 'origin':
                    self.sources['artwork']['origin'] = 'DawnHack derivative'
                elif mutation == 'tool':
                    del self.sources['artwork']['tool']
                elif mutation == 'prompt':
                    self.sources['artwork']['prompt_file'] = 'missing.md'
                else:
                    self.sources['sheets'][0]['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    self.build()

    def test_nondivisible_grid_requires_explicit_normalization(self):
        image = Image.new('RGBA', (1254, 1254), (20, 40, 80, 255))
        image.save(self.source)
        spec = self.sources['sheets'][0]
        spec.update(columns=8, rows=8,
                    sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'not divisible'):
            self.build()
        spec['grid'] = 'normalized'
        report = self.build()['evidence']
        self.assertEqual(report['inputs'][0]['grid'], 'normalized')
        spec['rows'] = 7
        with self.assertRaisesRegex(ValueError, 'square image and equal'):
            self.build()

    def test_source_cannot_escape_through_symlink(self):
        external = self.root / 'outside.png'
        external.write_bytes(self.source.read_bytes())
        self.source.unlink()
        self.source.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.build()

    def test_no_unsupported_transform(self):
        self.catalog['tiles'][0]['transform'] = 'fallback-official'
        with self.assertRaisesRegex(ValueError, 'unsupported transform'):
            self.build()

    def test_statue_keeps_exact_declared_background_and_alpha(self):
        image = Image.new('RGBA', (4, 1))
        original = [(0, 0, 0, 255), (24, 34, 33, 255),
                    (24, 34, 34, 255), (180, 40, 20, 80)]
        image.putdata(original)
        transformed = builder.stone(image, [24, 34, 33])
        self.assertEqual(transformed.getpixel((0, 0)), original[0])
        self.assertEqual(transformed.getpixel((1, 0)), original[1])
        self.assertNotEqual(transformed.getpixel((2, 0)), original[2])
        self.assertEqual(transformed.getpixel((3, 0))[3], 80)
        self.sources['artwork']['background_rgb'] = [24, 34, 256]
        with self.assertRaisesRegex(ValueError, 'background_rgb'):
            self.build()

    def test_known_art_is_rejected_even_after_renaming(self):
        self.source.write_bytes((ROOT / 'assets/tiles/official.png').read_bytes())
        self.sources['sheets'][0]['sha256'] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'third-party artwork'):
            self.build()

    def test_duplicate_json_keys_are_not_silently_replaced(self):
        path = self.root / 'duplicate.json'
        path.write_text('{"art": {}, "art": {}}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            builder.read_json(path)

    def test_preparation_never_rewrites_source_or_metadata(self):
        self.build()
        originals = {path: path.read_bytes() for path in
                     (self.source, self.root / 'catalog.json', self.root / 'sources.json',
                      self.root / 'PROMPTS.md')}
        builder.prepare(self.root)
        for path, original in originals.items():
            self.assertEqual(path.read_bytes(), original, path.name)


if __name__ == '__main__':
    unittest.main()
