#!/usr/bin/env python3
"""Verify approved wall reuse using existing isolated Medusa checkpoints.

Restore all four unchanged upstream variants and the unrevealed arrival with
the rebuilt packaged engine. Compare canonical appearances with the original
review captures, inspect without turns, check region boundaries and capture
both families/editions in the native app. This does not complete the encounter.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('medusa_prepare',ROOT/'scripts/prepare-medusa-review.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
checks,tour=prepare.checks,prepare.tour
INDEX=ART/'medusa-production-prepared.json'
RESULTS=ART/'medusa-production-engine.json'


def baseline_restore(row):
    """Compare equal restore redraws, not pre-save remembered occupants."""
    digest=row['metadata']['engine']
    engine=next((p for p in (ROOT/'.build').glob('previous-app.*/Atlas.app/Contents/Resources/engine/nethack')
                 if tour.digest(p)==digest),None)
    assert engine,'Original packaged review engine unavailable for comparison'
    current=tour.RES
    game=None
    try:
        tour.RES=engine.parent.parent
        run,directory,game=checks.clone(row,'medusa-original-engine-restore')
        checks.settle(game)
        assert tour.identity(game,directory)==row['metadata']['identity']
        observed=copy.deepcopy(game.cells)
        game.finish(automatic=True)
        return observed,tour.digest(engine)
    finally:
        tour.RES=current
        if game is not None:checks.cleanup(run,game)


def restore(row):
    m=row['metadata']
    baseline,baseline_engine=baseline_restore(row)
    run,directory,game=checks.clone(row,'medusa-production-'+m['case']['id'])
    try:
        checks.settle(game)
        assert tour.identity(game,directory)==m['identity']
        assert list(game.cursor)==list(m['arrival'])
        observed=list(game.cells.values())
        assert set(game.cells)==set(baseline)
        for c in observed:
            old=baseline[c['x'],c['y']]
            for field in ('tile','groundTile','char','color','pet'):
                assert c.get(field)==old.get(field),(m['case']['id'],field,c,old)
        context=checks.material(observed,prepare.MATERIALS)
        turn=game.turn
        inspection=[]
        for label,criterion in (
            ('wall',lambda c:1273<=c['tile']<=1283),
            ('water',lambda c:c['tile']==1314),
            ('unknown',lambda c:c['tile']==1469),
            ('hero',lambda c:(c['x'],c['y'])==game.cursor)):
            c=next((c for c in observed if criterion(c)),None)
            if c:
                description=game.inspect(c['x'],c['y'])
                if label=='unknown':assert 'unexplored' in description.lower()
                inspection.append(dict(category=label,description=description))
        assert game.turn==turn
        game.finish(automatic=True)
        meta=copy.deepcopy(m)
        meta.update(checkpoint=str(run),displayedCells=observed,expectedMaterial=prepare.MATERIALS,
            integratedMaterial=True,engine=tour.digest(tour.RES/'engine/nethack'),
            app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            originalReviewCheckpoint=row['run'],productionRestoreEvidence=str(run/'engine.jsonl'))
        checks.write(run/'metadata.json',meta)
        result=dict(case=m['case']['id'],run=str(run),material=context,
            canonicalForegroundAndGroundPreserved=True,baselineEngine=baseline_engine,
            turnFreeInspection=inspection,
            restoredIdentity=meta['identity'],sourceCheckpoint=row['run'])
        print('PASS production restore',m['case']['id'],flush=True)
        return dict(run=str(run),metadata=meta),result
    finally:
        checks.cleanup(run,game)


def boundaries(row):
    run,directory,game=checks.clone(row,'medusa-boundaries')
    try:
        checks.settle(game)
        depth=row['metadata']['identity']['depth']
        records=[]
        for destination,expected in ((depth-1,None),(depth,prepare.MATERIALS),(1,None)):
            checks.travel_depth(game,destination)
            identity=tour.identity(game,directory)
            assert identity['depth']==destination
            records.append(dict(identity=identity,material=checks.material(game.cells.values(),expected)))
        checks.travel_depth(game,depth)
        checks.material(game.cells.values(),prepare.MATERIALS)
        game.finish(automatic=True)
        print('PASS Medusa/adjacent dungeon/start boundaries',flush=True)
        return records
    finally:
        checks.cleanup(run,game)


def native(rows):
    spec=importlib.util.spec_from_file_location('medusa_native',ROOT/'scripts/build-garden-swamp-review.py')
    review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
    chosen=[r for r in rows if r['metadata']['case']['id'] in ('medusa-4','medusa-world')]
    results=review.capture('medusa-production',classic=True,rows=chosen)
    assert len(results)==8
    for result in results:
        cells=review.review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
        result.update(checks.material(cells,prepare.MATERIALS),approvedSokobanWallReuse=True)
    checks.write(ART/'medusa-production-native.json',results)
    body=['<!doctype html><meta charset="utf-8"><title>Medusa production review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d6bb84}</style>',
        '<h1>Medusa: approved Sokoban walls in the packaged app</h1>',
        '<p>All four editions, with a targeted original layout and unrevealed world-selected arrival. Same isolated checkpoints as the approved review. This verifies presentation and restoration, not a completed encounter.</p>']
    for r in results:
        image=Path(r['screenshot']).relative_to(ART).as_posix()
        label=html.escape(r['label']+' / '+r['mode']+' / '+r['tileset'])
        body.append('<h2>'+label+'</h2><a href="'+image+'"><img src="'+image+'" alt="'+label+'"></a>')
    target=ART/'medusa-native-review.html';target.write_text('\n'.join(body)+'\n')
    print('REVIEW',target,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    if args.native:
        native(json.loads(INDEX.read_text()));return
    originals=json.loads(prepare.INDEX.read_text())
    assert len(originals)==5
    rows,results=[],[]
    source=prepare.source_evidence()
    for original in originals:
        row,result=restore(original);rows.append(row);results.append(result)
        checks.write(INDEX,rows)
        checks.write(RESULTS,dict(source=source,restores=results))
    selected=next(r for r in rows if r['metadata']['case']['id']=='medusa-world')
    records=boundaries(selected)
    checks.write(RESULTS,dict(source=source,restores=results,boundaries=records,passed=True))


if __name__=='__main__':main()
