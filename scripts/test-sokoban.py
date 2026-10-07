#!/usr/bin/env python3
"""Review all eight pinned Sokoban layouts, with ordinary pushes and checkpoint checks.

--prepare creates isolated inspection checkpoints; --engine plans only as far as
one boulder filling one pit/hole per layout. Rolling-boulder traps remain active
and may be crossed through ordinary movement. If
that bounded search cannot finish, it checks a reachable ordinary push and records
fillDeferred. --require-fill makes a deferred fill fail the run. This is not a
full puzzle solver or proof of puzzle completion. --native captures both Modern editions
from the untouched prepared saves, using the actual packaged application.
"""
import argparse
from collections import deque
import heapq
import importlib.util
import itertools
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
INDEX = ROOT/'.artifacts/sokoban-prepared.json'
DIRECTIONS = ((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'


def prepare():
    rows = []
    for case in tour.catalog():
        if case['group'] != 'Sokoban':
            continue
        row = json.loads(subprocess.check_output([sys.executable,
            str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case', case['id'],
            '--mode', 'inspection'], text=True))
        # Bounds come from rendered cells in the engine's real preparation trace,
        # so randomized layout mirroring does not require guessed offsets.
        cells = {}
        trace=Path(row['metadata']['checkpoint'])/'preparation.jsonl'
        for line in trace.read_text().splitlines():
            e = json.loads(line)
            if e['type'] == 'cell':
                cells[(e['x'],e['y'])] = e
            elif e['type'] == 'clear' and e.get('window') == 'map':
                cells.clear()
        points = [p for p,c in cells.items() if c.get('char',' ').strip()]
        xs,ys=zip(*points)
        row['metadata']['shapeBounds']=[min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1]
        rows.append(row)
        INDEX.write_text(json.dumps(rows,indent=2)+'\n')
        print('PREPARED',case['id'],row['metadata']['shapeBounds'],flush=True)


def world(game,directory):
    """Engine oracle is confined to a disposable test, never the player UI."""
    start=len(game.events)
    tour.lua(game,directory,'''
local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 if m.typ_name=="room" or m.typ_name=="corridor" or m.typ_name=="stairs" or m.typ_name=="ladder" then
  nh.pline("SOKO_FLOOR:"..x..","..y);
 end;
 if m.has_trap then local t=nh.gettrap(x-ox,y-oy);nh.pline("SOKO_TRAP:"..x..","..y..","..t.ttyp_name);end;
 local o=obj.at(x-ox,y-oy);
 while o and not o:totable().NO_OBJ do
  if o:totable().otyp_name=="boulder" then nh.pline("SOKO_BOULDER:"..x..","..y);end;
  o=o:next(true);
 end;
end end;
''')
    floor,boulders,traps=set(),set(),{}
    for e in game.events[start:]:
        s=e.get('text','')
        if not s.startswith('SOKO_'):continue
        tag,value=s.split(':',1);fields=value.split(',');p=tuple(map(int,fields[:2]))
        if tag=='SOKO_FLOOR':floor.add(p)
        elif tag=='SOKO_BOULDER':boulders.add(p)
        else:traps[p]=fields[2]
    assert floor and boulders and traps,(floor,boulders,traps)
    return floor,boulders,traps


def routes(start,floor,blocked):
    paths={start:[]};pending=deque([start])
    while pending:
        p=pending.popleft()
        for dx,dy,key in DIRECTIONS:
            q=(p[0]+dx,p[1]+dy)
            if q in floor and q not in blocked and q not in paths:
                paths[q]=paths[p]+[(key,q)];pending.append(q)
    return paths


def plan(start,floor,boulders,traps):
    """Bounded search for first fill, preserving all upstream puzzle geometry."""
    goals={p for p,t in traps.items() if t in ('pit','hole','spiked pit')}
    blockedTraps={p for p,t in traps.items() if t!='rolling boulder'}
    distance={p:0 for p in goals};reverse=deque(goals)
    while reverse:
        p=reverse.popleft()
        for dx,dy,_ in DIRECTIONS:
            b=(p[0]-dx,p[1]-dy);stand=(b[0]-dx,b[1]-dy)
            if b in floor and stand in floor and b not in distance:
                distance[b]=distance[p]+1;reverse.append(b)
    serial=itertools.count()
    pending=[(0,next(serial),start,frozenset(boulders),[],0)]
    visited=set()
    while pending and len(visited)<20000:
        _,_,hero,stones,actions,pushes=heapq.heappop(pending)
        paths=routes(hero,floor,stones|blockedTraps)
        signature=(min(paths),stones)
        if signature in visited:continue
        visited.add(signature)
        for b in sorted(stones):
            for dx,dy,key in DIRECTIONS:
                behind=(b[0]-dx,b[1]-dy);dest=(b[0]+dx,b[1]+dy)
                if behind not in paths or dest not in floor or dest in stones:continue
                steps=actions+paths[behind]+[(key,b)]
                if traps.get(dest) in ('pit','hole','spiked pit'):
                    return steps,dest,len(visited)
                if dest in blockedTraps or dest not in distance:continue
                moved=frozenset((stones-{b})|{dest})
                estimate=min(distance.get(p,9999) for p in moved)
                heapq.heappush(pending,(estimate*10+pushes+1,next(serial),b,moved,steps,pushes+1))
    raise AssertionError(('No first-fill route within search bound',len(visited)))


def engine(data,require_fill=False):
    run=Path(tempfile.mkdtemp(prefix='sokoban-engine-',dir=ROOT/'.artifacts'))
    directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
    result=dict(case=data['metadata']['case']['id'],run=str(run))
    try:
        tour.settle(game)
        assert tour.identity(game,directory)['branch']=='Sokoban'
        # Resetting a layout can leave the wizard in the far-side chamber.
        # Place the test at the displayed downstairs, its normal branch entry.
        entry=next((p for p,c in game.cells.items() if c.get('char')=='>'),None)
        if entry and game.cursor!=entry:
            event=tour.named(game,'teleport')
            if event.get('kind')=='menu' and event.get('how')==0:
                game.send('key 32');event=game.wait_input()
            assert event.get('targeting'),event
            game.send(f'position {entry[0]} {entry[1]}');tour.settle(game)
            assert game.cursor==entry
            result['inspectionPlacement']='Wizard placed at displayed downstairs before ordinary movement.'
        floor,boulders,traps=world(game,directory)
        try:
            actions,target,states=plan(game.cursor,floor,boulders,traps)
        except AssertionError as error:
            if require_fill:raise
            paths=routes(game.cursor,floor,boulders|traps.keys())
            candidates=[]
            for b in sorted(boulders):
                for dx,dy,key in DIRECTIONS:
                    behind=(b[0]-dx,b[1]-dy);dest=(b[0]+dx,b[1]+dy)
                    if behind in paths and dest in floor and dest not in boulders and dest not in traps:
                        candidates.append(paths[behind]+[(key,b)])
            assert candidates,('No reachable legal push',result['case'])
            actions=min(candidates,key=len);target=None;states=20000
            result['fillDeferred']=str(error)

        result.update(start=game.cursor,bouldersBefore=len(boulders),trapsBefore=len(traps),
            target=target,targetKind=traps.get(target),plannedMoves=len(actions),searchStates=states)
        begin=len(game.events);startTurn=game.turn
        # Ordinary repeated movement also resolves hostile occupants through
        # upstream combat. Stop/replan for a monster behind a real boulder.
        blocked=set();replans=0
        while actions:
            key,position=actions.pop(0)
            startMove=game.cursor;moveStart=len(game.events)
            for attempt in range(80):
                tour.settle(game,game.command(key))
                if game.cursor==position:break
                recent=' '.join(e.get('text','') for e in game.events[moveStart:]).lower()
                if 'monster behind the boulder' in recent:break
            if game.cursor!=position:
                messages=' '.join(e.get('text','') for e in game.events[moveStart:])
                if 'monster behind the boulder' in messages.lower() and replans<8:
                    dx,dy=position[0]-startMove[0],position[1]-startMove[1]
                    blocked.add((position[0]+dx,position[1]+dy));replans+=1
                    currentFloor,currentStones,currentTraps=world(game,directory)
                    try:
                        actions,target,states=plan(game.cursor,currentFloor-blocked,currentStones,currentTraps)
                        result.update(target=target,targetKind=currentTraps[target],monsterReplans=replans)
                    except AssertionError:
                        result['fillDeferred']='An upstream monster blocks the route after a successful push; the puzzle was not modified.'
                        actions=[];target=None
                else:
                    raise AssertionError(('Unexpected route obstruction',key,position,game.cursor,messages))
        if require_fill:assert target is not None,('Fill required',result)
        messages=[e.get('text','') for e in game.events[begin:] if e.get('type')=='message']
        floor2,boulders2,traps2=world(game,directory)
        assert boulders2 != boulders,('No boulder moved',result)
        if target is not None:
            assert target not in traps2,('Trap was not filled',target,traps2)
            assert len(boulders2)==len(boulders)-1,(boulders,boulders2)
            assert len(traps2)==len(traps)-1,(traps,traps2)
            result['filledCell']=game.cells.get(target)
            result['inspectionAfterFill']=game.inspect(*target)
            # The final push leaves the hero one cell behind the filled trap.
            # Enter that square normally, then step back to expose its artwork.
            hero=game.cursor;dx,dy=target[0]-hero[0],target[1]-hero[1]
            forward=next(k for x,y,k in DIRECTIONS if (x,y)==(dx,dy))
            backward=next(k for x,y,k in DIRECTIONS if (x,y)==(-dx,-dy))
            tour.settle(game,game.command(forward));assert game.cursor==target
            tour.settle(game,game.command(backward));assert game.cursor==hero
            result['walkedAcrossFilledCell']=True
            result['visibleCellAfterWalk']=game.cells.get(target)
            assert result['visibleCellAfterWalk']['tile']==1291,result

        result.update(realMoves=game.turn-startTurn,bouldersAfter=len(boulders2),trapsAfter=len(traps2),messages=messages,filled=target is not None,pushed=True)
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        _,restoredBoulders,restoredTraps=world(game,directory)
        assert restoredBoulders==boulders2 and restoredTraps==traps2
        game.finish(automatic=True)
        result.update(restored=True,position=position,turn=turn)
        print('PASS',result['case'],'filled '+str(result['targetKind']) if result['filled'] else 'pushed; fill deferred',result['realMoves'],'turns; saved/restored',flush=True)
        return result
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--require-fill',action='store_true')
    parser.add_argument('--native-filled',action='store_true')
    parser.add_argument('--case',action='append')
    args=parser.parse_args()
    if args.prepare:prepare()
    rows=json.loads(INDEX.read_text())
    rows=[r for r in rows if not args.case or r['metadata']['case']['id'] in args.case]
    if args.engine:
        results=[]
        for row in rows:
            results.append(engine(row,require_fill=args.require_fill))
            (ROOT/'.artifacts/sokoban-engine.json').write_text(json.dumps(results,indent=2)+'\n')
    if args.native_filled:
        filled={r['case']:r for r in json.loads((ROOT/'.artifacts/sokoban-engine.json').read_text())}
        captures=[]
        for row in rows:
            result=filled[row['metadata']['case']['id']]
            assert result['filled'] and result['restored'] and result['walkedAcrossFilledCell']
            after=dict(row,run=result['run'])
            for tileset in ('lantern-modern','soot-and-brass'):
                captures.append(shapes.native(after,tileset))
                (ROOT/'.artifacts/sokoban-filled-native.json').write_text(json.dumps(captures,indent=2)+'\n')
                print('CAPTURED FILLED',result['case'],tileset,flush=True)
        path=shapes.gallery(captures,ROOT/'.artifacts/sokoban-filled-review.html','Sokoban after pit/hole filling')
        text=path.read_text().replace(
            'Inspection fixtures use the upstream named generators with random contents and lighting.',
            'Restored saves after a real boulder fill on each upstream Sokoban layout. The hero entered the filled square and stepped back, leaving its floor visible.')
        for row in rows:
            result=filled[row['metadata']['case']['id']]
            label=row['metadata']['case']['label']
            text=text.replace('<h2>'+label+'</h2>', '<h2>'+label+'; filled '+result['targetKind']+' at '+str(result['target'][0])+', '+str(result['target'][1])+'</h2>')
        path.write_text(text)
        print(path)
    if args.native:
        results=[]
        for row in rows:
            for tileset in ('lantern-modern','soot-and-brass'):
                results.append(shapes.native(row,tileset))
                (ROOT/'.artifacts/sokoban-native.json').write_text(json.dumps(results,indent=2)+'\n')
                print('CAPTURED',row['metadata']['case']['id'],tileset,flush=True)
        path=shapes.gallery(results,ROOT/'.artifacts/sokoban-review.html','Sokoban')
        path.write_text(path.read_text().replace('Inspection fixtures use the upstream named generators with random contents and lighting.',
            'Inspection checkpoints load each pinned upstream Sokoban layout into its real branch. Wizard map reveal and protection aid inspection; puzzle geometry and rules are unchanged.'))
        print(path)


if __name__=='__main__':main()
