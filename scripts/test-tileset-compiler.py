#!/usr/bin/env python3
"""Exercise contributor recipes and safe publication without changing shipped assets."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tileset_compiler', ROOT/'assets/tiles/compiler.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


class CompilerTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.artifacts').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='tileset-test-', dir=ROOT/'.artifacts')
        self.folder = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.source = self.folder/'source.png'
        self.recipe_path = self.folder/'recipe.json'
        self.out = self.folder/'compiled'
        self.image = Image.new('RGBA', (640, 1392))
        # Distinct first/last canonical tiles, with nonsquare proportions.
        self.image.paste((19,101,207,255), (0,0,16,24))
        self.image.paste((211,31,73,255), (368,1368,384,1392))
        self.image.save(self.source)
        self.recipe = {'schemaVersion': 1, 'id': 'cinder', 'name': 'Cinder',
                       'engineVersion': '5.0.0', 'output': 'cinder.png',
                       'provenance': 'cinder/provenance.json', 'license': 'MIT',
                       'credit': 'Test artist', 'licenseFile': 'docs/MIT-LICENSE.txt',
                       'description': 'An independent recipe fixture.', 'version': '1',
                       'source': {'kind': 'atlas', 'path': self.source.relative_to(ROOT).as_posix(),
                                  'sha256': compiler.digest(self.source), 'tileWidth': 16,
                                  'tileHeight': 24, 'columns': 40, 'count': 2304}}

    def write(self, recipe=None, name='recipe.json'):
        path = self.folder/name
        path.write_text(json.dumps(recipe or self.recipe))
        return path

    def build(self, recipe=None):
        return compiler.build([self.write(recipe)], self.out)

    def snapshot(self):
        return {p.relative_to(self.out): p.read_bytes() for p in self.out.rglob('*') if p.is_file()}

    def test_single_arbitrary_name_and_rectangular_canonical_order(self):
        entries = self.build()
        self.assertEqual([(e['id'],e['name'],e['file']) for e in entries], [('cinder','Cinder','cinder.png')])
        self.assertEqual(list(self.out.glob('*.png')), [self.out/'cinder.png'])
        self.assertEqual((self.out/'cinder.png').stat().st_mode & 0o777, 0o644)
        manifest = compiler.read(self.out/'manifest.json')
        self.assertEqual(manifest['default'], 'cinder')
        with Image.open(self.out/'cinder.png') as actual:
            self.assertEqual(actual.size, (640,1392))
            self.assertEqual(actual.convert('RGBA').tobytes(), self.image.tobytes())

    def test_single_named_tileset_can_declare_its_own_large_sprite(self):
        # The declared height is deliberately outside the original art tier table.
        self.image = Image.new('RGBA', (640,1632))
        self.image.paste((83,27,201,255), (0,1392,47,1529))
        self.image.save(self.source)
        rendering = self.folder/'rendering.json'
        rendering.write_text(json.dumps({'projectedFrames': {'version': 1, 'padding': [0,0,0,0],
            'frames': {'0': {'source': [0,1392,47,137], 'offset': [8,-73], 'depth': 64, 'kind': 'creature'}}}}))
        recipe = copy.deepcopy(self.recipe)
        recipe['source']['sha256'] = compiler.digest(self.source)
        recipe['source']['rendering'] = {'path': rendering.relative_to(ROOT).as_posix(), 'sha256': compiler.digest(rendering)}
        entry = self.build(recipe)[0]
        self.assertEqual(entry['name'], 'Cinder')
        frame = entry['projectedFrames']['frames']['0']
        self.assertEqual(frame['source'][2:], [47,137])
        self.assertEqual(frame['offset'], [8,-73])
        with Image.open(self.out/entry['file']) as image:
            x,y,w,h=frame['source']
            self.assertEqual(image.crop((x,y,x+w,y+h)).tobytes(), self.image.crop((0,1392,47,1529)).tobytes())
            self.assertEqual(image.height % 24, 0)
        self.assertEqual(len(list(self.out.glob('*.png'))), 1)

    def test_receipt_identifies_recipe_input_compiler_and_output(self):
        self.build()
        r = compiler.read(self.out/'cinder/provenance.json')
        for record in [r['recipe'],r['compiler'],r['packer'],*r['inputs']]:
            self.assertEqual(record['sha256'], compiler.digest(ROOT/record['file']))
        self.assertEqual(r['output']['sha256'], compiler.digest(self.out/'cinder.png'))
        self.assertEqual((r['output']['width'],r['output']['height']), (640,1392))
        self.assertEqual(r['artworkCredit'], 'Test artist')

    def test_repeated_build_is_byte_reproducible(self):
        self.build()
        previous = self.snapshot()
        self.build()
        self.assertEqual(self.snapshot(), previous)

    def test_prepared_receipts_ignore_local_metadata_and_track_artwork(self):
        sources = self.folder/'prepared'
        (sources/'recipes').mkdir(parents=True)
        artwork = sources/'artwork.png'
        artwork.write_bytes(b'retained artwork')
        recipe = copy.deepcopy(self.recipe)
        recipe['source'] = {'kind': 'prepared', 'provider': 'lantern', 'creatureSizing': 'grid'}
        with patch.object(compiler, 'HERE', sources):
            clean = compiler.input_records({}, recipe, [])
            for name in ('.DS_Store', 'nested/._artwork.png', 'cache/compiled.PYC',
                         '__MACOSX/metadata', '__pycache__/cached.pyc'):
                path = sources/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'local metadata')
            self.assertEqual(compiler.input_records({}, recipe, []), clean)
            artwork.write_bytes(b'updated retained artwork')
            updated = compiler.input_records({}, recipe, [])
        key = artwork.relative_to(ROOT).as_posix()
        original = next(record for record in clean if record['file'] == key)
        changed = next(record for record in updated if record['file'] == key)
        self.assertNotEqual(original['sha256'], changed['sha256'])
        self.assertEqual(changed['sha256'], compiler.digest(artwork))

    def test_bad_source_checksum_keeps_existing_publication(self):
        self.build(); previous = self.snapshot()
        bad = copy.deepcopy(self.recipe); bad['source']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.build(bad)
        self.assertEqual(self.snapshot(), previous)

    def test_entire_batch_is_validated_before_publication(self):
        self.build(); previous = self.snapshot()
        other = copy.deepcopy(self.recipe)
        other.update(id='other', output='other.png', provenance='other/provenance.json')
        other['source']['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            compiler.build([self.write(), self.write(other,'other.json')], self.out)
        self.assertEqual(self.snapshot(), previous)

    def test_duplicate_ids_and_outputs_are_rejected(self):
        for field in ('id','output','provenance'):
            other = copy.deepcopy(self.recipe)
            other.update(id='other', output='other.png', provenance='other/provenance.json')
            other[field] = self.recipe[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Duplicate'):
                compiler.build([self.write(),self.write(other,'other.json')], self.out)
        self.assertFalse(self.out.exists())

    def test_incomplete_grid_and_invalid_geometry_are_rejected(self):
        for field,value in [('count',2303),('columns',41),('tileWidth',0),('tileHeight',True)]:
            bad = copy.deepcopy(self.recipe); bad['source'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.build(bad)
        self.assertFalse(self.out.exists())

    def test_source_traversal_and_symlinks_are_rejected(self):
        bad = copy.deepcopy(self.recipe); bad['source']['path'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, 'traversal'):
            self.build(bad)
        link = self.folder/'link.png'; link.symlink_to(self.source)
        bad['source']['path'] = link.relative_to(ROOT).as_posix()
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            self.build(bad)
        self.assertFalse(self.out.exists())

    def test_out_of_bounds_projected_source_is_rejected(self):
        rendering = self.folder/'bad-frame.json'
        rendering.write_text(json.dumps({'projectedFrames': {'version': 1, 'frames': {
            '0': {'source': [639,1391,2,2], 'offset': [0,0]}}}}))
        bad = copy.deepcopy(self.recipe)
        bad['source']['rendering'] = {'path': rendering.relative_to(ROOT).as_posix(), 'sha256': compiler.digest(rendering)}
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.build(bad)
        self.assertFalse(self.out.exists())

    def test_filesystem_failure_restores_the_previous_complete_publication(self):
        self.build(); previous = self.snapshot()
        calls = 0
        replace = compiler.os.replace
        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Injected publication failure')
            return replace(source,target)
        with patch.object(compiler.os,'replace',side_effect=fail_second), self.assertRaises(OSError):
            self.build()
        self.assertEqual(self.snapshot(), previous)

    def test_existing_entry_cannot_lose_its_png_to_another_id(self):
        self.build(); previous=self.snapshot()
        other=copy.deepcopy(self.recipe);other.update(id='other',provenance='other/provenance.json')
        with self.assertRaisesRegex(ValueError, 'belongs'):
            self.build(other)
        self.assertEqual(self.snapshot(), previous)

    def test_unrelated_existing_json_cannot_be_replaced_by_a_receipt(self):
        self.out.mkdir()
        source_record = self.out/'catalog.json'
        original = b'{"canonicalSlots":2304}\n'; source_record.write_bytes(original)
        bad=copy.deepcopy(self.recipe); bad['provenance']='catalog.json'
        with self.assertRaisesRegex(ValueError, 'not owned'):
            self.build(bad)
        self.assertEqual(source_record.read_bytes(),original)
        self.assertFalse((self.out/'cinder.png').exists())

    def test_another_recipe_cannot_replace_an_existing_receipt(self):
        self.build(); previous=self.snapshot()
        other=copy.deepcopy(self.recipe);other.update(id='other',output='other.png')
        with self.assertRaisesRegex(ValueError, 'not owned'):
            self.build(other)
        self.assertEqual(self.snapshot(),previous)

    def test_unregistered_png_cannot_be_overwritten(self):
        self.out.mkdir();png=self.out/'cinder.png';png.write_bytes(b'preserve this artwork')
        with self.assertRaisesRegex(ValueError, 'not owned'):
            self.build()
        self.assertEqual(png.read_bytes(),b'preserve this artwork')

    def test_known_prepared_art_cannot_be_relicensed_by_a_recipe(self):
        recipe=copy.deepcopy(self.recipe)
        recipe['source']={'kind':'prepared','provider':'lantern','creatureSizing':'grid'}
        prepared={'image':self.image,'metadata':{},'evidence':{
            'artworkLicense':'CC-BY-4.0','artworkCredit':'NetHack Atlas project'}}
        with patch.object(compiler,'prepare',return_value=prepared), self.assertRaisesRegex(ValueError, 'retain'):
            self.build(recipe)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
