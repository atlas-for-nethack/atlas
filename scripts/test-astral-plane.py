#!/usr/bin/env python3
"""Bounded original Astral Plane checks and exact restored native states.

Original temples, shuffled high altars, doors and active crowds remain engine-owned.
Wizard Endgame entry, protection and positioning are disclosed setup.
Mapping is reserved for the final overview; no ascension action is performed.
No map reload, terrain/actor replacement or direct discovery mutation is used.
"""
import argparse
from collections import Counter, deque
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('astral_invocation',ROOT/'scripts/test-invocation.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)
checks,tour=inv.checks,inv.tour
spec=importlib.util.spec_from_file_location('astral_sanctum',ROOT/'scripts/test-sanctum.py')
sanctum=importlib.util.module_from_spec(spec);spec.loader.exec_module(sanctum)
INDEX=ART/'astral-plane-prepared.json'
STATES=ART/'astral-plane-states.json'
RESULTS=ART/'astral-plane-engine-results.json'
FIELDS=('tile','glyph','char','color','pet','groundTile','material')
CARDINAL=((-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j'))
IDS=['astral-plane-arrival','astral-plane-west-temple','astral-plane-center-temple',
     'astral-plane-east-temple','astral-plane-overview']


def write(path,value):checks.write(path,value)


def package():
    return dict(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'))


def expected_material():
    return 'astral'


def source_evidence():
    archive=tour.RES/'Source/nethack-500-src.tgz'
    paths=('dat/astral.lua','dat/dungeon.lua','src/priest.c','src/pager.c','src/do_name.c','src/do.c','include/display.h')
    hashes={}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member=next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            assert (tour.DAT.parent/path).read_bytes()==upstream.extractfile(member).read(),path
            hashes[path]=tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive))


def prepare():
    assert not INDEX.exists(),'Preserve prior Astral source evidence before preparing another world'
    run=Path(tempfile.mkdtemp(prefix='astral-plane-source-',dir=ART))
    case=next(c for c in tour.catalog() if c['id']=='astral')
    metadata=tour.prepare(case,'exploration',run)
    assert metadata['case']['source'] is None
    assert metadata['identity']['branch']=='The Elemental Planes'
    metadata.update(sourceEvidence=source_evidence(),worldSelected=True,designPreviewOnly=False,
                    astralPlaneRecipeSHA256=tour.digest(Path(__file__)),**package())
    metadata['setup'].append('Actual original generated Astral plane, selected by upstream wizard Endgame travel. No source reload or wizard mapping. The engine supplies the real Amulet for wizard Endgame access; this is not an ordinary campaign arrival.')
    write(run/'metadata.json',metadata)
    row=dict(run=str(run),metadata=metadata,originalGameSHA256=inv.files_hashes(run/'game'))
    write(INDEX,row);print('PREPARED original Astral plane',run,flush=True)
    return row


def clone(row,label):
    run=Path(tempfile.mkdtemp(prefix='astral-plane-'+label+'-',dir=ART));directory=run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat')==package()['dataSHA256'],'Stale source data'
    game=checks.open_game(directory);inv.settle(game)
    return run,directory,game


def messages(game,offset):
    return [e['text'] for e in game.events[offset:] if e['type']=='message' and
            not e['text'].startswith(('INV_','ATLAS_CONTEXT:'))]


def protect(game):
    event=tour.named(game,'levelchange');assert event['kind']=='line',event
    game.send('line 30');inv.settle(game)
    event=tour.named(game,'wizintrinsic');assert event['kind']=='menu',event
    wanted=('fire resistance','cold resistance','shock resistance','sleep resistance','free action','sickness resistance',
            'magic resistance','poison resistance','magical breathing','hp regeneration',
            'invulnerable','invisible','stealthy','very fast','see invisible',
            'half physical damage','half spell damage')
    rows=[i for i in event['items'] if i['text'].split('[')[0].strip().lower() in wanted]
    assert len(rows)==len(wanted),rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));inv.settle(game)


