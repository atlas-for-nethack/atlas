#!/usr/bin/env python3
"""Preserve real upstream worlds for approved natural ground material review.

Baseline preparation uses a frozen packaged engine. Refresh restores the same
source saves with the current packaged engine. Geometry, actors and lighting
are never changed; wizard travel, protection and reveal remain disclosed.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
SNAPSHOT = ART/'grounded-baseline-runtime'
BASELINE = ART/'grounded-environments-baseline.json'
INDEX = ART/'grounded-environments-review-prepared.json'
MANIFEST = ART/'grounded-environments-review-manifest.json'
spec = importlib.util.spec_from_file_location('grounded_shared',ROOT/'scripts/test-valley-level.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
tour = shared.tour
PACKAGED_RES, PACKAGED_APP = tour.RES, tour.APP
ROLES = ('Arc','Kni','Bar','Ran','Tou')
CANONICAL = ('tile','glyph','char','color','pet','groundTile')
FLOORS = (1291,1292,1293,1294,1295,1296)


def snapshot():
    """Never replace an existing frozen runtime, even after a root rebuild."""
    SNAPSHOT.mkdir(exist_ok=True)
    for relative,source in [('engine',PACKAGED_RES/'engine'),('Source',PACKAGED_RES/'Source'),('Contents/MacOS',PACKAGED_APP/'Contents/MacOS')]:
        target=SNAPSHOT/relative; target.mkdir(parents=True,exist_ok=True)
        names=['nethack-500-src.tgz'] if relative=='Source' else ['NetHackAtlas'] if relative=='Contents/MacOS' else ['nethack','recover','nhdat','license','symbols','sysconf']
        for name in names:
            dest=target/name
            if not dest.exists():
                # Older initial snapshot stored engine and archive at its root.
                old=SNAPSHOT/name
                shutil.copy2(old if old.exists() else source/name,dest)
    return dict(engine=tour.digest(SNAPSHOT/'engine/nethack'),data=tour.digest(SNAPSHOT/'engine/nhdat'),app=tour.digest(SNAPSHOT/'Contents/MacOS/NetHackAtlas'),upstream=tour.digest(SNAPSHOT/'Source/nethack-500-src.tgz'))


def expected_materials(identifier):
    """Approved stage contexts, recorded separately from emitted cell counts."""
    caves={'Kni-fila','Kni-loca','Kni-filb','Kni-goal','Bar-fila','Bar-filb','Bar-goal','Ran-loca','Ran-filb','Ran-goal','Tou-fila','Tou-filb'}
    outdoors={'Arc-strt','Arc-loca','Kni-strt','Bar-strt','Bar-loca','Ran-strt','Ran-fila','Tou-strt','Sam-strt','Sam-loca','Wiz-strt','Wiz-loca'}
    if identifier.startswith('minetn-'):return ['mines','mines-built']
    if identifier.startswith('medusa-'):return ['medusa','quest-earth']
    if identifier in caves:return ['caveman']
    if identifier in outdoors:return ['samurai' if identifier.startswith('Sam-') else None,'quest-earth']
    if identifier.startswith(('fill-garden','forest-paths')):return [None,'quest-earth']
    return [None]


def save_hashes(row):
    directory=Path(row['run'])/'game/save'
    return {str(p.relative_to(directory)):tour.digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def open_game(directory,baseline=False):
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    module=tour.load_game_module()
    module.RUNTIME=SNAPSHOT/'engine' if baseline else PACKAGED_RES/'engine'
    config=directory/'grounded.nethackrc';config.write_text('')
    class ClearAwareGame(module.Game):
        def next(self):
            event=super().next()
            if event['type']=='clear' and event.get('window')=='map': self.cells.clear()
            return event
    return ClearAwareGame(directory,name='wizard',options=shared.OPTIONS,config=config)


def clone(row,label,baseline=False):
    run=Path(tempfile.mkdtemp(prefix='grounded-'+label+'-',dir=ART)); directory=run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(SNAPSHOT/'engine/nhdat')
    return run,directory,open_game(directory,baseline)


def source_evidence(case):
    identifier=case['id']
    names=[]
    if identifier[:3] in (*ROLES,'Sam','Wiz'): names=[identifier+'.lua']
    elif identifier.startswith('medusa-') or identifier.startswith('minetn-'):
        names=[case['source']] if case.get('source') else [identifier.split('-')[0]+'-'+str(i)+'.lua' for i in range(1,5 if identifier.startswith('medusa') else 8)]
    elif case.get('fill') or identifier.startswith('forest-paths'): names=['themerms.lua']
    result={}
    with tarfile.open(SNAPSHOT/'Source/nethack-500-src.tgz') as archive:
        for name in names:
            members=[m for m in archive.getmembers() if m.name.endswith('/dat/'+name)]
            assert len(members)==1,(name,members)
            original=archive.extractfile(members[0]).read(); source=tour.DAT/name
            assert original==source.read_bytes(),name+' differs from pinned upstream'
            result[name]=tour.digest(source)
    return result


def bounds(cells):
    visible=[c for c in cells if c['tile'] not in (1469,1470)]
    x0=min(c['x'] for c in visible); y0=min(c['y'] for c in visible)
    x1=max(c['x'] for c in visible); y1=max(c['y'] for c in visible)
    return [x0,y0,x1-x0+1,y1-y0+1]


def named_main_level(game,identity):
    """Named context from the isolated upstream wizard menu, never player UI."""
    event=tour.named(game,'wizlevelport');assert event['kind']=='line'
    game.send('line ?');event=game.wait_input();assert event['kind']=='menu'
    inside=False;name=None
    for item in event['items']:
        text=item['text'].strip().lstrip('* ').strip()
        if text.startswith('The Dungeons of Doom: levels'):inside=True;continue
        if inside and not item.get('selectable'):break
        if inside:
            match=re.fullmatch(r'([a-z][a-z0-9-]*): '+str(identity['depth'])+r'(?: .*|)',text)
            if match:name=match[1]
    game.send('menu cancel');shared.settle(game)
    return name


def record(row,baseline):
    before=save_hashes(row); assert before,'Missing source checkpoint'
    run,directory,game=clone(row,'baseline' if baseline else 'refresh',baseline)
    try:
        shared.settle(game)
        m=copy.deepcopy(row['metadata']); cells=list(game.cells.values())
        identity=tour.identity(game,directory)
        assert identity == m['identity'],(m['case']['id'],identity,m['identity'])
        if m['case'].get('fill')=='Garden':
            m['namedMainLevel']=named_main_level(game,identity)
            if m['case'].get('requireOrdinary') and m['namedMainLevel']:
                raise RuntimeError('Garden fixture landed on named main dungeon level '+m['namedMainLevel'])
        terrain=shared.terrain_snapshot(game,directory)
        m.update(displayedCells=cells,shapeBounds=bounds(cells),arrival=list(game.cursor),turn=game.turn,
                 reviewCapture=m['mode']=='inspection' and m['case']['id'] in ('medusa-1','medusa-4','minetn-2','minetn-5','minetn-7','Arc-strt','Arc-loca','Kni-strt','Kni-loca','Bar-strt','Bar-loca','Ran-strt','Ran-fila','Ran-loca','Tou-strt','Tou-loca','Sam-strt','Sam-loca','Wiz-strt','Wiz-loca','fill-garden-lit'),
                 engine=tour.digest((SNAPSHOT/'engine' if baseline else PACKAGED_RES/'engine')/'nethack'),
                 app=tour.digest((SNAPSHOT if baseline else PACKAGED_APP)/'Contents/MacOS/NetHackAtlas'),
                 dataSHA256=tour.digest(directory/'nhdat'),sourceSaveHashes=before,
                 pinnedSources=source_evidence(m['case']),upstreamArchiveSHA256=tour.digest(SNAPSHOT/'Source/nethack-500-src.tgz'),
                 comparisonBoundary='Ordinary restore of preserved source checkpoint',
                 displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
                 displayedMaterialCounts=dict(Counter(c.get('material','absent') for c in cells)),
                 testTerrainTiles=sorted({c['tile'] for c in cells if c['tile'] in FLOORS}),
                 independentRestoreVerified=True,independentRestoreEvidence=str(run/'engine.jsonl'),
                 originalTerrainLightingMemory=terrain,recipeSHA256=tour.digest(Path(__file__)),
                 gameplayPlaytestPerformed=False,checkpoint=row['run'])
        assert m['testTerrainTiles'],'No actual displayed floor for native readiness'
        m['worldSelected']=not bool(m['case'].get('source')) and not (m['case'].get('fill') or m['case'].get('terrain'))
        m['targetedLayout']=not m['worldSelected']
        if baseline:
            m['canonicalBaselineCells']=cells
            m['baselineEngine']=m['engine']
        else:
            old={(c['x'],c['y']):c for c in m['canonicalBaselineCells']}
            assert set(old)==set(game.cells),'Restored cell coverage differs'
            changed=[(p,k,old[p].get(k),c.get(k)) for p,c in game.cells.items() for k in CANONICAL if old[p].get(k)!=c.get(k)]
            assert not changed,('Canonical original fields changed',m['case']['id'],changed[:10])
            assert terrain==m['originalBaselineTerrainLightingMemory'],'Original terrain/memory/lighting changed'
            m['canonicalOldNewIdentical']=True
            m['expectedMaterial']=[None] if m.get('namedMainLevel') and m['case'].get('fill')=='Garden' else expected_materials(m['case']['id'])
            m['integratedMaterial']=any(v is not None for v in m['expectedMaterial'])
        game.finish(automatic=True)
        assert save_hashes(row)==before,'Original source save changed'
        return dict(run=row['run'],metadata=m)
    finally: shared.cleanup(run,game)


def reused():
    rows=[]
    for filename,predicate in [
        ('medusa-production-prepared.json',lambda m:True),
        ('minetown-rooms-prepared.json',lambda m:True),
        ('samurai-review-prepared.json',lambda m:m['case']['id'] in ('Sam-strt','Sam-loca')),
        ('wizard-review-prepared.json',lambda m:m['case']['id'] in ('Wiz-strt','Wiz-loca')),
        ('garden-rooms-prepared.json',lambda m:True)]:
        for row in json.loads((ART/filename).read_text()):
            if predicate(row['metadata']): rows.append(row)
    return rows


def new_cases():
    for role in ROLES:
        for case in tour.catalog():
            if case['id'].startswith(role+'-'):
                case=dict(case,source=None)
                yield case,'inspection'
        yield dict(next(c for c in tour.catalog() if c['id']==role+'-strt'),source=None),'exploration'
    yield dict(id='fill-garden-ordinary-lit',group='Gardens and trees',label='Garden / lit ordinary dungeon',target=None,source=None,branch='The Dungeons of Doom',fill='Garden',lit=True,mixed=False,requireOrdinary=True),'inspection'


def prepare():
    hashes=snapshot(); tour.RES=SNAPSHOT; tour.APP=SNAPSHOT
    existing=json.loads(BASELINE.read_text()) if BASELINE.exists() else []
    keys={(r['metadata']['case']['id'],r['metadata']['mode']) for r in existing}
    for row in reused():
        key=row['metadata']['case']['id'],row['metadata']['mode']
        if key in keys:continue
        frozen=record(row,True)
        frozen['metadata']['originalBaselineTerrainLightingMemory']=frozen['metadata']['originalTerrainLightingMemory']
        existing.append(frozen);keys.add(key);shared.write(BASELINE,existing)
        print('FROZEN reused',*key,flush=True)
    for case,mode in new_cases():
        key=case['id'],mode
        if key in keys:continue
        for attempt in range(8):
            run=Path(tempfile.mkdtemp(prefix='grounded-original-'+case['id']+'-',dir=ART))
            m=tour.prepare(case,mode,run)
            m['setup'].append('Verified ordinary main dungeon context for the unchanged upstream lit Garden fill. New fixture retains source randomness; original reused named-level Garden checkpoint is preserved separately.' if case.get('requireOrdinary') else 'Original world-selected Quest stage, including original filler. No source reload, terrain/actor replacement or custom lighting. Wizard preparation does not establish normal quest admission or completion.')
            try:frozen=record(dict(run=str(run),metadata=m),True);break
            except RuntimeError as error:
                (run/'failure.txt').write_text(str(error)+'\n')
                if not str(error).startswith('Garden fixture landed'):raise
        else:raise RuntimeError('Eight isolated worlds lacked an ordinary depth12 Garden fixture')
        frozen['metadata']['originalBaselineTerrainLightingMemory']=frozen['metadata']['originalTerrainLightingMemory']
        existing.append(frozen);keys.add(key);shared.write(BASELINE,existing)
        print('FROZEN new',*key,flush=True)
    shared.write(ART/'grounded-baseline-ready.json',dict(hashes=hashes,index=str(BASELINE),rows=len(existing),sourceSavesPreserved=True))
    return existing


def manifest(rows):
    scenes={}
    for row in rows:
        m=row['metadata']; x,y,w,h=m['shapeBounds']; key=m['case']['id']+'-'+m['mode']
        scenes[key]=dict(label=m['case']['group']+' / '+m['case']['label']+' / '+m['mode'],width=w,height=h,
            cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in m['displayedCells'] if x<=c['x']<x+w and y<=c['y']<y+h],
            originalBounds=m['shapeBounds'],sourceCheckpoint=row['run'],engine=m['engine'],app=m['app'],identity=m['identity'],setup=m['setup'],mode=m['mode'],worldSelected=m['worldSelected'],targetedLayout=m['targetedLayout'],reviewOnly=True,reviewCapture=m.get('reviewCapture',False))
    shared.write(MANIFEST,dict(scenes=scenes,sourceIndex=str(INDEX),canonicalOldNewIdentical=all(r['metadata'].get('canonicalOldNewIdentical',False) for r in rows)))


def refresh():
    rows=[]
    for row in json.loads(BASELINE.read_text()):
        refreshed=record(row,False);rows.append(refreshed);shared.write(INDEX,rows)
        print('REFRESHED',row['metadata']['case']['id'],row['metadata']['mode'],flush=True)
    manifest(rows);return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    if args.prepare:prepare()
    elif args.refresh:refresh()
    else:parser.error('Choose --prepare or --refresh')

if __name__=='__main__':main()
