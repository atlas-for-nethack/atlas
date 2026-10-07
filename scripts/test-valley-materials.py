#!/usr/bin/env python3
"""Check the approved Valley composition without creating or modifying artwork.

Use --shipped after regeneration to require the production manifest entry.
Node executes the independent approved preview and actual game renderer.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / 'assets/tiles'
ORIGINALS = ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic')
SHIPPED = '--shipped' in sys.argv
if SHIPPED:
    sys.argv.remove('--shipped')


def node(script, value):
    return subprocess.check_output(['node', '-e', script], cwd=ROOT,
                                   input=json.dumps(value).encode()).decode()


class ValleyMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = {entry['id']: entry for entry in
                       json.loads((TILES / 'manifest.json').read_text())['tilesets']}
        spec = importlib.util.spec_from_file_location('valley_regional', TILES / 'regional_materials.py')
        cls.regional = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.regional)
        cls.examples = {}
        for ident in ORIGINALS:
            entry = copy.deepcopy(cls.entries[ident])
            if not SHIPPED:
                entry['regionalMaterials']['valley'] = cls.regional.compose_valley(
                    entry['regionalMaterials'], entry['lanternWalls'])
            if 'valley' not in entry['regionalMaterials']:
                raise AssertionError('Missing shipped Valley material: ' + ident)
            cls.examples[ident] = entry

    def test_exact_approved_preview_metadata(self):
        script = """
const fs=require('fs'),study=require('./tools/tileset-preview/fixtures/valley-preview.js');
const atlas=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(study.compose(atlas,null).atlas.regionalMaterials['valley-review']));
"""
        for ident, entry in self.examples.items():
            self.assertEqual(entry['regionalMaterials']['valley'],
                             json.loads(node(script, self.entries[ident])), ident)

    def test_composition_preserves_inputs_and_copies_wall_rules(self):
        for ident, entry in self.entries.items():
            if ident not in ORIGINALS:
                continue
            original = copy.deepcopy(entry)
            material = self.regional.compose_valley(entry['regionalMaterials'], entry['lanternWalls'])
            self.assertEqual(entry, original, ident)
            # Future edits to this material cannot mutate Vlad or ordinary walls.
            material['tileMap']['1273'] = -1
            material['wallTiles']['1482']['variants'][0] = -1
            self.assertEqual(entry, original, ident)
            self.assertNotEqual(material['wallTiles']['1273']['variants'][0], -1)

    def test_aliases_and_projection_bounds(self):
        for ident, entry in self.examples.items():
            with self.subTest(edition=ident):
                material = entry['regionalMaterials']['valley']
                vlad = entry['regionalMaterials']['vlad']['tileMap']
                for offset in range(11):
                    ordinary, infernal = str(1273 + offset), str(1482 + offset)
                    self.assertEqual(material['tileMap'][infernal], vlad[ordinary])
                    self.assertEqual(material['wallTiles'][ordinary], material['wallTiles'][infernal])
                    self.assertEqual(material['wallTiles'][infernal], entry['lanternWalls']['tiles'][ordinary])
                    for slot in material['wallTiles'][infernal]['variants']:
                        self.assertIn(str(slot), material['tileMap'])
                targets = set(material['tileMap'].values())
                self.assertTrue(all(isinstance(slot, int) and 0 <= slot < entry['count'] for slot in targets))
                with Image.open(TILES / entry['file']) as image:
                    for slot in targets:
                        self.assertLessEqual((slot % entry['columns'] + 1) * entry['tileWidth'], image.width)
                        self.assertLessEqual((slot // entry['columns'] + 1) * entry['tileHeight'], image.height)
                        frame = entry['projectedFrames']['frames'].get(str(slot))
                        if frame:
                            for pose in (frame, *frame.get('alternates', [])):
                                x, y, width, height = pose['source']
                                self.assertGreater(width, 0)
                                self.assertGreater(height, 0)
                                self.assertGreaterEqual(x, 0)
                                self.assertGreaterEqual(y, 0)
                                self.assertLessEqual(x + width, image.width)
                                self.assertLessEqual(y + height, image.height)

    def test_environment_parity(self):
        def frame_pixels(image, frame):
            x, y, width, height = frame['source']
            return image.crop((x, y, x + width, y + height)).tobytes()

        def equal_frames(first_image, first, second_image, second):
            for field in ('offset', 'depth', 'kind', 'occupiedSquares'):
                self.assertEqual(first.get(field), second.get(field), field)
            self.assertEqual(first['source'][2:], second['source'][2:])
            self.assertEqual(frame_pixels(first_image, first), frame_pixels(second_image, second))
            self.assertEqual(len(first.get('alternates', [])), len(second.get('alternates', [])))
            for a, b in zip(first.get('alternates', []), second.get('alternates', [])):
                equal_frames(first_image, a, second_image, b)

        for classic, modern in [('lantern', 'lantern-modern'), ('soot-and-brass-classic', 'soot-and-brass')]:
            a, b = self.examples[classic], self.examples[modern]
            material = a['regionalMaterials']['valley']
            self.assertEqual(material, b['regionalMaterials']['valley'])
            with Image.open(TILES / a['file']) as ai, Image.open(TILES / b['file']) as bi:
                for key, slot in material['tileMap'].items():
                    target = b['regionalMaterials']['valley']['tileMap'][key]
                    x, y = slot % 40 * 64, slot // 40 * 64
                    bx, by = target % 40 * 64, target // 40 * 64
                    self.assertEqual(ai.crop((x, y, x + 64, y + 64)).tobytes(),
                                     bi.crop((bx, by, bx + 64, by + 64)).tobytes())
                    frame = a['projectedFrames']['frames'].get(str(slot))
                    other = b['projectedFrames']['frames'].get(str(target))
                    if frame:
                        self.assertIsNotNone(other)
                        equal_frames(ai, frame, bi, other)
                    else:
                        self.assertIsNone(other)

    def test_third_party_exclusion(self):
        for ident, entry in self.entries.items():
            if ident not in ORIGINALS:
                self.assertNotIn('valley', entry.get('regionalMaterials', {}), ident)

    def test_actual_renderer_aliases_features_and_fallback(self):
        script = """
