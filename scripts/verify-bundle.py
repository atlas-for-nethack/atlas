#!/usr/bin/env python3
"""Check the distributable's architecture, dependencies, resources and signature."""
import sys
sys.dont_write_bytecode = True
if not __debug__:
    raise SystemExit('FAIL: Bundle verification requires Python assertions; unset PYTHONOPTIMIZE and do not use -O.')
import argparse
from pathlib import Path
import plistlib
import json
import struct
import hashlib
import subprocess
import importlib.util
import tarfile
import package

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, default=root / 'dist/Atlas.app')
parser.add_argument('--archive', type=Path, help='Also inspect a release ZIP and compare it byte-for-byte to the app')
arguments = parser.parse_args()
app = arguments.app
# This runs before platform commands so contaminants fail independently of
# signatures, architectures or whether the resource is otherwise required.
package.inspect_payload(app)
if arguments.archive:
    package.inspect_payload(arguments.archive)
    package.verify_zip_matches(app, arguments.archive)
resources = app / 'Contents/Resources'
plist = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
source_plist = plistlib.loads((root / 'native/Info.plist').read_bytes())
for key in ['CFBundleName', 'CFBundleDisplayName', 'CFBundleIdentifier',
            'CFBundleExecutable', 'CFBundleShortVersionString', 'CFBundleVersion']:
    assert plist[key] == source_plist[key], f'Outdated bundle {key}: {plist[key]}'
assert plist['LSMinimumSystemVersion'] == '13.0'
for path in [app / 'Contents/MacOS/NetHackAtlas', resources / 'engine/nethack', resources / 'engine/recover']:
    arches = subprocess.check_output(['lipo', '-archs', str(path)], text=True).split()
    assert set(arches) == {'arm64', 'x86_64'}, (path, arches)
    for arch in arches:
        headers = subprocess.check_output(['otool', '-arch', arch, '-l', str(path)], text=True)
        assert 'minos 13.0' in headers, path
        dependencies = subprocess.check_output(['otool', '-arch', arch, '-L', str(path)], text=True)
        for line in dependencies.splitlines()[1:]:
            dependency = line.strip().split(' (')[0]
            assert dependency.startswith(('/usr/lib/', '/System/Library/')), (path, dependency)
for name in ['LICENSE.txt', 'LICENSES.md', 'docs/MIT-LICENSE.txt', 'docs/LUA-LICENSE.txt', 'web/index.html', 'web/app.js', 'web/input.js', 'web/character.js', 'web/tiles.js', 'web/styles.css', 'engine/nhdat', 'engine/license',
             'engine/sysconf', 'assets/tiles/creature-scale.json', 'assets/tiles/creature_scale.py', 'assets/tiles/manifest.json', 'assets/tiles/LICENSES.txt',
             'assets/tiles/lantern/LICENSE.txt', 'assets/tiles/lantern/modern-provenance.json',
             'assets/tiles/soot-and-brass/LICENSE.txt',
             'assets/tiles/soot-and-brass/modern-provenance.json', 'assets/tiles/sources/CC-BY-4.0.txt',
             'assets/tiles/sources/NGPL.txt',
             'Source/atlas-source.tar.gz', 'Source/nethack-500-src.tgz', 'Source/lua-5.4.8.tar.gz',
             'Source/apply-beginner-patch.py', 'Source/package.py', 'Source/source-pins.json', 'docs/ENGINE_FORK.md',
             'Source/engine-upstream-modifications.tar.gz', 'Source/engine-fork-audit.json']:
    assert (resources / name).is_file(), name
assert (resources / 'LICENSE.txt').read_bytes() == (root / 'LICENSE.txt').read_bytes(), 'Outdated independent component license'
for name in ('LICENSES.md', 'docs/MIT-LICENSE.txt', 'docs/LUA-LICENSE.txt', 'docs/COMPONENT-LICENSES.md'):
    assert (resources / name).read_bytes() == (root / name).read_bytes(), 'Outdated component notice: ' + name
