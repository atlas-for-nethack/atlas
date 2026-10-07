#!/usr/bin/env python3
"""Prepare three real random Mines caves and check walking, digging and restore.

The launcher creates isolated upstream levels and inspection aids; this script
never changes cave geometry or gameplay rules. Native captures are a separate
parent-driven step using rows in .artifacts/mines-engine-prepared.json.
"""
import argparse
from collections import Counter, deque
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shapes',ROOT/'scripts/test-room-shapes.py')
shapes=importlib.util.module_from_spec(spec);spec.loader.exec_module(shapes)
tour=shapes.tour
INDEX=ROOT/'.artifacts/mines-engine-prepared.json'
RESULTS=ROOT/'.artifacts/mines-engine-results.json'
OPTIONS='color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS=((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))


def prepare():
    rows=[]
    for identifier in ('mines-1','mines-2','mines-3'):
        data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
            'prepare','--case',identifier,'--mode','inspection'],text=True))
        cells={}
        trace=Path(data['metadata']['checkpoint'])/'preparation.jsonl'
        for line in trace.read_text().splitlines():
            e=json.loads(line)
            if e['type']=='clear' and e.get('window')=='map':cells.clear()
            elif e['type']=='cell':cells[(e['x'],e['y'])]=e
        points=[p for p,c in cells.items() if c.get('char',' ').strip()]
        xs,ys=zip(*points)
        data['metadata']['shapeBounds']=[min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1]
        # Atlas framing may need a local crop for these nearly full-map caves.
        # Keep full bounds and actual cells rather than silently clipping evidence.
        data['metadata']['displayedTileCounts']=dict(Counter(str(c['tile']) for c in cells.values()))
        data['metadata']['displayedCells']=list(cells.values())
        rows.append(data);INDEX.write_text(json.dumps(rows,indent=2)+'\n')
        print('PREPARED',identifier,data['metadata']['shapeBounds'],flush=True)
    return rows


def dig_route(game):
    pending=deque([(game.cursor,[])]);seen={game.cursor}
    while pending:
        p,path=pending.popleft()
        for dx,dy,key in STEPS:
            q=(p[0]+dx,p[1]+dy);c=game.cells.get(q,{})
            if 1471<=c.get('tile',-1)<=1481 and 2<=q[0]<=77 and 1<=q[1]<=19:
                return path,key,q
        if len(path)>40:continue
        for dx,dy,key in STEPS:
            q=(p[0]+dx,p[1]+dy);c=game.cells.get(q,{})
            if q not in seen and c.get('char') in ('.','#'):
                pending.append((q,path+[(key,q)]));seen.add(q)
    raise AssertionError('No reachable perceived cave wall within forty ordinary steps')