def perception(game):
    return checks.material(game.cells.values(),expected_material())


def snapshot(row,game,directory,label,mode='exploration'):
    """Only stable actual engine-displayed cells form native metadata."""
    run=Path(tempfile.mkdtemp(prefix='astral-plane-state-'+label+'-',dir=ART))
    position,turn=game.cursor,game.turn
    identity=tour.identity(game,directory);memory=inv.diagnostics(game,directory)
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    game=checks.open_game(directory);inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn)
    assert tour.identity(game,directory)==identity
    restored_memory=inv.diagnostics(game,directory)
    # Upstream docrt/vision_reset recomputes seen vectors and remembered light
    # during ordinary restored vision on this hero-memory-enabled plane. Keep structural state and glyphs exact.
    assert restored_memory['traps']==memory['traps'] and restored_memory['stairs']==memory['stairs']
    visibility_refresh=[]
    for p,old in memory['terrain'].items():
        new=restored_memory['terrain'][p]
        changed=[f for f in old if old[f]!=new[f]]
        assert set(changed)<= {'seenv','waslit'},(p,old,new)
        if changed:visibility_refresh.append(dict(position=list(p),fields=changed,before=old,after=new))
    memory=restored_memory
    write(run/'restore-visibility-refresh.json',visibility_refresh)
    stable=copy.deepcopy(game.cells)
    game.finish(automatic=True)
    (run/'first-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    shutil.copytree(directory,run/'game')
    game=checks.open_game(directory);inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn) and set(game.cells)==set(stable)
    assert all(all(c.get(f)==stable[p].get(f) for f in FIELDS) for p,c in game.cells.items()),'Actual restored cells changed'
    assert inv.diagnostics(game,directory)==memory
    meta=copy.deepcopy(row['metadata'])
    meta.update(case={**meta['case'],'id':label,'label':label.replace('-',' ').title()},
        mode=mode,identity=identity,arrival=list(position),turn=turn,checkpoint=str(run),
        displayedCells=copy.deepcopy(list(game.cells.values())),perception=perception(game),
        nativeBounds=[1,0,79,21] if mode=='inspection' else
                     [max(1,min(60,position[0]-9)),max(0,min(8,position[1]-6)),20,13],
        exactTerrainLightingGlyphTrapRestore=True,exactDisplayedCellRestore=True,
        initialRestoreVisibilityRefreshCells=len(visibility_refresh),
        stableVisibilityMemoryRestore=True,
        originalSourceCheckpoint=row['run'],**package())
    write(run/'metadata.json',meta);write(run/'terrain-memory.json',inv.serial(memory))
    return game,dict(run=str(run),metadata=meta)


def floor_component(terrain,altar):
    found={altar};queue=[altar]
    while queue:
        p=queue.pop()
        for dx,dy,_ in CARDINAL:
            q=(p[0]+dx,p[1]+dy)
            if q not in found and terrain.get(q,{}).get('type') in ('room','altar'):
                found.add(q);queue.append(q)
    return found


def original_routes(terrain,arrival,altars):
    traversable={'room','corridor','door','altar'}
    previous={arrival:None};queue=deque([arrival])
    while queue:
        p=queue.popleft()
        for dx,dy,_ in CARDINAL:
            q=(p[0]+dx,p[1]+dy)
            if q not in previous and terrain.get(q,{}).get('type') in traversable:
                previous[q]=p;queue.append(q)
    result=[]
    for altar in altars:
        assert altar in previous,('Original temple disconnected',altar)
        route=[altar]
        while previous[route[-1]] is not None:route.append(previous[route[-1]])
        route.reverse()
        doors=[p for p in route if terrain[p]['type']=='door']
        assert doors,('Original shrine path has no doorway',altar)
        result.append(dict(altar=list(altar),tiles=len(route),doors=[list(p) for p in doors]))
    return dict(check='original connected three-temple topology',routes=result,
                limitation='Read-only topology evidence includes original closed/locked doors. It does not establish crowd clearance or continuous player traversal.')


