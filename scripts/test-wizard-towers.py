#!/usr/bin/env python3
"""Verify original Wizard/fake tower maps, portal, ladders and perception.

All gameplay uses isolated copied saves. Diagnostics select original features
for disclosed wizard positioning, never for player rendering. No level reload,
terrain replacement, engine patch or identity-specific artwork is introduced.
"""
import argparse
from collections import Counter
import copy
import html
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('tower_checks',ROOT/'scripts/test-valley-level.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
tour=checks.tour
CASES=('wizard1','wizard2','wizard3','fakewiz1','fakewiz2')
INDEX=ART/'wizard-towers-prepared.json'
RESULTS=ART/'wizard-towers-engine-results.json'
STATES=ART/'wizard-towers-states.json'
FLOORS=set(range(1291,1297))
HIDDEN=(1469,1470)
NAMES={'lantern-modern':'Lantern Modern','soot-and-brass':'Soot & Brass Modern',
       'lantern':'Lantern Classic','soot-and-brass-classic':'Soot & Brass Classic'}


def sources():
    archive=tour.RES/'Source/nethack-500-src.tgz'
    paths=[*('dat/'+c+'.lua' for c in CASES),'dat/dungeon.lua','src/teleport.c','src/trap.c','include/display.h']
    hashes={}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member=next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            original=upstream.extractfile(member).read()
            assert (tour.DAT.parent/path).read_bytes()==original,path
            hashes[path]=tour.digest(tour.DAT.parent/path)
    def map_text(case):
        return re.search(r'map = \[\[(.*?)\]\]',(tour.DAT/(case+'.lua')).read_text(),re.S)[1]
    assert map_text('fakewiz1')==map_text('fakewiz2'),'Fake terrain templates differ'
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive),identicalFakeTerrainTemplates=True)


def privacy(cells,mode=None):
    result=checks.material(cells,None)
    if mode=='exploration':assert result['hiddenCells']>0
    return result


def settle(game,event=None):
    """Answer an original monster's controlled-teleport prompt in the test.

    Choosing the current square is an ordinary target response. It grants no
    resistance and changes no actor, trap or feature. Unexpected targeting is
    still an error; generic paging/restoration remains in the shared helper.
    """
    event=event or game.wait_input()
    for _ in range(80):
        if event.get('command'):return event
        prompt=event.get('prompt','')
        if event.get('targeting'):
            messages=[e.get('text','') for e in game.events[-30:] if e['type']=='message']
            assert any('Where do you want to be teleported?' in m for m in messages),event
            game.send(f'position {game.cursor[0]} {game.cursor[1]}')
        elif event['kind']=='line' and prompt.lower().startswith('call '):game.send('key 27')
        elif event['kind']=='line' and 'wish' in prompt.lower():game.send('line nothing')
        elif event['kind']=='yn' and prompt=='Override?':game.send('key 121')
        elif event['kind']=='yn' and ('die' in prompt.lower() or prompt=='Do you want to keep the save file?'):game.send('key 110')
        elif event['kind'] in ('key','text') or (event['kind']=='menu' and event.get('how')==0):game.send('key 32')
        else:raise AssertionError(('Unexpected tower prompt',event))
        event=game.wait_input()
    raise AssertionError('Controlled teleport did not finish')


