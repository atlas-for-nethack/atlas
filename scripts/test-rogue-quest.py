#!/usr/bin/env python3
"""Prepare actual Rogue quest stages and verify predesign engine behavior.

These are isolated material-review checkpoints, not a quest completion test or production material acceptance.
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
INDEX = ROOT/'.artifacts/rogue-engine-prepared.json'
RESULTS = ROOT/'.artifacts/rogue-engine-results.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))
STAGES = (
    ('Rog-strt', 'home', "Home: Ransmannsby and the Thieves' Guild",
     'Dense built rooms and narrow streets surround the Master of Thieves. Regular and secret locked doors, treasure chest, a small pool and deceptive stair appearances are upstream features; this capture preserves only their displayed appearances.'),
    ('Rog-fila', 'upper', 'Upper approach: generated guild-side rooms',
     'Six ordinary rooms linked by random corridors contain leprechauns, water nymphs, guardian nagas, objects and traps. This is one generated example.'),
    ('Rog-loca', 'locate', 'Locate: irregular enclosed approach',
     'A broad lit irregular floor plan has hard, non-diggable walls, stairs and a side enclosure behind a secret door. The secret remains a displayed wall until discovered.'),
    ('Rog-filb', 'lower', 'Lower approach: generated assassin-side rooms',
     'The lower filler uses the same six-room generator as the upper filler, including inhabitants and objects. This is a separate generated example, not evidence of a different terrain type.'),
    ('Rog-goal', 'goal', "Goal: the Assassins' Guild Hall",
     'The Master Assassin and Master Key of Thievery occupy a built maze with secret doors beside a broad open area and an elaborate pool with sharks. The capture adds no occupants or hidden terrain.'),
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
            assert metadata['identity']['role'] == 'Rogue', metadata['identity']
            cells = displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
            metadata.update(scene=scene if mode=='inspection' else 'arrival',
                label=label if mode=='inspection' else 'Unrevealed home arrival',
                roleNotes=notes, displayedCells=list(cells.values()),
                displayedTileCounts=dict(Counter(str(c['tile']) for c in cells.values())),
                shapeBounds=bounds(cells), sourceScript='vendor/NetHack-5.0.0/dat/'+identifier+'.lua')
            for name in (identifier+'.lua','quest.lua'):
                metadata['sources'][name] = tour.digest(tour.DAT/name)
            metadata['sources']['src/role.c'] = tour.digest(ROOT/'vendor/NetHack-5.0.0/src/role.c')
            metadata['testTerrainTiles'] = [t for t in (1266,1285,1286,1287,1288,1289,1290,1291,1292,1293,1294,1297,1298,1306,1307,1308,1314)
                                            if str(t) in metadata['displayedTileCounts']]
            rows.append(row)
            INDEX.write_text(json.dumps(rows,indent=2)+'\n')
            print('PREPARED',identifier,mode,metadata['identity'],flush=True)
    return rows


def start(row):
    metadata = row['metadata']
    run = Path(tempfile.mkdtemp(prefix='rogue-'+metadata['scene']+'-',dir=ROOT/'.artifacts'))
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
        material = None  # Predesign packaged engine has no Rogue regional material.
        assert_material(game, material)
        before = game.turn
        observations = []
        for label,predicate in (
            ('wall',lambda c:1273 <= c.get('tile',-1) <= 1283),
            ('floor',lambda c:c.get('tile') in (1291,1292)),
            ('door',lambda c:c.get('tile') in (1284,1285,1286,1287,1288,1289,1290)),
            ('corridor',lambda c:c.get('tile') in (1293,1294)),
            ('water',lambda c:c.get('char') == '}'),
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
        # Do not teleport or reshape the level just to claim movement coverage.
        # An adjacent displayed bare floor is sufficient for this baseline.
        origin = game.cursor
        adjacent = next(((origin[0]+dx,origin[1]+dy,key) for dx,dy,key in STEPS
                         if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('tile') in (1291,1292)),None)
        if adjacent:
            turn = game.turn
            settle(game,game.command(adjacent[2]))
            destination = tuple(adjacent[:2])
            if game.cursor == destination:
                assert game.turn-turn == 1, (game.turn,turn)
                result['ordinaryMove'] = dict(origin=origin,destination=destination,turns=game.turn-turn)
            else:
                result['movementDeferred'] = 'An active occupant or upstream condition prevented the one-step attempt; no position override used.'
        else:
            result['movementDeferred'] = 'No adjacent displayed bare floor at this natural checkpoint arrival.'
        position,turn = game.cursor,game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory,role='Rogue',name='wizard',options=OPTIONS)
        settle(game)
        assert (game.cursor,game.turn) == (position,turn), (game.cursor,game.turn,position,turn)
        assert tour.identity(game,directory) == identity
        assert_material(game, material)
        result.update(restored=True,position=position,turn=turn)
        game.finish(automatic=True)
        print('PASS',metadata['case']['id'],metadata['mode'],'baseline material, inspection, perception and exact restore',flush=True)
        return result
    finally:
        cleanup(run,game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(check(row))
            RESULTS.write_text(json.dumps(results,indent=2)+'\n')


if __name__ == '__main__':
    main()