def direct(game,event,target):
    assert event.get('direction'),event
    delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
    i={(-1,0):0,(0,-1):2,(1,0):4,(0,1):6}[delta]
    game.send('key '+str(ord(event['directionKeys'][i])));return game.wait_input()


def flags(cell):return dict(v.split('=',1) for v in cell['flags'].split('|') if '=' in v)


def move(game,target,limit=5):
    origin=game.cursor;offset=len(game.events);turn=game.turn
    for _ in range(limit):
        if game.cursor==target:break
        delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
        if max(abs(v) for v in delta)>1:break
        key=next(k for dx,dy,k in inv.STEPS if (dx,dy)==delta)
        event=game.command('m');assert event.get('command'),event
        inv.settle(game,game.command(key))
    return dict(command='m + direction',origin=list(origin),destination=list(game.cursor),
                target=list(target),reached=game.cursor==target,turns=game.turn-turn,
                messages=messages(game,offset))


def bare_altar_position(game,altar,rooms,distance):
    choices=[p for p in rooms if p!=altar and max(abs(p[i]-altar[i]) for i in (0,1))==distance]
    choices.sort(key=lambda p:sum(abs(p[i]-game.cursor[i]) for i in (0,1)))
    for p in choices[:16]:
        try:inv.place(game,p)
        except AssertionError:continue
        if int(game.status.get(22,'0'))&2:
            sanctum.restore_sight(game)
        before=game.turn;text=game.inspect(*altar);assert game.turn==before
        if game.cells[altar]['tile']==1309 and 'high altar' in text.lower():
            return dict(position=list(p),inspection=text,cell=copy.deepcopy(game.cells[altar]),turnFree=True)
    raise AssertionError(('Original altar occupied/unseen in bounded temple positions',altar,distance))


def door_test(game,directory,terrain,rooms,altar):
    doors=[p for p,c in terrain.items() if c['type']=='door' and
           any((p[0]+dx,p[1]+dy) in rooms for dx,dy,_ in CARDINAL)]
    assert len(doors)==1,('Original temple door count differs',altar,doors)
    point=doors[0]
    outside=[(point[0]+dx,point[1]+dy) for dx,dy,_ in CARDINAL
             if (point[0]+dx,point[1]+dy) not in rooms and
             terrain.get((point[0]+dx,point[1]+dy),{}).get('type') in ('room','corridor')]
    assert outside,('No original exterior door approach',point)
    for approach in outside:
        try:inv.place(game,approach)
        except AssertionError:continue
        break
    else:return dict(check='original temple doorway',point=list(point),unperformed='All original exterior positions occupied')
    state=inv.diagnostics(game,directory)['terrain'][point];actions=[];healing=[]
    healing.extend(sanctum.restore_sight(game))
    if flags(state).get('locked')=='true':
        offset=len(game.events);inv.settle(game,direct(game,tour.named(game,'open'),point))
        text=messages(game,offset);assert any('locked' in m.lower() for m in text),text
        actions.append(dict(command='Open',messages=text))
        inv.wish(game,'uncursed skeleton key')
        for _ in range(12):
            healing.extend(sanctum.restore_sight(game))
            if flags(inv.diagnostics(game,directory)['terrain'][point]).get('locked')!='true':break
            offset=len(game.events);event=game.command('a');assert event['kind']=='menu',event
            key=next(i for i in event['items'] if i.get('selectable') and 'key' in i['text'].lower())
            game.send('menu '+str(key['id']));event=direct(game,game.wait_input(),point)
            if event.get('command'):
                # Active combat can confuse direction input or change a door.
                # A declined ordinary action is evidence, not a missing prompt.
                actions.append(dict(command='Apply key',messages=messages(game,offset),unlockPrompt=False))
                continue
            assert event['kind']=='yn',event
            if 'unlock' not in event['prompt'].lower():
                assert 'lock' in event['prompt'].lower(),event
                game.send('key 110');inv.settle(game)
                actions.append(dict(command='Decline relocking',messages=messages(game,offset)))
                continue
            game.send('key 121');inv.settle(game)
            actions.append(dict(command='Apply key',messages=messages(game,offset)))
            if flags(inv.diagnostics(game,directory)['terrain'][point]).get('locked')=='false':break
        else:return dict(check='original temple doorway',point=list(point),actions=actions,unperformed='Bounded ordinary unlock interrupted by original occupants')
    for _ in range(8):
        if flags(inv.diagnostics(game,directory)['terrain'][point]).get('isopen')=='true':break
        healing.extend(sanctum.restore_sight(game))
        offset=len(game.events);inv.settle(game,direct(game,tour.named(game,'open'),point))
        actions.append(dict(command='Open',messages=messages(game,offset)))
    opened=flags(inv.diagnostics(game,directory)['terrain'][point]).get('isopen')=='true'
    passage=move(game,point,limit=3) if opened else None
    return dict(check='original temple doorway',point=list(point),approach=list(approach),
                horizontal=terrain[point]['horizontal'],
                originalLocked=flags(terrain[point]).get('locked')=='true',opened=opened,
                actions=actions,passage=passage,ordinaryHealing=healing,
                limitation='Protected bounded ordinary Open/Apply-key/no-attack movement; original active occupants can block passage.')


