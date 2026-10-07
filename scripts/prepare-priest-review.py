#!/usr/bin/env python3
"""Prepare unmodified world-selected Priest quest stages with packaged NetHack.

Wizard protection, level travel, map reveal and test inventory are disclosed.
The normal quest filler recipes reload source layouts. This study clears that
optional reload, preserving each world's original randomly generated filler.
No renderer fixture supplies terrain, occupants, lighting or altar alignment.
"""
import argparse
from collections import Counter
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
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('priest_shared', ROOT/'scripts/test-valley-level.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
tour = shared.tour
outdoor_spec = importlib.util.spec_from_file_location('quest_outdoors',ROOT/'scripts/test-quest-outdoors.py')
outdoors = importlib.util.module_from_spec(outdoor_spec)
outdoor_spec.loader.exec_module(outdoors)
INDEX = ART/'priest-review-prepared.json'
MANIFEST = ART/'priest-baseline-review-manifest.json'
STAGES = [('strt','home'),('fila','upper-filler'),('loca','locate'),
          ('filb','lower-filler'),('goal','goal')]


def source_evidence():
    sources = {}
    archive = tour.RES/'Source/nethack-500-src.tgz'
    with tarfile.open(archive) as upstream:
        for filename in [*('Pri-'+s+'.lua' for s,_ in STAGES),'quest.lua']:
            members = [m for m in upstream.getmembers() if m.name.endswith('/dat/'+filename)]
            assert len(members) == 1, members
            original = upstream.extractfile(members[0]).read()
            assert original == (tour.DAT/filename).read_bytes(), filename+' differs from pinned upstream'
            sources[filename] = tour.digest(tour.DAT/filename)
    sources['src/role.c'] = tour.digest(ROOT/'vendor/NetHack-5.0.0/src/role.c')
    return dict(sources=sources,unchangedUpstreamSource=True,
                upstreamArchiveSHA256=tour.digest(archive))


def expected_material(identifier, integrated):
    if not integrated:
        return None
    return outdoors.expected(identifier,True,{'Pri-strt':None,'Pri-fila':None,'Pri-filb':None,
            'Pri-loca':'priest-temple','Pri-goal':'gehennom'}[identifier])


def privacy(cells, mode, expected):
    checked = outdoors.material(cells, expected, mode)
    if mode == 'exploration':
        assert checked['hiddenCells'], 'Exploration must retain unknown terrain'
    return dict(checked,noHiddenGround=True,noHiddenMaterial=True)


def worker(suffix, mode, integrated):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == 'Pri-'+suffix))
    case['source'] = None
    run = ART/('priest-original-'+suffix+'-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case,mode,run)
    assert metadata['identity']['branch'] == 'The Quest'
    assert metadata['identity']['role'] == 'Priest'
    cells = shared.displayed_cells(run/'preparation.jsonl')
    expected = expected_material(case['id'],integrated)
    metadata.update(source_evidence(), checkpoint=str(run),displayedCells=cells,
        shapeBounds=[1,0,79,21],worldSelected=True,designPreviewOnly=not integrated,
        expectedMaterial=expected,integratedMaterial=integrated,
        gameplayPlaytestPerformed=False,perception=privacy(cells,mode,expected),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    floors = Counter(c['tile'] for c in cells if c.get('char') == '.')
    assert floors, 'No displayed plain floor for native readiness'
    metadata['testTerrainTiles'] = [next(t for t in (1291,1292) if floors[t])]
    metadata['setup'].append('Original world-selected Priest stage. Optional generic filler source reload disabled. No des.reset_level, terrain or occupant replacement, custom lighting or local viewpoint teleport. Each checkpoint is a separate isolated world, not campaign progression.')
    shared.write(run/'metadata.json',metadata)
    print(json.dumps(dict(run=str(run),metadata=metadata)))


def scene(row,label):
    m = row['metadata']
    x,y,w,h = m['shapeBounds']
    return dict(label=label,width=w,height=h,
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in m['displayedCells']
               if x<=c['x']<x+w and y<=c['y']<y+h],
        sourceCheckpoint=row['run'],engine=m['engine'],app=m['app'],
        identity=m['identity'],setup=m['setup'],originalBounds=m['shapeBounds'],
        reviewOnly=True,worldSelected=True,mode=m['mode'],perception=m['perception'])


def crop(base,label,center,width=26,height=15):
    x = max(0,min(base['width']-width,center[0]-width//2))
    y = max(0,min(base['height']-height,center[1]-height//2))
    return dict(base,label=label,width=width,height=height,cropBounds=[x,y,width,height],
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in base['cells']
               if x<=c['x']<x+width and y<=c['y']<y+height])



def refresh():
    """Restore the same baseline saves and refresh native-ready presentation.

    Frozen baseline index/manifest/results remain separate. Original game
    directories are read-only sources; only their review metadata is updated.
    """
    test_spec = importlib.util.spec_from_file_location('priest_refresh_checks',ROOT/'scripts/test-priest-quest.py')
    tests = importlib.util.module_from_spec(test_spec)
    test_spec.loader.exec_module(tests)
    rows = json.loads(INDEX.read_text())
    old_manifest = json.loads(MANIFEST.read_text())
    frozen = ART/'priest-canonical-review-manifest.json'
    if not frozen.exists():
        shutil.copy2(MANIFEST,frozen)
    scenes = {}
    for row in rows:
        m = row['metadata']
        before = tests.hashes(Path(row['run'])/'game')
        run,directory,game = tests.clone(row,'integrated-refresh-'+m['case']['id']+'-'+m['mode'],True)
        try:
            shared.settle(game)
            assert tour.identity(game,directory) == m['identity']
            assert list(game.cursor) == list(m['arrival'])
            cells = list(game.cells.values())
            expected = expected_material(m['case']['id'],True)
            privacy(cells,m['mode'],expected)
            baseline = {(c['x'],c['y']):c for c in m['displayedCells']}
            fields = ('tile','glyph','char','color','pet','groundTile')
            assert all(all(c.get(k) == baseline[(c['x'],c['y'])].get(k) for k in fields)
                       for c in cells if (c['x'],c['y']) in baseline)
            m.setdefault('baselineEngine',m['engine'])
            m.setdefault('baselineApp',m['app'])
            m.update(engine=tour.digest(tour.RES/'engine/nethack'),
                app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
                dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
                expectedMaterial=expected,integratedMaterial=True,designPreviewOnly=False,
                displayedCells=cells,perception=privacy(cells,m['mode'],expected),
                displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
                integratedRefreshRecipeSHA256=tour.digest(Path(__file__)),
                integratedRestoreEvidence=str(run/'engine.jsonl'),
                canonicalGlyphAndGroundPreserved=True)
            game.finish(automatic=True)
            assert tests.hashes(Path(row['run'])/'game') == before, 'Original saved game changed'
            shared.write(Path(row['run'])/'metadata.json',m)
            key = 'home-exploration' if m['mode'] == 'exploration' else dict(STAGES)[m['case']['id'].split('-')[1]]
            scenes[key] = scene(row,old_manifest['scenes'][key]['label'])
            print('REFRESHED',m['case']['id'],m['mode'],expected,flush=True)
        finally:
            shared.cleanup(run,game)
    for key,old in old_manifest['scenes'].items():
        if key in scenes:
            continue
        base = 'home' if key == 'home-shrine' else 'goal' if key == 'goal-detail' else 'locate'
        x,y,w,h = old['cropBounds']
        scenes[key] = crop(scenes[base],old['label'],(x+w//2,y+h//2),w,h)
    shared.write(INDEX,rows)
    shared.write(MANIFEST,dict(old_manifest,scenes=scenes,integrated=True,
        note='Same original canonical source saves restored with integrated packaged engine. Actual emitted materials included; canonical glyph/ground fields unchanged. Source game files and frozen baseline evidence preserved.'))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',choices=[s for s,_ in STAGES])
    parser.add_argument('--mode',choices=['inspection','exploration'],default='inspection')
    parser.add_argument('--integrated',action='store_true')
    parser.add_argument('--refresh',action='store_true',help='Refresh same saves after integrated checks; no new worlds')
    args = parser.parse_args()
    if args.refresh:
        assert args.integrated, '--refresh requires --integrated'
        refresh()
        return
    if args.worker:
        worker(args.worker,args.mode,args.integrated)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX,INDEX.with_name('priest-review-prepared-before-'+stamp+'.json'))
    rows,scenes = [],{}
    for suffix,key,mode in [*( (s,k,'inspection') for s,k in STAGES),
                            ('strt','home-exploration','exploration')]:
        argv = [sys.executable,str(Path(__file__)),'--worker',suffix,'--mode',mode]
        if args.integrated:
            argv.append('--integrated')
        row = json.loads(subprocess.check_output(argv,text=True))
        rows.append(row)
        scenes[key] = scene(row,'Actual Priest '+key)
        shared.write(INDEX,rows)
        shared.write(MANIFEST,dict(scenes=scenes,reviewOnly=True))
        print('PREPARED',key,row['run'],flush=True)
    for key,label in [('home','Great Temple and desecrated altar'),
                      ('locate','Temple of Nalzok and graveyard')]:
        altars = [c for c in scenes[key]['cells'] if 1305 <= c['tile'] <= 1309]
        assert altars, 'No mapped altar in '+key
        altar = altars[0]
        scenes[key+'-shrine'] = crop(scenes[key],label,(altar['x'],altar['y']))
    goal = scenes['goal']
    stairs = next(c for c in goal['cells'] if c['tile'] == 1297)
    scenes['goal-detail'] = crop(goal,'Original unlit clearing amid lava',(stairs['x'],stairs['y']))
    graves = [c for c in scenes['locate']['cells'] if c['tile'] == 1310]
    if graves:
        grave = graves[len(graves)//2]
        scenes['graveyard'] = crop(scenes['locate'],'Original graveyard',(grave['x'],grave['y']))
    shared.write(MANIFEST,dict(scenes=scenes,reviewOnly=True,integrated=args.integrated,
        note='Original displayed engine geometry and appearances. Crops use mapped perceived features. Diagnostic terrain and undiscovered altar knowledge are excluded from scenes. No complete quest playthrough is claimed.'))
    print('MANIFEST',MANIFEST,flush=True)


if __name__ == '__main__':
    main()
