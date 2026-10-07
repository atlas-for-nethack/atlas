#!/usr/bin/env python3
"""Inspect actual random Gehennom levels in disposable engine games.

No terrain or generator is replaced. Three naturally selected examples are not
coverage of all seven hellfill generator families. No native app is launched.
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
spec=importlib.util.spec_from_file_location('mines',ROOT/'scripts/test-random-mines.py')
mines=importlib.util.module_from_spec(spec);spec.loader.exec_module(mines)
tour=mines.tour
INDEX=ROOT/'.artifacts/gehennom-engine-prepared.json'
RESULTS=ROOT/'.artifacts/gehennom-engine-results.json'
OPTIONS=mines.OPTIONS


def prepare():
    rows=[]
    for identifier in ('gehennom-1','gehennom-2','gehennom-3'):
        data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
            'prepare','--case',identifier,'--mode','inspection'],text=True))
        cells={}
        for line in (Path(data['metadata']['checkpoint'])/'preparation.jsonl').read_text().splitlines():
            event=json.loads(line)
            if event['type']=='clear' and event.get('window')=='map':cells.clear()
            elif event['type']=='cell':cells[event['x'],event['y']]=event
        points=[p for p,c in cells.items() if c.get('char',' ').strip()]
        xs,ys=zip(*points)
        metadata=data['metadata']
        metadata['shapeBounds']=[min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1]
        metadata['displayedCells']=list(cells.values())
        metadata['displayedTileCounts']=dict(Counter(str(c['tile']) for c in cells.values()))
        selection=metadata['fillerSelection']
        assert metadata['identity']['depth']==selection['selected']
        assert str(selection['selected']) not in selection['excluded']
        rows.append(data);INDEX.write_text(json.dumps(rows,indent=2)+'\n')
        print('PREPARED',identifier,metadata['identity'],flush=True)
    return rows


def start(data,prefix):
    run=Path(tempfile.mkdtemp(prefix='gehennom-'+prefix+'-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    # Dedicated test process only; never point the game at owner saves.
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    tour.settle(game)
    return run,directory,game


def trace(run,game,name='engine.jsonl'):
    (run/name).write_text(''.join(json.dumps(e)+'\n' for e in game.events))


def cleanup(run,game):
    trace(run,game,'last-engine.jsonl')
    if game.process.poll() is None:game.process.kill();game.process.wait()


def terrain_inventory(game,directory):
    """Read-only wizard evidence. These hidden diagnostics never enter the UI."""
    begin=len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0); local counts={};
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy); counts[m.typ_name]=(counts[m.typ_name] or 0)+1;
end;end;
for k,v in pairs(counts) do nh.pline("ATLAS_TERRAIN:"..k.."|"..v);end;''')
    return {e['text'].split(':',1)[1].split('|')[0]:int(e['text'].rsplit('|',1)[1])
        for e in game.events[begin:] if e.get('text','').startswith('ATLAS_TERRAIN:')}


def dig_route(game):
    pending=deque([(game.cursor,[])]);seen={game.cursor}
    while pending:
        point,path=pending.popleft()
        for dx,dy,key in mines.STEPS:
            target=(point[0]+dx,point[1]+dy)
            if 1482<=game.cells.get(target,{}).get('tile',-1)<=1492 and 2<=target[0]<=77 and 1<=target[1]<=19:
                return path,key,target
        if len(path)>=40:continue
        for dx,dy,key in mines.STEPS:
            target=(point[0]+dx,point[1]+dy)
            if target not in seen and game.cells.get(target,{}).get('char') in ('.','#'):
                seen.add(target);pending.append((target,path+[(key,target)]))
    raise AssertionError('No reachable displayed Gehennom stone wall')


def assert_material(game):
    known=[c for c in game.cells.values() if c.get('tile') not in (1469,1470)]
    assert known and all(c.get('material')=='gehennom' for c in known),known[:8]
    hidden=[c for c in game.cells.values() if c.get('tile')==1469]
    assert all('material' not in c and 'groundTile' not in c for c in hidden)


def engine(data):
    run,directory,game=start(data,'engine')
    result=dict(case=data['metadata']['case']['id'],run=str(run),setup=data['metadata']['setup'])
    try:
        assert_material(game)
        identity=tour.identity(game,directory)
        selected,selection=tour.gehennom_filler_depth(game,int(result['case'].rsplit('-',1)[1])-1)
        assert identity['branch']=='Gehennom' and identity['depth']==selected,(identity,selection)
        result.update(identity=identity,fillerSelection=selection,initialCells=list(game.cells.values()),
            initialStatus=dict(game.status),terrainCounts=terrain_inventory(game,directory))
        before=game.turn
        samples=[]
        for category,predicate in [('wall',lambda c:1482<=c.get('tile',-1)<=1492),
                ('floor',lambda c:c.get('tile') in (1291,1292)),
                ('hazard',lambda c:c.get('char') in ('}','^')),
                ('stairs',lambda c:c.get('char') in ('<','>'))]:
            cell=next((c for c in game.cells.values() if predicate(c)),None)
            if cell:samples.append(dict(category=category,cell=cell,description=game.inspect(cell['x'],cell['y'])))
        assert before==game.turn
        result.update(inspection=samples,turnFreeInspection=True)
        try:
            route,direction,target=dig_route(game)
        except AssertionError:
            result['digSkipped']='No reachable perceived stone wall within forty ordinary cardinal steps. Actual bars/lava are not stone to dig.'
            route=[]
        else:
            for key,p in route:
                for attempt in range(80):
                    tour.settle(game,game.command(key))
                    if game.cursor==p:break
                assert game.cursor==p,(p,game.cursor)
            result.update(approachSteps=len(route),digTarget=target,wallBefore=game.inspect(*target),wallCellBefore=game.cells[target])
            offset=len(game.events)
            event=tour.named(game,'zap');assert event['kind']=='menu',event
            wands=[i for i in event['items'] if i.get('selectable') and 'wand' in i['text']]
            assert len(wands)==1,wands # The inspection recipe supplies exactly one wand.
            wand=wands[0]
            game.send('menu '+str(wand['id']));event=game.wait_input();assert event.get('direction'),event
            tour.settle(game,game.command(direction))
            opened=game.cells[target]
            result.update(digMessages=[e['text'] for e in game.events[offset:] if e['type']=='message'],
                cellAfterDig=opened,afterDigCells=list(game.cells.values()))
            if opened['char'] in ('.','#'):
                tour.settle(game,game.command(direction));assert game.cursor==target,(target,game.cursor)
                result['enteredDugCell']=True
            else:
                assert any('hard' in m.lower() or 'glow' in m.lower() for m in result['digMessages']),result
                result['digBlockedByUpstream']=True
        # Independently exercise one plain-floor step if arrival was immediately
        # beside the dig target, or if the current maze has no stone wall.
        if not route:
            for dx,dy,key in mines.STEPS:
                p=(game.cursor[0]+dx,game.cursor[1]+dy)
                if game.cells.get(p,{}).get('char') in ('.','#'):
                    origin=game.cursor;tour.settle(game,game.command(key))
                    assert game.cursor==p,(origin,p,game.cursor)
                    result['plainFloorMove']=[origin,p];break
            else: result['plainFloorMoveSkipped']='No adjacent displayed plain floor at current position.'
        position,turn=game.cursor,game.turn
        game.finish(automatic=True);trace(run,game)
        game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert tour.identity(game,directory)==identity
        assert_material(game)
        result.update(restored=True,position=position,turn=turn,restoredHeroCell=game.cells[position])
        game.finish(automatic=True)
        print('PASS',result['case'],'movement/dig evidence and exact save/restore',flush=True)
        return result
    finally:cleanup(run,game)


def unknown():
    data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
        'prepare','--case','gehennom-1','--mode','exploration'],text=True))
    run,directory,game=start(data,'unknown')
    try:
        assert_material(game)
        hidden=[c for c in game.cells.values() if c.get('tile')==1469]
        assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
        before=game.turn
        samples=[dict(cell=c,description=game.inspect(c['x'],c['y'])) for c in hidden[::max(1,len(hidden)//8)]]
        assert game.turn==before
        assert all('unexplored' in row['description'].lower() for row in samples),samples
        result=dict(run=str(run),unknownCells=len(hidden),samples=samples,turnFreeInspection=True,
            noHiddenGround=True,noHiddenMaterial=True,identity=tour.identity(game,directory))
        game.finish(automatic=True);trace(run,game)
        (ROOT/'.artifacts/gehennom-engine-unknown.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS ordinary unrevealed Gehennom inspection',flush=True)
    finally:cleanup(run,game)


def stairs(data):
    run,directory,game=start(data,'stairs')
    try:
        origin=tour.identity(game,directory)
        assert_material(game)
        entry=next((p for p,c in game.cells.items() if c.get('char')=='>'),None)
        assert entry,'No displayed downstairs in filler'
        event=tour.named(game,'teleport')
        if event.get('kind')=='menu' and event.get('how')==0:
            game.send('key 32');event=game.wait_input()
        assert event.get('targeting'),event
        game.send(f'position {entry[0]} {entry[1]}');tour.settle(game)
        assert game.cursor==entry,(entry,game.cursor)
        before=game.turn
        game.cells.clear();tour.settle(game,game.command('>'))
        destination=tour.identity(game,directory)
        assert destination['branch']==origin['branch']=='Gehennom'
        assert destination['depth']==origin['depth']+1,(origin,destination)
        arrival=game.cursor
        game.cells.clear();tour.settle(game,game.command('<'))
        assert tour.identity(game,directory)==origin
        assert_material(game)
        assert game.cursor==entry and game.turn>before
        result=dict(run=str(run),origin=origin,destination=destination,departure=entry,arrival=arrival,
            returned=True,stairCommands=2,elapsedTurns=game.turn-before,
            setup='Wizard position teleport onto an existing mapped downstairs, then ordinary > and <. No terrain altered.')
        game.finish(automatic=True);trace(run,game)
        (ROOT/'.artifacts/gehennom-engine-stairs.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS real down/up Gehennom stair roundtrip',flush=True)
    finally:cleanup(run,game)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('prepare','engine','unknown','stairs','native'):parser.add_argument('--'+flag,action='store_true')
    args=parser.parse_args()
    rows=prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results=[]
        for row in rows:
            results.append(engine(row));RESULTS.write_text(json.dumps(results,indent=2)+'\n')
    if args.unknown:unknown()
    if args.stairs:stairs(rows[0])
    if args.native:
        results=[]
        for row in rows:
            counts=row['metadata']['displayedTileCounts']
            row['metadata']['testTerrainTiles']=[int(t) for t in counts if int(t) in (1289,1314,1315,1316,1324)]
            for tileset in ('lantern-modern','soot-and-brass','lantern','soot-and-brass-classic'):
                results.append(mines.shapes.native(row,tileset))
                (ROOT/'.artifacts/gehennom-native-baseline.json').write_text(json.dumps(results,indent=2)+'\n')
        mines.shapes.gallery([r for r in results if r['tileset'] in ('lantern-modern','soot-and-brass')],
            ROOT/'.artifacts/gehennom-native-baseline.html','Gehennom filler')



if __name__=='__main__':main()
