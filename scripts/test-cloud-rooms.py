#!/usr/bin/env python3
"""Prepare real upstream Cloud room fills for native artwork review.

Uses the named upstream themed fill, including sleeping fog-cloud monsters and
a vapor region, rather than replacing room floors with generic CLOUD terrain.
Native captures are sequenced separately by the review coordinator.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
tour = shapes.tour
INDEX = ROOT/'.artifacts/cloud-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/cloud-rooms-engine.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'


def cases():
    for variant, lit, mixed in [('lit', True, False), ('unlit', False, False),
                                ('mixed', True, True)]:
        yield dict(id='cloud-rooms-'+variant, label='Cloud room / '+variant,
                   group='Cloud rooms', target='', branch='The Dungeons of Doom',
                   fill='Cloud room', lit=lit, mixed=mixed)


def event_text(events):
    return ([e.get('text', '') for e in events]
            + [s for e in events for s in e.get('lines', [])]
            + [i.get('text', '') for e in events for i in e.get('items', [])])


def prepare():
    rows = []
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    for case in cases():
        destination = Path(tempfile.mkdtemp(prefix='cloud-rooms-prepared-',
                                          dir=ROOT/'.artifacts'))
        metadata = tour.prepare(case, 'inspection', destination)
        events = [json.loads(line) for line in (destination/'preparation.jsonl').read_text().splitlines()]
        cells = {}
        for event in events:
            if event['type'] == 'clear' and event.get('window') == 'map':
                cells.clear()
            elif event['type'] == 'cell':
                cells[event['x'], event['y']] = event
        metadata['displayedCellCount'] = metadata['displayedCells']
        metadata['displayedCells'] = list(cells.values())
        metadata['testTerrainTiles'] = sorted({c['tile'] for c in cells.values()
                                               if c['tile'] in (1323, 1324)})
        metadata['setup'].append('Cloud room invokes the untouched upstream named fill: sleeping fog clouds plus its nonpoisonous vapor region. No generic CLOUD terrain substituted.')
        (destination/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        row = dict(run=str(destination), metadata=metadata)
        rows.append(row)
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], destination, flush=True)


def check(data):
    run = Path(tempfile.mkdtemp(prefix='cloud-rooms-engine-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    os.environ.update(HOME=str(directory), NETHACKDIR=str(directory), HACKDIR=str(directory),
                      ATLAS_PLAY_MODE='standard')
    module = tour.load_game_module()
    game = module.Game(directory, name='wizard', options=OPTIONS)
    result = dict(case=data['metadata']['case']['id'], run=str(run))
    try:
        tour.settle(game)
        initial_turn = game.turn
        cells = [dict(c) for (x,y),c in game.cells.items() if 25 <= x <= 40 and 5 <= y <= 14]
        descriptions = {str((c['x'], c['y'])): game.inspect(c['x'], c['y']) for c in cells
                        if c.get('char', ' ').strip()}
        assert game.turn == initial_turn
        # Upstream wizard diagnostics report the real visible vapor region.
        start = len(game.events)
        tour.settle(game, tour.named(game, 'timeout'))
        messages = event_text(game.events[start:])
        vapor = [s for s in messages if 'vapor' in s.lower()]
        assert vapor, ('Missing real vapor region', messages)
        assert any(c['tile'] == 1323 for c in cells), 'No visible vapor for artwork review'
        # Read-only terrain and lighting oracle. Test diagnostics are never
        # added to owner checkpoints or copied into hover inspection.
        start = len(game.events)
        tour.lua(game, directory, '''local ox,oy=nh.abscoord(0,0);
for y=6,13 do for x=26,39 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("CLOUD_ROOM_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit));
end end;''')
        terrain = [e['text'].split(':',1)[1].split(',') for e in game.events[start:]
                   if e.get('text','').startswith('CLOUD_ROOM_TERRAIN:')]
        assert len(terrain) == 112
        assert sum(t[2] == 'room' for t in terrain) == 110
        assert sum(t[2] == 'stairs' for t in terrain) == 2
        assert all(t[3] == str(data['metadata']['case']['lit']).lower() for t in terrain)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = module.Game(directory, name='wizard', options=OPTIONS)
        tour.settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        start = len(game.events)
        tour.settle(game, tour.named(game, 'timeout'))
        restored_messages = event_text(game.events[start:])
        assert any('vapor' in s.lower() for s in restored_messages)
        game.finish(automatic=True)
        result.update(vaporDiagnostic=vapor, displayedCells=cells, inspections=descriptions,
                      turnFreeInspection=True, lightingVerified=True, genericCloudTerrain=False,
                      restored=True, vaporPreservedOnRestore=True)
        print('PASS', data['metadata']['case']['label'], flush=True)
        return result
    finally:
        (run/'latest-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    if args.engine:
        results = []
        for row in json.loads(INDEX.read_text()):
            results.append(check(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
