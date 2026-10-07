#!/usr/bin/env python3
"""Check original Valkyrie Quest maps through the packaged engine.

No terrain or occupants are replaced. Wizard setup, protection, reveal and
branch travel are recorded. Source saves remain untouched; no app is launched.
This verifies environment presentation, not quest admission or completion.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('valkyrie_prepare',ROOT/'scripts/prepare-valkyrie-review.py')
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks,tour=prepare.checks,prepare.tour
RESULTS=ART/'valkyrie-quest-engine-results.json'


def check(row,policy):
    m=row['metadata']
    suffix=m['case']['id'].split('-')[1]
    expected=prepare.expected(suffix,policy)
    run,directory,game=prepare.clone(row,'check-'+suffix+'-'+m['mode'])
    previous=[]
    result=dict(case=m['case']['id'],mode=m['mode'],run=str(run),sourceCheckpoint=row['run'],
        setup=m['setup'],engine=tour.digest(tour.RES/'engine/nethack'),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),expectedMaterial=expected)
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity==m['identity'] and identity['role']=='Valkyrie'
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        result.update(identity=identity,perception=prepare.privacy(list(game.cells.values()),m['mode'],expected))
        baseline={(c['x'],c['y']):c for c in m.get('canonicalBaselineCells',m['displayedCells'])}
        for p,c in game.cells.items():
            assert p in baseline
            for field in ('tile','groundTile','char','color','pet'):
                assert c.get(field)==baseline[p].get(field),(suffix,p,field,c,baseline[p])
        result['canonicalAppearanceAndGroundPreserved']=True
        turn=game.turn
        samples=[]
        for category,predicate in (
            ('wall',lambda c:1273<=c['tile']<=1283),
            ('door',lambda c:1285<=c['tile']<=1288),
            ('ground',lambda c:c['tile'] in (1291,1292,1293,1294,1295,1296)),
            ('altar',lambda c:1303<=c['tile']<=1308),
            ('lava',lambda c:c['tile']==1316),
            ('ice',lambda c:c['tile']==1315),
            ('water',lambda c:c['tile']==1314),
            ('drawbridge',lambda c:1318<=c['tile']<=1321),
            ('perceived-trap',lambda c:c.get('char')=='^'),
            ('foreground-on-known-ground',lambda c:c.get('groundTile') is not None and c['tile']<1273)):
            cell=next((c for c in game.cells.values() if predicate(c)),None)
            if cell:
                samples.append(dict(category=category,cell=cell,description=game.inspect(cell['x'],cell['y'])))
        assert samples and game.turn==turn
        result.update(inspection=samples,turnFreeInspection=True,
            groundUnderForegroundObserved=any(s['category']=='foreground-on-known-ground' for s in samples))
        if suffix=='strt' and m['mode']=='inspection':
            for category,word in (('ice','ice'),('water','pool'),('lava','lava')):
                sample=next((s for s in samples if s['category']==category),None)
                assert sample and word in sample['description'].lower(),(category,samples)
            result['originalIceWaterLavaPerceived']=True
        if suffix in ('filb','goal'):
            lava=next((s for s in samples if s['category']=='lava'),None)
            assert lava and 'lava' in lava['description'].lower(),samples
            result['originalLavaPerceived']=True
        if m['mode']=='exploration':
            unknown=[c for c in game.cells.values() if c['tile']==1469]
            assert unknown
            samples=[]
            for c in unknown[::max(1,len(unknown)//8)]:
                description=game.inspect(c['x'],c['y'])
                assert 'unexplored' in description.lower(),description
                samples.append(dict(cell=c,description=description))
            assert game.turn==turn
            result['unknownInspection']=samples
        origin=game.cursor
        adjacent=next(((origin[0]+dx,origin[1]+dy,key) for dx,dy,key in checks.STEPS
            if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('char')=='.'),None)
        if adjacent:
            checks.settle(game,game.command(adjacent[2]))
            if game.cursor==tuple(adjacent[:2]):
                assert game.turn>turn
                result['ordinaryMove']=dict(origin=origin,destination=game.cursor,turns=game.turn-turn,
                    destinationDisplayedCell=game.cells[game.cursor])
            else:
                result['movementDeferred']='Original occupant or upstream condition blocked the attempt; no position override used.'
        else:
            result['movementDeferred']='No adjacent perceived plain floor at original arrival.'
        terrain=checks.terrain_snapshot(game,directory)
        result['originalTerrainCounts']=dict(Counter(t[2] for t in terrain))
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        previous=list(game.events)
        game=prepare.open_game(directory)
        checks.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert tour.identity(game,directory)==identity
        assert checks.terrain_snapshot(game,directory)==terrain
        result.update(restored=True,position=position,turn=turn,exactTerrainLightingAndMemoryRestore=True,
            restoredPerception=prepare.privacy(list(game.cells.values()),m['mode'],expected))
        game.finish(automatic=True)
        print('PASS',m['case']['id'],m['mode'],'perception, inspection and exact restore',flush=True)
        return result
    finally:
        checks.cleanup(run,game,previous)


def boundaries(home,policy):
    run,directory,game=prepare.clone(home,'boundaries')
    records=[]
    try:
        checks.settle(game)
        # Enter goal from outside: home quest admission remains engine-owned.
        for target,material,branch in (
            ('oracle',None,'The Dungeons of Doom'),
            ('minetn-','mines','The Gnomish Mines'),
            ('Val-goal',prepare.expected('goal',policy),'The Quest'),
            ('Val-loca',prepare.expected('loca',policy),'The Quest'),
            ('Val-strt',None,'The Quest')):
            game.cells.clear()
            tour.teleport(game,target)
            identity=tour.identity(game,directory)
            assert identity['role']=='Valkyrie' and identity['branch']==branch,identity
            records.append(dict(target=target,identity=identity,**checks.material(game.cells.values(),material)))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    for suffix in ('strt','goal'):
        other_run=ART/('valkyrie-other-role-'+suffix+'-'+uuid.uuid4().hex)
        other_run.mkdir()
        case=dict(next(c for c in tour.catalog() if c['id']=='Kni-'+suffix))
        metadata=tour.prepare(case,'inspection',other_run)
        other=dict(run=str(other_run),metadata=metadata)
        run,directory,game=prepare.clone(other,'other-role-check-'+suffix)
        try:
            checks.settle(game)
            identity=tour.identity(game,directory)
            assert identity['role']=='Knight' and identity['branch']=='The Quest'
            records.append(dict(target=case['id'],identity=identity,**checks.material(game.cells.values(),[None,'quest-earth'] if suffix=='strt' else 'caveman')))
            game.finish(automatic=True)
        finally:
            checks.cleanup(run,game)
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--material',choices=('canonical','integrated'),default='canonical')
    args=parser.parse_args()
    evidence=prepare.source_evidence()
    print('PASS five Valkyrie sources match bundled pinned upstream',flush=True)
    if args.sources_only:return
    if args.prepare:
        subprocess.check_call([sys.executable,str(ROOT/'scripts/prepare-valkyrie-review.py'),'--material',args.material])
    rows=json.loads(prepare.INDEX.read_text())
    assert len(rows)==6
    for row in rows:
        assert row['metadata']['case']['source'] is None,'Original filler must not reload source terrain'
    if args.engine:
        result=dict(source=evidence,engine=tour.digest(tour.RES/'engine/nethack'),
            dataSHA256=tour.digest(tour.RES/'engine/nhdat'),policy=args.material,checks=[])
        for row in rows:
            result['checks'].append(check(row,args.material))
            checks.write(RESULTS,result)
        assert any('ordinaryMove' in r for r in result['checks'])
        home=next(r for r in rows if r['metadata']['case']['id']=='Val-strt' and r['metadata']['mode']=='inspection')
        result['boundaries']=boundaries(home,args.material)
        result['passed']=True
        checks.write(RESULTS,result)


if __name__=='__main__':main()