def diagnostics(game,directory):
    offset=len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("TOWER_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.has_trap));
 if m.has_trap then local t=nh.gettrap(x-ox,y-oy);
  nh.pline("TOWER_TRAP:"..x..","..y..","..t.ttyp_name..","..tostring(t.tseen));
 end;
end end;
for _,s in ipairs(nh.stairways()) do
 nh.pline("TOWER_STAIR:"..s.x..","..s.y..","..tostring(s.up)..","..tostring(s.ladder)..","..s.dnum..","..s.dlevel);
end;''')
    lines=[e['text'] for e in game.events[offset:] if e.get('text','').startswith('TOWER_')]
    terrain={};traps=[];stairs=[]
    for line in lines:
        tag,rest=line.split(':',1);r=rest.split(',');point=tuple(map(int,r[:2]))
        if tag=='TOWER_TERRAIN':terrain[point]=dict(type=r[2],trap=r[3]=='true')
        elif tag=='TOWER_TRAP':traps.append(dict(position=point,type=r[2],seen=r[3]))
        elif tag=='TOWER_STAIR':stairs.append(dict(position=point,up=r[2]=='true',ladder=r[3]=='true',dnum=int(r[4]),dlevel=int(r[5])))
    assert len(terrain)==1659
    return terrain,traps,stairs


def clone(row,label):
    return checks.clone(row,'wizard-towers-'+label)


def hashes(rows):
    return {str(p):tour.digest(p) for row in rows for p in sorted((Path(row['run'])/'game').rglob('*')) if p.is_file()}


def prepare():
    assert not INDEX.exists(),'Preserve existing tower evidence; use another archive before fresh preparation'
    rows=[]
    for case in CASES:
        for mode in ('inspection','exploration'):
            row=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
                'prepare','--case',case,'--mode',mode],text=True))
            m=row['metadata'];assert m['case']['source'] is None
            assert m['identity']['branch']=='Gehennom' and m['destination'].lstrip('* ').startswith(case+':')
            m.update(sourceEvidence=sources(),worldSelected=True,shapeBounds=[1,0,79,21],
                     dataSHA256=tour.digest(tour.RES/'engine/nhdat'),designPreviewOnly=False)
            checks.write(Path(row['run'])/'metadata.json',m)
            rows.append(row);checks.write(INDEX,rows)
            print('PREPARED',case,mode,flush=True)


def restore(row):
    run,directory,game=clone(row,'restore')
    previous=[]
    try:
        settle(game)
        m=row['metadata']
        assert tour.identity(game,directory)==m['identity'] and list(game.cursor)==m['arrival']
        cells=copy.deepcopy(list(game.cells.values()))
        perception=privacy(cells,m['mode'])
        terrain,traps,stairs=diagnostics(game,directory)
        counts=dict(Counter(t['type'] for t in terrain.values()))
        assert len([s for s in stairs if not s['ladder']])==2,stairs
        case=m['case']['id'];ladder_count={'wizard1':1,'wizard2':2,'wizard3':1,'fakewiz1':0,'fakewiz2':0}[case]
        assert len([s for s in stairs if s['ladder']])==ladder_count
        portals=[t for t in traps if t['type']=='magic portal']
        assert len(portals)==(1 if case in ('wizard3','fakewiz1') else 0),(case,portals)
        if case!='wizard2':assert counts.get('moat',0)>=28,(case,counts)
        inspection=[];before=game.turn
        for name,predicate in [('wall',lambda c:1482<=c['tile']<=1492),
             ('water',lambda c:c.get('char')=='}'),('floor',lambda c:c['tile'] in FLOORS),
             ('ladder',lambda c:c['tile'] in (1299,1300)),('unknown',lambda c:c['tile']==1469)]:
            cell=next((c for c in cells if predicate(c)),None)
            if cell:
                text=game.inspect(cell['x'],cell['y']);assert text.strip()
                if name=='unknown':assert 'unexplored' in text.lower()
                inspection.append(dict(category=name,cell=cell,description=text))
                assert game.turn==before
        memory=checks.terrain_snapshot(game,directory)
        position,turn=game.cursor,game.turn
        game.finish(automatic=True);previous=list(game.events)
        game=checks.open_game(directory);settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert tour.identity(game,directory)==m['identity']
        assert checks.terrain_snapshot(game,directory)==memory
        privacy(game.cells.values(),m['mode'])
        restored=copy.deepcopy(list(game.cells.values()))
        game.finish(automatic=True)
        meta=copy.deepcopy(m)
        meta.update(checkpoint=str(run),displayedCells=restored,perception=perception,
            engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            originalSourceCheckpoint=row['run'],terrainCounts=counts,stairways=stairs,
            turnFreeInspection=inspection,exactTerrainLightingMemoryRestore=True,
            towerCase=case,diagnosticPortals=portals)
        # Camera data is derived from already displayed water, never a hidden portal.
        water=[c for c in restored if c.get('char')=='}']
        if m['mode']=='inspection' and water:
            x=sum(c['x'] for c in water)//len(water);y=sum(c['y'] for c in water)//len(water)
            meta['nativeBounds']=[max(1,min(60,x-10)),max(0,min(7,y-7)),20,14]
        else:
            x,y=position;meta['nativeBounds']=[max(1,min(64,x-7)),max(0,min(11,y-5)),16,10]
        checks.write(run/'metadata.json',meta)
        print('PASS original restore',case,m['mode'],flush=True)
        return dict(run=str(run),metadata=meta),dict(case=case,mode=m['mode'],run=str(run),
            sourceTerrain=counts,material=perception,turnFreeInspection=inspection,
            exactRestore=True,portalCount=len(portals),originalLadders=ladder_count)
    finally:checks.cleanup(run,game,previous)


def protected(game,directory):
    event=tour.named(game,'wizintrinsic')
    wanted=('invulnerable','stealthy','water walking')
    rows=[i for i in event['items'] if i['text'].strip().lower() in wanted]
    assert len(rows)==3,rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));settle(game)
    tour.lua(game,directory,'nh.debug_flags({hunger=false}); u.giveobj(obj.new("blessed +50 long sword")); u.giveobj(obj.new("blessed wand of digging (0:50)"));')
    event=tour.named(game,'wizidentify');assert event['kind']=='menu'
    game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'));settle(game)
    event=game.command('w');assert event['kind']=='menu'
    sword=next(i for i in event['items'] if '+50 long sword' in i['text'])
    game.send('menu '+str(sword['id']));settle(game)


def place(game,target):
    event=tour.named(game,'teleport')
    if event['kind']=='yn' and event.get('prompt')=='Override?':
        game.send('key 121');event=game.wait_input()
    if event['kind']=='menu' and event.get('how')==0:
        game.send('key 32');event=game.wait_input()
    assert event.get('targeting'),event
    game.send(f'position {target[0]} {target[1]}');settle(game)
    assert game.cursor==target,('Upstream placement refused or redirected',target,game.cursor)


def step(game,target,force=False):
    dx,dy=target[0]-game.cursor[0],target[1]-game.cursor[1]
    key=next(k for x,y,k in checks.STEPS if (x,y)==(dx,dy))
    before=game.turn;offset=len(game.events)
    for attempt in range(40):
        if force:game.command('m')
        event=game.command(key)
        while event['kind']=='yn' and (event.get('prompt','').startswith('Really step ')
            or event.get('prompt')=='Step into that vapor cloud?'):
            game.send('key 121');event=game.wait_input()
        settle(game,event)
        if game.cursor==target or any('activated a magic portal' in e.get('text','').lower() for e in game.events[offset:]):break
    else:raise AssertionError(('Original ordinary route blocked',target,game.cursor,
        [e['text'] for e in game.events[offset:] if e['type']=='message'][-8:]))
    return dict(command=key,target=target,turns=game.turn-before,attempts=attempt+1,
                ordinaryMovePrefix=force,
                messages=[e['text'] for e in game.events[offset:] if e['type']=='message'])


def snapshot(row,game,directory,label):
    run=Path(tempfile.mkdtemp(prefix='wizard-tower-state-',dir=ART))
    settle(game,tour.named(game,'wizmap'))
    game.send('key 18');settle(game)
    meta=copy.deepcopy(row['metadata'])
    meta.update(case={**meta['case'],'id':label,'label':label.replace('-',' ').title()},
        identity=tour.identity(game,directory),arrival=list(game.cursor),mode='inspection',
        checkpoint=str(run),
        nativeBounds=[max(1,min(64,game.cursor[0]-7)),max(0,min(11,game.cursor[1]-5)),16,10])
    memory=checks.terrain_snapshot(game,directory);turn=game.turn
    meta['setup'].append('State from the targeted portal/ladder route: timed wizard invulnerability, stealth and water walking; supplied identified +50 sword and digging wand, with upstream debug hunger disabled for the route. Original moat crossed, inner wall dug and entrance portal used by ordinary commands. The upper arrival additionally follows ordinary ladder travel. Mapping this state is disclosed; original occupants remain active. This is not an unprotected encounter test.')
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    shutil.copytree(directory,run/'game')
    # Reopen only the working clone. The separate native state remains untouched.
    game=checks.open_game(directory);settle(game)
    assert tour.identity(game,directory)==meta['identity']
    assert (list(game.cursor),game.turn)==(meta['arrival'],turn)
    assert checks.terrain_snapshot(game,directory)==memory
    meta['displayedCells']=copy.deepcopy(list(game.cells.values()))
    privacy(meta['displayedCells'])
    meta['exactRouteStateRestore']=True
    checks.write(run/'metadata.json',meta)
    tour.lua(game,directory,'nh.debug_flags({hunger=false});')
    return game,dict(run=str(run),metadata=meta)


def reach(game,directory,target):
    """Original occupants can prevent exact wizard placement on a feature.

    Preserve them and approach by ordinary movement/attacks instead. Never
    replace a monster, doorway, ladder or stair to make the test succeed.
    """
    if game.cursor==target:return
    terrain=diagnostics(game,directory)[0]
    approaches=[(target[0]+dx,target[1]+dy) for dx,dy,_ in checks.STEPS
        if terrain.get((target[0]+dx,target[1]+dy),{}).get('type') in ('room','corridor')]
    # Use the actual adjacent stair landing before wizard placement. Trying to
    # teleport onto an occupied feature can redirect the hero elsewhere.
    approaches.sort(key=lambda p:p!=game.cursor)
    for point in approaches:
        if game.cursor!=point:
            try:place(game,point)
            except AssertionError:continue
        if 'boulder' in game.inspect(*target).lower():
            event=game.command('z');assert event['kind']=='menu'
            wand=next(i for i in event['items'] if 'wand of digging' in i['text'])
            game.send('menu '+str(wand['id']));event=game.wait_input();assert event.get('direction')
            key=next(k for x,y,k in checks.STEPS if (x,y)==(target[0]-point[0],target[1]-point[1]))
            game.send('key '+str(ord(key)));settle(game)
        step(game,target)
        assert game.cursor==target
        return
    place(game,target)
    assert game.cursor==target


def secret_passage(game,directory):
    """Exercise a real concealed interior threshold, without a GUI reveal."""
    spec=importlib.util.spec_from_file_location('tower_doors',ROOT/'scripts/test-quest-outdoors.py')
    doors=importlib.util.module_from_spec(spec);spec.loader.exec_module(doors)
    terrain=diagnostics(game,directory)[0]
    for point,data in terrain.items():
        if data['type']!='secret door' or not 1482<=game.cells.get(point,{}).get('tile',-1)<=1492:
            continue
        for dx,dy,_ in checks.STEPS:
            approach=(point[0]+dx,point[1]+dy)
            if terrain.get(approach,{}).get('type')!='room':continue
            try:place(game,approach)
            except AssertionError:continue
            break
        else:continue
        break
    else:raise AssertionError('No original interior approach to a perceived secret wall')
    before=game.turn;text=game.inspect(*point)
    assert 'wall' in text.lower() and 'secret door' not in text.lower() and game.turn==before,text
    for searches in range(100):
        if doors.door_state(game,directory,point)['type']=='door':break
        assert game.cursor==approach
        game.command('m');settle(game,game.command('s'))
    else:raise AssertionError(('Original secret door not discovered',point))
    # An original actor/cloud can cover the foreground after discovery.
    # Independent engine state proves discovery without assuming a bare tile.
    for opens in range(30):
        event=tour.named(game,'open');assert event.get('direction')
        index={(-1,0):0,(0,-1):2,(1,0):4,(0,1):6}[(point[0]-game.cursor[0],point[1]-game.cursor[1])]
        game.send('key '+str(ord(event['directionKeys'][index])));settle(game)
        if doors.door_state(game,directory,point)['isopen']:break
    else:raise AssertionError(('Original discovered door did not open',point))
    movement=step(game,point)
    assert game.cursor==point
    far=(2*point[0]-approach[0],2*point[1]-approach[1])
    assert terrain[far]['type'] in ('room','corridor'),('No original passage beyond threshold',far)
    onward=step(game,far)
    assert game.cursor==far
    privacy(game.cells.values())
    return dict(check='original secret wall, search, open and passage',position=point,approach=approach,
                concealedDescription=text,searchCommands=searches,openAttempts=opens+1,
                movement=movement,onward=onward)


def route(row):
    run,directory,game=clone(row,'portal-ladders')
    previous=[];records=[];states=[]
    try:
        settle(game);protected(game,directory)
        origin=tour.identity(game,directory)
        terrain,traps,_=diagnostics(game,directory)
        portal=tuple(next(t['position'] for t in traps if t['type']=='magic portal'))
        # Both fake templates have the same centered 9x9 moat and inner wall.
        # Position on original exterior floor; cross actual water and dig the
        # original inner wall with ordinary commands rather than bypassing it.
        for sign in (1,-1):
            start=(portal[0]+4*sign,portal[1])
            try:place(game,start);break
            except AssertionError:continue
        else:raise AssertionError('Neither original exterior approach accepted')
        water=(portal[0]+3*sign,portal[1]);wall=(portal[0]+2*sign,portal[1])
        assert terrain[water]['type']=='moat' and 'wall' in terrain[wall]['type']
        records.append(dict(check='original water crossing',**step(game,water,force=True)))
        event=game.command('z');assert event['kind']=='menu'
        wand=next(i for i in event['items'] if 'wand of digging' in i['text'])
        game.send('menu '+str(wand['id']));event=game.wait_input();assert event.get('direction')
        key='h' if sign==1 else 'l'
        game.send('key '+str(ord(key)));settle(game)
        assert diagnostics(game,directory)[0][wall]['type'] in ('corridor','room')
        records.append(dict(check='ordinary digging of original inner wall',position=wall))
        records.append(step(game,wall));records.append(step(game,(portal[0]+sign,portal[1])))
        records.append(dict(check='ordinary portal entry',**step(game,portal)))
        lower=tour.identity(game,directory)
        assert lower['branch']=='Gehennom' and lower['depth']==checks.named_depth(game,'wizard3')
        assert lower!=origin
        privacy(game.cells.values())
        actual=diagnostics(game,directory)[1]
        back=tuple(next(t['position'] for t in actual if t['type']=='magic portal'))
        assert max(abs(game.cursor[i]-back[i]) for i in (0,1))<=1,('Portal arrival not at or beside reciprocal portal',game.cursor,back)
        records.append(dict(check='reciprocal tower portal arrival',portal=back,arrival=game.cursor))
        previous.extend(game.events);game,state=snapshot(row,game,directory,'wizard3-portal-arrival');states.append(state)
        # Inside the actual tower after ordinary entry, wizard positioning stays
        # within its restricted interior. Only < and > perform each transition.
        for name,up,destination in [('wizard3',True,'wizard2'),('wizard2',True,'wizard1'),
                                   ('wizard1',False,'wizard2'),('wizard2',False,'wizard3')]:
            identity=tour.identity(game,directory)
            assert identity['depth']==checks.named_depth(game,name)
            ladder=next(s for s in diagnostics(game,directory)[2] if s['ladder'] and s['up']==up)
            target=tuple(ladder['position']);reach(game,directory,target)
            settle(game,game.command('<' if up else '>'))
            after=tour.identity(game,directory)
            assert after['level']==ladder['dlevel'] and after['depth']==checks.named_depth(game,destination)
            reciprocal=next(s for s in diagnostics(game,directory)[2] if s['ladder'] and s['up']!=up)
            assert game.cursor==tuple(reciprocal['position'])
            privacy(game.cells.values())
            records.append(dict(check='ordinary ladder',origin=identity,destination=after,command='<' if up else '>',arrival=game.cursor))
            if destination=='wizard1':
                previous.extend(game.events);game,state=snapshot(row,game,directory,'wizard1-ladder-arrival');states.append(state)
        # Clear the real portal's temporary stun by ordinary waits, then return
        # through its reciprocal portal from an original adjacent room square.
        for _ in range(12):
            if not int(game.status.get(22,'0')) & (1<<22):break
            settle(game,game.command('.'))
        assert not int(game.status.get(22,'0')) & (1<<22)
        records.append(secret_passage(game,directory))
        terrain,traps,_=diagnostics(game,directory)
        back=tuple(next(t['position'] for t in traps if t['type']=='magic portal'))
        adjacent=next((back[0]+dx,back[1]+dy) for dx,dy,_ in checks.STEPS if terrain.get((back[0]+dx,back[1]+dy),{}).get('type')=='room')
        place(game,adjacent);records.append(dict(check='ordinary reciprocal portal',**step(game,back)))
        assert tour.identity(game,directory)==origin
        assert max(abs(game.cursor[i]-portal[i]) for i in (0,1))<=1
        records.append(dict(check='reciprocal entrance portal arrival',portal=portal,arrival=game.cursor))
        privacy(game.cells.values());game.finish(automatic=True)
        print('PASS water, digging, actual portal roundtrip and four internal ladder crossings',flush=True)
        return dict(run=str(run),records=records,passed=True),states
    finally:checks.cleanup(run,game,previous)


def exterior(row):
    run,directory,game=clone(row,'exterior-stairs')
    records=[]
    try:
        settle(game);protected(game,directory)
        origin=tour.identity(game,directory)
        for up in (True,False):
            stair=next(s for s in diagnostics(game,directory)[2] if not s['ladder'] and s['up']==up)
            point=tuple(stair['position']);reach(game,directory,point)
            settle(game,game.command('<' if up else '>'))
            outside=tour.identity(game,directory)
            assert outside['branch']=='Gehennom' and outside['level']==stair['dlevel']
            checks.material(game.cells.values(),[None,'gehennom','valley','asmodeus','juiblex','baalz'])
            arrival=game.cursor
            reciprocal=next(s for s in diagnostics(game,directory)[2]
                if not s['ladder'] and s['up']!=up and s['dlevel']==origin['level'])
            # An original occupant can displace the arrival from its stairs.
            # Approach the actual reciprocal feature instead of assuming < or
            # > works from that nearby landing square.
            reach(game,directory,tuple(reciprocal['position']))
            settle(game,game.command('>' if up else '<'))
            assert tour.identity(game,directory)==origin
            returned=game.cursor
            reach(game,directory,point)
            privacy(game.cells.values())
            records.append(dict(origin=origin,destination=outside,command='<' if up else '>',
                destinationArrival=arrival,reciprocalStairs=reciprocal['position'],
                returnedArrival=returned,returned=True))
        game.finish(automatic=True)
        print('PASS exterior stair roundtrips',row['metadata']['case']['id'],flush=True)
        return dict(run=str(run),crossings=records,passed=True)
    finally:checks.cleanup(run,game)


def native(rows):
    spec=importlib.util.spec_from_file_location('tower_native',ROOT/'scripts/test-room-shapes.py')
    capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
    results=[];scenes={}
    for original in rows:
        row=copy.deepcopy(original);m=row['metadata']
        assert m['engine']==tour.digest(tour.RES/'engine/nethack') and m['app']==tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')
        cells=m['displayedCells'];m['shapeBounds']=m['nativeBounds']
        x,y,w,h=m['shapeBounds'];visible=[c for c in cells if x<=c['x']<x+w and y<=c['y']<y+h]
        m['testTerrainTiles']=[next(c['tile'] for c in visible if c.get('char')=='.')]
        key=m['case']['id']+'-'+m['mode']
        scenes[key]=dict(label=m['case']['label']+' / '+m['mode'],width=79,height=21,
                         cells=[dict(c,x=c['x']-1) for c in cells],setup=m['setup'])
        editions=['lantern-modern','soot-and-brass']
        if m['mode']=='inspection' and m['case']['id'] in ('fakewiz1','wizard1'):editions.extend(['lantern','soot-and-brass-classic'])
        for tileset in editions:
            r=capture.native(row,tileset)
            observed=checks.displayed_cells(Path(r['run'])/'diagnostics.jsonl.engine.jsonl')
            r.update(mode=m['mode'],engine=m['engine'],app=m['app'],**privacy(observed,m['mode']))
            baseline={(c['x'],c['y']):c for c in cells};assert {(c['x'],c['y']) for c in observed}==set(baseline)
            for c in observed:
                assert all(c.get(f)==baseline[c['x'],c['y']].get(f) for f in ('tile','glyph','char','color','pet','groundTile','material'))
            results.append(r);checks.write(ART/'wizard-towers-native.json',results)
            print('PASS native',key,tileset,flush=True)
    checks.write(ART/'wizard-towers-review-manifest.json',dict(scenes=scenes))
    body=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Wizard towers review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d8bd87}</style>',
        '<h1>Wizard’s Tower and look-alike towers: shared existing artwork</h1>',
        '<p>Actual packaged-app captures. The debug labels identify test cases only. All five original maps use the same canonical Gehennom walls, stone floors, doors and water. No artwork identifies the portal-bearing entrance or the portal-less decoy. Mapped views do not expose unseen actors. Wizard protection, mapping, equipment and positioning are disclosed test setup.</p>']
    for r in results:
        label=html.escape(r['label']+' / '+r['mode']+' / '+NAMES[r['tileset']]);src=Path(r['screenshot']).relative_to(ART).as_posix()
        body.append('<h2>'+label+'</h2><a href="'+src+'"><img src="'+src+'" alt="'+label+'"></a>')
    body.append('</html>');(ART/'wizard-towers-review.html').write_text('\n'.join(body)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true');p.add_argument('--engine',action='store_true');p.add_argument('--native',action='store_true')
    args=p.parse_args();assert sum((args.prepare,args.engine,args.native))==1
    if args.prepare:prepare();return
    rows=json.loads(INDEX.read_text());assert len(rows)==10
    original=hashes(rows)
    try:
        if args.native:
            data=json.loads((ART/'wizard-towers-restored.json').read_text())+json.loads(STATES.read_text());native(data);return
        source=sources();integrated=[];results=[]
        for row in rows:
            restored,result=restore(row);integrated.append(restored);results.append(result)
        checks.write(ART/'wizard-towers-restored.json',integrated)
        exteriors=[exterior(r) for r in integrated if r['metadata']['mode']=='inspection']
        entrance=next(r for r in integrated if r['metadata']['case']['id']=='fakewiz1' and r['metadata']['mode']=='inspection')
        connections,states=route(entrance);checks.write(STATES,states)
        checks.write(RESULTS,dict(restores=results,exteriors=exteriors,connections=connections,
            source=source,originalSaveHashes=original,originalSavesPreserved=True,passed=True,
            engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')))
    finally:assert hashes(rows)==original,'Original source checkpoint changed'


if __name__=='__main__':main()