const fs=require('fs'),assert=require('node:assert/strict'),tiles=require('./web/tiles.js');
const atlas=JSON.parse(fs.readFileSync(0,'utf8'));
const image={width:atlas.columns*atlas.tileWidth,height:Math.ceil(atlas.count/atlas.columns)*atlas.tileHeight};
// Projection images occupy additional rows below the logical tile allocation.
for(const frame of Object.values(atlas.projectedFrames.frames))
  for(const pose of [frame,...(frame.alternates||[])])
    image.height=Math.max(image.height,pose.source[1]+pose.source[3]);
function paint(cell,options=atlas,cells=null,ground=true){
  const calls=[];tiles.paint({drawImage:(...args)=>calls.push(args.slice(1))},image,options,cell,0,0,64,64,ground,cells);
  return calls;
}
const offsets=[[0,-1],[1,0],[0,1],[-1,0],[1,-1],[1,1],[-1,1],[-1,-1]];
for(let offset=0;offset<11;offset++)for(let mask=0;mask<256;mask++){
  const cells=new Map();
  offsets.forEach(([dx,dy],bit)=>{if(mask&(1<<bit))cells.set(`${5+dx},${5+dy}`,{tile:1291,x:5+dx,y:5+dy});});
  assert.deepEqual(paint({tile:1482+offset,x:5,y:5,material:'valley'},atlas,cells),
                   paint({tile:1273+offset,x:5,y:5,material:'vlad'},atlas,cells));
}
for(const tile of [1284,1291,1292,1293,1294,1295,1296])
  assert.deepEqual(paint({tile,material:'valley'}),paint({tile,material:'gehennom'}));
for(const tile of [1056,1305,1310,1297,1298,1299,1300,1301,1302,1303,1304,1469,1470]){
  assert.deepEqual(paint({tile,material:'valley'}),paint({tile}));
  assert.deepEqual(paint({tile,material:'valley'},atlas,null,false),paint({tile},atlas,null,false));
}
const legacy={...atlas};delete legacy.regionalMaterials;
for(const tile of [1291,1482,1286,1289]){
  assert.deepEqual(paint({tile,material:'valley'},legacy),paint({tile},legacy));
  assert.deepEqual(paint({tile,material:'unknown'}),paint({tile}));
}
const invalid={...atlas,regionalMaterials:{valley:{tileMap:{1291:999999}}}};
assert.deepEqual(paint({tile:1291,material:'valley'},invalid),paint({tile:1291},invalid));
"""
        for ident, entry in self.examples.items():
            with self.subTest(edition=ident):
                node(script, entry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
