#!/usr/bin/env python3
"""Review upstream item 30 shapes and fills in disposable real-engine games.

Named generators and deferred handlers are unmodified. Rectangular fill rooms,
stairs and arrival positions are declared test framing. No owner saves are used.
Native captures are coordinated separately so app launches cannot overlap.
"""
import argparse
import collections
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ice', ROOT/'scripts/test-ice-rooms.py')
ice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ice)
tour = ice.tour
OPTIONS = ice.OPTIONS
INDEX = ROOT/'.artifacts/mixed-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/mixed-rooms-engine.json'
DIRECTIONS = [(-1,0,'h'), (1,0,'l'), (0,-1,'k'), (0,1,'j')]


def restored_display(data):
    """Read checkpoint perception in a disposable copy, without a map reveal."""
    run=Path(tempfile.mkdtemp(prefix='mixed-rooms-display-',dir=ROOT/'.artifacts'))
    directory=run/'game'; shutil.copytree(Path(data['run'])/'game',directory)
    config=directory/'test.nethackrc'; config.write_text('')
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    game=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS,config=config)
    try:
        tour.settle(game)
        cells=list(game.cells.values())
        game.finish(automatic=True)
        return cells
    finally:
        (run/'restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def update_display(data):
    metadata=data['metadata']
    metadata['displayedCells']=restored_display(data)
    bx,by,bw,bh=metadata['shapeBounds']
    present={c['tile'] for c in metadata['displayedCells']
             if bx<=c['x']<bx+bw and by<=c['y']<by+bh}
    # Require a stable terrain glyph to synchronize native atlas/map loading.
    # Occupants, revealed traps and floor lighting can change glyphs on restore.
    preferred=[1314] if metadata['case'].get('shape')=='Water-surrounded vault' else [1291,1292]
    metadata['testTerrainTiles']=next(([tile] for tile in preferred if tile in present),[])
    (Path(data['run'])/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')


def cases():
    rows = []
    for shape in ['Water-surrounded vault', 'Twin businesses']:
        for mode in ['inspection', 'exploration']:
            rows.append(dict(id='mixed-'+shape.lower().replace(' ','-')+'-'+mode,
                group='Mixed themed rooms', label=shape+' / '+mode,
                target=None, source=None, branch='The Dungeons of Doom',
                shape=shape, mode=mode))
    for fill in ['Temple of the gods', 'Teleportation hub', 'Boulder room']:
        for variant, lit, mixed in [('lit',True,False), ('unlit',False,False), ('mixed',True,True)]:
            rows.append(dict(id='mixed-'+fill.lower().replace(' ','-')+'-'+variant,
                group='Mixed themed rooms', label=fill+' / '+variant,
                target=None, source=None, branch='The Dungeons of Doom',
                fill=fill, lit=lit, mixed=mixed,
                mode='inspection' if lit else 'exploration'))
    return rows


def prepare(selected=None):
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    rows = []
    for original in cases():
        if selected and original['id'] not in selected:
            continue
        case = dict(original)
        run = Path(tempfile.mkdtemp(prefix='mixed-rooms-', dir=ROOT/'.artifacts'))
        hub = case.get('fill') == 'Teleportation hub'
        if hub:
            # Deferred upstream trap handlers expect the normal level origin.
            source = run/'hub.lua'
            source.write_text((tour.DAT/'themerms.lua').read_text()+'''
des.level_init({style="solidfill",fg=" "}); des.level_flags("noflip");
des.map({x=1,y=0,map=[[
----------------
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
----------------]]});
des.region({region={1,1,14,8},type="themed",lit='''+str(int(case['lit']))+
                ',filled='+str(int(case['mixed']))+''',contents=function(rm)
 themeroom_fills[assert(lookup_by_name("Teleportation hub",true))].contents(rm);
end});
des.teleport_region({region={2,2,2,2}});
des.stair("up",1,1); des.stair("down",14,8);
post_level_generate();
''')
            case.pop('fill')
            case['source'] = str(source)
        metadata = tour.prepare(case, case['mode'], run)
        metadata['case'] = original
        if hub:
            metadata['shapeBounds'] = [1,0,16,10]
            metadata['sources']['themerms.lua'] = tour.digest(tour.DAT/'themerms.lua')
            metadata['setup'].append('Declared 14 by 8 room at whole-level origin (1,0). Untouched upstream Teleportation hub fill and post_level_generate create traps and original random destinations. No synthetic trap substitutes.')
        metadata['mixedRoomsRecipe'] = tour.digest(Path(__file__))
        metadata['setup'].append('Inspection uses wizard map memory; exploration retains ordinary undiscovered information. Artwork review and hazard acceptance remain separate.')
        (run/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        row=dict(run=str(run),metadata=metadata)
        update_display(row)
        rows.append(row)
        INDEX.write_text(json.dumps(rows,indent=2)+'\n')
        print('PREPARED',original['label'],run,flush=True)
    return rows


def oracle(game, directory, bounds):
    x,y,w,h = bounds
    start = len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y='''+str(y)+','+str(y+h-1)+' do for x='+str(x)+','+str(x+w-1)+''' do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("MIXED_CELL:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..m.roomno..","..tostring(m.flags.closed)..","..tostring(m.flags.locked));
 if m.has_trap then local t=nh.gettrap(x-ox,y-oy);
  nh.pline("MIXED_TRAP:"..x..","..y..","..t.ttyp_name..","..tostring(t.tseen)); end;
 local o=obj.at(x-ox,y-oy);
 while o and not o:totable().NO_OBJ do
  local v=o:totable();
  nh.pline("MIXED_OBJECT:"..x..","..y..","..v.otyp_name);
  if v.otyp_name=="chest" then
   local c=o:contents();
   while c and not c:totable().NO_OBJ do
    local cv=c:totable();
    nh.pline("MIXED_CONTAINER:"..x..","..y..","..cv.otyp_name..","..cv.oclass);
    c=c:next(true);
   end;
  end;
  o=o:next(true);
 end;
end end;''')
    messages = [e.get('text','') for e in game.events[start:]]
    return {kind:[s.split(':',1)[1].split(',') for s in messages if s.startswith('MIXED_'+kind.upper()+':')]
            for kind in ['cell','trap','object','container']}


def place(game, target):
    event = tour.named(game,'teleport')
    if event['kind']=='menu' and event.get('how')==0:
        game.send('key 32'); event=game.wait_input()
    assert event.get('targeting'),event
    game.send('position '+str(target[0])+' '+str(target[1]))
    tour.settle(game)


def route(game, targets, bounds, forbidden=()):
    """Find a route using perceived plain floor only, with test hazard exclusions."""
    x,y,w,h=bounds
    targets=set(targets); forbidden=set(forbidden)
    todo=collections.deque([(game.cursor,[])])
    seen={game.cursor}
    while todo:
        p,path=todo.popleft()
        if p in targets:
            return path
        for dx,dy,key in DIRECTIONS:
            q=(p[0]+dx,p[1]+dy)
            if q in seen or q in forbidden or not (x<=q[0]<x+w and y<=q[1]<y+h):
                continue
            if game.cells.get(q,{}).get('char') not in '.<>':
                continue
            seen.add(q); todo.append((q,path+[(key,q)]))
    return None


def walk(game, path):
    before=game.turn
    for key,target in path:
        tour.settle(game,game.command(key))
        assert game.cursor==target,(key,target,game.cursor)
    if path:
        # Fast Valkyries can take consecutive actions in one displayed turn.
        assert game.turn>=before,'Walking moved time backwards'


def push_boulder(game,directory,bounds,values,result):
    traps={(int(t[0]),int(t[1])) for t in values['trap']}
    for x,y,name in values['object']:
        if name!='boulder' or game.cells.get((int(x),int(y)),{}).get('char') not in {'0','`'}:
            continue
        target=(int(x),int(y))
        for dx,dy,key in DIRECTIONS:
            behind=(target[0]-dx,target[1]-dy)
            ahead=(target[0]+dx,target[1]+dy)
            if any(p in traps or game.cells.get(p,{}).get('char')!='.' for p in [behind,ahead]):
                continue
            path=route(game,[behind],bounds,traps)
            if path is None:
                place(game,behind)
                # Active upstream occupants can move onto mapped floor before
                # the framing action. Never remove them to force this check.
                if game.cursor!=behind:
                    continue
                result['boulderWizardFraming']=list(behind)
            else:
                walk(game,path)
            start=len(game.events)
            tour.settle(game,game.command(key))
            if game.cursor!=target:
                messages=[e.get('text','') for e in game.events[start:] if e['type']=='message']
                assert any('boulder' in m.lower() for m in messages),messages
                result['originalBoulderCollision']=dict(position=list(target),messages=messages)
                return
            current=oracle(game,directory,bounds)
            assert any((int(o[0]),int(o[1]))==ahead and o[2]=='boulder' for o in current['object']),current['object']
            result['pushedOriginalBoulder']=dict(original=list(target),destination=list(ahead))
            return
    result['boulderPushLimit']='No generated boulder with two perceived clear, trap-free squares.'


def shop_door(game,bounds,values,result):
    for cell in values['cell']:
        if cell[2]!='door' or cell[6]=='true':
            continue
        target=(int(cell[0]),int(cell[1]))
        if game.cells.get(target,{}).get('char') not in '+-|':
            continue
        for dx,dy,key in DIRECTIONS:
            p=(target[0]-dx,target[1]-dy)
            if game.cells.get(p,{}).get('char')!='.':
                continue
            path=route(game,[p],bounds)
            if path is None:
                place(game,p); assert game.cursor==p
                result['shopDoorWizardFraming']=list(p)
            else:
                walk(game,path)
            for _ in range(20):
                event=tour.named(game,'open')
                assert event.get('direction'),event
                game.send('key '+str(ord(key))); tour.settle(game)
                description=game.inspect(*target)
                if 'open door' in description.lower():
                    break
            assert 'open door' in description.lower(),description
            result['openedOriginalShopEntrance']=dict(position=list(target),description=description)
            return
    result['shopDoorLimit']='No accessible closed, unlocked generated entrance in this sample.'


def fill_checks(game,directory,data,values,result):
    case=data['metadata']['case']; name=case['fill']; bounds=data['metadata']['shapeBounds']
    cells=values['cell']; traps=values['trap']
    assert all(c[3]==str(case['lit']).lower() for c in cells
               if bounds[0]<int(c[0])<bounds[0]+bounds[2]-1 and bounds[1]<int(c[1])<bounds[1]+bounds[3]-1),cells
    result['lightingVerified']=True
    if name=='Temple of the gods':
        altars=[(int(c[0]),int(c[1])) for c in cells if c[2]=='altar']
        # Stairs can legally replace a generated feature in this test framing.
        assert 1<=len(altars)<=3,altars
        result['altarCount']=len(altars)
        result['altarDescriptions']=[dict(position=list(p),description=game.inspect(*p)) for p in altars]
        if case['mode']=='inspection':
            assert all('altar' in row['description'].lower() for row in result['altarDescriptions'])
            result['perceivedAlignments']=sorted({a for row in result['altarDescriptions']
                for a in ['lawful','neutral','chaotic'] if a in row['description'].lower()})
        else:
            for row in result['altarDescriptions']:
                if game.cells.get(tuple(row['position']),{}).get('char',' ')==' ':
                    assert 'altar' not in row['description'].lower(),row
        result['interactionLimit']='Altar perception and ordinary floor approach checked; sacrifice, prayer and conversion are not exercised.'
    elif name=='Boulder room':
        boulders=[o for o in values['object'] if o[2]=='boulder']
        rolling=[t for t in traps if t[2]=='rolling boulder']
        assert boulders and rolling,(boulders,rolling)
        result.update(boulderCount=len(boulders),rollingBoulderTrapCount=len(rolling))
        if case['mode']=='inspection':
            push_boulder(game,directory,bounds,values,result)
        result['interactionLimit']='Generated boulders, hidden rolling traps and safe floor movement checked. A boulder push is attempted when perceived safe space permits; rolling trap damage is not exercised.'
    else:
        tele=[t for t in traps if t[2]=='teleport']
        assert 2<=len(tele)<=4 and all(t[3]=='true' for t in tele),tele
        result['upstreamSeenTeleportTraps']=tele
        if case['mode']=='inspection':
            for t in tele:
                assert 'teleportation trap' in game.inspect(int(t[0]),int(t[1])).lower()
            for t in tele:
                target=(int(t[0]),int(t[1]))
                adjacent=[(target[0]+dx,target[1]+dy) for dx,dy,_ in DIRECTIONS]
                path=route(game,adjacent,bounds,[(int(v[0]),int(v[1])) for v in traps])
                if path is None:
                    continue
                walk(game,path)
                p=game.cursor
                key=next(k for dx,dy,k in DIRECTIONS if (p[0]+dx,p[1]+dy)==target)
                before=game.turn; start=len(game.events)
                event=game.command(key)
                if event['kind']=='yn' and 'trap' in event.get('prompt','').lower():
                    game.send('key 121'); event=game.wait_input()
                tour.settle(game,event)
                assert game.cursor!=target and game.turn>=before,(target,game.cursor)
                assert any('materialize in a different location' in e.get('text','').lower() for e in game.events[start:]),game.events[start:]
                result['triggeredTeleport']=dict(trap=list(target),arrival=list(game.cursor),turnBefore=before,turnAfter=game.turn)
                break
            assert 'triggeredTeleport' in result,'No reachable generated teleport trap'
        result['interactionLimit']='Known generated teleport trap activation checked in lit samples; random destination policy remains upstream. Unlit sample checks perception without forcing discovery.'


def check(data):
    case=data['metadata']['case']; bounds=data['metadata']['shapeBounds']
    assert data['metadata']['engine']==tour.digest(tour.RES/'engine/nethack'),'Packaged engine changed; prepare fresh checkpoints'
    assert data['metadata']['app']==tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),'Packaged app changed; prepare fresh checkpoints'
    for source,expected in data['metadata']['sources'].items():
        assert expected==tour.digest(tour.DAT/source),('Source changed; prepare fresh checkpoints',source)
    run=Path(tempfile.mkdtemp(prefix='mixed-rooms-check-',dir=ROOT/'.artifacts'))
    directory=run/'game'; shutil.copytree(Path(data['run'])/'game',directory)
    config=directory/'test.nethackrc'; config.write_text('')
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    module=tour.load_game_module()
    game=module.Game(directory,name='wizard',options=OPTIONS,config=config)
    result=dict(case=case['id'],run=str(run),isolatedConfiguration=True,
                checkRecipe=tour.digest(Path(__file__)),sourceDigestsVerified=True)
    events=[]
    try:
        tour.settle(game)
        assert game.cursor==tuple(data['metadata']['arrival'])
        before=game.turn
        values=oracle(game,directory,bounds)
        assert game.turn==before,'Read-only diagnostic advanced time'
        result['terrainCounts']={kind:sum(c[2]==kind for c in values['cell'])
            for kind in sorted({c[2] for c in values['cell']})}
        result['inspection']=[dict(position=list(game.cursor),description=game.inspect(*game.cursor))]
        featureCells=sorted(values['cell'],key=lambda c:c[2] not in ['altar','moat'])
        unknown=next(((int(c[0]),int(c[1])) for c in featureCells
            if c[2]!='stone' and game.cells.get((int(c[0]),int(c[1])),{}).get('char',' ')==' '),None)
        if case['mode']=='exploration' and unknown:
            description=game.inspect(*unknown)
            assert not any(word in description.lower() for word in ['chest','altar','teleportation trap','boulder','pool']),description
            result['unknownInspection']=dict(position=list(unknown),description=description)
        hidden=[]
        for x,y,kind,seen in values['trap']:
            if seen!='true' or game.cells.get((int(x),int(y)),{}).get('char',' ')==' ':
                description=game.inspect(int(x),int(y))
                assert kind not in description.lower(),(kind,description)
                hidden.append(dict(position=[int(x),int(y)],description=description))
        result['hiddenTrapChecks']=hidden
        if case.get('fill'):
            fill_checks(game,directory,data,values,result)
        elif case['shape']=='Water-surrounded vault':
            x,y,w,h=bounds
            assert (w,h)==(6,6),bounds
            border=[c for c in values['cell'] if int(c[0]) in [x,x+5] or int(c[1]) in [y,y+5]]
            assert all(c[2]=='moat' for c in border),border
            assert sum(o[2]=='chest' for o in values['object'])==4,values['object']
            escapes={('teleportation','?'),('teleportation','='),('teleportation','/'),('digging','/')}
            assert any((c[2],c[3]) in escapes for c in values['container']),values['container']
            result['originalWaterPerimeterAndEscapeItemVerified']=True
            result['containerInformationIsDiagnosticOnly']=True
            if case['mode']=='exploration':
                result['hiddenChestDescriptions']=[game.inspect(int(o[0]),int(o[1]))
                    for o in values['object'] if o[2]=='chest']
                assert all('chest' not in d.lower() for d in result['hiddenChestDescriptions'])
            assert not (x+2<=game.cursor[0]<=x+3 and y+2<=game.cursor[1]<=y+3),game.cursor
            result['levelArrivalOutsideVaultInterior']=list(game.cursor)
            result['interactionLimit']='Original moat perimeter, chests, guaranteed escape item and level arrival outside excluded interior checked. This generation exclusion is not a general ban on chosen horizontal teleport. Water entry, digging escape and chest opening are not exercised.'
        else:
            doors=[c for c in values['cell'] if c[2]=='door']
            assert len(doors)>=2,doors
            result['generatedDoorCount']=len(doors)
            result['shopFloorRoomNumbers']=sorted({int(c[4]) for c in values['cell'] if c[2]=='room'})
            assert len(result['shopFloorRoomNumbers'])>=3,result['shopFloorRoomNumbers']
            if case['mode']=='inspection':
                shop_door(game,bounds,values,result)
            result['interactionLimit']='Two original stocked shop subrooms, randomized entrance doors, shared aisles and ordinary floor movement checked. Closed unlocked entrances are opened when available. Purchases, theft and locked-door entry are not exercised.'
        assert game.turn>=before
        inspectionTurn=game.turn
        game.inspect(*game.cursor)
        assert game.turn==inspectionTurn
        result['turnFreeInspection']=True
        if case.get('shape')!='Water-surrounded vault':
            x,y,w,h=bounds
            if case['mode']=='inspection' and not (x<=game.cursor[0]<x+w and y<=game.cursor[1]<y+h):
                target=next(p for p,c in game.cells.items() if x<=p[0]<x+w and y<=p[1]<y+h and c.get('char')=='.')
                place(game,target); assert game.cursor==target
                result['wizardFraming']=list(target)
            candidates=[(game.cursor[0]+dx,game.cursor[1]+dy) for dx,dy,_ in DIRECTIONS]
            path=route(game,candidates,bounds,[(int(t[0]),int(t[1])) for t in values['trap']])
            if path:
                walk(game,path); result['ordinaryFloorMovement']=dict(steps=len(path),arrival=list(game.cursor))
            else:
                result['movementLimit']='No adjacent perceived hazard-free floor at current arrival.'
        position,turn=game.cursor,game.turn
        game.finish(automatic=True); events.extend(game.events)
        game=module.Game(directory,name='wizard',options=OPTIONS,config=config)
        tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        game.finish(automatic=True)
        result.update(restored=True,finalPosition=list(position),finalTurn=turn)
        print('PASS',case['label'],result['terrainCounts'],flush=True)
        return result
    finally:
        events.extend(game.events)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--case',action='append',help='Limit to case IDs; preparing writes only this selection.')
    args=parser.parse_args()
    rows=prepare(args.case) if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results=[]
        for row in rows:
            if args.case and row['metadata']['case']['id'] not in args.case:
                continue
            results.append(check(row))
            RESULTS.write_text(json.dumps(results,indent=2)+'\n')
    print('Index:',INDEX)


if __name__=='__main__':
    main()
