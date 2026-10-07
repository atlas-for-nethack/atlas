#!/usr/bin/env python3
"""Check the shipped mapping, reproducible inputs and directional sprite contracts."""
import hashlib
import json
from pathlib import Path
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'assets/tiles/soot-and-brass'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SootAndBrass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read(HERE.parent / 'manifest.json')
        cls.entry = next(t for t in cls.manifest['tilesets'] if t['id'] == 'soot-and-brass')
        cls.catalog = read(HERE.parent / 'lantern/catalog.json')
        cls.report = read(HERE / 'modern-provenance.json')
        cls.provenance = cls.report['sourceEvidence']
        cls.image = Image.open(HERE.parent / cls.entry['file']).convert('RGBA')

    def tile(self, slot):
        x, y = slot % 40 * 64, slot // 40 * 64
        return self.image.crop((x, y, x + 64, y + 64))

    def test_complete_explicit_appearance_coverage(self):
        expected = {item['key'] for item in self.catalog['art_keys']}
        covered = set(self.provenance['assignments']) | set(self.provenance['proceduralKeys'])
        self.assertEqual(expected, covered)
        self.assertEqual(len(self.catalog['tiles']), 2304)
        self.assertEqual(self.entry['canonicalCount'], 2304)
        self.assertEqual(self.image.width, 40 * 64)
        self.assertGreaterEqual(self.image.width * self.image.height // 4096, self.entry['count'])
        for item in self.catalog['tiles']:
            if item['category'] in ('monster', 'object'):
                self.assertIsNotNone(self.tile(item['slot']).getchannel('A').getbbox(), item)

    def test_retained_sources_and_output_match_provenance(self):
        for source in [self.report['recipe'], self.report['compiler'], self.report['packer'], *self.report['inputs']]:
            self.assertEqual(digest(ROOT/source['file']), source['sha256'], source['file'])
        self.assertEqual([self.report['output']['width'], self.report['output']['height']], list(self.image.size))
        for record in self.provenance['retainedInputs']:
            self.assertEqual(digest(HERE / record['file']), record['sha256'], record['file'])
        self.assertEqual(digest(HERE.parent / 'lantern/catalog.json'), self.provenance['catalog']['sha256'])
        self.assertEqual(digest(HERE.parent / self.entry['file']), self.report['output']['sha256'])
        for key, assignments in self.provenance['assignments'].items():
            self.assertTrue(assignments, key)
            self.assertTrue(all(a['file'].startswith(('monsters/', 'objects/', 'terrain/')) for a in assignments), key)

    def test_existing_sets_and_defaults_remain_available(self):
        ids = [entry['id'] for entry in self.manifest['tilesets']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.manifest['default'], 'lantern')
        self.assertEqual(ids[0], 'lantern')
        self.assertIn('official', ids)

    def test_projected_roster_and_packing(self):
        policy = read(HERE.parent / 'creature-scale.json')['monsters']
        expected = {item['key'] for item in self.catalog['art_keys'] if item['category'] == 'monster'}
        self.assertEqual(set(policy), expected, 'Every creature requires an explicit scale review')
        projection = self.entry['projectedFrames']
        self.assertEqual(projection['version'],1)
        frames = projection['frames']
        for tile in self.catalog['tiles']:
            if tile['art_key'] in expected:
                self.assertIn(str(tile['slot']),frames, tile['art_key'])
        left,top,right,bottom = projection['padding']
        packed_frames = [(slot, candidate) for slot,frame in frames.items()
                         for candidate in [frame, *frame.get('alternates', [])]]
        for slot,frame in packed_frames:
            x,y,w,h = frame['source']; dx,dy = frame['offset']
            self.assertTrue(0<=x<x+w<=self.image.width and 0<=y<y+h<=self.image.height,slot)
            self.assertIsNotNone(self.image.crop((x,y,x+w,y+h)).getchannel('A').getbbox(),slot)
            self.assertTrue(dx>=-left and dy>=-top and dx+w<=64+right and dy+h<=64+bottom,slot)
        self.assertGreater(frames['632']['source'][3], 120, 'Asmodeus retains approved imposing height')
        self.assertGreater(frames['532']['source'][3], 75, 'Human height retains reference proportions')
        self.assertLess(frames['12']['source'][3], 48, 'Acid blob remains small')

    def test_modern_creatures_share_canonical_size(self):
        scale = read(HERE.parent / 'creature-scale.json')
        policy = scale['monsters']
        self.assertEqual(scale['sizeOrder'], ['tiny', 'small', 'standard', 'large', 'very-large', 'huge', 'massive'])
        for key, rule in policy.items():
            self.assertEqual(rule['height'], scale['tiers'][rule['tier']]['height'], key)
        examples = ['newt', 'goblin', 'human', 'bone devil', 'balrog', 'titan', 'red dragon']
        for name, tier in zip(examples, scale['sizeOrder']):
            item = next(t for t in self.catalog['art_keys'] if t['category']=='monster' and t['label']==name)
            self.assertEqual(policy[item['key']]['tier'], tier, name)
        modern = [t for t in self.manifest['tilesets'] if t['id'] in ('soot-and-brass','lantern-modern')]
        self.assertEqual(len(modern), 2)
        for tile in self.catalog['tiles']:
            if tile['art_key'] not in policy:
                continue
            rule = policy[tile['art_key']]
            sizes = [t['projectedFrames']['frames'][str(tile['slot'])]['source'][2:] for t in modern]
            measured = [max(size) if rule.get('scaleAxis') == 'longest' else size[1] for size in sizes]
            self.assertEqual(measured, [rule['height']]*2, tile['art_key'])
            if tile['label'] in ('trapper', 'lurker above'):
                self.assertEqual(rule.get('scaleAxis'), 'longest')
                for w, h in sizes:
                    self.assertEqual(w, 160, tile['label'])
                    self.assertLess(h, w, 'Flat bodies must retain their low silhouette')
        record = self.provenance['creatureScale']
        self.assertEqual(digest(HERE/record['file']), record['sha256'])
        self.assertEqual(digest(HERE/record['helper']), record['helperSha256'])

    def test_transparent_recognizable_anchor_subjects(self):
        for slot in (0, 12, 32, 324, 632, 684, 1006, 1114):
            alpha = self.tile(slot).getchannel('A')
            histogram = alpha.histogram()
            self.assertGreater(histogram[0], 200, f'Anchor {slot} has an opaque studio background')
            self.assertGreater(sum(histogram[128:]), 60, f'Anchor {slot} is empty or faint')
        self.assertNotEqual(self.tile(12).tobytes(), self.tile(324).tobytes(), 'Blob and lichen must differ')

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

    def test_classic_preserves_architecture_and_bounds_occupants(self):
        classic = next(t for t in self.manifest['tilesets'] if t['id'] == 'soot-and-brass-classic')
        self.assertNotEqual(classic['file'], self.entry['file'])
        classic_image = Image.open(HERE.parent / classic['file']).convert('RGBA')
        grid_height = ((classic['count'] + 39) // 40) * 64
        self.assertEqual(classic_image.crop((0, 0, classic_image.width, grid_height)).tobytes(),
                         self.image.crop((0, 0, classic_image.width, grid_height)).tobytes())
        report = read(HERE / 'classic-provenance.json')
        for source in [report['recipe'], report['compiler'], report['packer'], *report['inputs']]:
            self.assertEqual(digest(ROOT/source['file']), source['sha256'], source['file'])
        self.assertEqual(digest(HERE.parent/classic['file']), report['output']['sha256'])
        self.assertEqual(classic['lanternWalls'], self.entry['lanternWalls'])
        frames = classic['projectedFrames']['frames']
        modern = self.entry['projectedFrames']['frames']
        for slot, frame in frames.items():
            self.assert_frame_equal(classic_image, frame, self.image, modern[slot])
        for tile in self.catalog['tiles']:
            slot = str(tile['slot'])
            if tile['category'] in ('monster', 'object', 'effect') or tile.get('transform') == 'statue':
                self.assertNotIn(slot, frames, tile)
            elif slot in modern:
                self.assert_frame_equal(classic_image, frames[slot], self.image, modern[slot])
        # Regional floors and packed-image padding are bounded atlas cells,
        # not projected architecture. Compare every supplemental frame that exists.
        for slot in modern:
            if int(slot) >= classic['canonicalCount']:
                self.assert_frame_equal(classic_image, frames[slot], self.image, modern[slot])
        self.assertEqual(classic.get('regionalMaterials'), self.entry.get('regionalMaterials'))

    def test_object_silhouettes_have_clear_cell_margins(self):
        # Equal-grid source cuts previously retained neighboring fragments and
        # clipped long items. Check the shipped sprites, not helper return values.
        for item in self.catalog['art_keys']:
            if item['category'] != 'object':
                continue
            alpha = self.tile(item['slots'][0]).getchannel('A').point(lambda a: 255 if a > 32 else 0)
            box = alpha.getbbox()
            self.assertIsNotNone(box, item['key'])
            self.assertTrue(box[0] >= 6 and box[1] >= 6 and box[2] <= 58 and box[3] <= 58,
                            (item['key'], box))

    def test_all_directional_lookups_stay_in_atlas(self):
        walls = self.entry['lanternWalls']
        self.assertEqual(walls['version'], 1)
        self.assertEqual(walls['neighborOrder'], ['N', 'E', 'S', 'W', 'NE', 'SE', 'SW', 'NW'])
        self.assertEqual(len(walls['tiles']), 55)
        self.assertEqual(set(walls['doors']), {'1285', '1286', '1287', '1288'})
        bars = walls['bars']
        self.assertEqual(bars['tile'], 1289)
        self.assertEqual(set(bars['connections']), {'3', '6', '7', '9', '11', '12', '13', '14', '15'})
        entries = [*walls['tiles'].values(), *walls['doors'].values(), bars['horizontal'], bars['vertical'], *bars['connections'].values()]
        for entry in entries:
            self.assertEqual(len(entry['variants']), 256, entry['topology'])
            for index in entry['variants']:
                self.assertTrue(2304 <= index < self.entry['count'], index)
            if 'groundBounds' in entry:
                self.assertEqual(len(entry['groundBounds']), 256)
                for x, y, width, height in entry['groundBounds']:
                    self.assertTrue(0 <= x < 64 and 0 <= y < 64)
                    self.assertTrue(0 < width <= 64 - x and 0 < height <= 64 - y)

    def test_open_door_frames_stay_put_and_bar_gaps_reveal_ground(self):
        walls = self.entry['lanternWalls']
        for closed, opened in [('1287', '1285'), ('1288', '1286')]:
            a, b = walls['doors'][closed], walls['doors'][opened]
            self.assertEqual(a['groundBounds'], b['groundBounds'], 'Opening must not shift door frame')
            self.assertTrue(b['open'])
            for mask in (0, 1, 2, 4, 8, 15, 255):
                self.assertNotEqual(self.tile(a['variants'][mask]).tobytes(), self.tile(b['variants'][mask]).tobytes())
        for direction, mask in [('horizontal', 1), ('horizontal', 4), ('vertical', 2), ('vertical', 8)]:
            entry = walls['bars'][direction]
            alpha = self.tile(entry['variants'][mask]).getchannel('A')
            x, y, width, height = entry['groundBounds'][mask]
            gaps = alpha.crop((x, y, x + width, y + height)).histogram()
            self.assertGreater(gaps[0], width * height * .15, f'{direction}/{mask}: blocked bar gaps')
            self.assertGreater(sum(gaps[128:]), width * height * .03, f'{direction}/{mask}: missing bars')


if __name__ == '__main__':
    unittest.main()