def nondig_wall(game,directory):
    terrain=inv.diagnostics(game,directory)['terrain']
    candidates=[p for p,c in terrain.items() if c['type'] in ('wall','vertical wall','horizontal wall') and
                any(terrain.get((p[0]+dx,p[1]+dy),{}).get('type')=='room' for dx,dy,_ in CARDINAL)]
    candidates.sort(key=lambda p:sum(abs(p[i]-game.cursor[i]) for i in (0,1)))
    inv.wish(game,'uncursed wand of digging (0:3)')
    event=tour.named(game,'wizidentify');assert event['kind']=='menu',event
    game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'));inv.settle(game)
    for point in candidates[:16]:
        try:approach=sanctum.near(game,directory,point,terrain)
        except AssertionError:continue
        break
    else:raise AssertionError('No clear original nondiggable wall approach in bounded sample')
    before=inv.diagnostics(game,directory)['terrain'][point];offset=len(game.events)
    event=game.command('z');assert event['kind']=='menu',event
    item=next(i for i in event['items'] if 'wand of digging' in i['text'].lower())
    game.send('menu '+str(item['id']));inv.settle(game,direct(game,game.wait_input(),point))
    after=inv.diagnostics(game,directory)['terrain'][point];text=messages(game,offset)
    assert all(before[f]==after[f] for f in ('type','horizontal','flags')),(before,after)
    assert any('wall glows then fades' in m.lower() for m in text),text
    return dict(position=list(point),approach=list(approach),command='zap wand of digging',terrainUnchanged=True,messages=text)


