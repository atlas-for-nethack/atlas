#!/usr/bin/env python3
"""Check appearance privacy and canonical boundaries in the Lantern tile catalog."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tile_catalog', ROOT / 'scripts/tile-catalog.py')
catalog_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_tool)


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = catalog_tool.generate(ROOT / 'vendor/NetHack-5.0.0')
        cls.tiles = cls.catalog['tiles']

    def test_committed_catalog_matches_engine(self):
        saved = json.loads(catalog_tool.DEFAULT_CATALOG.read_text())
        self.assertEqual(saved, self.catalog)
        self.assertEqual(len(self.tiles), 2304)
        self.assertEqual(self.tiles[788]['label'], 'invisible monster')
        self.assertEqual(self.tiles[789]['label'], 'strange object')
        self.assertEqual(self.tiles[1272]['label'], 'stone')
        self.assertEqual(self.tiles[1514]['label'], 'sokoban walls trwall')
        self.assertEqual(self.tiles[1515]['derived_from_slot'], 0)
        self.assertFalse(self.tiles[2303]['engine_referenced'])

    def test_art_cannot_reveal_hidden_object_identity(self):
        def obj(index):
            return self.tiles[789 + index]
        # Ordinary and magical lamps, all bags, and true/fake Yendor amulets
        # have matching appearances. Different art would disclose hidden state.
        for group in [(229, 230), (219, 220, 221, 222), (214, 215),
                      (472, 473, 474, 475), (441, 442, 454, 463)]:
            self.assertEqual(len({obj(i)['art_key'] for i in group}), 1)
        self.assertEqual(obj(299)['label'], 'ruby potion')
        self.assertEqual(obj(325)['label'], 'scroll labeled ZELGO MER')
        self.assertEqual(obj(416)['label'], 'pine wand')
        self.assertNotEqual(obj(188)['art_key'], obj(299)['art_key'])
        self.assertNotIn('gain ability', obj(299)['label'])
        self.assertNotIn('wishing', obj(416)['label'])

    def test_forms_and_statues_preserve_semantics(self):
        self.assertEqual(self.tiles[30]['art_key'], self.tiles[31]['art_key'])
        self.assertNotEqual(self.tiles[30]['art_key'], self.tiles[536]['art_key'])
        self.assertEqual(self.tiles[30]['label'], 'werejackal (animal form)')
        self.assertEqual(self.tiles[536]['label'], 'werejackal (human form)')
        for tile in self.tiles[1515:]:
            original = self.tiles[tile['derived_from_slot']]
            self.assertEqual(tile['art_key'], original['art_key'])
            self.assertEqual(tile['transform'], 'statue')

    def test_reordered_or_missing_headers_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tiles.txt'
            path.write_text('# tile 1 (first)\n# tile 0 (second)\n')
            with self.assertRaisesRegex(ValueError, 'contiguous headers'):
                catalog_tool.read_headers(path, 2)

    def test_wrong_engine_mapping_fails(self):
        source = (ROOT / 'vendor/NetHack-5.0.0/src/tile.c').read_text()
        old = '0, 0 },   /* [0000] monsters.txt:000'
        self.assertIn(old, source)
        corrupted = source.replace(old, '1, 0 },   /* [0000] monsters.txt:000', 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tile.c'
            path.write_text(corrupted)
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                catalog_tool.engine_references(path)


if __name__ == '__main__':
    unittest.main()
