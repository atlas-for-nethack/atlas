#!/usr/bin/env python3
"""Ordinary dungeon acceptance: real stair travel and a legal wall excavation."""
import collections
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


tour=module('tour',ROOT/'scripts/playtest/prepare.py')
terrain=module('terrain',ROOT/'scripts/test-lantern-gameplay.py')
DIRECTIONS=[(-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j')]


def walk_to(game,target):
    # Route only through displayed/remembered floor and doors, never hidden terrain.
    for _ in range(600):
        if game.cursor==target:return
        queue=collections.deque([(game.cursor,[])])
        visited={game.cursor}
        while queue:
            position,path=queue.popleft()
            if position==target:break
            for dx,dy,key in DIRECTIONS:
                nextpos=(position[0]+dx,position[1]+dy)
                cell=game.cells.get(nextpos,{})
                if nextpos in visited:continue
                if cell.get('char') not in ('.','#','<','>','+') and cell.get('groundTile') not in (1291,1292,1294,1295):continue
                visited.add(nextpos);queue.append((nextpos,path+[(key,nextpos)]))
        else:raise AssertionError(('No perceived route to stairs',game.cursor,target))
        key,nextpos=path[0]
        if game.cells[nextpos].get('char')=='+':
            event=tour.named(game,'open');assert event.get('direction'),event
            tour.settle(game,game.command(key))
            if game.cells[nextpos].get('char')=='+':
                event=tour.named(game,'kick');assert event.get('direction'),event
                tour.settle(game,game.command(key))
        else:tour.settle(game,game.command(key))
    raise AssertionError('Could not reach stairs within the movement budget')


def generated(case):
    data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),'prepare','--case',case,'--mode','inspection'],text=True))
    run=Path(data['run']);directory=run/'game'
    for key in ['HOME','NETHACKDIR','HACKDIR']:os.environ[key]=str(directory)
    game=tour.load_game_module().Game(directory,name='wizard',options='color,!news,!autopickup,force_invmenu,menustyle:full')
    try:
        tour.settle(game)
        initial=tour.identity(game,directory)
        stairs=next(p for p,c in game.cells.items() if c.get('char')=='>')
        walk_to(game,stairs)
        tour.settle(game,tour.named(game,'down'))
        below=tour.identity(game,directory)
        assert below['branch']==initial['branch'] and below['level']==initial['level']+1,(initial,below)
        tour.settle(game,tour.named(game,'up'))
        back=tour.identity(game,directory)
        assert back==initial and game.cursor==stairs,(initial,back,stairs,game.cursor)
        hints=next(e for e in reversed(game.events) if e['type']=='context')['commands']
        assert any(h['name']=='down' for h in hints),hints
        before=game.turn;game.inspect(*stairs);assert game.turn==before
        game.finish(automatic=True)
        (run/'stair-acceptance.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        print('PASS',case,'ordinary walking, downstairs/upstairs round trip, remembered stair inspection and save:',run,flush=True)
        return str(run)
    finally:
        if game.process.poll() is None:game.process.kill();game.process.wait()


def digging():
    run=Path(tempfile.mkdtemp(prefix='dungeon-dig-',dir=ROOT/'.artifacts'))
    directory=run/'game';directory.mkdir()
    for key in ['HOME','NETHACKDIR','HACKDIR']:os.environ[key]=str(directory)
    fixture=terrain.context.Fixture(str(directory));game=fixture.game
    try:
        terrain.load(fixture,arrival=(5,2))
        target=(16,5) # Shared vertical wall, next to the actual arrival square.
        assert game.cells[target]['char']=='|' and 'groundTile' not in game.cells[target]
        fixture.wish('blessed wand of digging (0:50)')
        tour.lua(game,directory,'nh.parse_config("OPTIONS=force_invmenu,menustyle:full");')
        before=game.turn
        event=tour.named(game,'zap')
        assert event['kind']=='menu',event
        wand=next(i for i in event['items'] if i['selectable'] and 'wand' in i['text'].lower())
        game.send('menu '+str(wand['id']))
        event=game.wait_input();assert event.get('direction'),event
        tour.settle(game,game.command('l'))
        assert game.turn>before and game.cells[target]['char'] in '.#',game.cells[target]
        tour.settle(game,game.command('l'))
        assert game.cursor==target and game.cells[target].get('groundTile') in (1291,1294,1295),game.cells[target]
        game.finish(automatic=True)
        print('PASS ordinary wand zap opens a legal wall, exposes ground and allows actual movement:',run,flush=True)
        return str(run)
    finally:
        (run/'dig-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        fixture.close()


if __name__=='__main__':
    results=dict(generated=[generated('dungeon-'+str(i)) for i in (1,2,3)],digging=digging())
    (ROOT/'.artifacts/dungeon-baseline.json').write_text(json.dumps(results,indent=2)+'\n')