spec = importlib.util.spec_from_file_location('engine_fork_audit', root / 'scripts/audit-engine-fork.py')
fork = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fork)
spec = importlib.util.spec_from_file_location('beginner_patch', root / 'engine/apply-beginner-patch.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)
archive = resources / 'Source/nethack-500-src.tgz'
package.verify_pins(resources / 'Source')
assert package.source_pins()['nethack-500-src.tgz']['sha256'] == fork.ARCHIVE_SHA256, 'Source pin and audit disagree'
with tarfile.open(archive) as upstream:
    allmain = upstream.extractfile('NetHack-5.0.0/src/allmain.c').read().decode()
    license_text = upstream.extractfile('NetHack-5.0.0/dat/license').read()
assert (resources / 'engine/license').read_bytes() == license_text
expected_updates = {
    'src/allmain.c': patch.apply_text(allmain).encode(),
    'win/shim/winshim.c': (root / 'engine/winatelier.c').read_bytes(),
    'sys/unix/hints/atelier': (root / 'engine/hints').read_bytes(),
}
with tarfile.open(resources / 'Source/engine-upstream-modifications.tar.gz') as updated:
    assert updated.getnames() == list(expected_updates), 'Unexpected updated engine source payload'
    for name, expected in expected_updates.items():
        assert updated.extractfile(name).read() == expected, 'Outdated updated source: '+name
report = json.loads((resources / 'Source/engine-fork-audit.json').read_text())
assert report['archiveSha256'] == fork.ARCHIVE_SHA256
assert set(report['modifiedFiles']) == fork.MODIFIED
assert report['originalFileCount'] == 1265 and report['unchangedFileCount'] == 1263
assert report['addedIntegrationFiles'] == ['sys/unix/hints/atelier']
for name in fork.MODIFIED:
    assert report['files'][name]['currentSha256'] == fork.digest(expected_updates[name]), name
for name in ('apply-beginner-patch.py', 'winatelier.c', 'hints'):
    assert (resources / 'Source' / name).read_bytes() == (root / 'engine' / name).read_bytes(), name
assert (resources / 'docs/ENGINE_FORK.md').read_bytes() == (root / 'docs/ENGINE_FORK.md').read_bytes()
with tarfile.open(resources / 'Source/atlas-source.tar.gz') as source:
    maintained = package.tracked_files(root)
    expected_source = set(package.selected_files(root, package.SOURCE_ROOTS, ('engine/runtime',), allowed=maintained))
    actual_source = {member.name for member in source if member.isfile()}
    assert actual_source == expected_source | {package.SOURCE_INVENTORY}, 'Unexpected/missing maintained Atlas source files'
    assert json.loads(source.extractfile(package.SOURCE_INVENTORY).read()) == sorted(maintained), 'Outdated standalone source inventory'
    for name in sorted(expected_source):
        assert source.extractfile(name).read() == (root / name).read_bytes(), 'Outdated Atlas source: '+name
assert not (resources / 'design').exists(), 'Retired design tree must not ship'
for name in package.selected_files(root, package.RESOURCE_ROOTS, allowed=maintained):
    assert (resources / name).read_bytes() == (root / name).read_bytes(), 'Outdated maintained resource: '+name
for name in ('package.py', 'source-pins.json', 'build-engine.sh'):
    assert (resources / 'Source' / name).read_bytes() == (root / 'scripts' / name).read_bytes(), 'Outdated standalone source helper: '+name
assert not (resources / 'engine/save').exists(), 'User saves must not ship in app'
manifest = json.loads((resources / 'assets/tiles/manifest.json').read_text())
recipes = [json.loads(path.read_text()) for path in sorted((root/'assets/tiles/recipes').glob('*.json'))]
assert len({recipe['id'] for recipe in recipes}) == len(recipes), 'Duplicate tileset recipe ID'
by_id = {recipe['id']: recipe for recipe in recipes}
assert set(by_id) == {atlas['id'] for atlas in manifest['tilesets']}, 'Recipe and bundled tileset inventory disagree'
assert len({atlas['file'] for atlas in manifest['tilesets']}) == len(manifest['tilesets']), 'Selectable tilesets must own distinct PNGs'
for identifier in ('lantern', 'lantern-modern', 'soot-and-brass', 'soot-and-brass-classic'):
    original = next(t for t in manifest['tilesets'] if t['id'] == identifier)
    assert original['license'] == 'CC-BY-4.0', identifier
    assert original['credit'] == 'NetHack Atlas project', identifier
for atlas in manifest['tilesets']:
    image = resources / 'assets/tiles' / atlas['file']
    assert image.is_file(), f'Missing bundled tileset: {atlas["id"]}'
    header = image.read_bytes()[:32]
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        width, height = struct.unpack('>II', header[16:24])
    elif header.startswith(b'BM'):
        width, height = struct.unpack('<ii', header[18:26])
        height = abs(height)
    else:
        raise AssertionError(f'Unsupported tileset image: {image}')
    tw, th = atlas['tileWidth'], atlas['tileHeight']
    assert width > 0 and height > 0 and tw > 0 and th > 0, atlas['id']
    assert width % tw == 0 and height % th == 0, atlas['id']
    assert width // tw == atlas['columns'], atlas['id']
    assert width // tw * (height // th) >= atlas['count'] >= manifest['requiredTileCount'], atlas['id']
    recipe = by_id[atlas['id']]
    assert recipe['output'] == atlas['file'], 'Recipe output mismatch: ' + atlas['id']
    receipt = json.loads((resources/'assets/tiles'/recipe['provenance']).read_text())
    assert receipt['schema'] == 1 and receipt['engineVersion'] == '5.0.0'
    assert receipt['output'] == {'file': atlas['file'], 'sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                                 'width': width, 'height': height}, 'Tileset receipt mismatch: ' + atlas['id']
    assert atlas['revision'] == receipt['output']['sha256'], 'Tileset revision mismatch'
    for field in ('license', 'credit'):
        assert recipe[field] == atlas[field], 'Tileset attribution mismatch'
    assert receipt['artworkLicense'] == recipe['license'] and receipt['artworkCredit'] == recipe['credit']
    for record in [receipt['recipe'], receipt['compiler'], receipt['packer'], *receipt['inputs']]:
        path = root/record['file']
        assert path.resolve().is_relative_to(root) and path.is_file(), 'Missing/nonlocal tileset input'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], 'Stale tileset input: ' + record['file']
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
print('PASS: Universal 2, macOS 13 minimum, system-only dependencies, clean resources/source/licenses and archives, both pinned sources, valid local signature.')
