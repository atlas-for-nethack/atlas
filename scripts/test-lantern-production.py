#!/usr/bin/env python3
"""Audit the built production atlas against independent source-art records."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'assets/tiles/lantern'


def read(path):
    return json.loads(path.read_text())


class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = next(t for t in read(HERE.parent/'manifest.json')['tilesets'] if t['id'] == 'lantern')
        cls.atlas = Image.open(HERE.parent/cls.entry['file']).convert('RGBA')
        cls.tiles = read(HERE/'catalog.json')['tiles']

    def crop(self, slot):
        x, y = slot % 40 * 64, slot // 40 * 64
        return self.atlas.crop((x, y, x+64, y+64))

    def test_reviewed_art_survives_actual_slot_assembly(self):
        for key, record in read(HERE/'production-overrides.json').items():
            source = HERE / record['file']
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), record['sha256'])
            expected = Image.open(source).convert('RGBA')
            self.assertEqual(expected.size, (64, 64))
            slots = [t['slot'] for t in self.tiles if t['art_key'] == key and not t.get('transform')]
            self.assertTrue(slots, key)
            for slot in slots:
                self.assertEqual(self.crop(slot).tobytes(), expected.tobytes(), (key, slot))

    def test_floor_grid_and_transparency(self):
        floor = Image.open(HERE/'production-sources/reference-floor.png').convert('RGBA')
        self.assertEqual(self.crop(1291).tobytes(), floor.tobytes())
        self.assertEqual(floor.getchannel('A').getextrema(), (255, 255))
        # Independent approved subject must preserve the floor at its edges.
        knight = next(t for t in self.tiles if t['art_key'] == 'monster/342-knight' and not t.get('transform'))
        sprite = self.crop(knight['slot'])
        self.assertEqual(sprite.getpixel((0, 0))[3], 0)
        composite = Image.alpha_composite(floor, sprite)
        self.assertEqual(composite.getpixel((0, 0)), floor.getpixel((0, 0)))
        self.assertNotEqual(composite.tobytes(), floor.tobytes())

    def test_wall_lookups_cannot_escape_appended_art(self):
        walls = self.entry['lanternWalls']
        self.assertEqual(walls['variantStart'], 2304)
        self.assertEqual(len(walls['tiles']), 55)
        self.assertEqual(len({v['topology'] for v in walls['tiles'].values()}), 11)
        self.assertEqual(set(walls['doors']), {'1285', '1286', '1287', '1288'})
        self.assertEqual(self.atlas.width, 2560)
        self.assertGreater(self.atlas.height, ((self.entry['count']+39)//40)*64)
        # Canonical and supplemental grid cells must not overlap packed frames.
        packed = [frame['source'] for record in
                  self.entry['projectedFrames']['frames'].values()
                  for frame in [record, *record.get('alternates', [])]]
        used = set()
        bars = walls['bars']
        self.assertEqual(bars['tile'], 1289)
        records = [*walls['tiles'].values(), *walls['doors'].values(),
                   bars['horizontal'], bars['vertical'], *bars.get('connections', {}).values()]
        for record in records:
            self.assertEqual(len(record['variants']), 256)
            for slot in record['variants']:
                self.assertGreaterEqual(slot, 2304)
                self.assertLess(slot, self.entry['count'])
                used.add(slot)
        self.assertIn(walls['variantStart'], used)
        for slot in used:
            self.assertIsNotNone(self.crop(slot).getchannel('A').getbbox())
            x, y = slot % 40 * 64, slot // 40 * 64
            self.assertLessEqual(x + 64, self.atlas.width)
            self.assertLessEqual(y + 64, self.atlas.height)
            for px, py, width, height in packed:
                self.assertFalse(max(x, px) < min(x + 64, px + width)
                                 and max(y, py) < min(y + 64, py + height),
                                 f'Wall slot {slot} overlaps a packed frame')

    def test_output_and_generator_provenance(self):
        report = read(HERE/'classic-provenance.json')
        for source in [report['recipe'], report['compiler'], report['packer'], *report['inputs']]:
            self.assertEqual(source['sha256'], hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest(), source['file'])
        self.assertEqual(report['output']['width'], self.atlas.width)
        self.assertEqual(report['output']['height'], self.atlas.height)
        record = report['sourceEvidence']['classicPreparation']
        self.assertEqual(report['output']['sha256'], hashlib.sha256((HERE.parent/self.entry['file']).read_bytes()).hexdigest())
        for field, filename in [('assemblerSha256', 'build_production.py'),
                                ('baseAssemblerSha256', 'build_atlas.py'),
                                ('wallGeneratorSha256', 'projected_architecture.py'),
                                ('catalogSha256', 'catalog.json'),
                                ('sourceRegistrySha256', 'sources.json'),
                                ('wallSourceRecordSha256', 'modern-architecture/extraction.json'),
                                ('architectureSourceSha256', 'modern-architecture/source.png'),
                                ('barsSourceRecordSha256', 'production-sources/iron-bars-provenance.json'),
                                ('cleanupSha256', 'prepare_foregrounds.py')]:
            self.assertEqual(record[field], hashlib.sha256((HERE/filename).read_bytes()).hexdigest())
        for source in [*record['inputs'], *record['prompts'], record['floor']]:
            self.assertEqual(source['sha256'], hashlib.sha256((HERE/source['file']).read_bytes()).hexdigest())
        for filename, digest in read(HERE/'modern-architecture/extraction.json')['sources'].items():
            self.assertEqual(digest, hashlib.sha256((HERE/'modern-architecture'/filename).read_bytes()).hexdigest())
        self.assertEqual(record['packerSha256'], hashlib.sha256((HERE.parent/'packing.py').read_bytes()).hexdigest())

    def frame(self, slot):
        f = self.entry['projectedFrames']['frames'][str(slot)]
        x,y,w,h = f['source']
        return f, self.atlas.crop((x,y,x+w,y+h))

    def test_architectural_frames_preserve_clear_passages_and_map_bounds(self):
        projection = self.entry['projectedFrames']
        left,top,right,bottom = projection['padding']
        for slot in projection['frames']:
            f, image = self.frame(slot)
            x,y,w,h = f['source']; dx,dy = f['offset']
            self.assertTrue(0 <= x < x+w <= self.atlas.width and 0 <= y < y+h <= self.atlas.height)
            self.assertTrue(dx >= -left and dy >= -top and dx+w <= 64+right and dy+h <= 64+bottom)
            self.assertIsNone(f.get('kind'), 'Classic architecture cannot opt creatures into overhang')
        bars = self.entry['lanternWalls']['bars']
        for orientation in ('horizontal','vertical'):
            for mask in (1,2,4,8,10):
                _, image = self.frame(bars[orientation]['variants'][mask])
                alpha = image.getchannel('A').histogram()
                self.assertGreater(alpha[0], image.width*image.height*.10)
                self.assertGreater(sum(alpha[240:]), image.width*image.height*.10)

    def test_door_states_share_threshold_and_have_visible_opening(self):
        doors = self.entry['lanternWalls']['doors']
        for closed,opened,mask in [('1287','1285',2),('1287','1285',8),
                                    ('1288','1286',1),('1288','1286',4),
                                    ('1287','1285',10),('1288','1286',5)]:
            cf,ci = self.frame(doors[closed]['variants'][mask])
            of,oi = self.frame(doors[opened]['variants'][mask])
            self.assertEqual(cf['offset'],of['offset'])
            self.assertEqual(cf['source'][2:],of['source'][2:])
            self.assertEqual(cf['depth'],of['depth'])
            self.assertEqual(cf['offset'][1]+ci.height,cf['depth'])
            self.assertGreater(ci.height,64, 'Door must retain upright height on every wall')
            self.assertGreater(oi.getchannel('A').histogram()[0],ci.getchannel('A').histogram()[0])
            self.assertEqual(doors[closed]['groundBounds'][mask],doors[opened]['groundBounds'][mask])


if __name__ == '__main__':
    unittest.main()
