#!/usr/bin/env python3
"""Check final terrain pixels against independent adjacency/passability contracts.

Requires development Pillow. Reads the actual registered source sheet, not
the generator's shape constants. Does not run the game or touch player data.
"""

from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from statistics import median

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'assets/tiles/lantern'


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ART / 'sources.json').read_text())
        cls.sheet_info = next(s for s in cls.registry['sheets'] if s['id'] == 'terrain-geometry')
        cls.sheet = Image.open(ART / cls.sheet_info['file']).convert('RGBA')

    def tile(self, key):
        assignment = self.registry['art']['terrain/' + key]
        self.assertEqual(assignment['sheet'], 'terrain-geometry')
        x, y = assignment['column'] * 32, assignment['row'] * 32
        return self.sheet.crop((x, y, x + 32, y + 32))

    @staticmethod
    def edge(image, side, depth=0):
        positions = {'N': [(x, depth) for x in range(32)],
                     'S': [(x, 31 - depth) for x in range(32)],
                     'W': [(depth, y) for y in range(32)],
                     'E': [(31 - depth, y) for y in range(32)]}
        return [image.getpixel(point) for point in positions[side]]

    def test_all_wall_families_have_correct_twelve_pixel_ports(self):
        # NetHack topology is spelled out independently of the artwork generator.
        expected = {'vertical': 'NS', 'horizontal': 'EW', 'tlcorn': 'SE',
                    'trcorn': 'SW', 'blcorn': 'NE', 'brcorn': 'NW',
                    'cross-wall': 'NSEW', 'tuwall': 'NEW', 'tdwall': 'SEW',
                    'tlwall': 'NSW', 'trwall': 'NSE'}
        for family in ('main', 'mines', 'gehennom', 'knox', 'sokoban'):
            for shape, connections in expected.items():
                with self.subTest(family=family, shape=shape):
                    tile = self.tile(f'{family}-walls-{shape}')
                    for side in 'NSEW':
                        for depth in range(4):
                            actual = [i for i, pixel in enumerate(self.edge(tile, side, depth))
                                      if pixel[3] != 0]
                            self.assertEqual(actual, list(range(10, 22)) if side in connections else [])

    def test_connectors_form_one_continuous_opaque_wall(self):
        for key in self.registry['art']:
            if '-walls-' not in key:
                continue
            tile = self.tile(key.removeprefix('terrain/'))
            opaque = {(x, y) for y in range(32) for x in range(32)
                      if tile.getpixel((x, y))[3] == 255}
            visited, pending = set(), [(15, 15)]
            while pending:
                point = pending.pop()
                if point not in opaque or point in visited:
                    continue
                visited.add(point)
                x, y = point
                pending.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])
            self.assertEqual(visited, opaque, key)

    def test_wall_retains_bright_cap_and_darker_textured_face(self):
        tile = self.tile('main-walls-horizontal')
        cap = [sum(tile.getpixel((x, y))[:3]) / 3 for x in range(2, 30)
               for y in (10, 11, 12)]
        face = [sum(tile.getpixel((x, y))[:3]) / 3 for x in range(2, 30)
                for y in (15, 16, 17, 18)]
        self.assertGreater(median(cap), median(face) + 40)
        # The accepted donor has detailed stone variation. A small flat palette
        # previously passed geometry checks while visibly losing that fidelity.
        colors = {tile.getpixel((x, y)) for x in range(2, 30) for y in range(10, 22)}
        self.assertGreater(len(colors), 100)

    def test_adjacent_wall_and_door_edge_profiles_match_exactly(self):
        north = self.edge(self.tile('main-walls-vertical'), 'N')
        west = self.edge(self.tile('main-walls-horizontal'), 'W')
        keys = [key.removeprefix('terrain/') for key in self.registry['art']
                if '-walls-' in key or key.endswith(('-open-door', '-closed-door'))]
        for key in keys:
            tile = self.tile(key)
            for side in 'NSEW':
                edge = self.edge(tile, side)
                if any(pixel[3] for pixel in edge):
                    self.assertEqual(edge, north if side in 'NS' else west, (key, side))

    @staticmethod
    def has_passage(image, horizontal):
        # A character walking between opposite edges needs a clear floor path.
        starts = [(0, y) for y in range(32)] if horizontal else [(x, 0) for x in range(32)]
        pending, visited = deque(starts), set()
        while pending:
            x, y = pending.popleft()
            if not 0 <= x < 32 or not 0 <= y < 32 or (x, y) in visited:
                continue
            if image.getpixel((x, y))[3] != 0:
                continue
            if (x == 31 if horizontal else y == 31):
                return True
            visited.add((x, y))
            pending.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])
        return False

    def test_open_doors_are_walkable_closed_doors_are_blocked(self):
        for orientation in ('vertical', 'horizontal'):
            with self.subTest(orientation=orientation):
                opened = self.tile(orientation + '-open-door')
                closed = self.tile(orientation + '-closed-door')
                self.assertTrue(self.has_passage(opened, orientation == 'vertical'))
                self.assertFalse(self.has_passage(closed, orientation == 'vertical'))
                self.assertNotEqual(opened.tobytes(), closed.tobytes())
                # At least six pixel rows/columns of the opening are fully clear.
                scans = [[opened.getpixel((x, y))[3] for x in range(32)] for y in range(32)]
                if orientation == 'horizontal':
                    scans = [[opened.getpixel((x, y))[3] for y in range(32)] for x in range(32)]
                self.assertGreaterEqual(sum(not any(scan) for scan in scans), 6)

    def test_ground_has_no_transparent_seams_or_framed_pool(self):
        for key in ('no-door', 'floor-of-a-room', 'dark-part-of-a-room', 'corridor',
                    'lit-corridor', 'pool', 'water', 'engraving-in-a-room',
                    'engraving-in-a-corridor'):
            with self.subTest(key=key):
                tile = self.tile(key)
                self.assertEqual(tile.getchannel('A').getextrema(), (255, 255))
                self.assertEqual(self.edge(tile, 'N'), self.edge(tile, 'S'))
                self.assertEqual(self.edge(tile, 'W'), self.edge(tile, 'E'))
        pool = self.tile('pool')
        # Blue water reaches every edge, without a gray stone basin frame.
        for side in 'NSEW':
            self.assertTrue(all(b > r + 15 for r, g, b, a in self.edge(pool, side)))

    def test_unknown_and_solid_rock_are_featureless(self):
        for key in ('stone', 'unexplored', 'nothing'):
            tile = self.tile(key)
            self.assertEqual(len({tile.getpixel((x, y)) for x in range(32) for y in range(32)}), 1)
            self.assertEqual(tile.getchannel('A').getextrema(), (255, 255))

    def test_source_dimensions_hash_and_reproducibility(self):
        self.assertEqual(self.sheet.size, (256, 128))
        actual = (ART / self.sheet_info['file']).read_bytes()
        self.assertEqual(hashlib.sha256(actual).hexdigest(), self.sheet_info['sha256'])
        self.assertEqual(self.sheet_info['grid'], 'exact')
        with tempfile.TemporaryDirectory(prefix='atlas-geometry-test-') as directory:
            path = Path(directory) / 'geometry.png'
            subprocess.run([sys.executable, str(ART / 'build_geometry.py'), '--output', str(path),
                            '--previews', str(Path(directory) / 'previews')], check=True,
                           stdout=subprocess.PIPE)
            self.assertEqual(actual, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