def temple_case(row,altar,label):
    run,directory,game=clone(row,label);record=dict(case=label,run=str(run),altar=list(altar))
    try:
        protect(game);terrain=inv.diagnostics(game,directory)['terrain'];rooms=floor_component(terrain,altar)
        assert len(rooms)==35,('Original temple interior dimensions differ',altar,len(rooms))
        distant=bare_altar_position(game,altar,rooms,2)
        assert 'aligned high altar' in distant['inspection'].lower()
        assert not any(w in distant['inspection'].lower() for w in ('lawful','neutral','chaotic','unaligned'))
        distant_priests=[]
        for p,c in game.cells.items():
            if not (0<=c.get('glyph',-1)<800) or max(abs(p[i]-game.cursor[i]) for i in (0,1))<=1:continue
            before=game.turn;text=game.inspect(*p);assert game.turn==before
            if 'high priest' in text.lower():
                assert ' of ' not in text.lower(),text
                distant_priests.append(dict(position=list(p),inspection=text,cell=copy.deepcopy(c),turnFree=True))
        # Reuse the identical frozen original world in a fresh clone so
        # distant-inspection turns cannot make a priest cover the altar before
        # the independent adjacent-perception check. No actor is relocated.
        game.finish(automatic=True);checks.cleanup(run,game)
        record['distantRun']=str(run)
        run,directory,game=clone(row,label+'-adjacent');record['run']=str(run)
        protect(game);terrain=inv.diagnostics(game,directory)['terrain'];rooms=floor_component(terrain,altar)
        adjacent=bare_altar_position(game,altar,rooms,1)
        assert all(distant['cell'][f]==adjacent['cell'][f] for f in ('tile','glyph','color')),'Distance/adjacency altered high-altar appearance'
        alignment=next((w for w in ('lawful','neutral','chaotic') if w+' high altar' in adjacent['inspection'].lower()),None)
        assert alignment,adjacent
        # Alignment is recorded only after legitimate adjacent inspection.
        record.update(distant=distant,adjacent=adjacent,observedAlignment=alignment,distantPriests=distant_priests,
                      distantPriestPrivacyVerified=bool(distant_priests),distantPriestLimitation=None if distant_priests else 'No sufficiently distant visible high priest in this bounded original view; deity concealment not verified for this temple.',
                      originalRoomSize=len(rooms),altarAppearance=dict((f,adjacent['cell'][f]) for f in ('tile','glyph','color')))
        observed=[]
        for p,c in game.cells.items():
            if p==game.cursor or not (0<=c.get('glyph',-1)<800) or c.get('groundTile') not in range(1291,1297):continue
            before=game.turn;text=game.inspect(*p);assert game.turn==before
            observed.append(dict(position=list(p),cell=copy.deepcopy(c),inspection=text,turnFree=True))
        assert any('high priest' in c['inspection'].lower() for c in observed),'Original high priest not perceived'
        record['occupantsWithKnownSupport']=observed
        m=copy.deepcopy(row)
        m['metadata']['setup'].append('Independent copied original temple review: wizard level30 and timed protection/stealth/invisibility/very-fast/see-invisible. Hero positions selected on original temple floor using read-only geometry; no mapping, altar assignment or actor replacement. Independent fresh distant/adjacent copies retain the same original shrine alignment. Distant versus adjacent hover respects upstream high-altar/priest alignment privacy. No ascension action.')
        # Freeze actual adjacent perception before spending doorway-combat turns.
        game,state=snapshot(m,game,directory,label)
        record['door']=door_test(game,directory,terrain,rooms,altar)
        game.finish(automatic=True)
        return state,record
    finally:checks.cleanup(run,game)


