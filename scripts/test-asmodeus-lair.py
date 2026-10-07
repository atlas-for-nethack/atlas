#!/usr/bin/env python3
"""Capture and check the actual Asmodeus lair with isolated packaged-engine saves.

This is design evidence. Wizard map reveal and placement are disclosed setup;
inspection, a plain-floor move, and save/restore use the real engine protocol.
"""
import argparse
from collections import Counter, deque
import importlib.util
import json
import os
import re
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
INDEX = ROOT/'.artifacts/asmodeus-engine-prepared.json'
RESULTS = ROOT/'.artifacts/asmodeus-engine-results.json'
UNKNOWN = ROOT/'.artifacts/asmodeus-engine-unknown.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))


def settle(game, event=None):
    """Answer incidental monster/item prompts without asserting item names."""
    event = event or game.wait_input()
    for _ in range(80):
        if event.get('command'):
            return event
        if event['kind'] == 'line':
            prompt = event.get('prompt', '').lower()
            if prompt.startswith('call '):
                game.send('line ')
            elif 'wish' in prompt:
                game.send('line nothing')
            else:
                raise RuntimeError('Unexpected test question: '+event.get('prompt', ''))
        elif event['kind'] == 'menu':
            game.send('menu cancel')
        elif event['kind'] == 'yn':
            game.send('key 110')
        else:
            game.send('key 27')
        event = game.wait_input()
    raise RuntimeError('Test did not reach an ordinary command prompt')


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return cells


def palace_layout(cells):
    """Locate the source map under upstream's random horizontal/vertical flips.

    This reads already revealed inspection cells, never a player UI channel.
    """
    source = (tour.DAT/'asmodeus.lua').read_text()
    lines = re.search(r'map = \[\[(.*?)\]\]', source, re.S).group(1).strip().splitlines()
    width, height = len(lines[0]), len(lines)
    down = next(c for c in cells.values() if c.get('tile') == 1298)
    matches = []
    for flip_x in (False,True):
        for flip_y in (False,True):
            dx,dy = (width-1-13 if flip_x else 13), (height-1-7 if flip_y else 7)
            bx,by = down['x']-dx, down['y']-dy
            score = total = 0
            for y,line in enumerate(lines):
                for x,char in enumerate(line):
                    if char not in '-|':
                        continue
                    total += 1
                    px = bx+(width-1-x if flip_x else x)
                    py = by+(height-1-y if flip_y else y)
                    score += 1482 <= cells.get((px,py),{}).get('tile',-1) <= 1492
            matches.append((score, [bx,by,width,height], flip_x, flip_y, total))
    score,bounds,flip_x,flip_y,total = max(matches)
    assert score == total, ('Palace wall layout mismatch', score, total, bounds)
    return dict(palaceBounds=bounds, palaceFlipX=flip_x, palaceFlipY=flip_y)


def palace_point(metadata, x, y):
    bx,by,width,height = metadata['palaceBounds']
    return (bx+(width-1-x if metadata['palaceFlipX'] else x),
            by+(height-1-y if metadata['palaceFlipY'] else y))


def step_key(origin, target):
    return next(key for dx,dy,key in STEPS if (origin[0]+dx,origin[1]+dy) == target)


def prepare(mode):
    data = json.loads(subprocess.check_output([sys.executable,
        str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case', 'asmodeus',
        '--mode', mode], text=True))
    metadata = data['metadata']
    assert metadata['identity']['branch'] == 'Gehennom'
    assert metadata['case']['id'] == 'asmodeus'
    cells = displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
    assert cells
    metadata['sourceScript'] = 'vendor/NetHack-5.0.0/dat/asmodeus.lua'
    metadata['sources']['asmodeus.lua'] = tour.digest(tour.DAT/'asmodeus.lua')
    metadata['displayedCells'] = list(cells.values())
    metadata['displayedTileCounts'] = dict(Counter(str(c['tile']) for c in cells.values()))
    # Keep the whole playable map. The palace, eastern passage, surrounding
    # maze, natural stairs and variable lava all matter to this review.
    metadata['shapeBounds'] = [1, 0, 79, 21]
    # These landmarks are visible after the wizard reveal, not in an
    # exploration checkpoint where disclosing them would leak the layout.
    if mode == 'inspection':
        metadata.update(palace_layout(cells))
        choose = min if metadata['palaceFlipX'] else max
        end_door = choose((c for c in cells.values() if c.get('tile') in (1287,1288)),
                          key=lambda c:c['x'])
        passage_x = end_door['x'] if metadata['palaceFlipX'] else end_door['x']-32
        metadata['eastPassageBounds'] = [passage_x, end_door['y']-2, 33, 5]
    metadata['testTerrainTiles'] = [t for t in (1287,1288,1297,1298,1315,1316)
                                    if str(t) in metadata['displayedTileCounts']]
    return data


