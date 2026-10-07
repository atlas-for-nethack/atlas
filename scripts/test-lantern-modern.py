#!/usr/bin/env python3
"""Check Lantern Modern's shipped artwork, source evidence and Classic isolation."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT/'assets/tiles'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LanternModern(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read(TILES/'manifest.json')
        cls.classic = next(t for t in cls.manifest['tilesets'] if t['id'] == 'lantern')
        cls.modern = next(t for t in cls.manifest['tilesets'] if t['id'] == 'lantern-modern')
        cls.old = Image.open(TILES/cls.classic['file']).convert('RGBA')
        cls.image = Image.open(TILES/cls.modern['file']).convert('RGBA')
        cls.catalog = read(TILES/'lantern/catalog.json')
        cls.report = read(TILES/'lantern/modern-provenance.json')
        cls.evidence = cls.report['sourceEvidence']

    def assert_frame_equal(self, first_image, first, second_image, second):
        for field in ('offset', 'depth', 'occupiedSquares', 'kind'):
            self.assertEqual(first.get(field), second.get(field), field)
        self.assertEqual(first['source'][2:], second['source'][2:])
        def pixels(image, frame):
            x, y, width, height = frame['source']
            return image.crop((x, y, x + width, y + height)).tobytes()
        self.assertEqual(pixels(first_image, first), pixels(second_image, second))
        self.assertEqual(len(first.get('alternates', [])), len(second.get('alternates', [])))
        for a, b in zip(first.get('alternates', []), second.get('alternates', [])):
            self.assert_frame_equal(first_image, a, second_image, b)

    def test_architecture_and_canonical_pixels_are_identical(self):
        grid_height = ((self.classic['count'] + 39) // 40) * 64
        self.assertEqual(self.image.crop((0, 0, self.old.width, grid_height)).tobytes(),
                         self.old.crop((0, 0, self.old.width, grid_height)).tobytes())
        self.assertEqual(self.modern['lanternWalls'], self.classic['lanternWalls'])
        self.assertEqual(self.modern['count'], self.classic['count'])
        for slot, frame in self.classic['projectedFrames']['frames'].items():
            self.assert_frame_equal(self.old, frame, self.image, self.modern['projectedFrames']['frames'][slot])
            self.assertNotEqual(frame.get('kind'), 'creature')
        self.assertEqual(self.manifest['default'], 'lantern')

    def test_complete_monster_policy_and_bounded_items(self):
        policy = read(TILES/'creature-scale.json')['monsters']
        self.assertEqual(set(policy), set(self.evidence['assignments']))
        frames = self.modern['projectedFrames']['frames']
        left,top,right,bottom = self.modern['projectedFrames']['padding']
        for tile in self.catalog['tiles']:
            frame = frames.get(str(tile['slot']))
            if tile['art_key'] not in policy:
                classic_frame = self.classic['projectedFrames']['frames'].get(str(tile['slot']))
                if classic_frame is None:
                    self.assertIsNone(frame, tile)
                else:
                    self.assert_frame_equal(self.old, classic_frame, self.image, frame)
                continue
            self.assertNotIn(str(tile['slot']), self.classic['projectedFrames']['frames'])
            self.assertIsNotNone(frame, tile)
            x,y,w,h = frame['source']; dx,dy = frame['offset']
            self.assertTrue(0<=x<x+w<=self.image.width and ((self.modern['count']+39)//40)*64<=y<y+h<=self.image.height)
            self.assertTrue(dx>=-left and dy>=-top and dx+w<=64+right and dy+h<=64+bottom)
            rule = policy[tile['art_key']]
            self.assertEqual(max(w, h) if rule.get('scaleAxis') == 'longest' else h, rule['height'])
            self.assertLessEqual(abs(dy+h-rule['footAnchor'][1]*64), .5)
            self.assertEqual(frame.get('kind'), None if tile.get('transform')=='statue' else 'creature')
        self.assertGreater(frames['632']['source'][3], 120, 'Asmodeus should retain stature')
        self.assertGreater(max(frames['300']['source'][2:]), 100, 'Adult dragon stature can be broad or tall')

    def test_provenance_matches_sources_and_output(self):
        for source in [self.report['recipe'], self.report['compiler'], self.report['packer'], *self.report['inputs']]:
            self.assertEqual(digest(ROOT/source['file']), source['sha256'], source['file'])
        self.assertEqual([self.report['output']['width'], self.report['output']['height']], list(self.image.size))
        r = self.evidence
        for file, sha in r['inputs'].items():
            self.assertEqual(digest(TILES/'lantern'/file), sha, file)
        for file, field in [('lantern/build_modern.py','builderSha256'),
                            ('packing.py','packerSha256'),
                            ('creature-scale.json','sizePolicySha256'),
                            ('creature_scale.py','scaleHelperSha256'),
                            ('lantern/prepare_foregrounds.py','cleanupSha256'),
                            ('lantern/catalog.json','catalogSha256')]:
            self.assertEqual(digest(TILES/file), r[field], file)
        classic_report = read(TILES/'lantern/classic-provenance.json')
        self.assertEqual(r['classicPreparation'], classic_report['sourceEvidence']['classicPreparation'])
        self.assertEqual(digest(TILES/self.modern['file']), self.report['output']['sha256'])

    def test_original_wall_height_does_not_change_with_exploration(self):
        for entry in self.manifest['tilesets']:
            if entry['id'] not in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
                continue
            frames = entry['projectedFrames']['frames']
            walls = entry['lanternWalls']
            for record in walls['tiles'].values():
                if record['topology'] != 'horizontal':
                    continue
                silhouettes = {(tuple(frames[str(slot)]['offset']),
                                tuple(frames[str(slot)]['source'][2:]), frames[str(slot)]['depth'])
                               for slot in record['variants']}
                self.assertEqual(silhouettes, {((0, -7), (64, 71), 64)}, entry['id'])
            for record in [walls['doors']['1286'], walls['doors']['1288'], walls['bars']['horizontal']]:
                for slot, ground in zip(record['variants'], record['groundBounds']):
                    frame = frames[str(slot)]
                    self.assertEqual(frame['offset'][1] + frame['source'][3], 64)
                    self.assertEqual(frame['depth'], 64)
                    self.assertEqual(ground, [0, 0, 64, 64])

    def test_original_editions_keep_chosen_license(self):
        for name in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
            entry = next(t for t in self.manifest['tilesets'] if t['id']==name)
            self.assertEqual(entry['license'], 'CC-BY-4.0')
            self.assertEqual(entry['credit'], 'NetHack Atlas project')
        self.assertEqual(self.report['artworkLicense'], 'CC-BY-4.0')

    def test_bottom_corners_close_the_room_at_full_height(self):
        # Owner reports 4A302715 and 57FA3F5B: a reused northern corner extends
        # its vertical column south, suggesting another room beyond this wall.
        for entry in self.manifest['tilesets']:
            if entry['id'] not in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
                continue
            frames = entry['projectedFrames']['frames']
            with Image.open(TILES/entry['file']) as image:
                for start in (1273, 1471, 1482, 1493, 1504):
                    for north, south in ((start+2,start+4),(start+3,start+5)):
                        upper, lower = frames[str(north)], frames[str(south)]
                        self.assertEqual(lower['source'][2:], [51,71], entry['id'])
                        self.assertEqual(lower['offset'][1]+lower['source'][3],64)
                        def pixels(frame):
                            x,y,w,h=frame['source']
                            return image.crop((x,y,x+w,y+h)).tobytes()
                        self.assertNotEqual(pixels(upper),pixels(lower),
                                            (entry['id'], 'South corner reused north-facing art', south))


if __name__ == '__main__':
    unittest.main()
