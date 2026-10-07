#!/usr/bin/env python3
"""Capture real Rogue home and goal levels in isolated packaged-app sessions.

Run scripts/test-rogue-quest.py --prepare first. No rebuild is required.
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
INDEX = ROOT/'.artifacts/rogue-engine-prepared.json'
OUT = ROOT/'.artifacts/rogue-native-results.json'
GALLERY = ROOT/'.artifacts/rogue-native-review.html'
UNKNOWN = {1469, 1470}
WALLS = set(range(1273, 1284))
FLOORS = {1291, 1292}
DOORS = set(range(1284, 1291))
WATER = {1314}
MANIFEST = ROOT/'.artifacts/rogue-review-manifest.json'


def within(cell, bounds):
    x, y, width, height = bounds
    return x <= cell['x'] < x + width and y <= cell['y'] < y + height


def fixture(source, focus):
    data = copy.deepcopy(source)
    metadata = data['metadata']
    scene = metadata['scene']
    assert scene in ('home', 'goal') and metadata['mode'] == 'inspection'
    anchor_tiles = DOORS if scene == 'home' else WATER
    if focus == 'detail':
        # Reuse the exact perceived-cell crop exported by the Rogue review.
        review = json.loads(MANIFEST.read_text())['scenes'][scene+'-detail']
        bounds = review['sourceBounds']
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
    metadata['testTerrainTiles'] = sorted({c['tile'] for c in cells if c.get('tile') in anchor_tiles})
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
    body = ['<!doctype html><meta charset="utf-8"><title>Rogue native review</title>',
            '<style>body{background:#101719;color:#e3e5df;font:16px system-ui;margin:24px}'
            'section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
            'img{width:100%}a{color:#d1b27a}</style>',
            '<h1>Rogue quest: packaged-app captures</h1>',
            '<p>Real engine inspection checkpoints, independently copied into disposable app sessions.'
            ' Detail views frame perceived guild doors/shared walls and the actual goal pool. The app’s room-shape'
            ' self-test also checks map readiness and hover focus. Screenshots are review evidence.</p>']
    for scene in ('home', 'goal'):
        for focus in ('detail',):
            matching = [r for r in results if r['scene'] == scene and r['focus'] == focus]
            if not matching:
                continue
            body.extend([f'<h2>{scene.title()} {focus}</h2>', '<section>'])
            for row in matching:
                label = html.escape(row['tileset'])
                if row.get('status') == 'failed':
                    body.append(f'<div><h3>{label}: native verification pending</h3>'
                                f'<p>{html.escape(row["error"])}</p>'
                                f'<p>Preserved run: {html.escape(row["run"])}</p></div>')
                    continue
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
    results = []
    for scene in ('home', 'goal'):
        source = rows[scene]
        identity = source['metadata']['identity']
        assert identity['branch'] == 'The Quest' and identity['role'] == 'Rogue'
        assert shapes.tour.digest(shapes.tour.RES/'engine/nethack') == source['metadata']['engine']
        assert shapes.tour.digest(shapes.tour.APP/'Contents/MacOS/NetHackAtlas') == source['metadata']['app']
        material = None  # Exact current ordinary-dungeon architecture.
        for focus in ('detail',):
            data, expected = fixture(source, focus)
            tilesets = ('lantern-modern', 'soot-and-brass')
            for tileset in tilesets:
                try:
                    result = shapes.native(data, tileset)
                except AssertionError as error:
                    # Preserve diagnostics rather than silently retrying or
                    # presenting a restored engine as a successfully drawn UI.
                    detail = error.args[0]
                    run = detail[-1] if isinstance(detail, tuple) else 'unknown'
                    result = dict(status='failed', scene=scene, focus=focus,
                                  tileset=tileset, run=str(run), error=str(error),
                                  screenshot=None, sourceIdentity=identity,
                                  engine=source['metadata']['engine'], app=source['metadata']['app'],
                                  architecture='Unchanged shipped ordinary-dungeon architecture',
                                  nativeVerified=False, scope='Native rendering remains unverified; no automatic retry')
                    results.append(result)
                    OUT.write_text(json.dumps(results, indent=2)+'\n')
                    gallery(results)
                    print('FAILED', scene, focus, tileset, str(error), flush=True)
                    print('REVIEW', GALLERY, flush=True)
                    return 1
                run = Path(result['run'])
                cells = final_cells(run/'diagnostics.jsonl.engine.jsonl')
                known = [c for c in cells if c.get('tile') not in UNKNOWN]
                hidden = [c for c in cells if c.get('tile') in UNKNOWN]
                assert known and all(c.get('material') == material for c in known), (scene, focus, tileset, run)
                assert all('material' not in c and 'groundTile' not in c for c in hidden), (scene, focus, tileset, run)
                visible = [c for c in known if within(c, data['metadata']['shapeBounds'])]
                anchor_tiles = DOORS if scene == 'home' else WATER
                actual = {'wall': sum(c.get('tile') in WALLS for c in visible),
                          'floor': sum(c.get('tile') in FLOORS for c in visible),
                          'landmark': sum(c.get('tile') in anchor_tiles for c in visible)}
                assert all(actual[name] > 0 for name in expected), (scene, focus, expected, actual, run)
                result.update(status='passed', nativeVerified=True,
                              scene=scene, focus=focus, bounds=data['metadata']['shapeBounds'],
                              material=material, expectedFeatures=expected, displayedFeatures=actual,
                              knownCells=len(known), hiddenCells=len(hidden),
                              noHiddenGround=True, noHiddenMaterial=True,
                              sourceCheckpoint=source['metadata']['checkpoint'],
                              engine=source['metadata']['engine'], app=source['metadata']['app'],
                              sourceIdentity=identity, setup=source['metadata']['setup'],
                              architecture='Unchanged shipped ordinary-dungeon architecture; no Rogue regional tag',
                              scope='Native map render/readiness/hover capture, not quest completion or combat/water traversal')
                results.append(result)
                OUT.write_text(json.dumps(results, indent=2)+'\n')
                print('PASS', scene, focus, tileset, result['screenshot'], flush=True)
    gallery(results)
    print('REVIEW', GALLERY, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
