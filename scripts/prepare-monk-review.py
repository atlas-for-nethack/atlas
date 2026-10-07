#!/usr/bin/env python3
"""Capture unchanged world-selected Monk maps for a visual proposal.

No production artwork, map geometry, actors, lighting or loot is replaced.
Wizard travel, protection, reveal and supplied test inventory are disclosed.
The generated manifest contains displayed engine cells, not source-map fixtures.
"""
from collections import Counter
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('monk_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
outdoor_spec = importlib.util.spec_from_file_location('quest_outdoors',ROOT/'scripts/test-quest-outdoors.py')
outdoors = importlib.util.module_from_spec(outdoor_spec)
outdoor_spec.loader.exec_module(outdoors)
INDEX = ART/'monk-review-prepared.json'
MANIFEST = ART/'monk-baseline-review-manifest.json'
STAGES = [('strt','home'), ('fila','upper-filler'), ('loca','locate'),
          ('filb','lower-filler'), ('goal','goal')]


def expected(suffix, policy):
    if policy == 'canonical':
        return None
    return outdoors.expected('Mon-'+suffix,True,{'loca':'caveman','goal':'gehennom'}.get(suffix))


def open_game(directory):
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    (directory/'monk.nethackrc').write_text('')
    module=tour.load_game_module()
    class ClearAwareGame(module.Game):
        def next(self):
            event=super().next()
            if event['type']=='clear' and event.get('window')=='map':
                self.cells.clear()
            return event
    return ClearAwareGame(directory,name='wizard',options=checks.OPTIONS,config=Path('monk.nethackrc'))


def clone(row, label):
    # Retain every source checkpoint; only this disposable clone is restored.
    run = ART/('monk-'+label+'-'+uuid.uuid4().hex)
    run.mkdir()
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat')
    return run,directory,open_game(directory)


def source_evidence():
    sources = {}
    archive = tour.RES/'Source/nethack-500-src.tgz'
    with tarfile.open(archive) as upstream:
        for suffix, _ in STAGES:
            filename = 'Mon-'+suffix+'.lua'
            found = [m for m in upstream.getmembers() if m.name.endswith('/dat/'+filename)]
            assert len(found) == 1, found
            original = upstream.extractfile(found[0]).read()
            assert original == (tour.DAT/filename).read_bytes(), filename+' differs from pinned upstream'
            sources[filename] = tour.digest(tour.DAT/filename)
        # Quest narrative and place names are pinned source evidence too.
        for relative in ('dat/quest.lua','src/role.c'):
            matches=[m for m in upstream.getmembers() if m.name.endswith('/'+relative)]
            assert len(matches)==1,matches
            original=upstream.extractfile(matches[0]).read()
            maintained=ROOT/'vendor/NetHack-5.0.0'/relative
            assert original==maintained.read_bytes(),relative+' differs from pinned upstream'
            sources[relative]=tour.digest(maintained)
    return dict(sources=sources, unchangedUpstreamSource=True,
                upstreamArchiveSHA256=tour.digest(archive))


def privacy(cells, mode, expected_material=None):
    return outdoors.material(cells,expected_material,mode)


def worker(suffix, mode, material):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == 'Mon-'+suffix))
    # The generic catalog reloads filler scripts as targeted fixtures. Clearing
    # that optional source preserves this world's already generated filler.
    case['source'] = None
    run = ART/('monk-original-'+suffix+'-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case, mode, run)
    assert metadata['identity']['branch'] == 'The Quest'
    assert metadata['identity']['role'] == 'Monk'
    cells = checks.displayed_cells(run/'preparation.jsonl')
    expected_material = expected(suffix, material)
    metadata.update(source_evidence(), checkpoint=str(run), displayedCells=cells,
        shapeBounds=[1,0,79,21], worldSelected=True, designPreviewOnly=expected_material is None,
        expectedMaterial=expected_material, integratedMaterial=expected_material is not None,
        gameplayPlaytestPerformed=False, perception=privacy(cells,mode,expected_material),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    floors=Counter(c['tile'] for c in cells if c.get('char') == '.')
    assert floors,'No displayed plain ground for native readiness check'
    metadata['testTerrainTiles']=[next(tile for tile in (1291,1292) if floors[tile])]
    metadata.update(scene=dict(STAGES)[suffix] if mode=='inspection' else 'home-exploration', label='Monk '+dict(STAGES)[suffix], stageMaterialPolicy=material,
        sourceScript='vendor/NetHack-5.0.0/dat/Mon-'+suffix+'.lua')
    metadata['setup'].append('Original world-selected Monk stage. Source reload removed for fillers; no des.reset_level, source reload, terrain replacement, actor replacement, custom lighting or local viewpoint teleport. Mapped distant terrain does not prove local encounters or route progression.')
    row=dict(run=str(run),metadata=metadata)
    restored_baseline(row)
    checks.write(run/'metadata.json', metadata)
    print(json.dumps(row))


def restored_baseline(row):
    """Freeze the same ordinary-restore boundary used after engine rebuilds.

    Wizard-map trap appearances can redraw as statues on restore. Keep raw
    preparation cells separately rather than attributing this upstream change
    to the visual material or modifying a preserved checkpoint.
    """
    m=row['metadata']
    source_save=Path(row['run'])/'game/save'
    save_hashes={p.name:tour.digest(p) for p in source_save.iterdir() if p.is_file()}
    assert save_hashes,'No source save to preserve'
    if 'preservedSaveHashes' in m:
        assert m['preservedSaveHashes']==save_hashes,'Original checkpoint changed'
    else:
        m['preservedSaveHashes']=save_hashes
    run,directory,game=clone(row,'freeze-'+m['case']['id']+'-'+m['mode'])
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        assert tour.identity(game,directory)==m['identity']
        assert list(game.cursor)==list(m['arrival'])
        cells=list(game.cells.values())
        if 'canonicalBaselineCells' in m:
            before={(c['x'],c['y']):c for c in m['canonicalBaselineCells']}
            for c in cells:
                p=c['x'],c['y']
                assert p in before
                for field in ('tile','groundTile','char','color','pet'):
                    assert c.get(field)==before[p].get(field),(m['case']['id'],p,field)
        else:
            m['canonicalBaselineCells']=cells
            m['preparedEngine']=m['engine']
            m['preparationDisplayedCells']=m['displayedCells']
        m.update(displayedCells=cells,
            displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
            independentRestoreEvidence=str(run/'engine.jsonl'),independentRestoreVerified=True,
            comparisonBoundary='Ordinary restore of preserved original checkpoint',
            perception=privacy(cells,m['mode'],m['expectedMaterial']))
        floors=Counter(c['tile'] for c in cells if c.get('char')=='.')
        m['testTerrainTiles']=[next(t for t in (1291,1292) if floors[t])]
        game.finish(automatic=True)
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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker', choices=[s for s,_ in STAGES])
    parser.add_argument('--refresh',action='store_true',help='Restore original checkpoints with rebuilt engine, preserving source saves and canonical baseline')
    parser.add_argument('--mode', choices=['inspection','exploration'],default='inspection')
    parser.add_argument('--material', choices=['canonical','integrated'],default='canonical')
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.mode,args.material)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX,INDEX.with_name('monk-review-prepared-before-'+stamp+'.json'))
    previous=json.loads(INDEX.read_text()) if args.refresh else []
    def obtain(suffix,mode):
        if not args.refresh:
            return json.loads(subprocess.check_output([sys.executable,str(Path(__file__)),
                '--worker',suffix,'--mode',mode,'--material',args.material],text=True))
        row=next(r for r in previous if r['metadata']['case']['id']=='Mon-'+suffix and r['metadata']['mode']==mode)
        m=row['metadata']
        m.update(expectedMaterial=expected(suffix,args.material),stageMaterialPolicy=args.material,
            engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            designPreviewOnly=args.material=='canonical',integratedMaterial=args.material=='integrated')
        restored_baseline(row)
        return row
    rows=[]
    scenes={}
    for suffix,key in STAGES:
        row=obtain(suffix,'inspection')
        if suffix == 'strt':
            restore_home(row)
        rows.append(row)
        scenes[key]=scene(row,'Actual Monk '+row['metadata']['case']['label'])
        if not args.refresh:
            checks.write(INDEX,rows)
        checks.write(MANIFEST,dict(scenes=scenes,reviewOnly=True))
        print('PREPARED',key,row['run'],flush=True)
    row=obtain('strt','exploration')
    rows.append(row)
    scenes['home-exploration']=scene(row,'Actual unrevealed Monk home arrival')
    home=scenes['home']
    doors=[c for c in home['cells'] if 1285<=c['tile']<=1288]
    assert doors,'No mapped original monastery doors'
    # Crops select only actual displayed geometry. No source-coordinate or
    # hidden-room guesses are used, so upstream map flips remain intact.
    door=min(doors,key=lambda c:(c['x'],c['y']))
    scenes['gate']=crop(home,'Original monastery gate', (door['x'],door['y']))
    center=sorted(doors,key=lambda c:c['x'])[len(doors)//2]
    scenes['home-detail']=crop(home,'Original monastery and temple',
                               (center['x'],center['y']),width=26,height=15)
    goal=scenes['goal']
    altar=next((c for c in goal['cells'] if 1303<=c['tile']<=1308),None)
    if altar:
        scenes['goal-detail']=crop(goal,'Original dry clearing, altar and lava',
            (altar['x'],altar['y']),width=26,height=15)
    locate_row=next(r for r in rows if r['metadata']['case']['id']=='Mon-loca')
    arrival=locate_row['metadata']['arrival']
    scenes['locate-detail']=crop(scenes['locate'],'Original cave arrival',
        (arrival[0]-1,arrival[1]),width=26,height=15)
    checks.write(INDEX,rows)
    checks.write(MANIFEST,dict(scenes=scenes,reviewOnly=True,
        stageMaterials={suffix:expected(suffix,args.material) for suffix,_ in STAGES},
        note='Original engine display with explicitly checked canonical or integrated material selection. No campaign completion is claimed.'))
    print('MANIFEST',MANIFEST,flush=True)


if __name__=='__main__':
    main()