def start(data, label):
    run = Path(tempfile.mkdtemp(prefix='asmodeus-'+label+'-', dir=ROOT/'.artifacts'))
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


def inspect(game, category, predicate):
    cell = next((c for c in game.cells.values() if predicate(c)), None)
    if cell is None:
        return None
    return dict(category=category, cell=cell,
                description=game.inspect(cell['x'], cell['y']))


def assert_material(game, inside=True):
    known = [c for c in game.cells.values() if c.get('tile') not in (1469,1470)]
    assert known, 'No displayed level cells'
    if inside:
        assert all(c.get('material') == 'asmodeus' for c in known), known[:8]
    else:
        assert all(c.get('material') != 'asmodeus' for c in known), known[:8]
    hidden = [c for c in game.cells.values() if c.get('tile') in (1469,1470)]
    assert all('material' not in c and 'groundTile' not in c for c in hidden)


def engine(data):
    run, directory, game = start(data, 'engine')
    result = dict(case='asmodeus', mode='inspection', run=str(run))
    try:
        identity = tour.identity(game, directory)
        assert identity == data['metadata']['identity']
        assert_material(game)
        result['material'] = 'asmodeus'
        result['identity'] = identity
        result['initialCells'] = list(game.cells.values())
        before = game.turn
        observations = [inspect(game, 'wall', lambda c: 1482 <= c.get('tile', -1) <= 1492),
                        inspect(game, 'door', lambda c: c.get('tile') in (1287,1288)),
                        inspect(game, 'upStair', lambda c: c.get('tile') == 1297),
                        inspect(game, 'downStair', lambda c: c.get('tile') == 1298),
                        inspect(game, 'lava', lambda c: c.get('tile') == 1316)]
        observations = [o for o in observations if o]
        assert {'wall','door','upStair','downStair'} <= {o['category'] for o in observations}
        assert game.turn == before
        result.update(inspection=observations, turnFreeInspection=True,
                      displayedIce=sum(c.get('tile') == 1315 for c in game.cells.values()))
        # Upstream's palace and long passage have nondiggable walls. Keep the
        # entire level intact, including randomly placed exterior lava.
        pair = next(((p, (p[0]+dx,p[1]+dy), key)
                     for p,c in game.cells.items() if c.get('char') == '.' and p[0] <= 5
                     for dx,dy,key in STEPS
                     if game.cells.get((p[0]+dx,p[1]+dy),{}).get('char') == '.'), None)
        assert pair, 'No displayed plain-floor pair'
        place(game, pair[0])
        turn = game.turn
        settle(game, game.command(pair[2]))
        assert game.cursor == pair[1], (pair, game.cursor)
        result['plainFloorMove'] = dict(origin=pair[0], destination=pair[1],
                                        turns=game.turn-turn)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS)
        settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        assert tour.identity(game, directory) == identity
        assert_material(game)
        result.update(restored=True, position=position, turn=turn,
                      restoredCells=list(game.cells.values()))
        game.finish(automatic=True)
        print('PASS Asmodeus identity, displayed features, turn-free inspection, movement, restore', flush=True)
        return result
    finally:
        cleanup(run, game)


