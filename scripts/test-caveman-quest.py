#!/usr/bin/env python3
"""Prepare actual Caveman quest stages and verify regional engine behavior.

These are isolated material-review checkpoints, not a quest completion test.
The existing launcher recipes reveal inspection maps and prepare the two filler
sources in their real Quest slots. Home exploration remains unrevealed. No
native application is launched and no owner's save or running game is touched.
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
spec = importlib.util.spec_from_file_location('tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/caveman-engine-prepared.json'
RESULTS = ROOT/'.artifacts/caveman-engine-results.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))
STAGES = (
    ('Cav-strt', 'home', 'Home: the Caves of the Ancestors',
     'The besieged home caves contain lit inhabited pockets and Shaman Karnov\'s temple, with dark outer passages and hostile bugbears.'),
    ('Cav-fila', 'upper', 'Upper caves: generated approach',
     'Joined, smoothed natural caves with bugbears and a hill giant connect the home to the locate level. This is one generated example.'),
    ('Cav-loca', 'locate', 'Locate: approach to the Dragon\'s Lair',
     'Broad branching tunnels lead into a lit large cavern defended by bugbears and hill giants. Quest text describes claw marks, carrion and bones.'),
    ('Cav-filb', 'lower', 'Lower caves: generated descent',
     'A second joined natural-cave generator supplies the lower approach, with more objects and giants than the upper filler. This is one generated example.'),
    ('Cav-goal', 'goal', 'Goal: the Chromatic Dragon\'s cavern',
     'A broad lit cavern houses the sleeping Chromatic Dragon and the Sceptre of Might. Quest text describes polished, fire-scorched walls, scattered bones and sulphurous air.'),
)


def settle(game, event=None):
    event = event or game.wait_input()
    for _ in range(80):
        if event.get('command'):
            return event
        if event['kind'] == 'line':
            prompt = event.get('prompt','').lower()
            if prompt.startswith('call '):
                game.send('line ')
            elif 'wish' in prompt:
                game.send('line nothing')
            else:
                raise RuntimeError('Unexpected test question: '+event.get('prompt',''))
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
            cells[event['x'],event['y']] = event
    return cells


def bounds(cells):
    visible = [p for p,c in cells.items() if c.get('char',' ').strip()]
    assert visible, 'No displayed level geometry'
    xs,ys = zip(*visible)
    x,y = max(1,min(xs)-1),max(0,min(ys)-1)
    return [x,y,min(79,max(xs)+1)-x+1,min(20,max(ys)+1)-y+1]


def prepare():
    rows = []
    for identifier,scene,label,notes in STAGES:
        modes = ('inspection','exploration') if scene == 'home' else ('inspection',)
        for mode in modes:
            row = json.loads(subprocess.check_output([sys.executable,
                str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case',identifier,
                '--mode',mode], text=True))
            metadata = row['metadata']
            assert metadata['identity']['branch'] == 'The Quest', metadata['identity']
            assert metadata['identity']['role'] == 'Caveman', metadata['identity']
            cells = displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
            metadata.update(scene=scene if mode=='inspection' else 'arrival',
                label=label if mode=='inspection' else 'Unrevealed home arrival',
                roleNotes=notes, displayedCells=list(cells.values()),
                displayedTileCounts=dict(Counter(str(c['tile']) for c in cells.values())),
                shapeBounds=bounds(cells), sourceScript='vendor/NetHack-5.0.0/dat/'+identifier+'.lua')
            for name in (identifier+'.lua','quest.lua'):
                metadata['sources'][name] = tour.digest(tour.DAT/name)
            metadata['sources']['src/role.c'] = tour.digest(ROOT/'vendor/NetHack-5.0.0/src/role.c')
            metadata['testTerrainTiles'] = [t for t in (1266,1287,1288,1297,1298,1306,1307,1308)
                                            if str(t) in metadata['displayedTileCounts']]
            rows.append(row)
            INDEX.write_text(json.dumps(rows,indent=2)+'\n')
            print('PREPARED',identifier,mode,metadata['identity'],flush=True)
    return rows


def start(row):
    metadata = row['metadata']
    run = Path(tempfile.mkdtemp(prefix='caveman-'+metadata['scene']+'-',dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game', directory)
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory))
    game = tour.load_game_module().Game(directory,role=metadata['identity']['role'],name='wizard',options=OPTIONS)
    settle(game)
    return run,directory,game


def cleanup(run,game):
    (run/'latest-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait()


def assert_material(game, expected):
    known = [c for c in game.cells.values() if c.get('tile') not in (1469,1470)]
    assert known, 'No displayed level cells'
    assert all(c.get('material') == expected for c in known), (expected,known[:8])
    hidden = [c for c in game.cells.values() if c.get('tile') in (1469,1470)]
    assert all('material' not in c and 'groundTile' not in c for c in hidden)


def check(row):
    metadata = row['metadata']
    run,directory,game = start(row)
    try:
        identity = tour.identity(game,directory)
        assert identity == metadata['identity'], (identity,metadata['identity'])
        material = 'caveman-goal' if metadata['case']['id'] == 'Cav-goal' else 'caveman'
        assert_material(game, material)
        before = game.turn
        observations = []
        for label,predicate in (
            ('wall',lambda c:1273 <= c.get('tile',-1) <= 1283),
            ('floor',lambda c:c.get('tile') in (1291,1292)),
            ('door',lambda c:c.get('tile') in (1287,1288)),
            ('upstairs',lambda c:c.get('tile') == 1297),
            ('downstairs',lambda c:c.get('tile') == 1298),
            ('altar',lambda c:c.get('tile') in (1306,1307,1308)),
            ('boulder',lambda c:c.get('tile') == 1266)):
            cell = next((c for c in game.cells.values() if predicate(c)),None)
            if cell:
                observations.append(dict(category=label,cell=cell,
                    description=game.inspect(cell['x'],cell['y'])))
        assert observations and game.turn == before
        hidden = [c for c in game.cells.values() if c.get('tile') in (1469,1470)]
        assert all('material' not in c and 'groundTile' not in c for c in hidden)
        unknown = []
        if metadata['mode'] == 'exploration':
            assert hidden, 'Home exploration unexpectedly revealed'
            for c in hidden[::max(1,len(hidden)//8)]:
                text = game.inspect(c['x'],c['y'])
                assert 'unexplored' in text.lower() or c['tile'] == 1470, text
                unknown.append(dict(cell=c,description=text))
            assert game.turn == before
        result = dict(case=metadata['case']['id'],scene=metadata['scene'],mode=metadata['mode'],
            run=str(run),identity=identity,inspection=observations,turnFreeInspection=True,
            hiddenCells=len(hidden),unknownInspection=unknown,noHiddenGround=True,noHiddenMaterial=True,
            material=material,engine=tour.digest(tour.load_game_module().RUNTIME/'nethack'))
        # Do not teleport or reshape caves just to claim movement coverage.
        # An adjacent displayed bare floor is sufficient for this baseline.
        origin = game.cursor
        adjacent = next(((origin[0]+dx,origin[1]+dy,key) for dx,dy,key in STEPS
                         if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('tile') in (1291,1292)),None)
        if adjacent:
            turn = game.turn
            settle(game,game.command(adjacent[2]))
            destination = tuple(adjacent[:2])
            if game.cursor == destination:
                result['ordinaryMove'] = dict(origin=origin,destination=destination,turns=game.turn-turn)
            else:
                result['movementDeferred'] = 'An active occupant or upstream condition prevented the one-step attempt; no position override used.'
        else:
            result['movementDeferred'] = 'No adjacent displayed bare floor at this natural checkpoint arrival.'
        position,turn = game.cursor,game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory,role='Caveman',name='wizard',options=OPTIONS)
        settle(game)
        assert (game.cursor,game.turn) == (position,turn), (game.cursor,game.turn,position,turn)
        assert tour.identity(game,directory) == identity
        assert_material(game, material)
        result.update(restored=True,position=position,turn=turn)
        game.finish(automatic=True)
        print('PASS',metadata['case']['id'],metadata['mode'],'regional material, inspection, perception and exact restore',flush=True)
        return result
    finally:
        cleanup(run,game)


def isolation(row):
    """Verify role and branch boundaries using ordinary wizard destination menus."""
    run,directory,game = start(row)
    transitions = []
    try:
        assert_material(game, 'caveman')
        origin = tour.identity(game,directory)
        for target,expected,branch in (
            ('oracle',None,'The Dungeons of Doom'),
            ('Cav-strt','caveman','The Quest'),
            # Unassigned quest descent from home is correctly blocked by
            # upstream. Use the outside debug entry for the goal checkpoint.
            ('oracle',None,'The Dungeons of Doom'),
            ('Cav-goal','caveman-goal','The Quest'),
            ('Cav-loca','caveman','The Quest')):
            game.cells.clear()
            tour.teleport(game,target)
            identity = tour.identity(game,directory)
            assert identity['role'] == 'Caveman' and identity['branch'] == branch, identity
            assert_material(game, expected)
            transitions.append(dict(destination=target,identity=identity,material=expected,
                                    displayedCells=list(game.cells.values())))
        game.finish(automatic=True)
        result = dict(run=str(run),origin=origin,transitions=transitions,
                      engine=tour.digest(tour.load_game_module().RUNTIME/'nethack'),
                      setup='Existing wizard checkpoint, ordinary debug level-destination commands; no terrain, occupants or role modifications.')
    finally:
        cleanup(run,game)
    other_roles = []
    for identifier in ('Val-strt','Val-goal'):
        data = json.loads(subprocess.check_output([sys.executable,
            str(ROOT/'scripts/playtest/prepare.py'),'prepare','--case',identifier,
            '--mode','inspection'],text=True))
        data['metadata']['scene'] = identifier
        run,directory,game = start(data)
        try:
            identity = tour.identity(game,directory)
            assert identity['branch'] == 'The Quest' and identity['role'] == 'Valkyrie', identity
            assert_material(game, None)
            other_roles.append(dict(case=identifier,run=str(run),identity=identity,
                                    noCavemanMaterial=True,displayedCells=list(game.cells.values())))
            game.finish(automatic=True)
        finally:
            cleanup(run,game)
    result['otherRoleQuests'] = other_roles
    (ROOT/'.artifacts/caveman-engine-isolation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS Caveman normal/goal/outside transitions and other-role home/goal exclusion',flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--isolation',action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(check(row))
            RESULTS.write_text(json.dumps(results,indent=2)+'\n')
    if args.isolation:
        isolation(next(row for row in rows if row['metadata']['scene']=='home'))


if __name__ == '__main__':
    main()
