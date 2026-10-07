#!/usr/bin/env python3
"""Verify real Vlad's Tower levels using isolated packaged-engine saves.

Preparation reveals terrain with the upstream wizard command. Ordinary commands
exercise movement and ladder connections. Diagnostic placement never replaces
terrain, occupants, or game rules. Native capture is left to the caller.
"""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
tour = shapes.tour
INDEX = ROOT/'.artifacts/vlad-engine-prepared.json'
RESULTS = ROOT/'.artifacts/vlad-engine-results.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))


def settle(game, event=None):
    """Allow active occupants' optional item labels without inventing a name."""
    event = event or game.wait_input()
    for _ in range(80):
        if event.get('command'): return event
        if event['kind'] == 'line':
            prompt = event.get('prompt','').lower()
            if prompt.startswith('call '): game.send('line ')
            elif 'wish' in prompt: game.send('line nothing')
            else: raise RuntimeError('Unexpected test question: '+event.get('prompt',''))
        elif event['kind'] == 'menu': game.send('menu cancel')
        elif event['kind'] == 'yn': game.send('key 110')
        else: game.send('key 27')
        event = game.wait_input()
    raise RuntimeError('Test did not reach an ordinary command prompt')


def prepare():
    rows = []
    for identifier in ('tower1', 'tower2', 'tower3'):
        data = json.loads(subprocess.check_output([sys.executable, str(ROOT/'scripts/playtest/prepare.py'),
            'prepare', '--case', identifier, '--mode', 'inspection'], text=True))
        cells = {}
        for line in (Path(data['metadata']['checkpoint'])/'preparation.jsonl').read_text().splitlines():
            event = json.loads(line)
            if event['type'] == 'clear' and event.get('window') == 'map': cells.clear()
            elif event['type'] == 'cell': cells[event['x'], event['y']] = event
        points = [p for p,c in cells.items() if c.get('char',' ').strip()]
        xs,ys = zip(*points)
        metadata = data['metadata']
        assert metadata['identity']['branch'] == "Vlad's Tower"
        assert metadata['identity']['level'] == int(identifier[-1])
        metadata['shapeBounds'] = [min(xs), min(ys), max(xs)-min(xs)+1, max(ys)-min(ys)+1]
        metadata['displayedCells'] = list(cells.values())
        metadata['displayedTileCounts'] = dict(Counter(str(c['tile']) for c in cells.values()))
        metadata['sources'][identifier+'.lua'] = tour.digest(tour.DAT/(identifier+'.lua'))
        metadata['testTerrainTiles'] = [t for t in (1299,1300,1311) if str(t) in metadata['displayedTileCounts']]
        rows.append(data)
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', identifier, metadata['identity'], metadata['shapeBounds'], flush=True)
    return rows


