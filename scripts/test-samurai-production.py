#!/usr/bin/env python3
"""Check Samurai presentation in isolated original-world engine checkpoints.

After building, prepare with prepare-samurai-review.py --material samurai.
This checks five stages, unrevealed home, ordinary movement, exact restoration
and role/branch boundaries. It does not claim quest completion or combat testing.
Use --native for twelve bounded packaged-app captures instead of engine checks.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('samurai_prepare',ROOT/'scripts/prepare-samurai-review.py')
prepare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks,tour=prepare.checks,prepare.tour
INDEX=prepare.INDEX
RESULTS=ART/'samurai-production-engine.json'
NATIVE=ART/'samurai-production-native.json'
STEPS=checks.STEPS


def check(row):
    m=row['metadata']
    expected=prepare.MATERIALS[m['case']['id'].split('-')[1]]
    run,directory,game=checks.clone(row,'samurai-production-'+m['case']['id']+'-'+m['mode'])
    previous=[]
    result=dict(case=m['case']['id'],mode=m['mode'],run=str(run),setup=m['setup'],
                sourceCheckpoint=row['run'],engine=tour.digest(tour.RES/'engine/nethack'))
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity==m['identity'] and identity['role']=='Samurai'
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        result.update(identity=identity,material=checks.material(game.cells.values(),expected))
        # Compare actual canonical foreground and ground fields with this
        # checkpoint's engine capture, not inferred room-purpose information.
        before={(c['x'],c['y']):c for c in m['displayedCells']}
        for p,c in game.cells.items():
            assert p in before
            for field in ('tile','groundTile','char','color','pet'):
                assert c.get(field)==before[p].get(field),(m['case']['id'],p,field,c,before[p])
        result['canonicalForegroundAndGroundPreserved']=True
        turn=game.turn
        samples=[]
        for category,criterion in (
            ('wall',lambda c:1273<=c['tile']<=1283),
            ('door',lambda c:1286<=c['tile']<=1290),
            ('ground',lambda c:1291<=c['tile']<=1296),
            ('water',lambda c:c['tile']==1314)):
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
        origin=game.cursor
        adjacent=next(((origin[0]+dx,origin[1]+dy,key) for dx,dy,key in STEPS
            if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('char')=='.'),None)
        if adjacent:
            checks.settle(game,game.command(adjacent[2]))
            if game.cursor==tuple(adjacent[:2]):
                assert game.turn>turn
                result['ordinaryMove']=dict(origin=origin,destination=game.cursor,turns=game.turn-turn)
            else:
                result['movementDeferred']='Original occupant or upstream condition blocked the attempt; no position override used.'
        else:
            result['movementDeferred']='No adjacent displayed plain floor at the original arrival.'
        checks.material(game.cells.values(),expected)
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
        print('PASS',m['case']['id'],m['mode'],'material, canonical appearance, inspection and exact restore',flush=True)
        return result
    finally:
        checks.cleanup(run,game,previous)


def boundaries(home):
    run,directory,game=checks.clone(home,'samurai-production-boundaries')
    records=[]
    try:
        checks.settle(game)
        for target,material,branch in (
            ('oracle',None,'The Dungeons of Doom'),
            ('minetn-',['mines','mines-built'],'The Gnomish Mines'),
            ('Sam-strt',prepare.MATERIALS['strt'],'The Quest')):
            game.cells.clear()
            tour.teleport(game,target)
            identity=tour.identity(game,directory)
            assert identity['role']=='Samurai' and identity['branch']==branch
            records.append(dict(target=target,identity=identity,
                                **checks.material(game.cells.values(),material)))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    # A separately created original Rogue Quest cannot inherit Samurai material.
    other=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
        'prepare','--case','Rog-strt','--mode','inspection'],text=True))
    run,directory,game=checks.clone(other,'samurai-production-other-role')
    try:
        checks.settle(game)
        identity=tour.identity(game,directory)
        assert identity['role']=='Rogue' and identity['branch']=='The Quest'
        records.append(dict(target='Rog-strt',identity=identity,
                            **checks.material(game.cells.values(),None)))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)
    print('PASS Samurai/main dungeon/Mines/other-role Quest boundaries',flush=True)
    return records


def native(rows,resume):
    spec=importlib.util.spec_from_file_location('garden_review',ROOT/'scripts/build-garden-swamp-review.py')
    review=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    home=[]
    focus=[]
    manifest=json.loads(prepare.MANIFEST.read_text())['scenes']
    for source in rows:
        m=source['metadata']
        suffix=m['case']['id'].split('-')[1]
        if suffix not in ('strt','fila','goal'):
            continue
        row=copy.deepcopy(source)
        meta=row['metadata']
        if suffix=='strt' and m['mode']=='inspection':
            x,y,w,h=manifest['home-detail']['cropBounds']
            meta['shapeBounds']=[x+1,y,w,h]
        elif suffix=='strt':
            known=[c for c in m['displayedCells'] if c['tile'] not in (1469,1470)]
            x=(min(c['x'] for c in known)+max(c['x'] for c in known))//2
            y=(min(c['y'] for c in known)+max(c['y'] for c in known))//2
            meta['shapeBounds']=[max(1,min(68,x-6)),max(0,min(9,y-6)),12,12]
        x,y,w,h=meta['shapeBounds']
        cells=[c for c in m['displayedCells'] if x<=c['x']<x+w and y<=c['y']<y+h]
        floor=next(c['tile'] for c in cells if c['tile'] in (1291,1292))
        meta['testTerrainTiles']=[floor]
        (home if suffix=='strt' else focus).append(row)
    assert len(home)==2 and len(focus)==2
    results=review.capture('samurai-production-home',classic=True,rows=home,resume=resume)
    results+=review.capture('samurai-production-focus',classic=False,rows=focus,resume=resume)
    for result in results:
        cells=review.review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
        source=next(row for row in rows if row['run']==result['sourceCheckpoint'])
        expected=prepare.MATERIALS[source['metadata']['case']['id'].split('-')[1]]
        result.update(checks.material(cells,expected),unchangedArtwork=False,
                      approvedSamuraiArchitecture=True)
    assert len(results)==12,len(results)
    checks.write(NATIVE,results)
    body=['<!doctype html><meta charset="utf-8"><title>Samurai production review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d6bb84}</style>',
        '<h1>Samurai quest: packaged-app captures</h1>',
        '<p>Original world-selected maps. Documented wizard inspection setup; unrevealed home uses ordinary perception. Every edition gets a separate copy of its checkpoint. This is environment verification, not a completed quest.</p>']
    for r in results:
        image=Path(r['screenshot']).relative_to(ART).as_posix()
        label=html.escape(r['label']+' / '+r['mode']+' / '+r['tileset'])
        body.append('<h2>'+label+'</h2><a href="'+image+'"><img src="'+image+'" alt="'+label+'"></a>')
    gallery=ART/'samurai-native-review.html'
    gallery.write_text('\n'.join(body)+'\n')
    print('REVIEW',gallery,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    evidence=prepare.source_evidence()
    print('PASS all five Samurai Lua sources match bundled pinned upstream',flush=True)
    if args.sources_only:
        return
    rows=json.loads(INDEX.read_text())
    assert len(rows)==6
    for row in rows:
        assert row['metadata']['case']['source'] is None
        assert row['metadata'].get('expectedMaterial')==prepare.MATERIALS[row['metadata']['case']['id'].split('-')[1]],'Reprepare with --material samurai after the build'
    if args.engine or not args.native:
        results=[]
        for row in rows:
            results.append(check(row))
            checks.write(RESULTS,dict(source=evidence,checks=results))
        assert any('ordinaryMove' in result for result in results),'No successful ordinary floor move observed'
        home=next(r for r in rows if r['metadata']['case']['id']=='Sam-strt' and r['metadata']['mode']=='inspection')
        records=boundaries(home)
        checks.write(RESULTS,dict(source=evidence,checks=results,boundaries=records,passed=True))
    if args.native:
        native(rows,args.resume)


if __name__=='__main__':
    main()
