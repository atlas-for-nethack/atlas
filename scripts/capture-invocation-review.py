#!/usr/bin/env python3
"""Capture real invocation checkpoints without revealing additional terrain.

Run test-invocation.py first. Native sessions restore isolated copies of its
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
    tower = load('invocation_tower_helpers', ROOT / 'scripts/test-wizard-towers.py')
    capture = load('invocation_native_helpers', ROOT / 'scripts/test-room-shapes.py')
    rows = json.loads((ART / 'invocation-states.json').read_text())
    originals = tower.hashes(rows)
    results, scenes = [], {}
    try:
        for original in rows:
            row = copy.deepcopy(original)
            m = row['metadata']
            assert m['engine'] == tower.tour.digest(tower.tour.RES / 'engine/nethack')
            assert m['app'] == tower.tour.digest(tower.tour.APP / 'Contents/MacOS/NetHackAtlas')
            assert m['dataSHA256'] == tower.tour.digest(tower.tour.RES / 'engine/nhdat')
            tower.privacy(m['displayedCells'])
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
                observed = tower.checks.displayed_cells(Path(r['run']) / 'diagnostics.jsonl.engine.jsonl')
                tower.privacy(observed)
                baseline = {(c['x'], c['y']): c for c in m['displayedCells']}
                assert {(c['x'], c['y']) for c in observed} == set(baseline)
                for c in observed:
                    assert all(c.get(f) == baseline[c['x'], c['y']].get(f)
                        for f in ('tile', 'glyph', 'char', 'color', 'pet', 'groundTile', 'material'))
                r.update(engine=m['engine'], app=m['app'], exactDisplayedCells=True)
                results.append(r)
                tower.checks.write(ART / 'invocation-native.json', results)
                print('PASS native', m['case']['id'], tileset, flush=True)
    finally:
        assert tower.hashes(rows) == originals, 'Original invocation checkpoints changed'
    tower.checks.write(ART / 'invocation-review-manifest.json', dict(scenes=scenes))
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Invocation review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;margin:24px} '
        '.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%}a{color:#d8bd87}</style>',
        '<h1>The vibrating square and invocation: real engine states</h1>',
        '<p>Actual packaged-app captures of isolated original-world saves. Discovery and transformation '
        'use ordinary engine commands, including the real candle, bell and book ritual. '
        'Wizard protection, supplied relics and positioning are disclosed test setup. '
        'Unknown terrain is not added. Modern and Classic share environment artwork.</p>',
        '<p>The protected test hero is invisible. The dropped scare scroll covers the new stair; '
        'the normal Descend action confirms the stair beneath it. These are ordinary engine states.</p>']
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
    (ART / 'invocation-review.html').write_text('\n'.join(body)+'\n')


if __name__ == '__main__':
    main()
