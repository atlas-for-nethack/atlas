#!/usr/bin/env python3
"""Capture unchanged world-selected Wizard maps for a visual proposal.

No production artwork, map geometry, actors, lighting or loot is replaced.
Wizard travel, protection, reveal and supplied test inventory are disclosed.
The generated manifest contains displayed engine cells, not source-map fixtures.
"""
from collections import Counter
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('wizard_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'wizard-review-prepared.json'
MANIFEST = ART/'wizard-baseline-review-manifest.json'
STAGES = [('strt','home'), ('fila','upper-filler'), ('loca','locate'),
          ('filb','lower-filler'), ('goal','goal')]
MATERIALS={suffix:[None,'quest-earth'] if suffix in ('strt','loca') else None
           for suffix,_ in STAGES}


def clone(row,label):
    import tempfile
    run=Path(tempfile.mkdtemp(prefix='wizard-'+label+'-',dir=ART))
    directory=run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat')==tour.digest(tour.RES/'engine/nhdat'),'Stale checkpoint data'
    return run,directory,checks.open_game(directory)


def source_evidence():
    sources = {}
    archive = tour.RES/'Source/nethack-500-src.tgz'
    with tarfile.open(archive) as upstream:
        for filename in [*('Wiz-'+suffix+'.lua' for suffix,_ in STAGES),'quest.lua']:
            found = [m for m in upstream.getmembers() if m.name.endswith('/dat/'+filename)]
            assert len(found) == 1, found
            original = upstream.extractfile(found[0]).read()
            assert original == (tour.DAT/filename).read_bytes(), filename+' differs from pinned upstream'
            sources[filename] = tour.digest(tour.DAT/filename)
    return dict(sources=sources, unchangedUpstreamSource=True,
                upstreamArchiveSHA256=tour.digest(archive))


def privacy(cells, mode, expected_material=None):
    assert cells and len({(c['x'],c['y']) for c in cells}) == len(cells)
    hidden = [c for c in cells if c['tile'] in (1469,1470)]
    known = [c for c in cells if c['tile'] not in (1469,1470)]
    allowed = expected_material if isinstance(expected_material, (list, tuple)) else [expected_material]
    assert known and all(c.get('material') in allowed for c in known), (
        'Unexpected material: use --material wizard for the integrated build',expected_material)
    assert all(c['tile'] in (1291, 1292) or c.get('groundTile') in (1291, 1292)
               for c in known if c.get('material') == 'quest-earth'), 'Exterior earth requires safely known dry support'
    assert all('groundTile' not in c and 'material' not in c for c in hidden), 'Hidden ground or material disclosed'
    if mode == 'exploration':
        assert hidden, 'Exploration must retain unknown terrain'
    return dict(knownCells=len(known), hiddenCells=len(hidden),
                expectedMaterial=expected_material, noHiddenMaterial=True, noHiddenGround=True)


def worker(suffix, mode, material):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == 'Wiz-'+suffix))
    # The generic catalog reloads filler scripts as targeted fixtures. Clearing
    # that optional source preserves this world's already generated filler.
    case['source'] = None
    run = ART/('wizard-original-'+suffix+'-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case, mode, run)
    assert metadata['identity']['branch'] == 'The Quest'
    assert metadata['identity']['role'] == 'Wizard'
    cells = checks.displayed_cells(run/'preparation.jsonl')
    expected_material = None if material == 'canonical' else MATERIALS[suffix]
    metadata.update(source_evidence(), checkpoint=str(run), displayedCells=cells,
        shapeBounds=[1,0,79,21], worldSelected=True, designPreviewOnly=material == 'canonical',
        expectedMaterial=expected_material, integratedMaterial=material == 'wizard',
        gameplayPlaytestPerformed=False, perception=privacy(cells,mode,expected_material),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    floors=Counter(c['tile'] for c in cells if c.get('char') == '.')
    assert floors,'No displayed plain ground for native readiness check'
    metadata['testTerrainTiles']=[next(tile for tile in (1291,1292) if floors[tile])]
    metadata['generationRecipe']='original-world-selected'
    metadata['nativeReady']=True
    metadata['editionArchitecturePolicy']='Lantern and Soot & Brass Classic/Modern share architecture.'
    metadata['setup'].append('Original world-selected Wizard stage. No des.reset_level, source reload, terrain replacement, actor replacement, custom lighting or local viewpoint teleport. Mapped distant terrain does not prove local encounters or route progression.')
    checks.write(run/'metadata.json', metadata)
    print(json.dumps(dict(run=str(run),metadata=metadata)))


def refresh(original,material):
    """Retain the same generated world and source save after a port rebuild."""
    import copy
    run,directory,game=clone(original,'refreshed')
    try:
        checks.settle(game)
        metadata=copy.deepcopy(original['metadata'])
        assert tour.identity(game,directory)==metadata['identity']
        assert list(game.cursor)==list(metadata['arrival'])
        suffix=metadata['case']['id'].split('-')[1]
        expected=None if material=='canonical' else MATERIALS[suffix]
        cells=list(game.cells.values())
        metadata.update(checkpoint=str(run),sourceCheckpoint=original['run'],
            engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            dataSHA256=tour.digest(tour.RES/'engine/nhdat'),displayedCells=cells,
            expectedMaterial=expected,integratedMaterial=material=='wizard',designPreviewOnly=material=='canonical',
            perception=privacy(cells,metadata['mode'],expected),reviewRecipeSHA256=tour.digest(Path(__file__)))
        metadata['setup'].append('Same original world restored in a separate checkpoint using rebuilt port; source save retained.')
        game.finish(automatic=True)
        (run/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        checks.write(run/'metadata.json',metadata)
        return dict(run=str(run),metadata=metadata)
    finally:
        checks.cleanup(run,game)


def scene(row, label):
    m = row['metadata']
    x,y,w,h = m['shapeBounds']
    return dict(label=label,width=w,height=h,
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in m['displayedCells']
               if x<=c['x']<x+w and y<=c['y']<y+h],
        sourceCheckpoint=row['run'], engine=m['engine'], app=m['app'],
        identity=m['identity'], setup=m['setup'], originalBounds=m['shapeBounds'],
        reviewOnly=True, worldSelected=True, mode=m['mode'],
        perception=m['perception'])


def restore_home(row):
    """Verify the actual isolated save remains restorable, without using it up."""
    run,directory,game=clone(row,'review-home-restore')
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        assert tour.identity(game,directory) == row['metadata']['identity']
        assert list(game.cursor) == list(row['metadata']['arrival'])
        privacy(list(game.cells.values()),'inspection',row['metadata'].get('expectedMaterial'))
        row['metadata']['independentRestoreEvidence']=str(run/'engine.jsonl')
        row['metadata']['independentRestoreVerified']=True
        game.finish(automatic=True)
        checks.write(Path(row['run'])/'metadata.json',row['metadata'])
    finally:
        checks.cleanup(run,game)


def crop(base, label, center, width=22, height=13):
    x=max(0,min(base['width']-width,center[0]-width//2))
    y=max(0,min(base['height']-height,center[1]-height//2))
    return dict(base,label=label,width=width,height=height,cropBounds=[x,y,width,height],
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in base['cells']
               if x<=c['x']<x+width and y<=c['y']<y+height])


def native_rows(rows,scenes):
    """Checkpoint rows and framing only; root owns native app launches."""
    import copy
    framed=[]
    for original in rows:
        row=copy.deepcopy(original)
        meta=row['metadata']
        suffix=meta['case']['id'].split('-')[1]
        key=dict(strt='home-detail',fila='upper-filler',loca='locate-detail',filb='lower-filler',goal='barred-hall')[suffix]
        if meta['mode']=='exploration':
            known=[c for c in meta['displayedCells'] if c['tile'] not in (1469,1470)]
            x=(min(c['x'] for c in known)+max(c['x'] for c in known))//2
            y=(min(c['y'] for c in known)+max(c['y'] for c in known))//2
            meta['shapeBounds']=[max(1,min(66,x-7)),max(0,min(7,y-7)),14,14]
        elif key in scenes and 'cropBounds' in scenes[key]:
            x,y,w,h=scenes[key]['cropBounds']
            meta['shapeBounds']=[x+1,y,w,h]
        x,y,w,h=meta['shapeBounds']
        cells=[c for c in meta['displayedCells'] if x<=c['x']<x+w and y<=c['y']<y+h]
        meta['testTerrainTiles']=[next(c['tile'] for c in cells if c['tile'] in (1291,1292))]
        meta['nativeFramingOnly']=True
        meta['nativeCapturePerformed']=False
        framed.append(row)
    checks.write(ART/'wizard-native-ready.json',framed)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh',action='store_true',help='Copy and restore existing checkpoints with the current packaged engine.')
    parser.add_argument('--worker', choices=[s for s,_ in STAGES])
    parser.add_argument('--mode', choices=['inspection','exploration'],default='inspection')
    parser.add_argument('--material', choices=['canonical','wizard'],default='wizard')
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.mode,args.material)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX,INDEX.with_name('wizard-review-prepared-before-'+stamp+'.json'))
    existing=json.loads(INDEX.read_text()) if args.refresh else []
    rows=[]
    scenes={}
    for suffix,key in STAGES:
        if args.refresh:
            original=next(r for r in existing if r['metadata']['case']['id']=='Wiz-'+suffix and r['metadata']['mode']=='inspection')
            row=refresh(original,args.material)
        else:
            row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__)),
                '--worker',suffix,'--mode','inspection','--material',args.material],text=True))
        if suffix == 'strt':
            restore_home(row)
        rows.append(row)
        scenes[key]=scene(row,'Actual Wizard '+row['metadata']['case']['label'])
        checks.write(INDEX,rows)
        checks.write(MANIFEST,dict(scenes=scenes,reviewOnly=True))
        print('PREPARED',key,row['run'],flush=True)
    if args.refresh:
        row=refresh(next(r for r in existing if r['metadata']['mode']=='exploration'),args.material)
    else:
        row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__)),
            '--worker','strt','--mode','exploration','--material',args.material],text=True))
    rows.append(row)
    scenes['home-exploration']=scene(row,'Actual unrevealed Wizard home arrival')
    home=scenes['home']
    doors=[c for c in home['cells'] if 1285<=c['tile']<=1288]
    assert doors,'No mapped original tower doors'
    # Crops select only actual displayed geometry. No source-coordinate or
    # hidden-room guesses are used, so upstream map flips remain intact.
    door=min(doors,key=lambda c:(c['x'],c['y']))
    scenes['gate']=crop(home,'Original tower door and mist', (door['x'],door['y']))
    center=sorted(doors,key=lambda c:c['x'])[len(doors)//2]
    scenes['home-detail']=crop(home,'Original Lonely Tower and cloud boundary',
                               (center['x'],center['y']),width=26,height=15)
    locate=scenes['locate']
    clouds=[c for c in locate['cells'] if c['tile']==1323]
    if clouds:
        c=clouds[len(clouds)//2]
        scenes['locate-detail']=crop(locate,'Original Tower of Darkness cloud and moat approach',(c['x'],c['y']),width=26,height=17)
    goal=scenes['goal']
    bars=[c for c in goal['cells'] if c['tile']==1289]
    assert bars,'Original goal barred halls absent'
    c=bars[len(bars)//2]
    scenes['barred-hall']=crop(goal,'Original barred goal dungeon halls',(c['x'],c['y']),width=28,height=17)
    altars=[c for c in goal['cells'] if c.get('char')=='_']
    if altars:
        altar=altars[0]
        scenes['altar']=crop(goal,'Original perceived goal altar, not a shrine',(altar['x'],altar['y']),width=22,height=15)
    checks.write(INDEX,rows)
    checks.write(MANIFEST,dict(scenes=scenes,reviewOnly=True,
        expectedMaterials={suffix:None if args.material=='canonical' else material for suffix,material in MATERIALS.items()},
        note='Original engine display with explicitly checked canonical or integrated material selection. No campaign completion is claimed.'))
    native_rows(rows,scenes)
    print('MANIFEST',MANIFEST,flush=True)


if __name__=='__main__':
    main()
