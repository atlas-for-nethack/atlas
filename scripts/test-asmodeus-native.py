#!/usr/bin/env python3
"""Capture Asmodeus's real level in the packaged app using isolated saves.

Run scripts/test-asmodeus-lair.py --prepare after rebuilding the app and engine.
Pass --encounter-only after the natural-arrival checkpoint is prepared to add
its two Modern captures without repeating the eight baseline captures.
Each capture copies its checkpoint. The player's saves are untouched.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('asmodeus', ROOT/'scripts/test-asmodeus-lair.py')
asmodeus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asmodeus)
OUT = ROOT/'.artifacts/asmodeus-native-results.json'
GALLERY = ROOT/'.artifacts/asmodeus-native-review.html'
PALACE = ROOT/'.artifacts/asmodeus-palace-prepared.json'
UNKNOWN = {1469, 1470}
WALLS = set(range(1482, 1493))
DOORS = {1287, 1288}
ASMODEUS = {632, 633}


def within(cell, bounds):
    x, y, width, height = bounds
    return x <= cell['x'] < x + width and y <= cell['y'] < y + height


def capture_data(source, focus):
    """Choose a view without altering the saved game or its preparation record."""
    data = copy.deepcopy(source)
    metadata = data['metadata']
    if focus == 'whole':
        bounds = metadata['shapeBounds']
        required = {'wall': WALLS, 'upstairs': {1297}, 'downstairs': {1298}}
        anchor = 1298
    elif focus in ('palace', 'natural-arrival'):
        bounds = metadata['palaceBounds']
        required = {'wall': WALLS, 'door': DOORS}
        if focus == 'natural-arrival':
            required['asmodeus'] = ASMODEUS
            # The hero occupies the arrival stair, so that stair need not be
            # a foreground tile in the displayed map. The visible resident
            # is a stronger readiness signal for this encounter capture.
            anchor = next(c['tile'] for c in metadata['displayedCells']
                          if within(c, bounds) and c.get('tile') in ASMODEUS)
        else:
            required['downstairs'] = {1298}
            anchor = 1298
    elif focus == 'east-passage':
        bounds = metadata['eastPassageBounds']
        required = {'wall': WALLS, 'door': DOORS}
        anchor = 1287 if any(within(c, bounds) and c.get('tile') == 1287
                              for c in metadata['displayedCells']) else 1288
    else:
        raise ValueError(focus)
    cells = [c for c in metadata['displayedCells'] if within(c, bounds)]
    features = {name: sum(c.get('tile') in tiles for c in cells)
                for name, tiles in required.items()}
    assert all(features.values()), (focus, features, bounds)
    assert any(c.get('tile') == anchor for c in cells), (focus, anchor)
    metadata['shapeBounds'] = bounds
    metadata['testTerrainTiles'] = [anchor]
    return data, features


def final_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return cells


def gallery(results):
    lines = ['<!doctype html><meta charset="utf-8"><title>Asmodeus native review</title>',
             '<style>body{background:#101719;color:#e3e5df;font:16px system-ui;margin:24px}'
             'section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
             'img{width:100%}a{color:#d1b27a}</style>',
             '<h1>Asmodeus: packaged-app captures</h1>',
             '<p>Real engine checkpoints, copied separately for each capture.'
             ' Natural arrival enters from the floor below; other views use the'
             ' revealed inspection checkpoint. These views are review evidence, not owner approval.</p>']
    for focus in ('whole', 'palace', 'east-passage', 'natural-arrival'):
        if not any(result['focus'] == focus for result in results):
            continue
        lines.extend([f'<h2>{html.escape(focus.replace("-", " ").title())}</h2>', '<section>'])
        for result in results:
            if result['focus'] != focus:
                continue
            label = html.escape(result['tileset'])
            image = Path(result['screenshot']).relative_to(GALLERY.parent).as_posix()
            lines.append(f'<div><h3>{label}</h3><a href="{image}">'
                         f'<img src="{image}" alt="{label}: {html.escape(focus)}"></a></div>')
        lines.append('</section>')
    GALLERY.write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--palace', action='store_true',
                        help='also capture the naturally reached palace checkpoint in both Modern families')
    parser.add_argument('--encounter-only', action='store_true',
                        help='append only natural-arrival Modern captures to existing baseline results')
    args = parser.parse_args()
    prepared = json.loads(asmodeus.INDEX.read_text())
    source = next(row for row in prepared
                  if row['metadata']['case']['id'] == 'asmodeus'
                  and row['metadata']['mode'] == 'inspection')
    assert source['metadata']['identity']['branch'] == 'Gehennom'
    assert source['metadata']['palaceBounds'] and source['metadata']['eastPassageBounds']
    manifest = json.loads((ROOT/'assets/tiles/manifest.json').read_text())
    atlases = {entry['id']: entry for entry in manifest['tilesets']}
    views = [] if args.encounter_only else [
        (focus, source) for focus in ('whole', 'palace', 'east-passage')]
    if args.palace or args.encounter_only:
        natural = json.loads(PALACE.read_text())
        assert natural['metadata']['case']['id'] == 'asmodeus'
        assert natural['metadata']['identity'] == source['metadata']['identity']
        assert Path(natural['run'], 'game').is_dir(), natural['run']
        views.append(('natural-arrival', natural))
    if args.encounter_only:
        assert OUT.is_file(), 'Run the eight baseline native captures before --encounter-only'
        results = [row for row in json.loads(OUT.read_text())
                   if row.get('focus') != 'natural-arrival']
        assert len(results) == 8, ('Expected eight baseline captures', len(results))
    else:
        results = []
    for focus, checkpoint in views:
        data, expected = capture_data(checkpoint, focus)
        tilesets = ('lantern-modern', 'soot-and-brass')
        if focus == 'palace':
            tilesets += ('lantern', 'soot-and-brass-classic')
        for tileset in tilesets:
            mapping = atlases[tileset]['regionalMaterials']['asmodeus']['tileMap']
            assert str(1291) in mapping and any(str(tile) in mapping for tile in WALLS), tileset
            result = asmodeus.shapes.native(data, tileset)
            run = Path(result['run'])
            cells = list(final_cells(run/'diagnostics.jsonl.engine.jsonl').values())
            known = [c for c in cells if c.get('tile') not in UNKNOWN]
            hidden = [c for c in cells if c.get('tile') in UNKNOWN]
            assert known and all(c.get('material') == 'asmodeus' for c in known), (focus, tileset, run)
            assert all('material' not in c and 'groundTile' not in c for c in hidden), (focus, tileset, run)
            bounds = data['metadata']['shapeBounds']
            visible = [c for c in known if within(c, bounds)]
            assert visible, (focus, tileset, run)
            actual = {name: sum(c.get('tile') in tiles for c in visible)
                      for name, tiles in ({'wall': WALLS, 'door': DOORS,
                                           'upstairs': {1297}, 'downstairs': {1298},
                                           'asmodeus': ASMODEUS}).items()}
            assert all(actual[name] > 0 for name in expected), (focus, tileset, expected, actual, run)
            result.update(focus=focus, bounds=bounds, expectedFeatures=expected,
                          displayedFeatures=actual, knownMaterialCells=len(known),
                          hiddenCells=len(hidden), noHiddenGround=True,
                          noHiddenMaterial=True, sourceCheckpoint=checkpoint['metadata']['checkpoint'])
            results.append(result)
            OUT.write_text(json.dumps(results, indent=2)+'\n')
            print('PASS', focus, tileset, result['screenshot'], flush=True)
    gallery(results)
    print('REVIEW', GALLERY, flush=True)


if __name__ == '__main__':
    main()
