#!/usr/bin/env python3
"""Prepare actual upstream Ice room fills for native visual review.

The named fill runs inside a bounded test room with lit, unlit and ordinary
mixed contents. Fill randomness, including optional melt timers, is retained.
This is engine-generated review evidence, not a naturally encountered level or
complete ice-hazard acceptance. Native captures are sequenced separately.
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
INDEX = ROOT/'.artifacts/ice-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/ice-rooms-engine.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'],event['y']] = event
    return list(cells.values())


def prepare():
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    rows = []
    for variant, lit, mixed in [('lit', True, False), ('unlit', False, False), ('mixed', True, True)]:
        case = dict(id='fill-ice-room-'+variant, group='Ice rooms',
                    label='Ice room / '+variant, target=None, source=None,
                    branch='The Dungeons of Doom', fill='Ice room', lit=lit, mixed=mixed)
        run = Path(tempfile.mkdtemp(prefix='ice-rooms-'+variant+'-', dir=ROOT/'.artifacts'))
        metadata = tour.prepare(case, 'inspection', run)
        metadata['displayedCells'] = displayed_cells(run/'preparation.jsonl')
        metadata['testTerrainTiles'] = sorted({c['tile'] for c in metadata['displayedCells']
                                             if c.get('char') == '.'})
        metadata['setup'].append('Ice room fill runs unchanged. Optional random melt timers are neither forced nor suppressed. Unlit inspection is mapped memory, not permanent room illumination.')
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        rows.append(dict(run=str(run), metadata=metadata))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], run, flush=True)
    return rows


def check(data):
    case = data['metadata']['case']
    run = Path(tempfile.mkdtemp(prefix='ice-rooms-check-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    os.environ.update(HOME=str(directory), NETHACKDIR=str(directory), HACKDIR=str(directory),
                      ATLAS_PLAY_MODE='standard')
    game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS)
    result = dict(case=case['id'], run=str(run))
    try:
        tour.settle(game)
        assert game.cursor == tuple(data['metadata']['arrival'])
        before = game.turn
        result['inspection'] = [dict(position=list(p), description=game.inspect(*p))
                                for p in [game.cursor, (29,8), (34,10), (25,5)]]
        assert game.turn == before, 'Inspection consumed a turn'
        start = len(game.events)
        # Test-only read-only oracle checks actual terrain under occupants and
        # remembered glyphs. Its hidden information never enters a review save.
        tour.lua(game, directory, '''
local ox,oy=nh.abscoord(0,0);
for y=6,13 do for x=26,39 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("ICE_ORACLE:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..tostring(nh.has_timer_at(x-ox,y-oy,"melt-ice")));
end end;
''')
        cells = [e['text'].split(':',1)[1].split(',') for e in game.events[start:]
                 if e.get('text','').startswith('ICE_ORACLE:')]
        assert len(cells) == 112, len(cells)
        assert all(c[3] == str(case['lit']).lower() for c in cells), cells
        ice = [c for c in cells if c[2] == 'ice']
        # Both stairs replace ice and any source-authorized timer can melt it.
        assert ice, ('No actual ice generated', cells)
        result.update(iceCount=len(ice), terrainCounts={kind:sum(c[2] == kind for c in cells)
                     for kind in sorted({c[2] for c in cells})},
                     activeMeltTimerCount=sum(c[4] == 'true' for c in cells),
                     lightingVerified=True, turnFreeInspection=True)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS)
        tour.settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        game.finish(automatic=True)
        result['restored'] = True
        print('PASS', case['label'], result['iceCount'], 'ice cells', flush=True)
        return result
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(check(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
