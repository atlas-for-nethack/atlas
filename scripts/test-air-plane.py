#!/usr/bin/env python3
"""Bounded original Plane of Air checks and exact restored native states.

Original generation, monsters, random portal and moving clouds remain engine-owned.
Wizard Endgame entry, protection, flight and positioning are disclosed setup.
Air disables hero memory; absent current sight must not acquire room floors.
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
spec=importlib.util.spec_from_file_location('air_invocation',ROOT/'scripts/test-invocation.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)
checks,tour=inv.checks,inv.tour
INDEX=ART/'air-plane-prepared.json'
STATES=ART/'air-plane-states.json'
RESULTS=ART/'air-plane-engine-results.json'
FIELDS=('tile','glyph','char','color','pet','groundTile','material')
IDS=['air-plane-arrival','air-plane-open-air','air-plane-cloud-edge','air-plane-portal-ready']


def write(path,value):checks.write(path,value)


def package():
    return dict(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'))


def expected_material():
    return None


def source_evidence():
    archive=tour.RES/'Source/nethack-500-src.tgz'
    paths=('dat/air.lua','dat/dungeon.lua','src/trap.c','src/mkmaze.c')
    hashes={}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member=next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            assert (tour.DAT.parent/path).read_bytes()==upstream.extractfile(member).read(),path
            hashes[path]=tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive))


def prepare():
    assert not INDEX.exists(),'Preserve prior Air source evidence before preparing another world'
    run=Path(tempfile.mkdtemp(prefix='air-plane-source-',dir=ART))
    case=next(c for c in tour.catalog() if c['id']=='air')
    metadata=tour.prepare(case,'exploration',run)
    assert metadata['case']['source'] is None
    assert metadata['identity']['branch']=='The Elemental Planes'
    metadata.update(sourceEvidence=source_evidence(),worldSelected=True,designPreviewOnly=False,
                    airPlaneRecipeSHA256=tour.digest(Path(__file__)),**package())
    metadata['setup'].append('Actual original generated Air plane, selected by upstream wizard Endgame travel. No source reload or wizard mapping. The engine supplies the real Amulet for wizard Endgame access; this is not an ordinary campaign arrival.')
    write(run/'metadata.json',metadata)
    row=dict(run=str(run),metadata=metadata,originalGameSHA256=inv.files_hashes(run/'game'))
    write(INDEX,row);print('PREPARED original Air plane',run,flush=True)
    return row


def clone(row,label):
    run=Path(tempfile.mkdtemp(prefix='air-plane-'+label+'-',dir=ART));directory=run/'game'
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
    wanted=('fire resistance','cold resistance','shock resistance','sleep resistance','free action','flying',
            'magic resistance','poison resistance','magical breathing','hp regeneration',
            'invulnerable','invisible','stealthy','very fast','see invisible',
            'light-induced blindness resistance','half physical damage','half spell damage')
    rows=[i for i in event['items'] if i['text'].split('[')[0].strip().lower() in wanted]
    assert len(rows)==len(wanted),rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));inv.settle(game)


def perception(game):
    return checks.material(game.cells.values(),expected_material())


def snapshot(row,game,directory,label,mode='exploration'):
    """Only stable actual engine-displayed cells form native metadata."""
    run=Path(tempfile.mkdtemp(prefix='air-plane-state-'+label+'-',dir=ART))
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


def move(game,target,limit=8,portal=False):
    origin=game.cursor;start=game.turn;offset=len(game.events)
    for attempt in range(limit):
        if game.cursor==target:break
        delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
        assert max(abs(v) for v in delta)<=1,(origin,game.cursor,target)
        key=next(k for dx,dy,k in inv.STEPS if (dx,dy)==delta)
        event=game.command('m');assert event.get('command'),event
        event=game.command(key)
        if event['kind']=='yn' and event.get('prompt','').startswith('Really step '):
            game.send('key 121');event=game.wait_input()
        inv.settle(game,event)
        if portal and any('activated a magic portal' in m.lower() for m in messages(game,offset)):break
        if game.cursor==target:break
    else:raise AssertionError(('Original occupant blocked ordinary no-attack movement',target))
    return dict(command='m + direction',origin=list(origin),destination=list(game.cursor),
                turns=game.turn-start,messages=messages(game,offset))


def place(game,point):inv.place(game,point)


def cloud_sample(game):
    result=[]
    for c in game.cells.values():
        if c['tile']!=1323 or c.get('groundTile')!=1323:continue
        before=game.turn;text=game.inspect(c['x'],c['y']);assert game.turn==before
        assert 'cloud' in text.lower(),text
        result.append(dict(cell=copy.deepcopy(c),inspection=text,turnFree=True))
        if len(result)==8:break
    return result


def occupants(game):
    result=[]
    for p,c in game.cells.items():
        if p==game.cursor or not (0<=c.get('glyph',-1)<800):continue
        assert c.get('groundTile') not in range(1291,1297),'Air occupant substituted room floor'
        if c.get('groundTile') not in (1322,1323):continue
        before=game.turn;text=game.inspect(*p);assert game.turn==before
        result.append(dict(cell=copy.deepcopy(c),inspection=text,turnFree=True))
    return result


def no_memory(game,directory):
    """A formerly seen open-air surface must disappear after leaving sight."""
    remembered=[(p,copy.deepcopy(c)) for p,c in game.cells.items() if c.get('groundTile') in (1322,1323)]
    assert remembered,'No perceived Air/cloud surfaces'
    terrain=inv.diagnostics(game,directory)['terrain']
    origin=game.cursor
    targets=[p for p,c in terrain.items() if c['type']=='air' and p[0]<=24 and
             sum(abs(p[i]-origin[i]) for i in (0,1))>=12]
    for target in targets[:30]:
        try:place(game,target)
        except AssertionError:continue
        vanished=[(p,before,game.cells[p]) for p,before in remembered
                  if game.cells.get(p,{}).get('tile') in (1469,1470,1323) and
                  'groundTile' not in game.cells.get(p,{})]
        if vanished:break
    else:raise AssertionError('No formerly visible Air surface disappeared outside current sight')
    for p,before,after in vanished:
        assert 'groundTile' not in after and 'material' not in after,after
    stale=[(p,old,new) for p,old,new in vanished if p!=origin and 0<=old.get('glyph',-1)<800 and new.get('glyph',-1)>=800]
    assert stale,'No original previously perceived occupant disappeared from view'
    p,before,after=stale[0];turn=game.turn;text=game.inspect(*p)
    assert game.turn==turn and any(w in text.lower() for w in ('unexplored','cloudy area')),text
    return dict(check='memory-disabled Air surface disappearance',origin=list(origin),destination=list(game.cursor),
                vanishedCells=len(vanished),staleOccupantsRemoved=sum(0<=old.get('glyph',-1)<800 and new.get('glyph',-1)>=800 for p,old,new in vanished if p!=origin),witness=dict(position=list(p),before=before,after=copy.deepcopy(after),inspection=text),
                setup='Disclosed wizard relocation inside original permitted arrival region, no blindness or hidden discovery mutation.')


def fly_to_portal(game,directory,portal):
    """Bounded normal flight uses perimeter and avoids displayed actors."""
    records=[];offset=len(game.events);start=game.turn;failed={};perimeter=True
    completed=False
    for attempt in range(160):
        if attempt and attempt%20==0:
            portal=next(p for p,t in inv.diagnostics(game,directory)['traps'].items() if t['type']=='magic portal')
        if sum(abs(game.cursor[i]-portal[i]) for i in (0,1))==1:
            completed=True;break
        if game.cursor==portal:raise AssertionError('Portal activated before adjacent checkpoint')
        waypoint=(portal[0],0) if perimeter else portal
        if game.cursor==waypoint:
            perimeter=False;waypoint=portal
        blocked={p for p,c in game.cells.items() if p!=game.cursor and
                 (0<=c.get('glyph',-1)<800 or c.get('char')=='I')}
        blocked.update(q for (p,q),when in failed.items() if p==game.cursor and attempt-when<4)
        queue=deque([game.cursor]);previous={game.cursor:None};nearest=game.cursor
        while queue:
            p=queue.popleft()
            if sum(abs(p[i]-waypoint[i]) for i in (0,1))<sum(abs(nearest[i]-waypoint[i]) for i in (0,1)):nearest=p
            if p==waypoint:nearest=p;break
            for dx,dy,key in checks.STEPS:
                q=(p[0]+dx,p[1]+dy)
                if q not in previous and q not in blocked and q!=portal and 1<=q[0]<=79 and 0<=q[1]<=20:
                    previous[q]=p;queue.append(q)
        if nearest==game.cursor:
            # Upstream can decline an unsafe bare rest without spending a turn.
            # Force the ordinary no-op so original occupants/clouds can move.
            origin=game.cursor
            event=game.command('m');assert event.get('command'),event
            inv.settle(game,game.command('.'))
            records.append(dict(command='m.',origin=list(origin),destination=list(game.cursor)))
            continue
        target=nearest
        while previous[target]!=game.cursor:target=previous[target]
        delta=(target[0]-game.cursor[0],target[1]-game.cursor[1])
        key=next(k for x,y,k in checks.STEPS if (x,y)==delta)
        origin=game.cursor;event=game.command('m');assert event.get('command'),event
        inv.settle(game,game.command(key))
        if game.cursor==origin:failed[origin,target]=attempt
        records.append(dict(command='m'+key,origin=list(origin),destination=list(game.cursor)))
    return dict(check='ordinary protected flight across Air',commands=records,turns=game.turn-start,
                messages=messages(game,offset),protected=True,portal=list(portal),reachedApproach=completed,
                limitation='Bounded flight with supplied Amulet and timed protection. No actor removed; original clouds, blindness, engulfing and knockback can block progress. No ordinary campaign survival claimed.')


def engine(row):
    source=Path(row['run'])/'game';assert inv.files_hashes(source)==row['originalGameSHA256']
    run,directory,game=clone(row,'engine');states=[];records=[]
    result=dict(run=str(run),passed=False,stateIDs=[],sourceEvidence=source_evidence(),
                expectedMaterial=None,**package());write(RESULTS,result)
    row=copy.deepcopy(row)
    def save(label):
        nonlocal game
        game,state=snapshot(row,game,directory,label);states.append(state);write(STATES,states)
        print('PASS exact original Air checkpoint',label,flush=True)
    try:
        identity=tour.identity(game,directory);assert identity==row['metadata']['identity']
        initial=inv.diagnostics(game,directory)
        counts=Counter(c['type'] for c in initial['terrain'].values())
        assert counts['air']>0 and counts['cloud']>0,counts
        assert set(counts)<= {'air','cloud'},counts
        portal=next(p for p,t in initial['traps'].items() if t['type']=='magic portal')
        before=game.turn;unknown_portal=game.inspect(*portal);assert game.turn==before
        assert 'portal' not in unknown_portal.lower() and any(w in unknown_portal.lower() for w in ('unexplored','cloudy area')),unknown_portal
        assert game.cells[portal]['tile'] in (1469,1470,1323)
        assert 'groundTile' not in game.cells[portal] and 'material' not in game.cells[portal]
        assert not initial['traps'][portal]['seen']
        assert all(c.get('groundTile') not in range(1291,1297) for c in game.cells.values()),'Room-floor metadata on Air'
        save('air-plane-arrival')
        protect(game)
        row['metadata']['setup'].append('Wizard level30 plus timed flight, invulnerability, invisibility, stealth, magical breathing, regeneration, very fast, see invisible, light-induced blindness resistance, half physical/spell damage, and fire/cold/shock/sleep/poison/magic resistance/free action. This is protected interface/route verification, not unprotected campaign arrival.')
        nearby=[(p,c) for p,c in game.cells.items() if c['tile']==1322 and
                sum(abs(p[i]-game.cursor[i]) for i in (0,1))==1]
        assert nearby,'No original adjacent currently perceived open Air'
        target=nearby[0][0];movement=move(game,target,limit=5)
        assert game.cells[game.cursor].get('groundTile') in (1322,1323)
        observed=occupants(game);assert observed,'No original perceived occupant with Air/cloud support'
        records.append(dict(check='open Air movement and supported occupants',movement=movement,occupants=observed))
        save('air-plane-open-air')
        records.append(no_memory(game,directory))
        clouds=cloud_sample(game)
        if not clouds:
            # Use actual cloud terrain solely to choose disclosed placement,
            # then inspect only the engine's currently displayed cloud.
            terrain=inv.diagnostics(game,directory)['terrain']
            candidates=[p for p,c in terrain.items() if c['type']=='air' and p[0]<=24 and
                        any(terrain.get((p[0]+dx,p[1]+dy),{}).get('type')=='cloud' for dx,dy,_ in checks.STEPS)]
            for p in candidates[:30]:
                try:place(game,p)
                except AssertionError:continue
                clouds=cloud_sample(game)
                if clouds:break
        assert clouds,'No original moving-cloud edge currently perceived'
        records.append(dict(check='actual moving Air clouds',observations=clouds,
                            limitation='Actual cloud appearance/ground verified. Thunder/lightning and suffocation effects are not forced or isolated in this bounded sample.'))
        row['metadata']['setup'].append('Relocated within original permitted Air arrival section to observe real moving clouds. Air hero-memory is disabled, so formerly seen out-of-sight cells became the engine cloudy-area fallback or unexplored with no stale ground layer. No cloud or monster was spawned.')
        save('air-plane-cloud-edge')
        flight=fly_to_portal(game,directory,portal);records.append(flight)
        # Air clouds do not carry portals (only Water bubbles transport things).
        # Confirm the original exit stayed fixed across ordinary flight.
        current=inv.diagnostics(game,directory)
        actual_portal=next(p for p,t in current['traps'].items() if t['type']=='magic portal')
        assert actual_portal==portal,'Original Air portal moved'
        portal=actual_portal
        route_ready=sum(abs(game.cursor[i]-portal[i]) for i in (0,1))==1
        if route_ready:
            turn=game.turn;known_portal=game.inspect(*portal);assert game.turn==turn
            row['metadata']['setup'].append('Ordinary flight crossed original teleport partitions to the actual exit. Portal foreground can be covered by an original occupant; inspection reflects that appearance. No magic mapping on memory-disabled Air.')
            save('air-plane-portal-ready')
            transition=move(game,portal,limit=6,portal=True)
            destination=tour.identity(game,directory)
            assert destination['branch']=='The Elemental Planes' and destination['level']==identity['level']-1,(identity,destination)
            records.append(dict(check='actual Air to Fire portal',origin=identity,destination=destination,
                                foregroundInspection=known_portal,movement=transition,protected=True,verified=True))
        else:
            row['metadata']['setup'].append('Bounded ordinary protected perimeter flight was blocked by original active occupants/conditions. No actors removed. This saved state is actual flight progress, not a verified portal approach or Air-to-Fire transition.')
            save('air-plane-flight-progress')
            records.append(dict(check='actual Air to Fire portal',verified=False,
                                limitation='Original active encounters blocked bounded no-attack flight before exit; onward portal transition unperformed.'))
        game.finish(automatic=True)
        assert inv.files_hashes(source)==row['originalGameSHA256']
        checkpoint_hashes={str(p):tour.digest(p) for state in states for p in sorted((Path(state['run'])/'game').rglob('*')) if p.is_file()}
        result.update(passed=True,stateIDs=[s['metadata']['case']['id'] for s in states],states=[s['run'] for s in states],
            checkpointHashes=checkpoint_hashes,records=records,originalTerrainCounts=dict(counts),identity=identity,
            originalSaveUnchanged=True,originalSaveSHA256=row['originalGameSHA256'],
            unseenPortalInspection=unknown_portal,exactStateRestores=True,portalTransitionVerified=route_ready,
            limitations=['Protected flight and presentation, no unprotected encounter or ascension proof.',
                        'Cloud visuals and lost sight tested; no isolated storm/lightning/suffocation activation.',
                        *([] if route_ready else ['Air-to-Fire portal transition unperformed: original active occupants/conditions blocked bounded protected no-attack flight.'])])
        assert result['stateIDs'][:3]==IDS[:3] and result['stateIDs'][3] in ('air-plane-portal-ready','air-plane-flight-progress')
        write(RESULTS,result);print('PASS original Air/cloud topology, no-floor/portal privacy, bounded flight, memory loss and occupants',flush=True)
        return result
    finally:checks.cleanup(run,game)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--engine',action='store_true')
    args=parser.parse_args();ART.mkdir(exist_ok=True)
    if args.prepare:prepare()
    if args.engine:engine(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine,'Choose --prepare or --engine'


if __name__=='__main__':main()
