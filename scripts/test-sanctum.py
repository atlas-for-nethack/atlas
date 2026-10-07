#!/usr/bin/env python3
"""Verify original Sanctum in copied item-53 invocation checkpoints.

Wizard protection inherited from item 53, positioning, item wishes and the final
wizard map are disclosed. No level reload, terrain replacement, actor deletion,
or direct discovery mutation is used. Lua geometry is read-only test evidence,
never a source for native review rendering or inspection.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('sanctum_invocation', ROOT/'scripts/test-invocation.py')
inv = importlib.util.module_from_spec(spec); spec.loader.exec_module(inv)
checks, tour = inv.checks, inv.tour
INDEX = ART/'sanctum-prepared.json'
STATES = ART/'sanctum-states.json'
RESULTS = ART/'sanctum-engine-results.json'
FIELDS = ('tile','glyph','char','color','pet','groundTile','material')
STATE_IDS = ['sanctum-arrival','sanctum-hidden-entrance','sanctum-open-entrance',
             'sanctum-interior','sanctum-mapped-overview']


def package():
    return dict(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'))


def sources():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    paths = ('dat/sanctum.lua','src/detect.c','src/lock.c','src/dig.c','src/pager.c','src/priest.c')
    hashes = {}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member = next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            assert (tour.DAT.parent/path).read_bytes() == upstream.extractfile(member).read(), path
            hashes[path] = tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive))


def prepare():
    assert not INDEX.exists(), 'Preserve prior Sanctum evidence before preparing another source'
    original = next(r for r in json.loads((ART/'invocation-states.json').read_text())
                    if r['metadata']['case']['id']=='invocation-transformed')
    run = Path(tempfile.mkdtemp(prefix='sanctum-source-', dir=ART))
    shutil.copytree(Path(original['run'])/'game',run/'game')
    assert tour.digest(run/'game/nhdat') == package()['dataSHA256'], 'Stale item-53 checkpoint data'
    metadata = copy.deepcopy(original['metadata'])
    metadata.update(case=dict(id='sanctum',label="Moloch's Sanctum",source=None,target='sanctum',branch='Gehennom'),
                    originalInvocationCheckpoint=original['run'], sourceEvidence=sources(), **package())
    metadata['setup'].append('Copied item-53 invocation-transformed checkpoint. Source remains checksummed and unopened. Inherited wizard protection and equipment are retained; ordinary > selects original Sanctum.')
    row = dict(run=str(run),metadata=metadata,originalGameSHA256=inv.files_hashes(run/'game'),
               originalInvocationSHA256=inv.files_hashes(Path(original['run'])/'game'))
    checks.write(run/'metadata.json',metadata); checks.write(INDEX,row)
    print('PREPARED original Sanctum from protected invocation checkpoint',run,flush=True)
    return row


def identity(game,directory):
    return tour.identity(game,directory)


def diagnostic(game,directory):
    return inv.diagnostics(game,directory)


def flags(cell):
    return dict(v.split('=',1) for v in cell['flags'].split('|') if '=' in v)


def cells_equal(left,right):
    assert set(left)==set(right), 'Restored displayed cell coverage differs'
    differences=[dict(position=p,before=left[p],after=right[p]) for p in left
                 if any(left[p].get(f)!=right[p].get(f) for f in FIELDS)]
    assert not differences, ('Restored displayed cells differ',differences[:5])


def snapshot(row,game,directory,label,mode='exploration'):
    """Native rows contain actual stable restored cells, never Lua geometry."""
    run = Path(tempfile.mkdtemp(prefix='sanctum-state-'+label+'-',dir=ART))
    position,turn = game.cursor,game.turn
    expected_identity=identity(game,directory)
    expected_memory=diagnostic(game,directory)
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    shutil.copytree(directory,run/'game')
    game=checks.open_game(directory); inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn)
    assert identity(game,directory)==expected_identity
    assert diagnostic(game,directory)==expected_memory, 'Terrain/light/glyph/trap memory changed'
    stable=copy.deepcopy(game.cells)
    game.finish(automatic=True)
    (run/'first-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    # Save the restored boundary to prove native will see these precise cells.
    shutil.rmtree(run/'game'); shutil.copytree(directory,run/'game')
    game=checks.open_game(directory); inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn)
    cells_equal(stable,game.cells)
    assert diagnostic(game,directory)==expected_memory
    metadata=copy.deepcopy(row['metadata'])
    metadata.update(case={**metadata['case'],'id':label,'label':label.replace('-',' ').title()},
        mode=mode,identity=expected_identity,arrival=list(position),turn=turn,
        checkpoint=str(run),displayedCells=copy.deepcopy(list(game.cells.values())),
        nativeBounds=[1,0,79,21] if mode=='inspection' else
                     [max(1,min(60,position[0]-9)),max(0,min(8,position[1]-6)),20,13],
        perception=checks.material(game.cells.values(),None),
        exactTerrainLightingGlyphTrapRestore=True,exactDisplayedCellRestore=True,
        originalSourceCheckpoint=row['run'],**package())
    checks.write(run/'metadata.json',metadata)
    checks.write(run/'terrain-memory.json',inv.serial(expected_memory))
    inv.lua(game,directory,'nh.debug_flags({hunger=false});')
    return game,dict(run=str(run),metadata=metadata)


def messages(game,offset):
    return [e['text'] for e in game.events[offset:] if e['type']=='message' and
            not e['text'].startswith(('INV_','ATLAS_CONTEXT:'))]


def direct(game,event,target):
    assert event.get('direction'),event
    delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
    index={(-1,0):0,(0,-1):2,(1,0):4,(0,1):6}[delta]
    game.send('key '+str(ord(event['directionKeys'][index])))
    return game.wait_input()


def near(game,directory,target,terrain,far_from=None):
    options=[(target[0]+dx,target[1]+dy) for dx,dy,_ in checks.STEPS
             if terrain.get((target[0]+dx,target[1]+dy),{}).get('type') in ('room','corridor')]
    if far_from:
        # The original exterior entrance approach is a fire-trap square.
        # Wizard teleport rejects trap destinations, so position one original
        # floor farther outside, then use ordinary protected movement onto it.
        target_approach=max(options,key=lambda p:sum((p[i]-far_from[i])**2 for i in (0,1)))
        delta=(target_approach[0]-target[0],target_approach[1]-target[1])
        stage=(target_approach[0]+delta[0],target_approach[1]+delta[1])
        assert terrain[stage]['type']=='room',stage
        inv.place(game,stage)
        move_without_attack(game,target_approach)
        return target_approach
    for p in options:
        try: inv.place(game,p)
        except AssertionError: continue
        return p
    raise AssertionError(('Original adjacent floor occupied',target,game.cursor))


def move_without_attack(game,target,limit=40):
    origin=game.cursor;start=game.turn;offset=len(game.events)
    for attempt in range(limit):
        if game.cursor==target:break
        delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
        assert max(abs(v) for v in delta)<=1,(game.cursor,target)
        key=next(k for x,y,k in inv.STEPS if (x,y)==delta)
        event=game.command('m');assert event.get('command'),event
        event=game.command(key)
        if event['kind']=='yn' and event.get('prompt','').startswith('Really step '):
            game.send('key 121');event=game.wait_input()
        inv.settle(game,event)
    else:raise AssertionError(('Original occupant blocked no-attack movement',target))
    return dict(command='m + direction',origin=list(origin),destination=list(target),
                turns=game.turn-start,messages=messages(game,offset))


def open_door(game,directory,target):
    records=[]
    for _ in range(25):
        before=game.turn;offset=len(game.events)
        inv.settle(game,direct(game,tour.named(game,'open'),target))
        record=dict(command='open',turns=game.turn-before,messages=messages(game,offset))
        records.append(record)
        state=diagnostic(game,directory)['terrain'][target]
        if flags(state).get('isopen')=='true': return records
        if flags(state).get('locked')=='true': return records
    raise AssertionError(('Original door did not open',target,records))


def ordinary_doors(game,directory,terrain):
    records=[]
    for locked in (False,True):
        choices=[p for p,c in terrain.items() if c['type']=='door' and
                 flags(c).get('locked')==str(locked).lower()]
        choices.sort(key=lambda p:sum((p[i]-game.cursor[i])**2 for i in (0,1)))
        for point in choices:
            current=diagnostic(game,directory)['terrain'][point]
            if not (flags(current).get('closed')=='true' or flags(current).get('locked')=='true'):continue
            try:approach=near(game,directory,point,terrain)
            except AssertionError:continue
            break
        else:raise AssertionError(('No original closed-door approach available',locked))
        before=game.turn;description=game.inspect(*point)
        assert game.turn==before and 'door' in description.lower(),description
        actions=open_door(game,directory,point)
        if locked:
            assert any('locked' in m.lower() for a in actions for m in a['messages']),actions
            inv.wish(game,'uncursed skeleton key')
            for _ in range(20):
                offset=len(game.events);event=game.command('a');assert event['kind']=='menu',event
                item=next(i for i in event['items'] if i.get('selectable') and 'key' in i['text'].lower())
                game.send('menu '+str(item['id']));event=game.wait_input()
                event=direct(game,event,point)
                assert event['kind']=='yn' and 'unlock' in event['prompt'].lower(),event
                game.send('key 121');inv.settle(game)
                actions.append(dict(command='apply skeleton key',messages=messages(game,offset)))
                if flags(diagnostic(game,directory)['terrain'][point]).get('locked')=='false':break
            else: raise AssertionError('Ordinary skeleton key never unlocked original door')
            actions.extend(open_door(game,directory,point))
        assert flags(diagnostic(game,directory)['terrain'][point]).get('isopen')=='true'
        records.append(dict(position=list(point),approach=list(approach),originalLocked=locked,
                            appearance=description,actions=actions))
    return records


def nondig(game,directory,terrain):
    point=next(p for p,c in terrain.items() if c['type'] in ('wall','vertical wall','horizontal wall') and
               any(terrain.get((p[0]+dx,p[1]+dy),{}).get('type')=='room' for dx,dy,_ in checks.STEPS))
    near(game,directory,point,terrain)
    inv.wish(game,'uncursed wand of digging (0:3)')
    event=tour.named(game,'wizidentify');assert event['kind']=='menu',event
    game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'));inv.settle(game)
    before=diagnostic(game,directory)['terrain'][point];offset=len(game.events)
    event=game.command('z');assert event['kind']=='menu',event
    item=next(i for i in event['items'] if 'wand of digging' in i['text'].lower())
    game.send('menu '+str(item['id']));event=game.wait_input()
    inv.settle(game,direct(game,event,point))
    after=diagnostic(game,directory)['terrain'][point]
    text=messages(game,offset)
    assert before['type']==after['type'] and any('wall glows then fades' in m.lower() for m in text),(point,before,after,text)
    return dict(position=list(point),command='zap wand of digging',terrainUnchanged=True,messages=text)


def restore_sight(game):
    records=[]
    for _ in range(4):
        if not (int(game.status.get(22,'0')) & 2):return records
        inv.wish(game,'blessed potion of full healing')
        event=tour.named(game,'wizidentify');assert event['kind']=='menu',event
        game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'));inv.settle(game)
        records.append(inv.select_item(game,'q','potion of full healing'))
    assert not (int(game.status.get(22,'0')) & 2),'Original spell repeatedly blinded hero after normal healing'
    return records


def protect(game):
    event=tour.named(game,'wizintrinsic');assert event['kind']=='menu',event
    wanted=('sleep resistance','free action','magic resistance','cold resistance',
            'poison resistance','light-induced blindness resistance','half physical damage')
    rows=[i for i in event['items'] if i['text'].split('[')[0].strip().lower() in wanted]
    assert len(rows)==len(wanted),rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));inv.settle(game)


def feature_checks(row):
    run=Path(tempfile.mkdtemp(prefix='sanctum-features-',dir=ART));directory=run/'game'
    shutil.copytree(Path(row['run'])/'game',directory);game=checks.open_game(directory)
    try:
        inv.settle(game);protect(game);inv.settle(game,game.command('>'))
        terrain=diagnostic(game,directory)['terrain']
        records=[dict(check='original ordinary closed and locked doors',
                      doors=ordinary_doors(game,directory,terrain),isolatedClone=str(run),
                      setup='Wizard position on original floor, uncursed key wish. Ordinary Open, Apply key, Open. No terrain/actor assignment.')]
        try:records.append(dict(check='nondiggable original wall',evidence=nondig(game,directory,terrain),
                                isolatedClone=str(run),setup='Wizard position on original floor, wand of digging wish and equipment-only wizard Identify. Ordinary Zap on true original wall, no actor removal.'))
        except StopIteration:records.append(dict(check='nondiggable original wall',unperformed='No ordinary wall type candidate'))
        game.finish(automatic=True)
        return records
    finally:checks.cleanup(run,game)


def engine(row):
    source=Path(row['run'])/'game'
    assert inv.files_hashes(source)==row['originalGameSHA256'], 'Sanctum source changed'
    original=Path(row['metadata']['originalInvocationCheckpoint'])/'game'
    assert inv.files_hashes(original)==row['originalInvocationSHA256'], 'Item-53 source changed'
    run=Path(tempfile.mkdtemp(prefix='sanctum-engine-',dir=ART));directory=run/'game'
    shutil.copytree(source,directory);game=checks.open_game(directory)
    states=[];records=[];result=dict(run=str(run),passed=False,stateIDs=[],sourceEvidence=sources(),**package())
    checks.write(RESULTS,result)
    def save(label,mode='exploration'):
        nonlocal game
        game,state=snapshot(row,game,directory,label,mode);states.append(state)
        checks.write(STATES,states)
        print('PASS exact real-engine checkpoint',label,flush=True)
    try:
        inv.settle(game);protect(game);origin=identity(game,directory);square=game.cursor
        inv.settle(game,game.command('>'));sanctum=identity(game,directory)
        assert sanctum['branch']=='Gehennom' and sanctum['level']==origin['level']+1
        terrain=diagnostic(game,directory)
        altar=next(p for p,c in terrain['terrain'].items() if c['type']=='altar')
        # Read-only diagnostics bound positioning to the actual enclosed temple
        # room; an original closed/secret door is not a flood edge. This never
        # supplies a hidden floor or geometry field to displayed cells.
        temple_rooms={altar};pending=[altar]
        while pending:
            p=pending.pop()
            for dx,dy,_ in checks.STEPS:
                q=(p[0]+dx,p[1]+dy)
                if q not in temple_rooms and terrain['terrain'].get(q,{}).get('type')=='room':
                    temple_rooms.add(q);pending.append(q)
        before=game.turn;unseen=game.inspect(*altar)
        assert 'unexplored' in unseen.lower() and 'altar' not in unseen.lower() and game.turn==before,unseen
        assert game.cells[altar]['tile'] in (1469,1470)
        assert 'groundTile' not in game.cells[altar] and 'material' not in game.cells[altar]
        row=copy.deepcopy(row)
        row['metadata']['setup'].append('Additional timed wizard sleep resistance, free action, magic resistance, cold resistance, poison resistance, light-induced blindness resistance and half physical damage bound protected inspection without changing actors. Ordinary > enters original generated Sanctum from item-53 ritual stair. Inherited invulnerability, stealth, invisibility and other wizard protection remain active. No map reveal before temple entry; original actors retained.')
        save('sanctum-arrival')
        stair=next(s for s in terrain['stairs'] if s['up'])
        if game.cursor!=tuple(stair['position']):inv.place(game,tuple(stair['position']))
        inv.settle(game,game.command('<'));assert identity(game,directory)==origin and game.cursor==square
        inv.settle(game,game.command('>'));assert identity(game,directory)==sanctum
        records.append(dict(check='ordinary invocation stair roundtrip',down='>',up='<',origin=origin,destination=sanctum))
        # Only read-only diagnostics choose existing test positions. No diagnostic
        # coordinates or terrain are forwarded to native cells or the renderer.
        temple= min((p for p,c in terrain['terrain'].items() if c['type']=='secret door'),
                    key=lambda p:sum((p[i]-altar[i])**2 for i in (0,1)))
        approach=near(game,directory,temple,terrain['terrain'],far_from=altar)
        before=game.turn;concealed=game.inspect(*temple);unknown_altar=game.inspect(*altar)
        assert 'wall' in concealed.lower() and 'secret' not in concealed.lower() and game.turn==before,concealed
        assert 'altar' not in unknown_altar.lower(),unknown_altar
        row['metadata']['setup'].append('Wizard teleport positioned hero on original exterior temple approach, selected by read-only diagnostics. Original concealed entrance remains a wall. This setup does not claim a normal route across the non-passwall divider.')
        save('sanctum-hidden-entrance')
        offset=len(game.events);start=game.turn
        for searches in range(100):
            if diagnostic(game,directory)['terrain'][temple]['type']=='door':break
            if game.cursor!=approach:inv.place(game,approach)
            event=game.command('m');assert event.get('command'),event
            inv.settle(game,game.command('s'))
        else:raise AssertionError('Original temple entrance never discovered by ordinary Search')
        search=dict(command='search',attempts=searches,turns=game.turn-start,messages=messages(game,offset))
        assert any('hidden door' in m.lower() for m in search['messages']),search
        if game.cursor!=approach:inv.place(game,approach)
        opening=open_door(game,directory,temple)
        assert flags(diagnostic(game,directory)['terrain'][temple]).get('isopen')=='true'
        row['metadata']['setup'].append('Ordinary Search discovered the original concealed temple entrance; ordinary Open changed it to an open door. No wizard reveal or direct door-state assignment.')
        save('sanctum-open-entrance')
        far=(2*temple[0]-approach[0],2*temple[1]-approach[1])
        passage_start=game.turn;passage_offset=len(game.events)
        try:
            passage=move_without_attack(game,temple,limit=4)
            onward=move_without_attack(game,far,limit=4)
            assert game.cursor==far
            ordinary_passage=True
        except AssertionError as error:
            passage=dict(command='m + direction',blocked=True,reason=str(error),
                         turns=game.turn-passage_start,messages=messages(game,passage_offset))
            onward=dict(unperformed='Original active occupants blocked threshold; no actor removed')
            ordinary_passage=False
            candidates=sorted(temple_rooms-{altar},key=lambda p:(game.cells.get(p,{}).get('tile') not in range(1291,1297),sum(abs(p[i]-game.cursor[i]) for i in (0,1))))
            for p in candidates:
                try:inv.place(game,p)
                except AssertionError:continue
                if game.cursor in temple_rooms:break
            else:raise AssertionError('No original interior position available')
            row['metadata']['setup'].append('Original priest-summoned insects blocked ordinary no-attack threshold movement. No actor removed. Disclosed wizard teleport positioned hero on original interior floor for protected temple presentation; successful ordinary temple entry is not claimed.')
        records.append(dict(check='temple concealment search opening and bounded passage',position=list(temple),approach=list(approach),
                            concealedInspection=concealed,search=search,opening=opening,passage=passage,onward=onward,ordinaryPassage=ordinary_passage))
        # Interior visibility is actual ordinary sight after entry. Occupants
        # may cover the altar: record their known support without inventing an
        # altar foreground. Reposition on original unoccupied interior floor
        # only if needed for a direct altar appearance.
        healing=restore_sight(game)
        if healing:
            records.append(dict(check='ordinary cure of priest spell blindness',actions=healing))
            row['metadata']['setup'].append('Original priest spell blindness was cured using ordinary Quaff of a wished, wizard-identified blessed potion of full healing. No direct condition assignment or actor change.')
        before=game.turn;known=game.inspect(*altar);assert game.turn==before;cell=copy.deepcopy(game.cells[altar])
        assert game.cells[altar]['tile'] not in (1469,1470), 'Interior altar still unexplored'
        occupants=[copy.deepcopy(c) for p,c in game.cells.items() if p!=game.cursor and
                   0<=c.get('glyph',-1)<800 and c.get('groundTile') in range(1291,1297)]
        assert len(occupants)>=2,'No original perceived crowd with known floor support'
        crowd_inspections=[]
        for c in occupants:
            before=game.turn;text=game.inspect(c['x'],c['y']);assert game.turn==before
            crowd_inspections.append(dict(position=[c['x'],c['y']],text=text))
        assert any('high priest' in c['text'].lower() for c in crowd_inspections),'Original high priest not perceived in crowd'
        if 'altar' in known.lower():assert 'high altar' in known.lower() and 'unaligned' in known.lower(),known
        row['metadata']['setup'].append('Interior altar/occupants are actual engine perceptions; original priest and monsters remain active. Interior wizard positioning uses existing floor and does not replace actors. Threshold movement success or blockage is recorded separately.')
        save('sanctum-interior')
        records.append(dict(check='altar perception and original crowd',unseenInspection=unseen,
            visibleInspection=known,visibleCell=cell,altarForegroundObserved='altar' in known.lower(),
            occupantsWithKnownSupport=occupants,crowdInspections=crowd_inspections,inspectionTurnFree=True))
        inv.settle(game,tour.named(game,'wizmap'))
        row['metadata']['setup'].append('Final inspection overview uses upstream wizard mapping, despite original nommap restriction. It reveals terrain/traps through engine mapping but leaves secret doors concealed and does not reveal unseen actors. It is development setup, not ordinary gameplay access.')
        before=game.turn;mapped_altar=game.inspect(*altar);assert game.turn==before
        assert 'unaligned high altar' in mapped_altar.lower(),mapped_altar
        records.append(dict(check='known mapped high altar',inspection=mapped_altar,
                            cell=copy.deepcopy(game.cells[altar]),wizardMapping=True,inspectionTurnFree=True))
        save('sanctum-mapped-overview','inspection')
        game.finish(automatic=True)
        records.extend(feature_checks(row))
        assert inv.files_hashes(source)==row['originalGameSHA256']
        assert inv.files_hashes(original)==row['originalInvocationSHA256']
        checkpoint_hashes={str(p):tour.digest(p) for state in states
                           for p in sorted((Path(state['run'])/'game').rglob('*')) if p.is_file()}
        result.update(passed=True,stateIDs=[s['metadata']['case']['id'] for s in states],
            states=[s['run'] for s in states],checkpointHashes=checkpoint_hashes,records=records,
            originalSaveUnchanged=True,originalInvocationUnchanged=True,exactStateRestores=True,
            identity=sanctum,altar=list(altar),templeEntrance=list(temple))
        assert result['stateIDs']==STATE_IDS
        checks.write(RESULTS,result)
        print('PASS Sanctum arrival/return, concealed temple Search/Open, bounded threshold evidence, altar privacy, original crowds, doors and exact save restores',flush=True)
        return result
    finally:checks.cleanup(run,game)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--engine',action='store_true')
    args=parser.parse_args();ART.mkdir(exist_ok=True)
    if args.prepare:prepare()
    if args.engine:engine(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine,'Choose --prepare or --engine'


if __name__=='__main__':main()