def engine(data):
    run=Path(tempfile.mkdtemp(prefix='mines-engine-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    result=dict(case=data['metadata']['case']['id'],run=str(run),setup=data['metadata']['setup'])
    try:
        tour.settle(game)
        result['identity']=tour.identity(game,directory)
        assert result['identity']['branch']=='The Gnomish Mines'
        assert_material(game,True)
        result['initialCells']=list(game.cells.values())
        before=game.turn
        categories={
            'wall':lambda c:1471<=c.get('tile',-1)<=1481,
            'darkFloor':lambda c:c.get('tile')==1292,
            'litFloor':lambda c:c.get('tile')==1291,
            'blankStone':lambda c:c.get('tile')==1272,
            'knownGroundUnderOccupant':lambda c:'groundTile' in c and c.get('char') not in ('.','#'),
        }
        observations={}
        for name,predicate in categories.items():
            cell=next((c for c in game.cells.values() if predicate(c)),None)
            if cell:
                observations[name]={'cell':cell,'description':game.inspect(cell['x'],cell['y'])}
        assert game.turn==before
        result['inspection']=observations
        route,direction,target=dig_route(game)
        for key,p in route:
            for attempt in range(80):
                tour.settle(game,game.command(key))
                if game.cursor==p:break
            assert game.cursor==p,(p,game.cursor)
        result['approachSteps']=len(route);result['digTarget']=target
        result['wallBefore']=game.inspect(*target)
        wall=game.cells[target]
        assert 1471<=wall['tile']<=1481,wall
        start=len(game.events)
        event=tour.named(game,'zap');assert event['kind']=='menu',event
        wand=next(i for i in event['items'] if i.get('selectable') and 'wand' in i['text'])
        game.send('menu '+str(wand['id']));event=game.wait_input();assert event.get('direction'),event
        tour.settle(game,game.command(direction))
        result['digMessages']=[e['text'] for e in game.events[start:] if e['type']=='message']
        opened=game.cells[target]
        assert opened['char'] in ('.','#'),('Digging did not open cave boundary',opened)
        result['dugCell']=opened;result['dugInspection']=game.inspect(*target)
        tour.settle(game,game.command(direction));assert game.cursor==target,(target,game.cursor)
        result['enteredDugCell']=True
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        # Hero covers the dug floor; groundTile is the perceived surface beneath.
        restored=game.cells[position]
        assert restored.get('groundTile') in (1291,1292,1294,1295),restored
        assert restored.get('material')=='mines',restored
        assert_material(game,True)
        result.update(restored=True,restoredHeroCell=restored,position=position,turn=turn,
            turnFreeInspection=True,boundaryTileBefore=wall['tile'])
        game.finish(automatic=True)
        print('PASS',result['case'],'walked',len(route),'dug',target,'and restored',flush=True)
        return result
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()


def unknown():
    data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
        'prepare','--case','mines-1','--mode','exploration'],text=True))
    run=Path(tempfile.mkdtemp(prefix='mines-engine-unknown-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    try:
        tour.settle(game)
        hidden=[c for c in game.cells.values() if c.get('tile')==1469]
        assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
        assert_material(game,True)
        before=game.turn
        samples=[dict(cell=c,description=game.inspect(c['x'],c['y'])) for c in hidden[::max(1,len(hidden)//8)]]
        assert game.turn==before
        assert all('unexplored' in row['description'].lower() for row in samples),samples
        result=dict(run=str(run),unknownCellCount=len(hidden),samples=samples,
            turnFreeInspection=True,noHiddenGround=True,noHiddenMaterial=True)
        game.finish(automatic=True)
        (ROOT/'.artifacts/mines-engine-unknown.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS unexplored Mines cells remain undisclosed; inspection spends no turns',flush=True)
    finally:
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()


def assert_material(game,expected):
    known=[c for c in game.cells.values() if c.get('tile') not in (1469,1470)]
    assert known,'No displayed known cells'
    if expected:
        allowed=['mines'] if expected is True else ([expected] if isinstance(expected,str) else expected)
        assert all(c.get('material') in allowed for c in known),known[:12]
    else:
        assert all('material' not in c for c in game.cells.values()),'Material leaked outside the Mines branch'
    assert all('material' not in c and 'groundTile' not in c for c in game.cells.values() if c.get('tile') in (1469,1470))


def boundaries(data):
    """Exercise actual level transitions, including same-branch special levels."""
    run=Path(tempfile.mkdtemp(prefix='mines-engine-boundaries-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    records=[]
    try:
        tour.settle(game)
        origin=tour.identity(game,directory)
        def check(label,expected,branch):
            identity=tour.identity(game,directory)
            assert identity['branch']==branch,identity
            assert_material(game,expected)
            records.append(dict(label=label,identity=identity,material=expected,
                knownCells=sum(c.get('tile') not in (1469,1470) for c in game.cells.values())))
        def depth(n):
            game.cells.clear()
            e=tour.named(game,'wizlevelport');assert e['kind']=='line',e
            game.send('line '+str(n));tour.settle(game)
        def special(name):
            game.cells.clear();tour.teleport(game,name)
        check('Random cave before departure',True,'The Gnomish Mines')
        special('minetn-');check('Minetown exterior/known built interiors', ['mines','mines-built'],'The Gnomish Mines')
        special('minend-');check("Mines End retains Mines material",True,'The Gnomish Mines')
        depth(1);check('Main dungeon excludes material',False,'The Dungeons of Doom')
        special('minetn-');check('Minetown revisited', ['mines','mines-built'],'The Gnomish Mines')
        depth(origin['depth']);check('Return to original random cave',True,'The Gnomish Mines')
        assert tour.identity(game,directory)==origin
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        (run/'outbound-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        check('Restore returned cave',True,'The Gnomish Mines')
        game.finish(automatic=True)
        result=dict(run=str(run),checks=records,restored=True,
            setup='Isolated real level transitions via upstream wizard level teleport; no terrain modifications.')
        (ROOT/'.artifacts/mines-engine-boundaries.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS random Mines, Minetown, Mines End, main dungeon and return/restore material boundaries',flush=True)
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()


def stairs(data):
    """Use real adjoining stairs between the prepared cave and Minetown."""
    run=Path(tempfile.mkdtemp(prefix='mines-engine-stairs-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    try:
        tour.settle(game)
        origin=tour.identity(game,directory);assert_material(game,True)
        entry=next((p for p,c in game.cells.items() if c.get('char')=='>'),None)
        assert entry,'Prepared cave has no displayed downstairs'
        event=tour.named(game,'teleport')
        if event.get('kind')=='menu' and event.get('how')==0:
            game.send('key 32');event=game.wait_input()
        assert event.get('targeting'),event
        game.send(f'position {entry[0]} {entry[1]}');tour.settle(game)
        assert game.cursor==entry,(entry,game.cursor)
        start=game.turn
        game.cells.clear();tour.settle(game,game.command('>'))
        destination=tour.identity(game,directory)
        assert destination['branch']==origin['branch']=='The Gnomish Mines'
        assert destination['level']==origin['level']+1,(origin,destination)
        # The catalog prepares exactly one level above Minetown. The actual
        # downstairs therefore tests entry into named Minetown, where known
        # built interiors retain canonical ground within the Mines architecture.
        assert_material(game,['mines','mines-built'])
        arrival=game.cursor;arrivalCell=game.cells[arrival]
        assert arrivalCell.get('groundTile') in (1291,1292),arrivalCell
        game.cells.clear();tour.settle(game,game.command('<'))
        returned=tour.identity(game,directory)
        assert returned==origin,(returned,origin)
        assert game.cursor==entry,(game.cursor,entry)
        assert game.turn>start,(game.turn,start)
        elapsed=game.turn-start
        assert_material(game,True)
        game.finish(automatic=True)
        result=dict(run=str(run),origin=origin,destination=destination,returned=returned,
            departure=entry,arrival=arrival,returnPosition=game.cursor,stairCommands=2,elapsedTurns=elapsed,
            sourceMaterial='mines',destinationMaterials=['mines','mines-built'],returnMaterial='mines',
            setup='Upstream wizard coordinate teleport places the test on existing displayed downstairs; actual > and < perform both level transitions. No level geometry changes.')
        (ROOT/'.artifacts/mines-engine-stairs.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS real downstairs to Minetown and upstairs back; Mines material retained, exact return position verified',flush=True)
    finally:
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--native',action='store_true',help='Capture three caves in both Modern sets and one in both Classic sets')
    parser.add_argument('--stairs',action='store_true',help='Use actual down/up stairs between the random cave and Minetown')
    parser.add_argument('--boundaries',action='store_true',help='Check Mines material covers caves and named Mines levels, disappears in the main dungeon, and restores correctly')
    parser.add_argument('--unknown',action='store_true',help='Check undisclosed cells in an unrevealed exploration cave')
    args=parser.parse_args()
    if args.unknown:unknown()
    rows=prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.boundaries:boundaries(rows[0])
    if args.stairs:stairs(rows[0])
    if args.engine:
        results=[]
        for row in rows:
            results.append(engine(row));RESULTS.write_text(json.dumps(results,indent=2)+'\n')

    if args.native:
        captures=[]
        for index,row in enumerate(rows):
            data=json.loads(json.dumps(row))
            x,y=data['metadata']['arrival']
            data['metadata']['shapeBounds']=[max(0,min(60,x-9)),max(0,min(11,y-4)),20,10]
            sets=['lantern-modern','soot-and-brass']
            if index==0:sets+=['lantern','soot-and-brass-classic']
            for tileset in sets:
                captures.append(shapes.native(data,tileset))
                (ROOT/'.artifacts/mines-native.json').write_text(json.dumps(captures,indent=2)+'\n')
                print('PASS native',data['metadata']['case']['id'],tileset,flush=True)
        shapes.gallery(captures,ROOT/'.artifacts/mines-native-review.html','Random Mines')


if __name__=='__main__':main()
