#!/usr/bin/env python3
"""Prepare unchanged world-selected Baalzebub displays for visual review.

Wizard travel, protection and reveal are disclosed. No terrain, source, actors,
viewpoint or player saves are replaced. These are frozen examples, not campaign
progression or encounter verification.
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
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('baalz_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'baalz-review-prepared.json'
MANIFEST = ART/'baalz-review-manifest.json'
BOUNDS = [1, 0, 79, 21]
WALL_FAMILIES = {'dungeon': range(1273,1284), 'mines': range(1471,1482),
                 'gehennom': range(1482,1493), 'knox': range(1493,1504),
                 'sokoban': range(1504,1515)}
WALLS = set().union(*[set(slots) for slots in WALL_FAMILIES.values()])
FLOORS = set(range(1291,1297))


def source_evidence():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    hashes = {}
    with tarfile.open(archive) as upstream:
        for relative in ('dat/baalz.lua', 'src/mkmaze.c'):
            source = tour.DAT.parent/relative
            matches = [m for m in upstream.getmembers() if m.name.endswith('/'+relative)]
            assert len(matches) == 1, matches
            original = upstream.extractfile(matches[0]).read()
            assert source.read_bytes() == original, relative+' differs from pinned upstream'
            hashes[relative] = tour.digest(source)
            if relative == 'dat/baalz.lua':
                text = original.decode()
                assert 'style = "solidfill"' in text and '"corrmaze"' in text
                assert 'des.door("locked",00,06)' in text
                assert 'the two pools are fakes' in text
                assert 'lava' not in text.lower(), 'Unexpected prescribed lava'
            else:
                text = original.decode()
                assert 'baalz_fixup(void)' in text
                assert 'levl[x][y].typ = HWALL;' in text
    return dict(sourceScript='vendor/NetHack-5.0.0/dat/baalz.lua',
        baalzSourceSHA256=hashes['dat/baalz.lua'], mkmazeSourceSHA256=hashes['src/mkmaze.c'],
        upstreamArchiveSHA256=tour.digest(archive), unchangedUpstreamSource=True,
        originalSourceFeatures=dict(generator='Unlit solidfill, mazelevel and corrmaze.',
            fortress='Original insect-shaped walls, locked entrance, secret doors and two iron-bar eyes.',
            wallFixup='Upstream baalz_fixup wallifies the legs, replaces fake pool markers with walls and permits digging beside the eyes.',
            hazards='Original traps, loot and active occupants. No prescribed lava setting.'))


def privacy(cells, mode):
    cells = list(cells)
    assert cells and len({(c['x'],c['y']) for c in cells}) == len(cells)
    hidden = [c for c in cells if c['tile'] in (1469,1470)]
    known = [c for c in cells if c['tile'] not in (1469,1470)]
    assert known and all('material' not in c for c in cells), 'Baalzebub acquired regional material'
    assert all('groundTile' not in c for c in hidden), 'Hidden ground disclosed'
    if mode == 'exploration':
        assert hidden, 'Unrevealed arrival must retain unknown cells'
    else:
        assert any(c['tile'] in WALLS for c in cells), 'Missing original fortress walls'
        assert sum(c['tile'] == 1289 for c in cells) == 2, 'Missing two original bar eyes'
    return dict(knownCells=len(known),hiddenCells=len(hidden),noRegionalMaterial=True,noHiddenGround=True)


def wall_counts(cells):
    tiles = Counter(c['tile'] for c in cells)
    return {name:dict(total=sum(tiles[t] for t in slots),
        tiles={str(t):tiles[t] for t in slots if tiles[t]})
        for name,slots in WALL_FAMILIES.items()}


def worker(mode):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == 'baalz'))
    assert case['source'] is None and case['target'] == 'baalz'
    run = ART/('baalz-original-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case,mode,run)
    assert metadata['identity']['branch'] == 'Gehennom'
    assert metadata['case']['source'] is None
    assert metadata['destination'].lstrip('* ').startswith('baalz:')
    cells = checks.displayed_cells(run/'preparation.jsonl')
    floors = Counter(c['tile'] for c in cells if c['tile'] in FLOORS)
    assert floors, 'No displayed original room or corridor floor'
    metadata.update(source_evidence(),checkpoint=str(run),displayedCells=cells,
        shapeBounds=BOUNDS,worldSelected=True,targetedLayout=False,
        designPreviewOnly=True,gameplayPlaytestPerformed=False,
        reviewTreatment='Review-only starting point: existing Gehennom architecture and floors. Shipped Baalzebub has no material tag; named special level blocks ordinary Gehennom routing.',
        perception=privacy(cells,mode),canonicalWallFamilies=wall_counts(cells),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        testTerrainTiles=[next(t for t in sorted(FLOORS) if floors[t])],
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    metadata['sources'].update({'baalz.lua':metadata['baalzSourceSHA256'],
                               'mkmaze.c':metadata['mkmazeSourceSHA256']})
    metadata['setup'].append(
        'Original world-selected unrevealed Baalzebub arrival. No source reset/reload, map reveal, extra protection, supplied inventory or viewpoint placement.'
        if mode == 'exploration' else
        'Original world-selected Baalzebub insect fortress and maze. Original wall fixups, two bar eyes, doors, stairs, traps, loot and active occupants retained. No source reset/reload or viewpoint placement. Wizard reveal supplies remembered remote terrain, not hidden occupants or encounters.')
    checks.write(run/'metadata.json',metadata)
    print(json.dumps(dict(run=str(run),metadata=metadata)))


def terrain_diagnostic(game,directory):
    """Read-only original terrain evidence in a check clone, never scene data."""
    offset = len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("BAALZ_TERRAIN:"..x..","..y..","..m.typ_name);
end end;''')
    rows = [e['text'].split(':',1)[1].split(',') for e in game.events[offset:]
            if e.get('text','').startswith('BAALZ_TERRAIN:')]
    assert len(rows) == 79*21,len(rows)
    counts = dict(Counter(row[2] for row in rows))
    assert counts.get('pool',0) == 0, 'Fake pool markers survived upstream wall fixup'
    assert counts.get('iron bars',0) == 2, counts
    return counts


def restore(row):
    run = Path(tempfile.mkdtemp(prefix='baalz-independent-restore-',dir=ART))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat')
    game = checks.open_game(directory)
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        assert tour.identity(game,directory) == row['metadata']['identity']
        assert list(game.cursor) == list(row['metadata']['arrival'])
        perception = privacy(game.cells.values(),row['metadata']['mode'])
        inspections = []
        before = game.turn
        for category,predicate in (
            ('wall',lambda c:c['tile'] in WALLS),
            ('bars',lambda c:c['tile'] == 1289),
            ('floor',lambda c:c['tile'] in FLOORS),
            ('unknown',lambda c:c['tile'] in (1469,1470))):
            cell = next((c for c in game.cells.values() if predicate(c)),None)
            if cell is None:
                continue
            description = game.inspect(cell['x'],cell['y'])
            assert description.strip(),(category,cell)
            if category == 'unknown':
                assert any(w in description.lower() for w in ('unknown','unexplored','nothing')),description
            if category == 'wall':
                assert any(w in description.lower() for w in ('wall','stone')),description
            if category == 'bars':
                assert 'bars' in description.lower(),description
            inspections.append(dict(category=category,position=[cell['x'],cell['y']],
                displayedTile=cell['tile'],description=description))
        assert game.turn == before,'Inspection spent turns'
        categories = {r['category'] for r in inspections}
        if row['metadata']['mode'] == 'inspection':
            assert {'wall','bars','floor'} <= categories
        else:
            assert 'unknown' in categories
        row['metadata'].update(independentRestoreVerified=True,
            independentRestoreEvidence=str(run/'engine.jsonl'),restoredPerception=perception,
            turnFreeInspection=True,inspection=inspections,
            nativeRestoreFloorCounts=dict(Counter(c['tile'] for c in game.cells.values()
                if c['tile'] in FLOORS)))
        if row['metadata']['mode'] == 'inspection':
            row['metadata'].update(originalTerrainCounts=terrain_diagnostic(game,directory),
                terrainDiagnosticEvidence=str(run/'engine.jsonl'),
                noPoolMarkersAfterUpstreamFixup=True,
                diagnosticUse='Read-only terrain counts in an independent clone. No hidden actor/object query, diagnostic location, or inferred content enters scenes or crop selection.')
        game.finish(automatic=True)
        checks.write(Path(row['run'])/'metadata.json',row['metadata'])
    finally:
        checks.cleanup(run,game)


def scene(row,label):
    m = row['metadata']
    x,y,w,h = BOUNDS
    return dict(label=label,width=w,height=h,
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in m['displayedCells']
            if x <= c['x'] < x+w and y <= c['y'] < y+h],
        sourceCheckpoint=row['run'],engine=m['engine'],app=m['app'],
        identity=m['identity'],setup=m['setup'],originalBounds=BOUNDS,
        reviewOnly=True,worldSelected=True,targetedLayout=False,
        mode=m['mode'],perception=m['perception'])


def detail(base):
    # Insect walls and both eyes establish the full displayed fortress span.
    # This rule uses displayed glyphs only, without source coordinates or actors.
    points = [(c['x'],c['y']) for c in base['cells']
              if c['tile'] in WALLS or c['tile'] == 1289]
    assert points,'No displayed fortress walls'
    x = max(0,min(px for px,py in points)-1)
    y = max(0,min(py for px,py in points)-1)
    right = min(base['width'],max(px for px,py in points)+2)
    bottom = min(base['height'],max(py for px,py in points)+2)
    w,h = right-x,bottom-y
    return dict(base,label='Actual engine Baalzebub: displayed fortress wall detail',
        width=w,height=h,cropBounds=[x,y,w,h],
        cropSelection='Bounds of displayed walls and iron-bar eyes, padded one cell. No hidden contents or source-coordinate inference.',
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in base['cells']
            if x <= c['x'] < x+w and y <= c['y'] < y+h])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('inspection','exploration'))
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX,INDEX.with_name('baalz-review-prepared-before-'+stamp+'.json'))
    rows,scenes = [],{}
    for mode in ('inspection','exploration'):
        row = json.loads(subprocess.check_output([sys.executable,str(Path(__file__)),
            '--worker',mode],text=True))
        restore(row)
        rows.append(row)
        if mode == 'inspection':
            scenes['fortress'] = scene(row,'Actual engine Baalzebub fortress (world-selected, revealed for review)')
            scenes['fortress-detail'] = detail(scenes['fortress'])
        else:
            scenes['arrival'] = scene(row,'Actual unrevealed world-selected Baalzebub arrival')
        checks.write(INDEX,rows)
        checks.write(MANIFEST,dict(scenes=scenes,reviewOnly=True,
            note='Unchanged world-selected Baalzebub inspection and unrevealed arrival. Frozen engine display; no terrain or occupant replacement, source reload, viewpoint placement or campaign playthrough.'))
        print('PREPARED Baalzebub',mode,row['run'],flush=True)
    print('MANIFEST',MANIFEST,flush=True)


if __name__ == '__main__':
    main()
