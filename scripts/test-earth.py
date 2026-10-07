#!/usr/bin/env python3
"""Capture real Earth arrivals and test ordinary wand digging in isolated saves.

Production Earth material, digging and save/restore checks, not complete ascent
acceptance. The launcher enters the actual plane; no level script is replaced.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quest_test', ROOT/'scripts/test-rogue-quest.py')
quest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quest)
tour = quest.tour
INDEX = ROOT/'.artifacts/earth-engine-prepared.json'
RESULTS = ROOT/'.artifacts/earth-engine-results.json'
STEPS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))


def prepare():
    rows = []
    for mode in ('inspection', 'exploration'):
        row = json.loads(subprocess.check_output([sys.executable,
            str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case', 'earth',
            '--mode', mode], text=True))
        metadata = row['metadata']
        assert metadata['identity']['branch'] == 'The Elemental Planes'
        assert metadata['identity']['depth'] == -1, metadata['identity']
        cells = quest.displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
        metadata.update(scene='earth' if mode == 'inspection' else 'arrival',
            label='Actual Plane of Earth' if mode == 'inspection' else 'Unrevealed Earth arrival',
            displayedCells=list(cells.values()), shapeBounds=[1,0,79,21],
            sourceScript='vendor/NetHack-5.0.0/dat/earth.lua')
        metadata['sources']['earth.lua'] = tour.digest(tour.DAT/'earth.lua')
        metadata['sources']['src/dig.c'] = tour.digest(ROOT/'vendor/NetHack-5.0.0/src/dig.c')
        rows.append(row)
    INDEX.write_text(json.dumps(rows,indent=2)+'\n')
    return rows


def check(row):
    metadata = row['metadata']
    run = Path(tempfile.mkdtemp(prefix='earth-'+metadata['scene']+'-',dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    game = tour.load_game_module().Game(directory,name='wizard',options=quest.OPTIONS)
    result = dict(mode=metadata['mode'],run=str(run),setup=metadata['setup'],checkpoint=metadata['checkpoint'])
    try:
        quest.settle(game)
        identity = tour.identity(game,directory)
        assert identity == metadata['identity'], (identity,metadata['identity'])
        result['identity'] = identity
        known = [c for c in game.cells.values() if c['tile'] not in (1469,1470)]
        assert known and all(c.get('material') == 'earth' for c in known), 'Missing Earth material'
        result['knownMaterialCells'] = len(known)
        before = game.turn
        hidden = [c for c in game.cells.values() if c['tile'] in (1469,1470)]
        assert all('groundTile' not in c and 'material' not in c for c in hidden)
        if metadata['mode'] == 'exploration':
            assert hidden, 'Unrevealed arrival contains no unknown cells'
            cell = hidden[len(hidden)//2]
            assert 'unexplored' in game.inspect(cell['x'],cell['y']).lower()
        samples = []
        for cell in game.cells.values():
            if cell['tile'] in (1272,1291,1292,1266,1341) and cell['tile'] not in [s['cell']['tile'] for s in samples]:
                samples.append(dict(cell=cell,description=game.inspect(cell['x'],cell['y'])))
        assert game.turn == before
        result.update(turnFreeInspection=True,unknownCellCount=len(hidden),inspection=samples)
        # Plain-floor movement is ordinary player input. Do not clear occupants
        # or replace a random obstacle to force a route.
        origin = game.cursor
        for dx,dy,key in STEPS:
            target = (origin[0]+dx,origin[1]+dy)
            if game.cells.get(target,{}).get('char') == '.':
                quest.settle(game,game.command(key))
                assert game.cursor == target, (origin,target,game.cursor)
                assert game.turn == before+1, (before,game.turn)
                result['plainFloorMove'] = [origin,target]
                break
        else:
            result['plainFloorMoveSkipped'] = 'No adjacent displayed unoccupied plain floor.'
        if metadata['mode'] == 'inspection':
            # Read-only hidden-state diagnostic verifies a displayed blank is
            # actual STONE for this test. It never becomes artwork metadata.
            targets = []
            for dx,dy,key in STEPS:
                x,y = game.cursor[0]+dx,game.cursor[1]+dy
                if game.cells.get((x,y),{}).get('tile') != 1272:
                    continue
                start = len(game.events)
                tour.lua(game,directory,f'local ox,oy=nh.abscoord(0,0); local m=nh.getmap({x}-ox,{y}-oy); nh.pline("ATLAS_DIG_TYPE:"..m.typ_name);')
                if any(e.get('text') == 'ATLAS_DIG_TYPE:stone' for e in game.events[start:]):
                    targets.append((key,(x,y)))
            assert targets, 'No adjacent actual stone for digging baseline'
            key,target = targets[0]
            result['digBefore'] = game.cells[target]
            offset = len(game.events)
            event = tour.named(game,'zap')
            assert event['kind'] == 'menu', event
            wands = [i for i in event['items'] if i.get('selectable') and 'wand' in i['text']]
            assert len(wands) == 1, wands
            game.send('menu '+str(wands[0]['id']))
            event = game.wait_input()
            assert event.get('direction'), event
            quest.settle(game,game.command(key))
            opened = game.cells[target]
            assert opened.get('groundTile',opened['tile']) in (1291,1292,1293,1294), opened
            assert opened.get('material') == 'earth', opened
            result.update(digTarget=target,digAfter=game.cells[target],
                digMessages=[e['text'] for e in game.events[offset:] if e['type'] == 'message'],
                afterDigCells=list(game.cells.values()),afterDigArrival=game.cursor)
            if opened['char'] in ('.','#'):
                quest.settle(game,game.command(key))
                assert game.cursor == target, (game.cursor,target)
                result['enteredDugCell'] = True
            else:
                result['enteredDugCell'] = False
                result['entrySkipped'] = 'Excavated ground has an active occupant appearance. It was not removed or displaced to force a movement check.'
        position,turn = game.cursor,game.turn
        game.finish(automatic=True)
        (run/'outbound-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory,name='wizard',options=quest.OPTIONS)
        quest.settle(game)
        assert (game.cursor,game.turn) == (position,turn)
        assert tour.identity(game,directory) == identity
        assert all(c.get('material') == 'earth' for c in game.cells.values() if c['tile'] not in (1469,1470))
        if 'digTarget' in result:
            restored = game.cells[tuple(result['digTarget'])]
            assert restored.get('groundTile',restored['tile']) in (1291,1292,1293,1294)
        result.update(restored=True,position=position,turn=turn)
        game.finish(automatic=True)
        print('PASS Earth',metadata['mode'],'turn-free inspection, movement, save/restore'+(' and wand digging' if 'digTarget' in result else ''),flush=True)
        return result
    finally:
        (run/'latest-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill()
            game.process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = [check(row) for row in rows]
        RESULTS.write_text(json.dumps(results,indent=2)+'\n')
