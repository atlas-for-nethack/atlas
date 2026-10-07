#!/usr/bin/env python3
"""Capture real Astral Plane checkpoints without revealing additional terrain.

Run test-astral-plane.py first. Native sessions restore isolated copies of its
actual states; the shared preview receives only displayed engine cells.
"""
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    tower = load('astral-plane_tower_helpers', ROOT / 'scripts/test-wizard-towers.py')
    capture = load('astral-plane_native_helpers', ROOT / 'scripts/test-room-shapes.py')
    rows = json.loads((ART / 'astral-plane-states.json').read_text())
    verified = json.loads((ART / 'astral-plane-engine-results.json').read_text())
    assert verified.get('passed') is True, 'Complete the live engine checks before capture'
    state_ids = [row['metadata']['case']['id'] for row in rows]
    assert state_ids and len(set(state_ids)) == len(state_ids), 'Missing or duplicate checkpoints'
    assert set(state_ids) == set(verified['stateIDs']), 'Incomplete engine checkpoint set'
    for field, path in (('engine', tower.tour.RES / 'engine/nethack'),
                        ('app', tower.tour.APP / 'Contents/MacOS/NetHackAtlas'),
                        ('dataSHA256', tower.tour.RES / 'engine/nhdat')):
        assert verified[field] == tower.tour.digest(path), 'Engine evidence predates the current package'
    originals = tower.hashes(rows)
    assert originals == verified['checkpointHashes'], 'Checkpoint files changed after engine verification'
    results, scenes = [], {}
    try:
        for original in rows:
            row = copy.deepcopy(original)
            m = row['metadata']
            assert m['engine'] == tower.tour.digest(tower.tour.RES / 'engine/nethack')
            assert m['app'] == tower.tour.digest(tower.tour.APP / 'Contents/MacOS/NetHackAtlas')
            assert m['dataSHA256'] == tower.tour.digest(tower.tour.RES / 'engine/nhdat')
            tower.checks.material(m['displayedCells'], 'astral')
            m['shapeBounds'] = m['nativeBounds']
            x, y, w, h = m['shapeBounds']
            visible = [c for c in m['displayedCells'] if x <= c['x'] < x+w and y <= c['y'] < y+h]
            # Assert a genuine already displayed floor, not diagnostic terrain.
            floor = next((c['tile'] for c in visible if c.get('char') == '.'), None)
            m['testTerrainTiles'] = [] if floor is None else [floor]
            scenes[m['case']['id']] = dict(label=m['case']['label'], width=79, height=21,
                cells=[dict(c, x=c['x']-1) for c in m['displayedCells']], setup=m['setup'])
            for tileset in tower.NAMES:
                r = capture.native(row, tileset)
                log = Path(r['run']) / 'diagnostics.jsonl.engine.jsonl'
                events = [json.loads(line) for line in log.read_text().splitlines()]
                cursor = next(e for e in reversed(events) if e.get('type') == 'cursor')
                turn = next(e for e in reversed(events)
                    if e.get('type') == 'status' and e.get('name') == 'time')
                assert [cursor['playerX'], cursor['playerY']] == m['arrival'], 'Native restore moved the hero'
                assert int(turn['value']) == m['turn'], 'Native capture advanced gameplay'
                observed = tower.checks.displayed_cells(log)
                tower.checks.material(observed, 'astral')
                baseline = {(c['x'], c['y']): c for c in m['displayedCells']}
                assert {(c['x'], c['y']) for c in observed} == set(baseline)
                for c in observed:
                    assert all(c.get(f) == baseline[c['x'], c['y']].get(f)
                        for f in ('tile', 'glyph', 'char', 'color', 'pet', 'groundTile', 'material'))
                r.update(engine=m['engine'], app=m['app'], exactDisplayedCells=True,
                    exactPositionAndTurn=True)
                results.append(r)
                tower.checks.write(ART / 'astral-plane-native.json', results)
                print('PASS native', m['case']['id'], tileset, flush=True)
    finally:
        assert tower.hashes(rows) == originals, 'Original astral-plane checkpoints changed'
    tower.checks.write(ART / 'astral-plane-review-manifest.json', dict(scenes=scenes))
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Astral Plane review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;margin:24px} '
        '.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}figure{margin:0}img{width:100%}a{color:#d8bd87}</style>',
        '<h1>Astral Plane: real engine states</h1>',
        '<p>Actual packaged-app captures from the original Astral Plane and its three temples. '
        'Both families use the approved pale Astral variant of their Sokoban stone, with existing directional door geometry and canonical features. '
        'Wizard protection, supplied equipment, positioning and any map reveal are disclosed test setup. '
        'Unknown terrain and altar information are not added. Each altar uses upstream knowledge rules; no decorative marker identifies a correct destination. Modern and Classic share environment artwork. The final mapped overview is disclosed wizard setup, not ordinary vision.</p>']
    for original in rows:
        m = original['metadata']
        body.append('<h2>'+html.escape(m['case']['label'])+'</h2>')
        for editions in (('lantern-modern', 'soot-and-brass'), ('lantern', 'soot-and-brass-classic')):
            body.append('<div class="pair">')
            for tileset in editions:
                r = next(r for r in results if r['case'] == m['case']['id'] and r['tileset'] == tileset)
                src = Path(r['screenshot']).relative_to(ART).as_posix()
                label = html.escape(tower.NAMES[tileset])
                body.append('<figure><figcaption>'+label+'</figcaption><a href="'+src+'"><img src="'+src+'" alt="'+label+'"></a></figure>')
            body.append('</div>')
    body.append('</html>')
    (ART / 'astral-plane-review.html').write_text('\n'.join(body)+'\n')


if __name__ == '__main__':
    main()