def start(data, prefix):
    run = Path(tempfile.mkdtemp(prefix='vlad-'+prefix+'-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    os.environ.update(NETHACKDIR=str(directory), HACKDIR=str(directory))
    game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS)
    settle(game)
    return run, directory, game


def cleanup(run, game):
    (run/'latest-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait()


def place(game, target):
    event = tour.named(game, 'teleport')
    if event.get('kind') == 'menu' and event.get('how') == 0:
        game.send('key 32')
        event = game.wait_input()
    assert event.get('targeting'), event
    game.send(f'position {target[0]} {target[1]}')
    settle(game)
    assert game.cursor == target, (target, game.cursor)


def assert_material(game, inside=True):
    known = [c for c in game.cells.values() if c.get('tile') not in (1469,1470)]
    assert known, 'No displayed tower cells'
    if inside:
        assert all(c.get('material') == 'vlad' for c in known), known[:8]
    else:
        assert all(c.get('material') != 'vlad' for c in known), known[:8]
    hidden = [c for c in game.cells.values() if c.get('tile') in (1469,1470)]
    assert all('material' not in c and 'groundTile' not in c for c in hidden)


def engine(data):
    run, directory, game = start(data, 'engine')
    result = dict(case=data['metadata']['case']['id'], run=str(run))
    try:
        identity = tour.identity(game, directory)
        assert identity == data['metadata']['identity']
        assert_material(game)
        result.update(identity=identity, initialCells=list(game.cells.values()), material='vlad')
        before = game.turn
        observed = []
        for category, predicate in (
            ('door', lambda c: c.get('tile') in (1287,1288)),
            ('ladderUp', lambda c: c.get('tile') == 1299),
            ('ladderDown', lambda c: c.get('tile') == 1300),
            ('throne', lambda c: c.get('tile') == 1311),
            ('wall', lambda c: 1273 <= c.get('tile',-1) <= 1283)):
            cell = next((c for c in game.cells.values() if predicate(c)), None)
            if cell:
                observed.append(dict(category=category, cell=cell, description=game.inspect(cell['x'], cell['y'])))
        assert game.turn == before
        assert {'door','wall'} <= {r['category'] for r in observed}
        if identity['level'] == 1:
            assert 'throne' in {r['category'] for r in observed}
        result.update(inspection=observed, turnFreeInspection=True)
        # Choose a pair only from displayed plain floor. Wizard placement is
        # setup; the single movement command is ordinary upstream gameplay.
        pair = next(((p,(p[0]+dx,p[1]+dy),key) for p,c in game.cells.items() if c.get('char') == '.'
            for dx,dy,key in STEPS if game.cells.get((p[0]+dx,p[1]+dy),{}).get('char') == '.'), None)
        assert pair, 'No perceived plain-floor pair'
        place(game, pair[0])
        turn = game.turn
        settle(game, game.command(pair[2]))
        assert game.cursor == pair[1] and game.turn >= turn, (pair, game.cursor)
        result['plainFloorMove'] = dict(origin=pair[0], destination=pair[1], turns=game.turn-turn)
        # Speed can permit a successful action without incrementing displayed
        # time. Position changes, rather than one-turn assumptions, prove moves.
        result['nonDiggableWall'] = dig_wall(game)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS)
        settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        assert tour.identity(game, directory) == identity
        assert_material(game)
        result.update(restored=True, position=position, turn=turn)
        game.finish(automatic=True)
        print('PASS', result['case'], 'inspection, ordinary movement, exact save/restore', flush=True)
        return result
    finally:
        cleanup(run, game)



def dig_wall(game):
    pair = next(((game.cursor,(game.cursor[0]+dx,game.cursor[1]+dy),key)
        for dx,dy,key in STEPS if 1273 <= game.cells.get((game.cursor[0]+dx,game.cursor[1]+dy),{}).get('tile',-1) <= 1283), None)
    assert pair, 'No displayed floor beside tower wall'
    before = dict(game.cells[pair[1]])
    offset = len(game.events)
    event = tour.named(game, 'zap')
    assert event['kind'] == 'menu', event
    wands = [i for i in event['items'] if i.get('selectable') and 'wand' in i['text']]
    assert len(wands) == 1, wands
    game.send('menu '+str(wands[0]['id']))
    event = game.wait_input()
    assert event.get('direction'), event
    settle(game, game.command(pair[2]))
    after = game.cells[pair[1]]
    messages = [e['text'] for e in game.events[offset:] if e['type'] == 'message']
    assert after['tile'] == before['tile'], (before, after, messages)
    assert any('hard' in m.lower() or 'glow' in m.lower() for m in messages), messages
    return dict(position=pair[0], target=pair[1], before=before, after=after, messages=messages,
        blockedByUpstream=True)


def branch_connection(data):
    run, directory, game = start(data, 'branch')
    try:
        origin = tour.identity(game,directory)
        assert origin['level'] == 3 and origin['branch'] == "Vlad's Tower"
        assert_material(game)
        target = next((p for p,c in game.cells.items() if c.get('tile') == 1298), None)
        assert target, 'No displayed tower branch stairs'
        place(game,target)
        game.cells.clear()
        settle(game,game.command('>'))
        outside = tour.identity(game,directory)
        assert outside['branch'] == 'Gehennom', outside
        assert_material(game, inside=False)
        outside_materials = sorted({c['material'] for c in game.cells.values() if 'material' in c})
        arrival = game.cursor
        game.cells.clear()
        settle(game,game.command('<'))
        assert tour.identity(game,directory) == origin
        assert game.cursor == target
        assert_material(game)
        result = dict(run=str(run),origin=origin,destination=outside,departure=target,arrival=arrival,
            returned=True,noVladMaterialOutside=True,outsideMaterials=outside_materials,
            restoredVladMaterial=True,
            setup='Wizard placement on existing tower branch stairs, ordinary > then <.')
        game.finish(automatic=True)
        (ROOT/'.artifacts/vlad-engine-branch.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS actual tower/Gehennom branch stair roundtrip',flush=True)
        return result
    finally:
        cleanup(run,game)


def ladder_target(game, directory, up):
    """Read actual stairway identity for wizard setup, never player UI data.

    Occupants can displace arrival beside a ladder or cover its displayed glyph.
    """
    offset = len(game.events)
    tour.lua(game, directory, 'for _,s in ipairs(nh.stairways()) do if s.ladder and s.up == '
        + ('true' if up else 'false')
        + ' then nh.pline("ATLAS_LADDER:"..s.x..","..s.y); end; end;')
    points = [tuple(map(int,e['text'].split(':',1)[1].split(','))) for e in game.events[offset:]
        if e.get('text','').startswith('ATLAS_LADDER:')]
    assert len(points) == 1, points
    return points[0]


def connections(data):
    run, directory, game = start(data, 'connections')
    result = dict(run=str(run), setup='Read-only upstream stairway diagnostics locate original ladders even under occupants. Wizard placement, then ordinary < and > for every crossing.', crossings=[])
    try:
        # A single world proves the actual top-middle-bottom ladder network.
        assert tour.identity(game, directory)['level'] == 1
        for origin_level, destination_level, key in ((1,2,'>'), (2,3,'>'), (3,2,'<'), (2,1,'<')):
            origin = tour.identity(game, directory)
            assert origin['level'] == origin_level and origin['branch'] == "Vlad's Tower"
            assert_material(game)
            settle(game, tour.named(game, 'wizmap'))
            target = ladder_target(game, directory, key == '<')
            place(game, target)
            before = game.turn
            game.cells.clear()
            settle(game, game.command(key))
            destination = tour.identity(game, directory)
            assert destination['branch'] == "Vlad's Tower" and destination['level'] == destination_level, (origin, destination)
            assert_material(game)
            assert game.turn >= before
            result['crossings'].append(dict(origin=origin, destination=destination, departure=target,
                arrival=game.cursor, command=key, turns=game.turn-before))
        game.finish(automatic=True)
        (ROOT/'.artifacts/vlad-engine-connections.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS actual top-middle-bottom ladder network, both directions', flush=True)
        return result
    finally:
        cleanup(run, game)


def unknown():
    data = json.loads(subprocess.check_output([sys.executable, str(ROOT/'scripts/playtest/prepare.py'),
        'prepare', '--case', 'tower3', '--mode', 'exploration'], text=True))
    run, directory, game = start(data, 'unknown')
    try:
        assert_material(game)
        hidden = [c for c in game.cells.values() if c.get('tile') == 1469]
        assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
        turn = game.turn
        samples = [dict(cell=c, description=game.inspect(c['x'], c['y'])) for c in hidden[::max(1,len(hidden)//8)]]
        assert game.turn == turn
        assert all('unexplored' in r['description'].lower() for r in samples), samples
        result = dict(run=str(run), identity=tour.identity(game,directory), unknownCells=len(hidden),
            samples=samples, turnFreeInspection=True, noHiddenGround=True, noHiddenMaterial=True)
        game.finish(automatic=True)
        (ROOT/'.artifacts/vlad-engine-unknown.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS unrevealed tower inspection and hidden-ground invariants', flush=True)
    finally:
        cleanup(run, game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('prepare','engine','connections','unknown','branch'):
        parser.add_argument('--'+flag, action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(engine(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    if args.connections: connections(rows[0])
    if args.branch: branch_connection(rows[2])
    if args.unknown: unknown()


if __name__ == '__main__':
    main()
