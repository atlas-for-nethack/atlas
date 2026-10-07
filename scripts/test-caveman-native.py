#!/usr/bin/env python3
"""Capture real Caveman home and goal levels in isolated packaged-app sessions.

Run scripts/test-caveman-quest.py --prepare after the packaged engine is rebuilt.
The normal app self-test draws the actual saved engine map with the current atlas;
each capture starts from a fresh copy of its prepared save. No player data is used.
"""
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
INDEX = ROOT/'.artifacts/caveman-engine-prepared.json'
OUT = ROOT/'.artifacts/caveman-native-results.json'
GALLERY = ROOT/'.artifacts/caveman-native-review.html'
UNKNOWN = {1469, 1470}
WALLS = set(range(1273, 1284))
FLOORS = {1291, 1292}
ALTARS = {1306, 1307, 1308}
DRAGON = {737}


def within(cell, bounds):
    x, y, width, height = bounds
    return x <= cell['x'] < x + width and y <= cell['y'] < y + height


def fixture(source, focus):
    data = copy.deepcopy(source)
    metadata = data['metadata']
    scene = metadata['scene']
    assert scene in ('home', 'goal') and metadata['mode'] == 'inspection'
    anchor_tiles = ALTARS if scene == 'home' else DRAGON
    anchor = next(c for c in metadata['displayedCells'] if c.get('tile') in anchor_tiles)
    if focus == 'detail':
        # Both landmarks come from displayed engine cells. The crop adapts to
        # a new generated world instead of assuming a fixed map origin.
        x = max(1, min(anchor['x']-7, 80-14))
        y = max(0, min(anchor['y']-(7 if scene == 'home' else 5), 21-10))
        bounds = [x, y, 14, 10]
    elif focus == 'whole':
        bounds = metadata['shapeBounds']
    else:
        raise ValueError(focus)
    cells = [c for c in metadata['displayedCells'] if within(c, bounds)]
    features = {'wall': sum(c.get('tile') in WALLS for c in cells),
                'floor': sum(c.get('tile') in FLOORS for c in cells),
                'landmark': sum(c.get('tile') in anchor_tiles for c in cells)}
    assert all(features.values()), (scene, focus, bounds, features)
    metadata['shapeBounds'] = bounds
    metadata['testTerrainTiles'] = [anchor['tile']]
    return data, features


def final_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def gallery(results):
    body = ['<!doctype html><meta charset="utf-8"><title>Caveman native review</title>',
            '<style>body{background:#101719;color:#e3e5df;font:16px system-ui;margin:24px}'
            'section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
            'img{width:100%}a{color:#d1b27a}</style>',
            '<h1>Caveman quest: packaged-app captures</h1>',
            '<p>Real engine inspection checkpoints, independently copied into disposable app sessions.'
            ' Detail views center the displayed altar or Chromatic Dragon. The app’s room-shape'
            ' self-test also checks map readiness and hover focus. Screenshots are review evidence.</p>']
    for scene in ('home', 'goal'):
        for focus in ('whole', 'detail'):
            matching = [r for r in results if r['scene'] == scene and r['focus'] == focus]
            if not matching:
                continue
            body.extend([f'<h2>{scene.title()} {focus}</h2>', '<section>'])
            for row in matching:
                label = html.escape(row['tileset'])
                image = Path(row['screenshot']).relative_to(GALLERY.parent).as_posix()
                body.append(f'<div><h3>{label}</h3><a href="{image}">'
                            f'<img src="{image}" alt="{scene} {focus}, {label}"></a></div>')
            body.append('</section>')
    GALLERY.write_text('\n'.join(body)+'\n')


def main():
    prepared = json.loads(INDEX.read_text())
    rows = {row['metadata']['scene']: row for row in prepared
            if row['metadata']['mode'] == 'inspection'
            and row['metadata']['scene'] in ('home', 'goal')}
    assert set(rows) == {'home', 'goal'}
    manifest = json.loads((ROOT/'assets/tiles/manifest.json').read_text())
    atlases = {entry['id']: entry for entry in manifest['tilesets']}
    results = []
    for scene in ('home', 'goal'):
        source = rows[scene]
        identity = source['metadata']['identity']
        assert identity['branch'] == 'The Quest' and identity['role'] == 'Caveman'
        material = 'caveman-goal' if scene == 'goal' else 'caveman'
        for focus in ('whole', 'detail'):
            data, expected = fixture(source, focus)
            tilesets = ('lantern-modern', 'soot-and-brass')
            if focus == 'detail':
                tilesets += ('lantern', 'soot-and-brass-classic')
            for tileset in tilesets:
                atlas = atlases[tileset]
                mapping = atlas['regionalMaterials'][material]
                assert str(1291) in mapping['tileMap'], (tileset, material)
                assert all(str(tile) in mapping['wallTiles'] for tile in WALLS), (tileset, material)
                result = shapes.native(data, tileset)
                run = Path(result['run'])
                cells = final_cells(run/'diagnostics.jsonl.engine.jsonl')
                known = [c for c in cells if c.get('tile') not in UNKNOWN]
                hidden = [c for c in cells if c.get('tile') in UNKNOWN]
                assert known and all(c.get('material') == material for c in known), (scene, focus, tileset, run)
                assert all('material' not in c and 'groundTile' not in c for c in hidden), (scene, focus, tileset, run)
                visible = [c for c in known if within(c, data['metadata']['shapeBounds'])]
                anchor_tiles = ALTARS if scene == 'home' else DRAGON
                actual = {'wall': sum(c.get('tile') in WALLS for c in visible),
                          'floor': sum(c.get('tile') in FLOORS for c in visible),
                          'landmark': sum(c.get('tile') in anchor_tiles for c in visible)}
                assert all(actual[name] > 0 for name in expected), (scene, focus, expected, actual, run)
                result.update(scene=scene, focus=focus, bounds=data['metadata']['shapeBounds'],
                              material=material, expectedFeatures=expected, displayedFeatures=actual,
                              knownMaterialCells=len(known), hiddenCells=len(hidden),
                              noHiddenGround=True, noHiddenMaterial=True,
                              sourceCheckpoint=source['metadata']['checkpoint'])
                results.append(result)
                OUT.write_text(json.dumps(results, indent=2)+'\n')
                print('PASS', scene, focus, tileset, result['screenshot'], flush=True)
    gallery(results)
    print('REVIEW', GALLERY, flush=True)


if __name__ == '__main__':
    main()
