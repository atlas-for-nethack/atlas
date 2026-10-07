#!/usr/bin/env python3
"""Capture real Water-plane checkpoints without revealing additional terrain.

Run test-water-plane.py first. Native sessions restore isolated copies of its
actual states; the shared preview receives only displayed engine cells.
"""
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
# The pinned 5.0 catalog calls moat/pool 1314, Water 1324 and air 1322.
# Water's moving bubbles are original air pockets, never dry room floors.
SUPPORT = (1314, 1324, 1322)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def perception(cells):
    values = list(cells)
    for cell in values:
        assert 'material' not in cell, 'Water received a regional ground treatment'
        ground = cell.get('groundTile')
        assert ground is None or ground in SUPPORT, ('Non-water/air supporting surface', cell)
        if cell.get('tile') in (1469, 1470):
            assert ground is None, 'Unknown ground disclosed'
    return values


def main():
    tower = load('water_plane_tower_helpers', ROOT / 'scripts/test-wizard-towers.py')
    capture = load('water_plane_native_helpers', ROOT / 'scripts/test-room-shapes.py')
    rows = json.loads((ART / 'water-plane-states.json').read_text())
    verified = json.loads((ART / 'water-plane-engine-results.json').read_text())
    assert verified.get('passed') is True, 'Complete the live engine checks before capture'
    state_ids = [row['metadata']['case']['id'] for row in rows]
    assert state_ids and len(set(state_ids)) == len(state_ids), 'Missing or duplicate checkpoints'
    assert len(verified['stateIDs']) == len(state_ids), 'Incomplete engine checkpoint set'
    assert set(state_ids) == set(verified['stateIDs']), 'Incomplete engine checkpoint set'
    package = dict(engine=tower.tour.digest(tower.tour.RES / 'engine/nethack'),
                   app=tower.tour.digest(tower.tour.APP / 'Contents/MacOS/NetHackAtlas'),
                   dataSHA256=tower.tour.digest(tower.tour.RES / 'engine/nhdat'))
    resources=tower.tour.RES
    visual_paths=('web/tiles.js','web/app.js','assets/tiles/manifest.json')
    # Bind screenshots to actual renderer/resources, not only the host binary.
    visual_hashes={path:tower.tour.digest(ROOT/path) for path in visual_paths}
    for path,digest in visual_hashes.items():
        assert tower.tour.digest(resources/path)==digest, 'Rebuild changed renderer resources before capture'
    for field, digest in package.items():
        assert verified[field] == digest, 'Engine evidence predates the current package'
    originals = tower.hashes(rows)
    assert originals == verified['checkpointHashes'], 'Checkpoint files changed after engine verification'
    results, scenes = [], {}
    try:
        for original in rows:
            row = copy.deepcopy(original)
            m = row['metadata']
            assert all(m[field] == digest for field, digest in package.items()), 'Stale native checkpoint package'
            perception(m['displayedCells'])
            m['shapeBounds'] = m['nativeBounds']
            x, y, w, h = m['shapeBounds']
            visible = [c for c in m['displayedCells'] if x <= c['x'] < x+w and y <= c['y'] < y+h]
            # Assert actual foreground water/air in the crop, never infer land.
            terrain = next((c['tile'] for c in visible if c.get('tile') in SUPPORT), None)
            assert terrain is not None, 'Native crop contains no displayed original water or air pocket'
            m['testTerrainTiles'] = [terrain]
            scenes[m['case']['id']] = dict(label=m['case']['label'], width=79, height=21,
                cells=[dict(c, x=c['x']-1) for c in m['displayedCells']], setup=m['setup'])
            if m['case']['id']=='water-plane-arrival':
                cx=max(1,min(67,m['arrival'][0]-6));cy=max(0,min(12,m['arrival'][1]-4))
                scenes['water-plane-arrival-detail']=dict(label='Arrival: visible air-pocket close-up',width=13,height=9,
                    cells=[dict(c,x=c['x']-cx,y=c['y']-cy) for c in m['displayedCells']
                        if cx<=c['x']<cx+13 and cy<=c['y']<cy+9],
                    setup=m['setup']+['Crop of the same displayed engine cells; no new terrain or occupant information.'])
            for tileset in tower.NAMES:
                assert tower.hashes(rows) == originals, 'Original Water-plane checkpoints changed'
                r = capture.native(row, tileset)
                log = Path(r['run']) / 'diagnostics.jsonl.engine.jsonl'
                events = [json.loads(line) for line in log.read_text().splitlines()]
                cursor = next(e for e in reversed(events) if e.get('type') == 'cursor')
                turn = next(e for e in reversed(events)
                    if e.get('type') == 'status' and e.get('name') == 'time')
                assert [cursor['playerX'], cursor['playerY']] == m['arrival'], 'Native restore moved the hero'
                assert int(turn['value']) == m['turn'], 'Native capture advanced gameplay'
                observed = perception(tower.checks.displayed_cells(log))
                baseline = {(c['x'], c['y']): c for c in m['displayedCells']}
                assert len(baseline) == len(m['displayedCells']), 'Duplicate displayed checkpoint cells'
                assert {(c['x'], c['y']): c for c in observed} == baseline, 'Native restored display differs from checkpoint'
                r.update(**package, exactDisplayedCells=True, exactPositionAndTurn=True,
                    visualResourceSHA256=visual_hashes,
                    sourceCheckpointHashes={path: digest for path, digest in originals.items()
                        if Path(path).is_relative_to(Path(original['run']) / 'game')})
                results.append(r)
                tower.checks.write(ART / 'water-plane-native.json', results)
                print('PASS native', m['case']['id'], tileset, flush=True)
    finally:
        assert tower.hashes(rows) == originals, 'Original Water-plane checkpoints changed'
    assert len(results) == len(rows) * len(tower.NAMES), 'Incomplete four-edition native captures'
    tower.checks.write(ART / 'water-plane-review-manifest.json', dict(scenes=scenes))
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Plane of Water review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;margin:24px} '
        '.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}figure{margin:0}figcaption{margin:8px 0}img{width:100%}a{color:#d8bd87}</style>',
        '<h1>Plane of Water: real engine states</h1>',
        '<p>Actual packaged-app captures from the original Plane of Water. '
        'Both families retain canonical water; currently perceived air receives quiet cyan cap shading. '
        'The inward rim outlines currently supported AIR only, without classifying unseen water or reconstructing a hidden bubble. '
        'Sprites remain opaque above the cap. The moving original bubbles are air pockets, '
        'not dry land or room floors. Wizard Endgame access, protection and other checkpoint setup are '
        'disclosed below. Unknown terrain and hidden portal information are not added. '
        'Modern and Classic share environment artwork. These frozen displays do not simulate movement '
        'or prove an unprotected encounter, ordinary campaign arrival or ascension.</p>']
    for original in rows:
        m = original['metadata']
        body.append('<h2>'+html.escape(m['case']['label'])+'</h2>')
        body.append('<p>Checkpoint hero position: '+html.escape(str(m['arrival']))+
            '; turn: '+html.escape(str(m['turn']))+'.</p>')
        body.append('<ul>'+''.join('<li>'+html.escape(text)+'</li>' for text in m['setup'])+'</ul>')
        for editions in (('lantern-modern', 'soot-and-brass'), ('lantern', 'soot-and-brass-classic')):
            body.append('<div class="pair">')
            for tileset in editions:
                r = next(r for r in results if r['case'] == m['case']['id'] and r['tileset'] == tileset)
                src = html.escape(Path(r['screenshot']).relative_to(ART).as_posix(), quote=True)
                label = html.escape(tower.NAMES[tileset])
                body.append('<figure><figcaption>'+label+'</figcaption><a href="'+src+'"><img src="'+src+'" alt="'+label+'"></a></figure>')
            body.append('</div>')
    body.append('</html>')
    (ART / 'water-plane-review.html').write_text('\n'.join(body)+'\n')


if __name__ == '__main__':
    main()