def unknown(data):
    run, directory, game = start(data, 'unknown')
    try:
        assert tour.identity(game, directory) == data['metadata']['identity']
        assert_material(game)
        hidden = [c for c in game.cells.values() if c.get('tile') == 1469]
        assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
        turn = game.turn
        samples = [dict(cell=c, description=game.inspect(c['x'], c['y']))
                   for c in hidden[::max(1,len(hidden)//8)]]
        assert game.turn == turn
        assert all('unexplored' in r['description'].lower() for r in samples), samples
        result = dict(run=str(run), identity=tour.identity(game,directory),
                      hiddenCells=len(hidden), samples=samples,
                      turnFreeInspection=True, noHiddenGround=True, noHiddenMaterial=True)
        game.finish(automatic=True)
        UNKNOWN.write_text(json.dumps(result, indent=2)+'\n')
        print('PASS unrevealed Asmodeus inspection and hidden-ground invariants', flush=True)
        return result
    finally:
        cleanup(run, game)


def connections(data):
    run, directory, game = start(data, 'connections')
    try:
        origin = tour.identity(game, directory)
        assert_material(game)
        # The natural entrance is outside the palace's teleport-restricted
        # interior. Wizard placement is setup; both stair commands are ordinary
        # upstream actions and no map geometry or occupants are replaced.
        entry = next((p for p,c in game.cells.items() if c.get('tile') == 1297), None)
        assert entry, 'No displayed upstairs in Asmodeus level'
        place(game, entry)
        game.cells.clear()
        settle(game, game.command('<'))
        outside = tour.identity(game, directory)
        assert outside['branch'] == origin['branch'] == 'Gehennom'
        assert outside['depth'] == origin['depth']-1, (origin, outside)
        assert_material(game, inside=False)
        outside_materials = sorted({c['material'] for c in game.cells.values() if 'material' in c})
        arrival = game.cursor
        game.cells.clear()
        settle(game, game.command('>'))
        assert tour.identity(game, directory) == origin
        assert game.cursor == entry, (entry, game.cursor)
        assert_material(game)
        result = dict(run=str(run), origin=origin, destination=outside,
                      departure=entry, arrival=arrival, returned=True,
                      noAsmodeusMaterialOutside=True, outsideMaterials=outside_materials,
                      restoredAsmodeusMaterial=True,
                      setup='Wizard placement on existing upstairs, ordinary < then >.')
        game.finish(automatic=True)
        (ROOT/'.artifacts/asmodeus-engine-connections.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS actual Asmodeus/Gehennom stairs and material roundtrip', flush=True)
        return result
    finally:
        cleanup(run, game)


def palace(data):
    """Prepare a separate natural palace arrival without bypassing its walls."""
    run, directory, game = start(data, 'palace')
    try:
        identity = tour.identity(game, directory)
        event = tour.named(game, 'wizlevelport')
        assert event['kind'] == 'line', event
        game.send('line '+str(identity['depth']+1))
        settle(game)
        below = tour.identity(game, directory)
        assert below['branch'] == 'Gehennom' and below['depth'] == identity['depth']+1
        settle(game, tour.named(game, 'wizmap'))
        upstairs = next(p for p,c in game.cells.items() if c.get('tile') == 1297)
        place(game, upstairs)
        game.cells.clear()
        settle(game, game.command('<'))
        assert tour.identity(game, directory) == identity
        # An upstream invisible resident cannot be evaluated visually without
        # granting this normal perception ability in disclosed wizard setup.
        event = tour.named(game, 'wizintrinsic')
        sight = next(i for i in event['items'] if i['text'].strip().lower() == 'see invisible')
        game.send('menu '+str(sight['id'])+':1000000')
        settle(game)
        assert_material(game)
        resident = next((dict(cell=c, description=game.inspect(*p))
                         for p,c in game.cells.items() if c.get('tile') == 632), None)
        assert resident and 'Asmodeus' in resident['description'], resident
        metadata = json.loads(json.dumps(data['metadata']))
        metadata.update(checkpoint=str(run), arrival=list(game.cursor),
                        displayedCells=list(game.cells.values()),
                        displayedTileCounts=dict(Counter(str(c['tile']) for c in game.cells.values())),
                        shapeBounds=metadata['palaceBounds'], residentInspection=resident,
                        status=game.status)
        metadata['setup'].append('Separate palace arrival: wizard level-port one floor below, wizard placement on existing upstairs, ordinary < into the palace. Timed see-invisible granted for the actual invisible resident. No terrain or occupants replaced.')
        game.finish(automatic=True)
        assert any((directory/'save').iterdir())
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        (run/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        result = dict(run=str(run), metadata=metadata)
        (ROOT/'.artifacts/asmodeus-palace-prepared.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PREPARED natural palace arrival', run, flush=True)
        return result
    finally:
        cleanup(run, game)


def move_to(game, target):
    """Walk along perceived room floor, avoiding revealed traps and occupants."""
    for _ in range(80):
        if game.cursor == target:
            return
        queue,seen = deque([(game.cursor,[])]),{game.cursor}
        route = None
        while queue:
            point,path = queue.popleft()
            if point == target:
                route = path
                break
            for dx,dy,key in STEPS:
                dest = point[0]+dx,point[1]+dy
                cell = game.cells.get(dest,{})
                tile = cell.get('tile',-1)
                floor = tile in (1285,1286,1291,1292,1297,1298)
                item_on_floor = 762 <= tile < 1270 and cell.get('groundTile') in (1291,1292)
                if dest not in seen and (floor or item_on_floor):
                    seen.add(dest)
                    queue.append((dest,path+[key]))
        assert route, ('No perceived safe floor route', game.cursor, target)
        settle(game, game.command(route[0]))
    raise AssertionError(('Could not walk to displayed palace position', target, game.cursor))


def palace_geometry(data):
    run, directory, game = start(data, 'palace-geometry')
    try:
        metadata = data['metadata']
        # Source-defined eastern room wall is protected by des.non_diggable.
        move_to(game, palace_point(metadata,15,7))
        target = palace_point(metadata,16,7)
        before = dict(game.cells[target])
        assert 1482 <= before['tile'] <= 1492, before
        offset = len(game.events)
        event = tour.named(game, 'zap')
        wand = next(i for i in event['items'] if i.get('selectable') and 'wand' in i['text'])
        game.send('menu '+str(wand['id']))
        assert game.wait_input().get('direction')
        settle(game, game.command(step_key(game.cursor,target)))
        after = dict(game.cells[target])
        messages = [e['text'] for e in game.events[offset:] if e['type'] == 'message']
        assert after['tile'] == before['tile'] and any('glow' in m.lower() for m in messages), messages
        digging = dict(target=target, before=before, after=after, messages=messages, blockedByUpstream=True)
        # This original secret door connects the resident room to the palace.
        # Search, opening and crossing remain ordinary engine actions.
        move_to(game, palace_point(metadata,15,6))
        move_to(game, palace_point(metadata,7,6))
        target = palace_point(metadata,6,6)
        for searches in range(100):
            if game.cells[target]['tile'] in (1287,1288):
                break
            # NetHack refuses an unprefixed search beside a known monster.
            # Its ordinary m prefix explicitly requests the search anyway.
            game.command('m')
            settle(game, game.command('s'))
        assert game.cells[target]['tile'] in (1287,1288), game.cells[target]
        closed = dict(game.cells[target])
        for _ in range(20):
            event = tour.named(game, 'open')
            assert event.get('direction'), event
            settle(game, game.command(step_key(game.cursor,target)))
            if game.cells[target]['tile'] in (1285,1286):
                break
        opened = dict(game.cells[target])
        assert opened['tile'] in (1285,1286), opened
        move_to(game, target)
        assert_material(game)
        result = dict(run=str(run), protectedWall=digging,
                      doorway=dict(closed=closed, opened=opened, searches=searches,
                                   crossed=True, position=game.cursor),
                      setup='Natural palace checkpoint; ordinary movement, wand zap, search, open and crossing. Monsters remain active.')
        game.finish(automatic=True)
        (ROOT/'.artifacts/asmodeus-palace-geometry.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS palace protected wall, secret door discovery, opening and traversal', flush=True)
        return result
    finally:
        cleanup(run, game)


def interaction(data):
    run, directory, game = start(data, 'interaction')
    try:
        cell = next(c for c in game.cells.values() if c.get('tile') == 632)
        before = game.turn
        description = game.inspect(cell['x'],cell['y'])
        assert 'Asmodeus' in description and game.turn == before
        delta = (cell['x']-game.cursor[0], cell['y']-game.cursor[1])
        key = next(key for dx,dy,key in STEPS if (dx,dy) == delta)
        # Without cash the upstream demon skips the offer prompt. Supplying
        # coins here exercises the actual negotiation, never a simulated UI.
        tour.lua(game,directory,'u.giveobj(obj.new("20000 gold pieces"));')
        offset = len(game.events)
        event = tour.named(game, 'chat')
        assert event.get('direction'), event
        event = game.command(key)
        assert event['kind'] == 'line' and 'offer' in event['prompt'].lower(), event
        game.send('line 0')
        settle(game)
        messages = [e['text'] for e in game.events[offset:] if e['type'] == 'message']
        assert any('Asmodeus demands' in m for m in messages), messages
        assert any('refuse' in m.lower() for m in messages), messages
        assert any('Asmodeus gets angry' in m for m in messages), messages
        assert_material(game)
        result = dict(run=str(run), inspected=description, turnFreeInspection=True,
                      prompt=event, response='0', messages=messages,
                      setup='Natural palace checkpoint with see-invisible; 20000 wizard-supplied coins for ordinary chat and refusal. No monster or map changes.')
        game.finish(automatic=True)
        (ROOT/'.artifacts/asmodeus-interaction.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS perceived Asmodeus, ordinary bribe prompt and refusal consequence', flush=True)
        return result
    finally:
        cleanup(run, game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    parser.add_argument('--unknown', action='store_true')
    parser.add_argument('--connections', action='store_true')
    parser.add_argument('--palace', action='store_true')
    parser.add_argument('--palace-tests', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        rows = [prepare('inspection'), prepare('exploration')]
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', *(row['run'] for row in rows), flush=True)
    else:
        rows = json.loads(INDEX.read_text())
    if args.engine:
        result = engine(rows[0])
        RESULTS.write_text(json.dumps(result, indent=2)+'\n')
    if args.unknown:
        unknown(rows[1])
    if args.connections:
        connections(rows[0])
    palace_data = palace(rows[0]) if args.palace else None
    if args.palace_tests:
        palace_data = palace_data or json.loads((ROOT/'.artifacts/asmodeus-palace-prepared.json').read_text())
        palace_geometry(palace_data)
        interaction(palace_data)


if __name__ == '__main__':
    main()