def engine(row):
    source=Path(row['run'])/'game';assert inv.files_hashes(source)==row['originalGameSHA256']
    run,directory,game=clone(row,'engine');states=[];records=[]
    result=dict(run=str(run),passed=False,stateIDs=[],sourceEvidence=source_evidence(),expectedMaterial=expected_material(),**package())
    write(RESULTS,result)
    try:
        identity=tour.identity(game,directory);assert identity==row['metadata']['identity']
        initial=inv.diagnostics(game,directory)
        altars=sorted(p for p,c in initial['terrain'].items() if c['type']=='altar')
        assert len(altars)==3
        original_doors=[c for c in initial['terrain'].values() if c['type']=='door']
        assert len(original_doors)==9,'Original Astral source has nine doors'
        assert sum(flags(c).get('locked')=='true' for c in original_doors)==4
        assert sum(flags(c).get('closed')=='true' for c in original_doors)==5
        records.append(dict(check='original Astral door inventory',doors=len(original_doors),closed=sum(flags(c).get('closed')=='true' for c in original_doors),locked=sum(flags(c).get('locked')=='true' for c in original_doors)))
        assert not initial['stairs'] and not any(t['type']=='magic portal' for t in initial['traps'].values())
        unknown=[]
        for p in altars:
            before=game.turn;text=game.inspect(*p);assert game.turn==before
            assert 'unexplored' in text.lower() and 'altar' not in text.lower(),text
            assert game.cells[p]['tile'] in (1469,1470) and 'groundTile' not in game.cells[p] and 'material' not in game.cells[p]
            unknown.append(dict(position=list(p),inspection=text,turnFree=True))
        records.append(dict(check='unseen Astral high altars',inspections=unknown))
        records.append(original_routes(initial['terrain'],game.cursor,altars))
        game,state=snapshot(row,game,directory,'astral-plane-arrival');states.append(state);write(STATES,states)
        print('PASS exact original Astral arrival',flush=True)
        for altar,label in zip(altars,IDS[1:4]):
            state,record=temple_case(row,altar,label);states.append(state);records.append(record);write(STATES,states)
            print('PASS original temple privacy and exact checkpoint',label,flush=True)
        temple_records=[r for r in records if 'altarAppearance' in r]
        assert len({tuple(r['altarAppearance'][f] for f in ('tile','glyph','color')) for r in temple_records})==1,'Shuffled altar alignment leaked into appearance'
        assert {r['observedAlignment'] for r in temple_records}=={'lawful','neutral','chaotic'},'Actual adjacent observations do not cover all three shuffled alignments'
        features,feature_directory,feature_game=clone(row,'nondig-wall')
        try:
            protect(feature_game)
            record=nondig_wall(feature_game,feature_directory)
            records.append(dict(check='original nondiggable Astral wall',evidence=record,run=str(features),
                setup='Independent copied source; wizard original-floor positioning, wished equipment-only-identified digging wand, ordinary Zap. Original wall and actors retained.'))
            feature_game.finish(automatic=True)
        finally:checks.cleanup(features,feature_game)
        protect(game);inv.settle(game,tour.named(game,'wizmap'))
        overview=copy.deepcopy(row)
        overview['metadata']['setup'].append('Final overview only: upstream wizard mapping reveals original terrain despite nommap. Original actors retained; high altar graphics are identical regardless shuffled alignment. This is development inspection, not campaign exploration or ascension.')
        mapped=[]
        for p in altars:
            turn=game.turn;text=game.inspect(*p);assert game.turn==turn
            if game.cells[p]['tile']==1309:
                assert 'aligned high altar' in text.lower() and not any(w in text.lower() for w in ('lawful','neutral','chaotic','unaligned')),text
            mapped.append(dict(position=list(p),cell=copy.deepcopy(game.cells[p]),inspection=text,turnFree=True))
        records.append(dict(check='late mapped overview preserves high altar privacy',observations=mapped))
        game,state=snapshot(overview,game,directory,'astral-plane-overview','inspection');states.append(state);write(STATES,states)
        game.finish(automatic=True)
        assert inv.files_hashes(source)==row['originalGameSHA256']
        result.update(passed=True,stateIDs=[s['metadata']['case']['id'] for s in states],states=[s['run'] for s in states],
            checkpointHashes={str(p):tour.digest(p) for s in states for p in sorted((Path(s['run'])/'game').rglob('*')) if p.is_file()},
            records=records,identity=identity,originalSaveUnchanged=True,originalSaveSHA256=row['originalGameSHA256'],
            exactStateRestores=True,altarAppearanceParity=True,noAscensionAction=True,
            limitations=['Independent protected temple positions, not continuous crowd clearance or a completed ascension.',
                        'Bounded ordinary doorway actions can be blocked by original active occupants.'])
        assert result['stateIDs']==IDS
        write(RESULTS,result);print('PASS original Astral temples, altar/privacy/parity, priest support, bounded doors and five exact states',flush=True)
        return result
    finally:checks.cleanup(run,game)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--engine',action='store_true')
    args=parser.parse_args();ART.mkdir(exist_ok=True)
    if args.prepare:prepare()
    if args.engine:engine(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine,'Choose --prepare or --engine'


if __name__=='__main__':main()
