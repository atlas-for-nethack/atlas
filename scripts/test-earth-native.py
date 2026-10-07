#!/usr/bin/env python3
"""Capture real Earth arrival checkpoints in isolated packaged-app sessions.

Prepare .artifacts/earth-engine-prepared.json with the rebuilt app first.
Each capture copies the checkpoint game directory; player saves are never used.
Default captures inspection and exploration in both Modern families.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
INDEX = ROOT/'.artifacts/earth-engine-prepared.json'
OUT = ROOT/'.artifacts/earth-native-results.json'
GALLERY = ROOT/'.artifacts/earth-native-review.html'
UNKNOWN = {1469, 1470}


def within(cell, bounds):
    x, y, width, height = bounds
    return x <= cell['x'] < x + width and y <= cell['y'] < y + height


def fixture(source):
    data = copy.deepcopy(source)
    metadata = data['metadata']
    x, y = metadata['arrival']
    # Bounded arrival crops avoid the full-map native capture timeout.
    bounds = [max(1, min(64, x-8)), max(0, min(10, y-5)), 16, 11]
    cells = [cell for cell in metadata['displayedCells'] if within(cell, bounds)]
    assert any(cell.get('tile') not in UNKNOWN for cell in cells), bounds
    metadata['shapeBounds'] = bounds
    # Readiness must use a plain visible floor, rather than the hero's ground.
    metadata['testTerrainTiles'] = [1291] if any(cell.get('tile') == 1291 for cell in cells) else []
    return data


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
    body = ['<!doctype html><meta charset="utf-8"><title>Earth native review</title>',
            '<style>body{background:#101719;color:#e3e5df;font:16px system-ui;margin:24px}'
            'section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
            'img{width:100%}a{color:#d1b27a}</style>',
            '<h1>Plane of Earth: packaged-app arrival captures</h1>',
            '<p>Actual upstream Earth checkpoints copied into disposable native sessions. '
            'Inspection reveals the map; exploration preserves unrevealed cells. '
            'These captures verify rendering and hover readiness, not campaign arrival or completion.</p>']
    for mode in ('inspection', 'exploration'):
        body.extend([f'<h2>{mode.title()}</h2>', '<section>'])
        for row in results:
            if row['mode'] != mode:
                continue
            label = html.escape(row['tileset'])
            if row['status'] == 'failed':
                body.append(f'<div><h3>{label}: verification pending</h3>'
                            f'<p>{html.escape(row["error"])}</p></div>')
                continue
            image = Path(row['screenshot']).relative_to(GALLERY.parent).as_posix()
            body.append(f'<div><h3>{label}</h3><a href="{image}">'
                        f'<img src="{image}" alt="Earth {mode}, {label}"></a></div>')
        body.append('</section>')
    GALLERY.write_text('\n'.join(body)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classic', action='store_true', help='Also capture both Classic editions')
    args = parser.parse_args()
    prepared = json.loads(INDEX.read_text())
    rows = {row['metadata']['mode']: row for row in prepared}
    assert set(rows) == {'inspection', 'exploration'}, rows.keys()
    manifest = json.loads((shapes.tour.RES/'assets/tiles/manifest.json').read_text())
    tilesets = ['lantern-modern', 'soot-and-brass']
    if args.classic:
        tilesets.extend(['lantern', 'soot-and-brass-classic'])
    results = []
    for mode in ('inspection', 'exploration'):
        source = rows[mode]
        metadata = source['metadata']
        assert metadata['case']['id'] == 'earth'
        assert metadata['identity']['branch'] == 'The Elemental Planes'
        assert metadata['identity']['depth'] == -1
        assert shapes.tour.digest(shapes.tour.RES/'engine/nethack') == metadata['engine']
        assert shapes.tour.digest(shapes.tour.APP/'Contents/MacOS/NetHackAtlas') == metadata['app']
        data = fixture(source)
        for tileset in tilesets:
            selected = next(tile for tile in manifest['tilesets'] if tile['id'] == tileset)
            material = selected['regionalMaterials']['earth']
            assert '1272' not in material['tileMap'], (tileset, 'Earth must retain solid rock')
            try:
                result = shapes.native(data, tileset)
                run = Path(result['run'])
                cells = final_cells(run/'diagnostics.jsonl.engine.jsonl')
                known = [cell for cell in cells if cell.get('tile') not in UNKNOWN]
                hidden = [cell for cell in cells if cell.get('tile') in UNKNOWN]
                assert known and all(cell.get('material') == 'earth' for cell in known), (tileset, mode, run)
                assert all('material' not in cell and 'groundTile' not in cell for cell in hidden), (tileset, mode, run)
                if mode == 'exploration':
                    assert hidden, (tileset, 'Exploration must retain unknown cells', run)
                result.update(status='passed', nativeVerified=True, mode=mode,
                              bounds=data['metadata']['shapeBounds'], arrival=metadata['arrival'],
                              knownCells=len(known), hiddenCells=len(hidden), material='earth',
                              noHiddenGround=True, noHiddenMaterial=True, solidRockUnmapped=True,
                              sourceCheckpoint=metadata['checkpoint'], setup=metadata['setup'],
                              engine=metadata['engine'], app=metadata['app'], sourceIdentity=metadata['identity'],
                              scope='Native arrival rendering/readiness/hover, not digging or campaign completion')
            except AssertionError as error:
                result = dict(status='failed', nativeVerified=False, mode=mode,
                              tileset=tileset, error=str(error), screenshot=None)
                results.append(result)
                OUT.write_text(json.dumps(results, indent=2)+'\n')
                gallery(results)
                print('FAILED', mode, tileset, str(error), flush=True)
                return 1
            results.append(result)
            OUT.write_text(json.dumps(results, indent=2)+'\n')
            print('PASS', mode, tileset, result['screenshot'], flush=True)
    gallery(results)
    print('REVIEW', GALLERY, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
