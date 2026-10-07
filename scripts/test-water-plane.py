#!/usr/bin/env python3
"""Original moving Plane of Water checks and exact restored native states.

Original generation, monsters, random portal and moving bubbles remain engine-owned.
Wizard Endgame entry, protection and positioning are disclosed setup.
Water disables hero memory; absent current sight must not retain air pockets.
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
spec=importlib.util.spec_from_file_location('water_invocation',ROOT/'scripts/test-invocation.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)
checks,tour=inv.checks,inv.tour
INDEX=ART/'water-plane-prepared.json'
STATES=ART/'water-plane-states.json'
RESULTS=ART/'water-plane-engine-results.json'
FIELDS=('tile','glyph','char','color','pet','groundTile','material')
IDS=['water-plane-arrival','water-plane-drifting','water-plane-later-bubbles','water-plane-immersed','water-plane-exit-approach']


def write(path,value):checks.write(path,value)


def package():
    return dict(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'))


def expected_material():
    return None


def source_evidence():
    archive=tour.RES/'Source/nethack-500-src.tgz'
    paths=('dat/water.lua','dat/dungeon.lua','src/trap.c','src/mkmaze.c','src/vision.c','src/display.c','src/save.c','src/restore.c')
    hashes={}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member=next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            assert (tour.DAT.parent/path).read_bytes()==upstream.extractfile(member).read(),path
            hashes[path]=tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive))


def prepare():
    assert not INDEX.exists(),'Preserve prior Water source evidence before preparing another world'
    run=Path(tempfile.mkdtemp(prefix='water-plane-source-',dir=ART))
    case=next(c for c in tour.catalog() if c['id']=='water')
    metadata=tour.prepare(case,'exploration',run)
    assert metadata['case']['source'] is None
    assert metadata['identity']['branch']=='The Elemental Planes'
    metadata.update(sourceEvidence=source_evidence(),worldSelected=True,designPreviewOnly=False,
                    waterPlaneRecipeSHA256=tour.digest(Path(__file__)),**package())
    metadata['setup'].append('Actual original generated Water plane, selected by upstream wizard Endgame travel. No source reload or wizard mapping. The engine supplies the real Amulet for wizard Endgame access; this is not an ordinary campaign arrival.')
    write(run/'metadata.json',metadata)
    row=dict(run=str(run),metadata=metadata,originalGameSHA256=inv.files_hashes(run/'game'))
    write(INDEX,row);print('PREPARED original Water plane',run,flush=True)
    return row


def clone(row,label):
    run=Path(tempfile.mkdtemp(prefix='water-plane-'+label+'-',dir=ART));directory=run/'game'
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
    wanted=('fire resistance','cold resistance','shock resistance','sleep resistance','free action',
            'acid resistance','stoning resistance','disintegration resistance','unchanging',
            'magic resistance','poison resistance','magical breathing','hp regeneration',
            'invulnerable','invisible','stealthy','see invisible',
            'light-induced blindness resistance','half physical damage','half spell damage')
    rows=[i for i in event['items'] if i['text'].split('[')[0].strip().lower() in wanted]
    assert len(rows)==len(wanted),rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));inv.settle(game)


def perception(game):
    result=checks.material(game.cells.values(),None)
    for c in game.cells.values():
        assert c.get('groundTile') is None or c['groundTile'] in (1322,1324),c
        if c['tile'] in (1469,1470):assert 'groundTile' not in c,c
    return result


def snapshot(row,game,directory,label,mode='exploration'):
    """Only stable actual engine-displayed cells form native metadata."""
    run=Path(tempfile.mkdtemp(prefix='water-plane-state-'+label+'-',dir=ART))
    position,turn=game.cursor,game.turn
    identity=tour.identity(game,directory);memory=inv.diagnostics(game,directory)
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    game=checks.open_game(directory);inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn)
    assert tour.identity(game,directory)==identity
    restored_memory=inv.diagnostics(game,directory)
    # Upstream docrt/vision_reset recomputes seen vectors and remembered light
    # even on this memory-disabled plane. Keep structural state and glyphs exact.
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


def wait_turn(game):
    before=game.turn;offset=len(game.events)
    # Intrinsic speed can grant more than one hero action per world tick.
    # Observe the engine's time field rather than equating input with a tick.
    for _ in range(4):
        event=game.command('m');assert event.get('command'),event
        inv.settle(game,game.command('.'))
        if game.turn>before:break
    assert game.turn>before,('Ordinary forced wait did not advance',game.cursor)
    return dict(turns=game.turn-before,messages=messages(game,offset))


def sample(game,directory):
    memory=inv.diagnostics(game,directory)
    perception(game)
    supported=[];occupants=[];obscured_support=[]
    for p,c in game.cells.items():
        ground=c.get('groundTile')
        if ground is None:continue
        if c.get('tile') in (1323,1390):
            # Upstream newsym/show_region returns before updating lastseentyp.
            # The current region can conceal a moved bubble's actual surface.
            # Verify the supplied support was disclosed before the cloud, never
            # require the port to expose actual terrain hidden beneath gas.
            previous=next((e for e in reversed(game.events)
                if e.get('type')=='cell' and (e.get('x'),e.get('y'))==p
                and e.get('tile') not in (1323,1390)
                and e.get('groundTile') in (1322,1324)),None)
            assert previous and previous['groundTile']==ground,('Region support not previously disclosed',p,c,previous)
            obscured_support.append(dict(position=list(p),cell=copy.deepcopy(c),previous=copy.deepcopy(previous)))
            continue
        expected=1322 if memory['terrain'][p]['type']=='air' else 1324
        assert ground==expected,('Stale moving-bubble ground',p,c,memory['terrain'][p])
        supported.append(p)
        if p!=game.cursor and 0<=c.get('glyph',-1)<800:
            before=game.turn;text=game.inspect(*p);assert game.turn==before
            occupants.append(dict(position=list(p),cell=copy.deepcopy(c),inspection=text))
    swallowed=any(1392<=c.get('tile',-1)<=1399 for c in game.cells.values())
    blinded=bool(int(game.status.get(22,'0')) & 2)
    if swallowed:
        assert not supported and not obscured_support,'Engulfed view disclosed outside supporting water/air'
    elif blinded:
        assert not supported and not obscured_support,'Blind memory-disabled view retained supporting water/air'
    else:assert supported,'No perceived supporting air/water'
    portal=next(p for p,t in memory['traps'].items() if t['type']=='magic portal')
    if not memory['traps'][portal]['seen']:
        before=game.turn;text=game.inspect(*portal);assert game.turn==before
        assert 'portal' not in text.lower(),('Hidden moving exit disclosed',portal,text)
        assert game.cells.get(portal,{}).get('tile')!=1341,game.cells.get(portal)
    return memory,dict(turn=game.turn,position=list(game.cursor),portal=list(portal),
        portalSeen=memory['traps'][portal]['seen'],supportedCells=len(supported),occupants=occupants,
        swallowed=swallowed,blinded=blinded,obscuredRegionSupport=obscured_support)


def relocate(game,point):
    # The normal wizard teleport command is test setup. Water can carry the
    # hero again before the next command boundary, so exact landing is not
    # asserted. No terrain, actors or bubble internals are assigned.
    offset=len(game.events);event=tour.named(game,'teleport')
    if event['kind']=='yn' and event.get('prompt')=='Override?':
        game.send('key 121');event=game.wait_input()
    if event['kind']=='menu' and event.get('how')==0:
        game.send('key 32');event=game.wait_input()
    assert event.get('targeting'),event
    game.send(f'position {point[0]} {point[1]}');inv.settle(game)
    return dict(requested=list(point),arrival=list(game.cursor),messages=messages(game,offset))


def drift(game,directory,turns):
    frames=[];old_cells=copy.deepcopy(game.cells);old_memory,frame=sample(game,directory)
    frames.append(frame);changed=0;removed=0;stale_occupants=0;hero_moves=0;portal_moves=0
    witnesses=[]
    for _ in range(turns):
        wait_turn(game)
        memory,frame=sample(game,directory);frames.append(frame)
        if frame['position']!=frames[-2]['position']:hero_moves+=1
        if frame['portal']!=frames[-2]['portal']:portal_moves+=1
        shifts=[p for p,c in memory['terrain'].items() if c['type']!=old_memory['terrain'][p]['type']]
        changed+=len(shifts)
        for p,old in old_cells.items():
            c=game.cells.get(p,{})
            if old.get('groundTile')==1322 and c.get('groundTile')!=1322:
                removed+=1
                if len(witnesses)<8:witnesses.append(dict(position=list(p),before=old,after=copy.deepcopy(c)))
            if p!=tuple(frames[-2]['position']) and 0<=old.get('glyph',-1)<800 and c.get('glyph')!=old.get('glyph'):
                stale_occupants+=1
        old_cells=copy.deepcopy(game.cells);old_memory=memory
    assert hero_moves and portal_moves and removed and changed,(hero_moves,portal_moves,removed,changed)
    return dict(check='ordinary waits carry original bubbles and refresh perception',
        turns=game.turn-frames[0]['turn'],frames=frames,terrainTransitions=changed,
        oldAirSupportReplaced=removed,changedOccupantAppearances=stale_occupants,
        heroCarriedTurns=hero_moves,portalCarriedTurns=portal_moves,witnesses=witnesses)


def engine(row):
    source=Path(row['run'])/'game';assert inv.files_hashes(source)==row['originalGameSHA256']
    run,directory,game=clone(row,'engine');states=[];records=[]
    result=dict(run=str(run),passed=False,stateIDs=[],sourceEvidence=source_evidence(),
                expectedMaterial=None,**package());write(RESULTS,result)
    row=copy.deepcopy(row)
    def save(label):
        nonlocal game
        game,state=snapshot(row,game,directory,label);states.append(state);write(STATES,states)
        print('PASS exact original Water checkpoint',label,flush=True)
    try:
        identity=tour.identity(game,directory);assert identity==row['metadata']['identity']
        initial,first=sample(game,directory);counts=Counter(c['type'] for c in initial['terrain'].values())
        assert counts['air'] and counts['water'] and set(counts)=={'air','water'},counts
        assert not initial['stairs']
        assert len(initial['traps'])==1 and not first['portalSeen']
        portal=tuple(first['portal']);hidden=game.cells[portal]
        assert hidden['tile'] in (1324,1469,1470) and 'groundTile' not in hidden and 'material' not in hidden,hidden
        assert initial['terrain'][game.cursor]['type']=='air'
        records.append(dict(check='original arrival and unseen moving portal',**first))
        save(IDS[0]);protect(game)
        row['metadata']['setup'].append('Wizard level 30 and timed invulnerability, invisibility, stealth, magical breathing, regeneration, see invisible, unchanging, half damage and resistances including acid, stoning and disintegration. No flight or water walking supplied. Original monsters remain active. Protected environment tests are not an ordinary survival campaign.')
        records.append(drift(game,directory,16));save(IDS[1])
        records.append(drift(game,directory,24))
        if any(1392<=c.get('tile',-1)<=1399 for c in game.cells.values()):
            memory=inv.diagnostics(game,directory)
            pocket=next(p for p,c in memory['terrain'].items() if c['type']=='air' and p[0]<=25)
            records.append(dict(check='disclosed wizard escape from original engulfing encounter',placement=relocate(game,pocket)))
            row['metadata']['setup'].append('Original active encounter engulfed the hero during waiting; the restricted view cleared all outside support. Disclosed wizard teleport escapes that encounter for further bubble inspection, without removing the creature.')
        save(IDS[2])
        # Observe actual immersion through disclosed wizard placement in original
        # water. Movement and damage/equipment effects remain upstream-owned.
        immersion=[]
        for _ in range(8):
            memory=inv.diagnostics(game,directory)
            targets=[p for p,c in memory['terrain'].items() if c['type']=='water' and
                     5<=p[0]<=25 and 3<=p[1]<=17 and
                     sum(abs(p[i]-game.cursor[i]) for i in (0,1))>=5]
            immersion.append(relocate(game,targets[len(immersion)%len(targets)]))
            memory,frame=sample(game,directory)
            if memory['terrain'][game.cursor]['type']=='water':break
        assert memory['terrain'][game.cursor]['type']=='water',immersion
        assert game.cells[game.cursor].get('groundTile')==1324,game.cells[game.cursor]
        records.append(dict(check='protected actual water occupancy',placements=immersion,frame=frame,
                            hero=copy.deepcopy(game.cells[game.cursor])))
        row['metadata']['setup'].append('Disclosed wizard placement in original water to inspect actual immersion with magical breathing. No invented land, swimming shortcut, spawned actor or terrain replacement. Drowning and ordinary equipment survival are not isolated by this protected check.')
        save(IDS[3])
        # Place beside the ORIGINAL moving portal for a bounded ordinary attempt.
        # Read-only truth selects setup coordinates, never presentation content.
        attempts=[];transition=False
        for _ in range(18):
            memory=inv.diagnostics(game,directory)
            portal=next(p for p,t in memory['traps'].items() if t['type']=='magic portal')
            adjacent=[(portal[0]+dx,portal[1]+dy) for dx,dy,_ in inv.STEPS
                      if memory['terrain'].get((portal[0]+dx,portal[1]+dy),{}).get('type')=='air']
            if not adjacent:wait_turn(game);continue
            attempts.append(relocate(game,adjacent[len(attempts)%len(adjacent)]))
            memory,frame=sample(game,directory);portal=tuple(frame['portal'])
            delta=(portal[0]-game.cursor[0],portal[1]-game.cursor[1])
            if max(abs(v) for v in delta)<=1 and delta!=(0,0):break
        else:raise AssertionError(('No original moving exit approach',attempts))
        row['metadata']['setup'].append('Disclosed wizard relocation beside the original moving exit bubble. The portal remains engine-owned and hidden until normally perceived. No portal or discovery state assigned.')
        save(IDS[4])
        for _ in range(24):
            memory=inv.diagnostics(game,directory);portal=next(p for p,t in memory['traps'].items() if t['type']=='magic portal')
            delta=(portal[0]-game.cursor[0],portal[1]-game.cursor[1])
            if max(abs(v) for v in delta)>1 or delta==(0,0):break
            key=next(k for dx,dy,k in inv.STEPS if (dx,dy)==delta)
            offset=len(game.events);event=game.command('m');assert event.get('command')
            event=game.command(key)
            if event['kind']=='yn' and event.get('prompt','').startswith('Really step '):
                game.send('key 121');event=game.wait_input()
            inv.settle(game,event)
            destination=tour.identity(game,directory)
            if destination!=identity:
                assert destination['branch']=='The Elemental Planes' and destination['level']==identity['level']-1,destination
                assert any('activated a magic portal' in t.lower() for t in messages(game,offset))
                transition=True;break
        records.append(dict(check='ordinary original Water to Astral portal',verified=transition,
            setupPlacements=attempts,origin=identity,destination=tour.identity(game,directory),
            limitation=None if transition else 'Active original occupants or bubble movement blocked bounded approach; no actor removed.'))
        occupied=[o for r in records for f in r.get('frames',[]) for o in f['occupants']]
        assert occupied and any(o['cell']['groundTile']==1322 for o in occupied),'No original occupied air witnesses'
        game.finish(automatic=True)
        assert inv.files_hashes(source)==row['originalGameSHA256']
        checkpoint_hashes={str(p):tour.digest(p) for state in states for p in sorted((Path(state['run'])/'game').rglob('*')) if p.is_file()}
        result.update(passed=True,stateIDs=[s['metadata']['case']['id'] for s in states],states=[s['run'] for s in states],
            checkpointHashes=checkpoint_hashes,records=records,originalTerrainCounts=dict(counts),identity=identity,
            originalSaveUnchanged=True,originalSaveSHA256=row['originalGameSHA256'],exactStateRestores=True,
            portalTransitionVerified=transition,limitations=['Timed protection and disclosed positioning; no ordinary survival/ascension proof.',
                'Restore checks current terrain, occupants, turn and portal, not identical future random trajectories or unsaved bubble iteration order.'])
        assert result['stateIDs']==IDS
        write(RESULTS,result);print('PASS original Water bubbles, changing support, privacy, immersion and stable restoration',flush=True)
        return result
    finally:checks.cleanup(run,game)


def interactions(row):
    """Independent disposable probes preserve all native review checkpoints."""
    source=Path(row['run'])/'game';original=inv.files_hashes(source);records=[]
    run,directory,game=clone(row,'ordinary')
    try:
        start=game.turn;offset=len(game.events);positions=[list(game.cursor)]
        for _ in range(4):
            wait_turn(game);positions.append(list(game.cursor));sample(game,directory)
        records.append(dict(check='four ordinary unprotected world ticks',turns=game.turn-start,
            positions=positions,messages=messages(game,offset),status=copy.deepcopy(game.status),
            setup='Original wizard Endgame source with normal role equipment and no added intrinsics. Debug death refusal may occur; not an ordinary campaign arrival or survival proof.'))
        game.finish(automatic=True)
    finally:checks.cleanup(run,game)
    run,directory,game=clone(row,'object')
    try:
        protect(game);inv.wish(game,'uncursed rock named WaterDriftProbe')
        event=tour.named(game,'wizidentify');assert event['kind']=='menu',event
        game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'));inv.settle(game)
        dropped=inv.select_item(game,'d','WaterDriftProbe')
        movement=[]
        for _ in range(4):
            targets=[(dx,dy,k) for dx,dy,k in inv.STEPS if
                     game.cells.get((game.cursor[0]+dx,game.cursor[1]+dy),{}).get('tile')==1322]
            assert targets,'No currently perceived open air beside dropped probe'
            origin=game.cursor;dx,dy,key=targets[0]
            event=game.command('m');assert event.get('command')
            inv.settle(game,game.command(key))
            movement.append(dict(key=key,origin=list(origin),arrival=list(game.cursor)))
            if any(c.get('char')=='*' for c in game.cells.values()):break
        gems=[];old_air=copy.deepcopy(game.cells)
        for _ in range(16):
            memory,frame=sample(game,directory)
            for c in game.cells.values():
                if c.get('char')=='*':
                    turn=game.turn;text=game.inspect(c['x'],c['y']);assert game.turn==turn
                    if 'WaterDriftProbe' in text:
                        assert c.get('groundTile')==1322,c
                        gems.append(dict(turn=turn,position=[c['x'],c['y']],inspection=text,cell=copy.deepcopy(c)))
            wait_turn(game)
        assert len({tuple(g['position']) for g in gems})>=2,('Dropped probe not visibly carried',gems,dropped,movement)
        memory=inv.diagnostics(game,directory)
        pocket=next(p for p,c in memory['terrain'].items() if c['type']=='air' and p[0]>50)
        relocation=relocate(game,pocket)
        forgotten=[dict(position=list(p),before=c,after=copy.deepcopy(game.cells[p]))
            for p,c in old_air.items() if c.get('groundTile')==1322 and p in game.cells and
            game.cells[p].get('tile') in (1324,1469,1470) and 'groundTile' not in game.cells[p]]
        assert forgotten,'Old visible air did not lose support after distant relocation'
        witness=forgotten[0];p=tuple(witness['position']);turn=game.turn;text=game.inspect(*p);assert game.turn==turn
        assert any(w in text.lower() for w in ('water','unexplored')),text
        witness['inspection']=text
        records.append(dict(check='supplied rock dropped and carried by original bubble',drop=dropped,
            movement=movement,observations=gems,setup='Named uncursed rock supplied through upstream wizard wish/identify, then ordinary Drop and no-attack movement aside. No object coordinate assigned.'))
        records.append(dict(check='memory-disabled old air support removal',relocation=relocation,
            forgottenCells=len(forgotten),witness=witness,turnFreeInspection=True,
            setup='Disclosed wizard relocation to another original air pocket, no map reveal.'))
        game.finish(automatic=True)
    finally:checks.cleanup(run,game)
    run,directory,game=clone(row,'portal')
    try:
        protect(game);inv.wish(game,'blessed +50 long sword')
        inv.select_item(game,'w','long sword')
        origin=tour.identity(game,directory);attempts=[];transition=False
        for _ in range(12):
            memory=inv.diagnostics(game,directory)
            portal=next(p for p,t in memory['traps'].items() if t['type']=='magic portal')
            candidates=[(portal[0]+dx,portal[1]+dy) for dx,dy,_ in checks.STEPS
                if memory['terrain'].get((portal[0]+dx,portal[1]+dy),{}).get('type')=='air']
            if not candidates:wait_turn(game);continue
            setup=relocate(game,candidates[len(attempts)%len(candidates)])
            for _ in range(8):
                memory=inv.diagnostics(game,directory)
                portal=next(p for p,t in memory['traps'].items() if t['type']=='magic portal')
                delta=portal[0]-game.cursor[0],portal[1]-game.cursor[1]
                if max(abs(v) for v in delta)>1 or delta==(0,0):break
                key=next(k for dx,dy,k in inv.STEPS if (dx,dy)==delta)
                offset=len(game.events);event=game.command(key)
                if event['kind']=='yn' and event.get('prompt','').startswith('Really step '):
                    game.send('key 121');event=game.wait_input()
                inv.settle(game,event)
                destination=tour.identity(game,directory)
                attempts.append(dict(setup=setup,key=key,arrival=list(game.cursor),messages=messages(game,offset)))
                if destination!=origin:
                    assert destination['level']==origin['level']-1 and destination['branch']==origin['branch'],destination
                    assert any('activated a magic portal' in t.lower() for t in messages(game,offset))
                    transition=True;break
            if transition:break
        records.append(dict(check='ordinary Water to Astral portal activation with active encounters',
            verified=transition,attempts=attempts,origin=origin,destination=tour.identity(game,directory),
            setup='Disclosed timed protection, supplied +50 sword and wizard placement beside original moving exit. Normal directional movement/attacks activate portal; no trap, actor, discovery or destination assigned.',
            limitation=None if transition else 'Original moving bubbles/occupants blocked bounded portal activation.'))
        game.finish(automatic=True)
    finally:checks.cleanup(run,game)
    assert inv.files_hashes(source)==original==row['originalGameSHA256']
    result=dict(passed=True,records=records,originalSaveUnchanged=True,**package())
    write(ART/'water-plane-interaction-results.json',result)
    print('PASS ordinary Water probe, dropped-object transport and removed out-of-sight air',flush=True)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--engine',action='store_true');parser.add_argument('--interactions',action='store_true')
    args=parser.parse_args();ART.mkdir(exist_ok=True)
    if args.prepare:prepare()
    if args.engine:engine(json.loads(INDEX.read_text()))
    if args.interactions:interactions(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine or args.interactions,'Choose --prepare, --engine or --interactions'


if __name__=='__main__':main()
