#!/usr/bin/env python3
"""Check Wizard presentation in isolated original-world engine checkpoints.

After building, prepare with prepare-wizard-review.py --material wizard.
This checks five stages, unrevealed home, ordinary movement, exact restoration
and role/branch boundaries. It does not claim quest completion or combat testing.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('wizard_prepare',ROOT/'scripts/prepare-wizard-review.py')
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks,tour=prepare.checks,prepare.tour
INDEX=prepare.INDEX
RESULTS=ART/'wizard-quest-engine.json'
STEPS=checks.STEPS


def check(row):
    m=row['metadata']
    expected=prepare.MATERIALS[m['case']['id'].split('-')[1]]
    run,directory,game=prepare.clone(row,'wizard-production-'+m['case']['id']+'-'+m['mode'])
    previous=[]
    source_saves={str(f.relative_to(Path(row['run']))):tour.digest(f) for f in (Path(row['run'])/'game/save').iterdir() if f.is_file()}
    assert source_saves,'Missing original checkpoint'
    assert m['engine']==tour.digest(tour.RES/'engine/nethack'),'Prepared binary changed, reprepare first'
    result=dict(case=m['case']['id'],mode=m['mode'],run=str(run),setup=m['setup'],
                sourceCheckpoint=row['run'],sourceSaveSHA256=source_saves,engine=tour.digest(tour.RES/'engine/nethack'))
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity==m['identity'] and identity['role']=='Wizard'
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        result.update(identity=identity,material=checks.material(game.cells.values(),expected))
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
            ('altar',lambda c:c.get('char')=='_'),
            ('cloud',lambda c:c['tile']==1323),
            ('iron-bars',lambda c:c['tile']==1289)):
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
        # Canonical displayed cloud and pool cells support their own perceived
        # terrain, without inferring unseen aquatic occupants.
        supported_surfaces=[]
        for surface in (1314,1323):
            cells=[c for c in game.cells.values() if c['tile']==surface]
            assert all(c.get('groundTile')==surface for c in cells),cells[:3]
            supported_surfaces.append(dict(tile=surface,count=len(cells),sameKnownSupport=True))
        result['perceivedWaterAndCloudSupport']=supported_surfaces
        occupants=[c for c in game.cells.values() if c['tile']<1273 or c.get('pet')]
        dry=[c for c in occupants if c.get('groundTile') in (1291,1292)]
        water=[c for c in occupants if c.get('groundTile')==1314]
        cloud=[c for c in occupants if c.get('groundTile')==1323]
        result['knownGroundBeneathOccupants']=dict(dry=dry,water=water,cloud=cloud,
            note='Only engine-emitted safely known ground fields. Empty water sample means no perceived water occupant at original arrival.')
        floor=[c for c in game.cells.values() if c['tile'] in (1291,1292)]
        pools=[c for c in game.cells.values() if c['tile']==1314]
        result['perceivedShorePairs']=[dict(dry=d,water=w) for d in floor for w in pools
            if abs(d['x']-w['x'])+abs(d['y']-w['y'])==1][:12]
        for sample in samples:
            if sample['category']=='altar':
                assert 'altar' in sample['description'].lower(),sample

        observed_terrain=checks.terrain_snapshot(game,directory)
        from collections import Counter
        result['originalTerrainCounts']=dict(Counter(row[2] for row in observed_terrain))
        result['originalLightingCounts']=dict(Counter(row[3] for row in observed_terrain))
        origin=game.cursor
        approaches=[(origin[0]+dx,origin[1]+dy,key) for dx,dy,key in STEPS
            if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('char')=='.']
        altar=next((s['cell'] for s in samples if s['category']=='altar'),None)
        if altar and m['case']['id']=='Wiz-goal':
            approaches.sort(key=lambda p:abs(p[0]-altar['x'])+abs(p[1]-altar['y']))
        adjacent=next(iter(approaches),None)
        if adjacent:
            checks.settle(game,game.command(adjacent[2]))
            if game.cursor==tuple(adjacent[:2]):
                assert game.turn>turn
                result['ordinaryMove']=dict(origin=origin,destination=game.cursor,turns=game.turn-turn)
                if altar and m['case']['id']=='Wiz-goal':
                    old_distance=abs(origin[0]-altar['x'])+abs(origin[1]-altar['y'])
                    new_distance=abs(game.cursor[0]-altar['x'])+abs(game.cursor[1]-altar['y'])
                    assert new_distance<old_distance,'No successful ordinary altar approach'
                    result['ordinaryAltarApproach']=dict(perceivedAltar=altar,
                        distanceBefore=old_distance,distanceAfter=new_distance,
                        note='Adjacent displayed dry floor selected by perceived altar position, no hidden terrain or occupant replacement.')
            else:
                result['movementDeferred']='Original occupant or upstream condition blocked the attempt; no position override used.'
        else:
            result['movementDeferred']='No adjacent displayed plain floor at the original arrival.'
        checks.material(game.cells.values(),expected)
        if m['case']['id']=='Wiz-goal':
            # Test-only source diagnostics distinguish an occupied original
            # altar from its currently perceived foreground. Nothing becomes
            # a UI map layer or an inferred hover name.
            altar_positions=[(int(r[0]),int(r[1])) for r in observed_terrain if r[2]=='altar']
            assert len(altar_positions)==1,altar_positions
            altar_position=altar_positions[0]
            perceived=game.cells[altar_position]
            before_inspect=game.turn
            altar_description=game.inspect(*altar_position)
            assert game.turn==before_inspect
            if perceived.get('char')=='_':
                assert 'altar' in altar_description.lower()
            result['originalAltarPerception']=dict(position=altar_position,foreground=perceived,
                description=altar_description,unobscured=perceived.get('char')=='_',
                sourceDiagnosticOnly=True,note='Original altar is not a shrine. Covered foreground is preserved and inspection uses engine perception.')
            bars=[(p,c) for p,c in game.cells.items() if c['tile']==1289]
            candidates=[(point,(point[0]-dx,point[1]-dy),key) for point,_ in bars
                for dx,dy,key in STEPS if game.cells.get((point[0]-dx,point[1]-dy),{}).get('char')=='.']
            assert candidates,'No displayed dry floor beside original goal bars'
            candidates.sort(key=lambda row:abs(row[1][0]-game.cursor[0])+abs(row[1][1]-game.cursor[1]))
            redirects=[]
            for target,approach,key in candidates[:12]:
                try:
                    checks.place(game,approach)
                except AssertionError as error:
                    redirects.append(dict(requested=approach,actual=game.cursor,note=str(error)))
                    continue
                break
            else:
                raise AssertionError('No original goal bar approach accepted wizard placement')
            assert game.cells[target]['tile']==1289
            bar=game.cells[target]
            assert bar.get('groundTile') in (1291,1292),bar
            before_move=game.turn
            description=game.inspect(*target)
            assert 'iron bars' in description.lower() and game.turn==before_move
            checks.settle(game,game.command(key))
            assert game.cursor==approach and game.turn==before_move,'Original iron bars failed ordinary human collision'
            result['ordinaryBarCollision']=dict(approach=approach,target=target,cell=bar,description=description,
                command=key,noTurnConsumed=True,placementRedirects=redirects,
                setup='Wizard placement onto displayed dry approach in isolated check clone. Original terrain and occupants retained.')
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
            restoredMaterial=checks.material(game.cells.values(),expected))
        game.finish(automatic=True)
        print('PASS',m['case']['id'],m['mode'],'material, known support, inspection and exact restore',flush=True)
        return result
    finally:
        checks.cleanup(run,game,previous)
        assert source_saves=={str(f.relative_to(Path(row['run']))):tour.digest(f) for f in (Path(row['run'])/'game/save').iterdir() if f.is_file()},'Source checkpoint modified'


def boundaries(home):
    run,directory,game=prepare.clone(home,'wizard-production-boundaries')
    records=[]
    try:
        checks.settle(game)
        for target,material,branch in (
            ('oracle',None,'The Dungeons of Doom'),
            ('minetn-',['mines','mines-built'],'The Gnomish Mines'),
            ('Wiz-strt',prepare.MATERIALS['strt'],'The Quest')):
            game.cells.clear()
            tour.teleport(game,target)
            identity=tour.identity(game,directory)
            assert identity['role']=='Wizard' and identity['branch']==branch
            records.append(dict(target=target,identity=identity,
                                **checks.material(game.cells.values(),material)))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    # A separately created original Knight Quest cannot inherit Wizard material.
    case=dict(next(c for c in tour.catalog() if c['id']=='Kni-strt'))
    other_run=ART/('wizard-other-role-'+__import__('uuid').uuid4().hex)
    other_run.mkdir()
    other_metadata=tour.prepare(case,'inspection',other_run)
    other=dict(run=str(other_run),metadata=other_metadata)
    run,directory,game=prepare.clone(other,'wizard-production-other-role')
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity['role']=='Knight' and identity['branch']=='The Quest' and identity['level']==1
        known=[c for c in game.cells.values() if c['tile'] not in (1469,1470)]
        assert all(c.get('material') not in ('wizard','wizard-goal') for c in known),'Wizard-specific material leaked into Knight home'
        records.append(dict(target='Kni-strt',identity=identity,wizardRegionLeakageExcluded=True,
                            expectedKnightStageMaterials=[None,'quest-earth'],
                            **checks.material(game.cells.values(),[None,'quest-earth'])))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    print('PASS Wizard/main dungeon/Mines/other-role Quest boundaries',flush=True)
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--compare-baseline',action='store_true',help='Assert exact restored canonical cells and terrain/memory/light match preserved baseline.')
    args=parser.parse_args()
    evidence=prepare.source_evidence()
    print('PASS five Wizard stage sources and quest lore match bundled pinned upstream',flush=True)
    if args.sources_only:
        return
    rows=json.loads(INDEX.read_text())
    assert len(rows)==6
    for row in rows:
        assert row['metadata']['case']['source'] is None
        assert row['metadata']['generationRecipe']=='original-world-selected'
        assert row['metadata'].get('expectedMaterial')==prepare.MATERIALS[row['metadata']['case']['id'].split('-')[1]],'Refresh with --material wizard after rebuilding'
    results=[]
    for row in rows:
        results.append(check(row))
        checks.write(RESULTS,dict(source=evidence,checks=results))
    assert any('ordinaryMove' in result for result in results),'No successful ordinary dry-floor move'
    assert any(s['category']=='water' for r in results for s in r['inspection'])
    assert any(s['category']=='iron-bars' for r in results for s in r['inspection']),'No original perceived iron bars'
    assert any(s['category']=='cloud' for r in results for s in r['inspection']),'No original perceived clouds'
    assert any('originalAltarPerception' in r for r in results),'Original altar perception not checked'
    assert any('ordinaryBarCollision' in r for r in results),'Original bars collision not checked'
    # Water occupants may remain unseen at the original tower arrivals; do
    # not reveal or replace them to fill a visual test quota.
    assert any(r['knownGroundBeneathOccupants']['dry'] for r in results),'No known dry ground beneath occupants'
    home=next(r for r in rows if r['metadata']['case']['id']=='Wiz-strt' and r['metadata']['mode']=='inspection')
    comparison=None
    if args.compare_baseline:
        baseline=json.loads((ART/'wizard-canonical-quest-engine.json').read_text())
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
