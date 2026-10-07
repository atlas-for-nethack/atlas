#!/usr/bin/env python3
"""Bounded original Plane of Fire checks and exact restored native states.

Original generation, monsters, random portal and fire traps remain engine-owned.
Wizard Endgame entry, protection, positioning and mapping are disclosed setup.
Separate unprotected clones verify ordinary fire effects with debug death refusal.
No map reload, terrain/actor replacement or direct discovery mutation is used.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('fire_invocation',ROOT/'scripts/test-invocation.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)
checks,tour=inv.checks,inv.tour
INDEX=ART/'fire-plane-prepared.json'
STATES=ART/'fire-plane-states.json'
RESULTS=ART/'fire-plane-engine-results.json'
FIELDS=('tile','glyph','char','color','pet','groundTile','material')
IDS=['fire-plane-arrival','fire-plane-lava-edge',
     'fire-plane-mapped-overview','fire-plane-portal-ready']


def write(path,value):checks.write(path,value)


def package():
    return dict(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'))


def expected_material():
    return 'gehennom'


def source_evidence():
    archive=tour.RES/'Source/nethack-500-src.tgz'
    paths=('dat/fire.lua','dat/dungeon.lua','src/trap.c','src/mkmaze.c')
    hashes={}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member=next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            assert (tour.DAT.parent/path).read_bytes()==upstream.extractfile(member).read(),path
            hashes[path]=tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True,hashes=hashes,upstreamArchive=tour.digest(archive))


def prepare():
    assert not INDEX.exists(),'Preserve prior Fire source evidence before preparing another world'
    run=Path(tempfile.mkdtemp(prefix='fire-plane-source-',dir=ART))
    case=next(c for c in tour.catalog() if c['id']=='fire')
    metadata=tour.prepare(case,'exploration',run)
    assert metadata['case']['source'] is None
    assert metadata['identity']['branch']=='The Elemental Planes'
    metadata.update(sourceEvidence=source_evidence(),worldSelected=True,designPreviewOnly=False,
                    firePlaneRecipeSHA256=tour.digest(Path(__file__)),**package())
    metadata['setup'].append('Actual original generated Fire plane, selected by upstream wizard Endgame travel. No source reload or wizard mapping. The engine supplies the real Amulet for wizard Endgame access; this is not an ordinary campaign arrival.')
    write(run/'metadata.json',metadata)
    row=dict(run=str(run),metadata=metadata,originalGameSHA256=inv.files_hashes(run/'game'))
    write(INDEX,row);print('PREPARED original Fire plane',run,flush=True)
    return row


def clone(row,label):
    run=Path(tempfile.mkdtemp(prefix='fire-plane-'+label+'-',dir=ART));directory=run/'game'
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
    wanted=('fire resistance','cold resistance','sleep resistance','free action',
            'magic resistance','poison resistance','magical breathing','hp regeneration',
            'invulnerable','invisible','stealthy')
    rows=[i for i in event['items'] if i['text'].split('[')[0].strip().lower() in wanted]
    assert len(rows)==len(wanted),rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows));inv.settle(game)


def perception(game):
    return checks.material(game.cells.values(),expected_material())


def snapshot(row,game,directory,label,mode='exploration'):
    """Only stable actual engine-displayed cells form native metadata."""
    run=Path(tempfile.mkdtemp(prefix='fire-plane-state-'+label+'-',dir=ART))
    position,turn=game.cursor,game.turn
    identity=tour.identity(game,directory);memory=inv.diagnostics(game,directory)
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    game=checks.open_game(directory);inv.settle(game)
    assert (game.cursor,game.turn)==(position,turn)
    assert tour.identity(game,directory)==identity and inv.diagnostics(game,directory)==memory
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


def find_dry_edge(game,directory,terrain):
    pairs=[(p,(p[0]+dx,p[1]+dy)) for p,c in terrain.items() if c['type']=='room'
           for dx,dy,_ in checks.STEPS if terrain.get((p[0]+dx,p[1]+dy),{}).get('type')=='lava pool']
    pairs.sort(key=lambda r:sum(abs(r[0][i]-game.cursor[i]) for i in (0,1)))
    for floor,lava in pairs[:30]:
        try:place(game,floor)
        except AssertionError:continue
        before=game.turn;text=game.inspect(*lava);assert game.turn==before
        if 'lava' in text.lower():return floor,lava,text
    raise AssertionError('No ordinary perceived lava shore available')


def hazard(row,protected):
    run,directory,game=clone(row,'protected-hazard' if protected else 'ordinary-hazard')
    try:
        if protected:protect(game)
        terrain=inv.diagnostics(game,directory)
        traps=[p for p,t in terrain['traps'].items() if t['type']=='fire']
        for target in traps:
            approaches=[(target[0]+dx,target[1]+dy) for dx,dy,_ in checks.STEPS
                        if terrain['terrain'].get((target[0]+dx,target[1]+dy),{}).get('type')=='room' and
                        (target[0]+dx,target[1]+dy) not in terrain['traps']]
            for approach in approaches:
                try:place(game,approach)
                except AssertionError:continue
                hp=int(game.status[18]);offset=len(game.events)
                try:movement=move(game,target,limit=3)
                except AssertionError:continue
                text=messages(game,offset)
                if any('tower of flame' in m.lower() for m in text):break
            else:continue
            break
        else:raise AssertionError('No original fire trap could be triggered without actor removal')
        observed=inv.diagnostics(game,directory)['traps'][target]
        assert observed['type']=='fire' and observed['seen']
        assert any('tower of flame' in m.lower() for m in text),text
        record=dict(check='protected original fire trap' if protected else 'ordinary original fire trap',
            run=str(run),protected=protected,fireResistanceSetup=protected,trap=list(target),movement=movement,
            inventoryBurnMessageObserved=any(any(w in m.lower() for w in ('smoulder','burn','boils','destroyed')) for m in text),
            hpBefore=hp,hpAfter=int(game.status[18]),messages=text,
            hpDeltaCannotAttributeToTrap=True,
            limitation='Original occupants can attack during the same action; recorded HP/death refusal is the combined encounter, not isolated trap damage or ordinary survival proof.',
            debugDeathRefusal=any("don't die" in m.lower() for m in text),
            setup='Wizard position on original dry floor. No terrain/actor/feature state assigned. Death refusal remains available in disposable wizard game.')
        game.finish(automatic=True);return record
    finally:checks.cleanup(run,game)


def engine(row):
    source=Path(row['run'])/'game'
    assert inv.files_hashes(source)==row['originalGameSHA256'],'Original source changed'
    run,directory,game=clone(row,'engine');states=[];records=[]
    result=dict(run=str(run),passed=False,stateIDs=[],sourceEvidence=source_evidence(),
                expectedMaterial=expected_material(),**package());write(RESULTS,result)
    row=copy.deepcopy(row)
    def save(label,mode='exploration'):
        nonlocal game
        game,state=snapshot(row,game,directory,label,mode);states.append(state);write(STATES,states)
        print('PASS exact original Fire checkpoint',label,flush=True)
    try:
        identity=tour.identity(game,directory);assert identity==row['metadata']['identity']
        initial=inv.diagnostics(game,directory)
        counts=Counter(c['type'] for c in initial['terrain'].values())
        assert counts['lava pool']>0 and counts['room']>0
        assert not any('wall' in typ or typ in ('door','secret door') for typ in counts),counts
        hidden=[(p,c) for p,c in game.cells.items() if c['tile'] in (1469,1470)]
        assert hidden,'Original arrival already mapped'
        before=game.turn;unknown=game.inspect(*hidden[0][0]);assert game.turn==before and 'unexplored' in unknown.lower()
        portal=next(p for p,t in initial['traps'].items() if t['type']=='magic portal')
        portal_cell=copy.deepcopy(game.cells[portal]);portal_text=game.inspect(*portal)
        assert not initial['traps'][portal]['seen'] and 'portal' not in portal_text.lower()
        assert portal_cell['tile'] in (1469,1470) and 'groundTile' not in portal_cell and 'material' not in portal_cell
        save('fire-plane-arrival')
        protect(game)
        row['metadata']['setup'].append('Protected review: wizard level30, timed invulnerability, invisibility, stealth, fire/cold/sleep/poison/magic resistance, free action, magical breathing and regeneration. Original actors remain active; no actor removal.')
        floor,lava,lava_text=find_dry_edge(game,directory,initial['terrain'])
        adjacent=[(floor[0]+dx,floor[1]+dy) for dx,dy,_ in checks.STEPS
                  if initial['terrain'].get((floor[0]+dx,floor[1]+dy),{}).get('type')=='room' and
                  game.cells.get((floor[0]+dx,floor[1]+dy),{}).get('tile') in range(1291,1297)]
        movement=None
        for target in adjacent:
            try:movement=move(game,target,limit=3);break
            except AssertionError:continue
        assert movement,'No ordinary dry movement beside original lava'
        records.append(dict(check='dry floor and lava shore',floor=list(floor),lava=list(lava),
                            inspection=lava_text,inspectionTurnFree=True,movement=movement))
        row['metadata']['setup'].append('Wizard position on original dry lava shore, then ordinary no-attack movement over adjacent displayed dry floor. Lava hover is actual engine appearance, turn-free.')
        clouds=[copy.deepcopy(c) for c in game.cells.values() if c['tile'] in (1323,1390)]
        cloud_evidence=[]
        for c in clouds:
            before=game.turn;text=game.inspect(c['x'],c['y']);assert game.turn==before
            assert 'cloud' in text.lower(),text
            kind='poison cloud' if c['tile']==1390 else 'vapor cloud'
            assert ('poison' in text.lower()) == (c['tile']==1390),text
            cloud_evidence.append(dict(kind=kind,cell=c,inspection=text,turnFree=True))
        records.append(dict(check='natural cloud appearances',observed=bool(cloud_evidence),
            evidence=cloud_evidence,sampledTurn=game.turn,
            limitation=None if cloud_evidence else 'No natural displayed cloud in this bounded live sample; no cloud spawned or hidden cloud queried.'))
        if cloud_evidence:row['metadata']['setup'].append('Actual engine-generated vapor and poison cloud appearances are inspected separately over known supporting terrain. Poison clouds are consistent with original fumaroles, but this check does not trace an individual emitter. Magical breathing is protected setup, not evidence that ordinary clouds are harmless.')
        # Known occupants use only actual displayed foreground/support cells.
        crowd=[]
        for _ in range(20):
            crowd=[copy.deepcopy(c) for p,c in game.cells.items() if p!=game.cursor and
                   0<=c.get('glyph',-1)<800 and c.get('groundTile') in (*range(1291,1297),1316)]
            if crowd:break
            visible_dry=[p for p,c in game.cells.items() if c['tile'] in range(1291,1297)]
            if not visible_dry:break
            try:place(game,visible_dry[-1])
            except AssertionError:continue
        assert crowd,'No original perceived occupant with known floor/lava support'
        inspections=[]
        for c in crowd:
            before=game.turn;text=game.inspect(c['x'],c['y']);assert game.turn==before
            inspections.append(dict(position=[c['x'],c['y']],text=text,cell=c))
        records.append(dict(check='original occupants on known support',inspections=inspections,turnFree=True))
        row['metadata']['setup'].append('Crowd consists solely of original active monsters perceived by the engine, using real remembered dry/lava supporting ground. No monster detection, spawning or hidden actor geometry supplied.')
        save('fire-plane-lava-edge')
        inv.settle(game,tour.named(game,'wizmap'))
        row['metadata']['setup'].append('Final overview uses upstream wizard mapping to reveal original terrain/fire traps/portal. It is disclosed development setup and does not reveal unseen actors.')
        save('fire-plane-mapped-overview','inspection')
        mapped=inv.diagnostics(game,directory)
        portal=next(p for p,t in mapped['traps'].items() if t['type']=='magic portal')
        before=game.turn;mapped_portal_inspection=game.inspect(*portal);assert game.turn==before and 'portal' in mapped_portal_inspection.lower(),mapped_portal_inspection
        approaches=[(portal[0]+dx,portal[1]+dy) for dx,dy,_ in checks.STEPS
                    if mapped['terrain'].get((portal[0]+dx,portal[1]+dy),{}).get('type')=='room' and
                    (portal[0]+dx,portal[1]+dy) not in mapped['traps']]
        for approach in approaches:
            try:place(game,approach)
            except AssertionError:continue
            break
        else:raise AssertionError('No original dry portal approach available')
        before=game.turn;known_portal=game.inspect(*portal);assert game.turn==before
        assert inv.diagnostics(game,directory)['traps'][portal]['seen']
        row['metadata']['setup'].append('Wizard positioning on original dry floor adjacent to actual mapped exit portal. Ordinary no-attack movement tests actual Water transition; this does not prove an ascension route.')
        save('fire-plane-portal-ready','inspection')
        transition=move(game,portal,limit=5,portal=True)
        destination=tour.identity(game,directory)
        assert destination['branch']=='The Elemental Planes' and destination['level']==identity['level']-1,(identity,destination)
        records.append(dict(check='actual Fire to Water portal',knownInspection=mapped_portal_inspection,approachForegroundInspection=known_portal,
                            movement=transition,origin=identity,destination=destination,protected=True))
        game.finish(automatic=True)
        records.extend([hazard(row,True),hazard(row,False)])
        assert inv.files_hashes(source)==row['originalGameSHA256']
        checkpoint_hashes={str(p):tour.digest(p) for state in states for p in sorted((Path(state['run'])/'game').rglob('*')) if p.is_file()}
        result.update(passed=True,stateIDs=[s['metadata']['case']['id'] for s in states],
            states=[s['run'] for s in states],checkpointHashes=checkpoint_hashes,records=records,
            originalSaveUnchanged=True,originalSaveSHA256=row['originalGameSHA256'],
            originalTerrainCounts=dict(counts),identity=identity,unseenPortalInspection=portal_text,
            unknownInspection=unknown,exactStateRestores=True)
        assert result['stateIDs']==IDS
        write(RESULTS,result);print('PASS original Fire topology/privacy/lava/crowds/portal and protected vs ordinary traps',flush=True)
        return result
    finally:checks.cleanup(run,game)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--engine',action='store_true')
    args=parser.parse_args();ART.mkdir(exist_ok=True)
    if args.prepare:prepare()
    if args.engine:engine(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine,'Choose --prepare or --engine'


if __name__=='__main__':main()
