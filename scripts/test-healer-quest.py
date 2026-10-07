#!/usr/bin/env python3
"""Check Healer presentation in isolated original-world engine checkpoints.

After building, prepare with prepare-healer-review.py --material healer.
This checks five stages, unrevealed home, ordinary movement, exact restoration
and role/branch boundaries. It does not claim quest completion or combat testing.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('healer_prepare',ROOT/'scripts/prepare-healer-review.py')
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks,tour=prepare.checks,prepare.tour
outdoors=prepare.outdoors
INDEX=prepare.INDEX
RESULTS=ART/'healer-quest-engine.json'
STEPS=checks.STEPS


def check(row):
    m=row['metadata']
    run,directory,game=prepare.clone(row,'healer-production-'+m['case']['id']+'-'+m['mode'])
    previous=[]
    source_saves={str(f.relative_to(Path(row['run']))):tour.digest(f) for f in (Path(row['run'])/'game/save').iterdir() if f.is_file()}
    assert source_saves,'Missing original checkpoint'
    assert m['engine']==tour.digest(tour.RES/'engine/nethack'),'Prepared binary changed, reprepare first'
    result=dict(case=m['case']['id'],mode=m['mode'],run=str(run),setup=m['setup'],
                sourceCheckpoint=row['run'],sourceSaveSHA256=source_saves,engine=tour.digest(tour.RES/'engine/nethack'))
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity==m['identity'] and identity['role']=='Healer'
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        result.update(identity=identity,material=outdoors.material(game.cells.values(),m.get('expectedMaterial')))
        # Save/restore redraw may correctly expose a moving occupant over a
        # previously mapped trap. Compare unchanged safely known support and
        # independently snapshot original terrain; record foreground changes.
        before={(c['x'],c['y']):c for c in m['displayedCells']}
        changes=[]
        for position,cell in game.cells.items():
            assert position in before
            original=before[position]
            if cell.get('groundTile') is not None and original.get('groundTile') is not None:
                assert cell['groundTile']==original['groundTile'],(position,cell,original)
            if any(cell.get(f)!=original.get(f) for f in ('tile','char','color','pet')):
                changes.append(dict(position=position,before=original,restored=cell))
        result['canonicalRestoredCells']=[{field:c[field] for field in ('x','y','tile','glyph','char','color','pet','groundTile') if field in c} for _,c in sorted(game.cells.items())]
        result['initialTerrainGroundAndLightingSnapshot']=checks.terrain_snapshot(game,directory)
        result['knownSupportPreserved']=True
        result['foregroundRedrawChanges']=changes
        turn=game.turn
        samples=[]
        for category,criterion in (
            ('wall',lambda c:1273<=c['tile']<=1283),
            ('door',lambda c:1285<=c['tile']<=1288),
            ('ground',lambda c:1291<=c['tile']<=1296),
            ('water',lambda c:c['tile']==1314),
            ('altar',lambda c:c.get('char')=='_')):
            c=next((c for c in game.cells.values() if criterion(c)),None)
            if c:
                samples.append(dict(category=category,cell=c,description=game.inspect(c['x'],c['y'])))
        assert samples and game.turn==turn
        if m['mode']=='exploration':
            unknown=[c for c in game.cells.values() if c['tile']==1469]
            assert unknown
            c=unknown[len(unknown)//2]
            description=game.inspect(c['x'],c['y'])
            assert 'unexplored' in description.lower() and game.turn==turn
            result['unknownInspection']=dict(cell=c,description=description)
        result.update(inspection=samples,turnFreeInspection=True)
        occupants=[c for c in game.cells.values() if c['tile']<1273 or c.get('pet')]
        dry=[c for c in occupants if c.get('groundTile') in (1291,1292)]
        water=[c for c in occupants if c.get('groundTile')==1314]
        result['knownGroundBeneathOccupants']=dict(dry=dry,water=water,
            note='Only engine-emitted safely known ground fields. Empty water sample means no perceived water occupant at original arrival.')
        floor=[c for c in game.cells.values() if c['tile'] in (1291,1292)]
        pools=[c for c in game.cells.values() if c['tile']==1314]
        result['perceivedShorePairs']=[dict(dry=d,water=w) for d in floor for w in pools
            if abs(d['x']-w['x'])+abs(d['y']-w['y'])==1][:12]
        for sample in samples:
            if sample['category']=='altar':
                assert 'altar' in sample['description'].lower(),sample

        origin=game.cursor
        approaches=[(origin[0]+dx,origin[1]+dy,key) for dx,dy,key in STEPS
            if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('char')=='.']
        altar=next((s['cell'] for s in samples if s['category']=='altar'),None)
        if altar and m['case']['id']=='Hea-loca':
            approaches.sort(key=lambda p:abs(p[0]-altar['x'])+abs(p[1]-altar['y']))
        adjacent=next(iter(approaches),None)
        if adjacent:
            checks.settle(game,game.command(adjacent[2]))
            if game.cursor==tuple(adjacent[:2]):
                assert game.turn>turn
                result['ordinaryMove']=dict(origin=origin,destination=game.cursor,turns=game.turn-turn)
                if altar and m['case']['id']=='Hea-loca':
                    old_distance=abs(origin[0]-altar['x'])+abs(origin[1]-altar['y'])
                    new_distance=abs(game.cursor[0]-altar['x'])+abs(game.cursor[1]-altar['y'])
                    assert new_distance<old_distance,'No successful ordinary shrine approach'
                    result['ordinaryShrineApproach']=dict(perceivedAltar=altar,
                        distanceBefore=old_distance,distanceAfter=new_distance,
                        note='Adjacent displayed dry floor selected by perceived altar position, no hidden terrain or occupant replacement.')
            else:
                result['movementDeferred']='Original occupant or upstream condition blocked the attempt; no position override used.'
        else:
            result['movementDeferred']='No adjacent displayed plain floor at the original arrival.'
        outdoors.material(game.cells.values(),m.get('expectedMaterial'))
        terrain=checks.terrain_snapshot(game,directory)
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        previous=list(game.events)
        game=checks.open_game(directory)
        checks.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert tour.identity(game,directory)==identity
        assert checks.terrain_snapshot(game,directory)==terrain,'Terrain or lighting/memory changed across restore'
        result.update(restored=True,position=position,turn=turn,
            exactTerrainGroundAndLightingRestore=True,
            restoredMaterial=outdoors.material(game.cells.values(),m.get('expectedMaterial')))
        game.finish(automatic=True)
        print('PASS',m['case']['id'],m['mode'],'material, known support, inspection and exact restore',flush=True)
        return result
    finally:
        checks.cleanup(run,game,previous)
        assert source_saves=={str(f.relative_to(Path(row['run']))):tour.digest(f) for f in (Path(row['run'])/'game/save').iterdir() if f.is_file()},'Source checkpoint modified'


def boundaries(home):
    run,directory,game=prepare.clone(home,'healer-production-boundaries')
    records=[]
    try:
        checks.settle(game)
        for target,material,branch in (
            ('oracle',None,'The Dungeons of Doom'),
            ('minetn-','mines','The Gnomish Mines'),
            ('Hea-strt',home['metadata'].get('expectedMaterial'),'The Quest')):
            game.cells.clear()
            tour.teleport(game,target)
            identity=tour.identity(game,directory)
            assert identity['role']=='Healer' and identity['branch']==branch
            records.append(dict(target=target,identity=identity,
                                **outdoors.material(game.cells.values(),material)))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    # A separately created original Knight Quest cannot inherit Healer material.
    case=dict(next(c for c in tour.catalog() if c['id']=='Kni-strt'))
    other_run=ART/('healer-other-role-'+__import__('uuid').uuid4().hex)
    other_run.mkdir()
    other_metadata=tour.prepare(case,'inspection',other_run)
    other=dict(run=str(other_run),metadata=other_metadata)
    run,directory,game=prepare.clone(other,'healer-production-other-role')
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity['role']=='Knight' and identity['branch']=='The Quest'
        records.append(dict(target='Kni-strt',identity=identity,
                            **outdoors.material(game.cells.values(),[None,'quest-earth'])))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    print('PASS Healer/main dungeon/Mines/other-role Quest boundaries',flush=True)
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--compare-baseline',action='store_true',help='Assert exact restored canonical cells and terrain/memory/light match preserved baseline.')
    args=parser.parse_args()
    evidence=prepare.source_evidence()
    print('PASS five Healer stage sources and quest lore match bundled pinned upstream',flush=True)
    if args.sources_only:
        return
    rows=json.loads(INDEX.read_text())
    assert len(rows)==6
    for row in rows:
        assert row['metadata']['case']['source'] is None
        assert row['metadata']['generationRecipe']=='original-world-selected'
    results=[]
    for row in rows:
        results.append(check(row))
        checks.write(RESULTS,dict(source=evidence,checks=results))
    assert any('ordinaryMove' in result for result in results),'No successful ordinary dry-floor move'
    assert any(s['category']=='water' for r in results for s in r['inspection'])
    assert any('ordinaryShrineApproach' in r for r in results),'No ordinary shrine approach'
    assert any(r['knownGroundBeneathOccupants']['water'] for r in results),'No known water beneath occupants'
    assert any(r['knownGroundBeneathOccupants']['dry'] for r in results),'No known dry ground beneath occupants'
    home=next(r for r in rows if r['metadata']['case']['id']=='Hea-strt' and r['metadata']['mode']=='inspection')
    comparison=None
    if args.compare_baseline:
        baseline=json.loads((ART/'healer-canonical-quest-engine.json').read_text())
        for result in results:
            old=next(r for r in baseline['checks'] if r['case']==result['case'] and r['mode']==result['mode'])
            assert old['identity']==result['identity'],'World identity changed'
            assert old['canonicalRestoredCells']==result['canonicalRestoredCells'],('Canonical cells changed',result['case'],result['mode'])
            assert old['initialTerrainGroundAndLightingSnapshot']==result['initialTerrainGroundAndLightingSnapshot'],('Original terrain, memory or lighting changed',result['case'],result['mode'])
        comparison=dict(passed=True,baselineEngine=baseline['checks'][0]['engine'],currentEngine=results[0]['engine'],cases=len(results),sameSavedWorld=True,exactCanonicalCells=True,exactTerrainMemoryAndLighting=True)
        print('PASS exact canonical cells and terrain/memory/light against all six preserved baseline saves',flush=True)
    records=boundaries(home)
    checks.write(RESULTS,dict(source=evidence,checks=results,boundaries=records,passed=True,baselineComparison=comparison,
        limitation='Bounded environment checks, not a completed quest, ordinary campaign access or exhaustive encounter testing.'))

if __name__=='__main__':
    main()
