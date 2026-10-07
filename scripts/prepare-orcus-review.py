#!/usr/bin/env python3
"""Prepare unchanged world-selected Orcus levels for an integrated art study.

This creates isolated real-engine saves, not a gameplay or encounter test.
Wizard protection, map reveal and original-floor positioning are disclosed.
No terrain, actors, loot, lighting or random generation are replaced. Orcus
retains its canonical terrain and uses the approved existing Valley material.
"""
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('valley_checks',ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ROOT/'.artifacts/orcus-rooms-prepared.json'
BOUNDS = [1,0,79,21]


def source_evidence():
    source = tour.DAT/'orcus.lua'
    archive = tour.RES/'Source/nethack-500-src.tgz'
    with tarfile.open(archive) as upstream:
        matches = [m for m in upstream.getmembers() if m.name.endswith('/dat/orcus.lua')]
        assert len(matches) == 1,matches
        original = upstream.extractfile(matches[0]).read()
    assert source.read_bytes() == original,'Orcus terrain differs from pinned upstream source'
    text = original.decode()
    boulders = len(re.findall(r'des\.object\("boulder",',text))
    doors = dict(Counter(re.findall(r'des\.door\("([^"]+)"',text)))
    assert boulders == 24 and doors == {'closed':9,'open':5,'nodoor':2},(boulders,doors)
    assert 'style="mazegrid"' in text and 'des.mazewalk(00,06,"west")' in text
    assert 'type="morgue"' in text and 'type="sanctum"' in text
    return dict(sourceScript='vendor/NetHack-5.0.0/dat/orcus.lua',
        orcusSourceSHA256=hashlib.sha256(original).hexdigest(),
        upstreamArchiveSHA256=tour.digest(archive),unchangedUpstreamSource=True,
        originalSourceFeatures=dict(placedBoulders=boulders,doorStates=doors,
            ruinedWalls='Original ghost-town wall gaps and original boulders; no new ruin tiles.',
            graveyard='One unlit filled morgue.',altar='One unaligned sanctum altar.',
            shops='Two originally lit filled shops.',
            mazeApproach='Original mazegrid west approach and mazewalk connection, with upstream hell_tweaks outside protected city.'))


def fallback(cells):
    values = list(cells)
    checks.material(values, 'valley')
    known = [c for c in values if c['tile'] not in (1469,1470)]
    hidden = [c for c in values if c['tile'] in (1469,1470)]
    assert known and all('groundTile' not in c for c in hidden),'Unknown ground exposed'
    return dict(knownCells=len(known),hiddenCells=len(hidden),expectedMaterial='valley',noHiddenGround=True)


def diagnostics(game,directory):
    """Read-only location evidence in a separate check clone, never player UI."""
    offset = len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 local fs={}; for k,v in pairs(m.flags) do fs[#fs+1]=k.."="..tostring(v); end; table.sort(fs);
 nh.pline("ORCUS_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..tostring(m.has_trap)..","..table.concat(fs,"|"));
 local o=obj.at(x-ox,y-oy); while not o:isnull() do
  if o:totable().otyp_name=="boulder" then nh.pline("ORCUS_BOULDER:"..x..","..y); end;
  o=o:next(true);
 end;
end end;''')
    terrain = [e['text'].split(':',1)[1].split(',') for e in game.events[offset:]
               if e.get('text','').startswith('ORCUS_TERRAIN:')]
    boulders = [tuple(map(int,e['text'].split(':',1)[1].split(','))) for e in game.events[offset:]
                if e.get('text','').startswith('ORCUS_BOULDER:')]
    assert len(terrain) == 79*21,len(terrain)
    assert len(boulders) >= 24,('Missing original boulder population',boulders)
    return terrain,boulders


def marker(row):
    run,directory,game = checks.clone(row,'orcus-restore-marker')
    try:
        checks.settle(game)
        assert tour.identity(game,directory) == row['metadata']['identity']
        fallback(game.cells.values())
        x,y,w,h = row['metadata']['shapeBounds']
        counts = Counter(c['tile'] for p,c in game.cells.items() if c.get('char') == '.'
                         and x <= p[0] < x+w and y <= p[1] < y+h)
        assert counts,'No restored plain floor in review bounds'
        row['metadata'].update(testTerrainTiles=[next(t for t in (1292,1291) if counts[t])],
            nativeRestoreFloorCounts=dict(counts),nativeRestoreMarkerEvidence=str(run/'engine.jsonl'))
        game.finish(automatic=True)
    finally:
        checks.cleanup(run,game)


def prepare(mode,source):
    row = json.loads(subprocess.check_output([sys.executable,
        str(ROOT/'scripts/playtest/prepare.py'),'prepare','--case','orcus','--mode',mode],text=True))
    metadata = row['metadata']
    assert metadata['case']['source'] is None,'Do not reload a named terrain fixture'
    assert metadata['identity']['branch'] == 'Gehennom'
    cells = checks.displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
    perception = fallback(cells)
    if mode == 'inspection':
        assert any(1482 <= c['tile'] <= 1492 for c in cells),'Missing canonical Gehennom walls'
        assert any(c['tile'] == 1305 for c in cells),'Missing mapped unaligned altar'
        assert any(c['tile'] == 1310 for c in cells),'Missing mapped graves'
    else:
        assert perception['hiddenCells'] > 0,'Exploration must retain unknown map space'
    metadata.update(source,shapeBounds=BOUNDS,displayedCells=cells,
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),worldSelected=True,
        designPreviewOnly=False,gameplayPlaytestPerformed=False,
        reviewTreatment='Integrated exact existing Valley material on perceived Orcus cells.',
        perception=perception,orcusRecipeSHA256=tour.digest(Path(__file__)))
    metadata['sources']['orcus.lua'] = source['orcusSourceSHA256']
    metadata['setup'].append('Original world-selected Orcus arrival, source geometry, maze approach, doors, boulders, random loot, altar, graves, shops and active occupants retained. This prepares art review only; it does not verify campaign progression or encounters.')
    marker(row)
    checks.write(Path(row['run'])/'metadata.json',metadata)
    print('PREPARED Orcus',mode,row['run'],flush=True)
    return row


def focused(base,focus):
    run,directory,game = checks.clone(base,'orcus-focus-'+focus)
    try:
        checks.settle(game)
        terrain,boulders = diagnostics(game,directory)
        mapped = {(int(r[0]),int(r[1])):r for r in terrain}
        features = boulders if focus == 'city' else [p for p,r in mapped.items() if r[2] == 'grave']
        assert features,('No original focus features',focus)
        # Existing mapped, unoccupied foreground floor plus actual room/trap
        # diagnostics are the only setup candidates. Original flips are already
        # represented in these world coordinates; no source coordinate guesses.
        candidates = [p for p,c in game.cells.items() if focus == 'city' and c.get('char') == '.'
            and mapped.get(p,[None,None,None,None,None])[2] == 'room'
            and mapped[p][4] == 'false'
            and any(1 <= max(abs(p[0]-f[0]),abs(p[1]-f[1])) <= (1 if focus == 'city' else 4)
                    for f in features)]
        if focus == 'city':
            assert candidates,('No existing safe floor beside original feature',focus)
        candidates.sort(key=lambda p:(min(max(abs(p[0]-f[0]),abs(p[1]-f[1])) for f in features),
                                       -sum(abs(p[0]-f[0])+abs(p[1]-f[1]) <= 7 for f in features),
                                       abs(p[0]-40)+abs(p[1]-10)))
        target = game.cursor
        if focus == 'city':
            for target in candidates[:16]:
                try:
                    checks.place(game,target)
                    break
                except AssertionError:
                    checks.cleanup(run,game)
                    run,directory,game = checks.clone(base,'orcus-focus-'+focus+'-retry')
                    checks.settle(game)
            else:
                raise AssertionError('Sixteen original safe-floor placements were rejected: '+focus)
        before = game.turn
        tile = 1266 if focus == 'city' else 1310
        cell = next((c for p,c in game.cells.items() if c['tile'] == tile
                     and (focus == 'graveyard' or max(abs(p[0]-target[0]),abs(p[1]-target[1])) <= 2)), None)
        assert cell,('Original nearby feature is not perceived',focus,target)
        description = game.inspect(cell['x'],cell['y'])
        assert ('boulder' if focus == 'city' else 'grave') in description.lower(),description
        assert game.turn == before
        fallback(game.cells.values())
        metadata = copy.deepcopy(base['metadata'])
        metadata.update(case=dict(metadata['case'],id='orcus-'+focus,
            label='Orcus / '+('ghost-town ruins and original boulders' if focus == 'city' else 'graveyard and surrounding buildings')),
            shapeBounds=BOUNDS,
            arrival=list(game.cursor),status=dict(game.status),displayedCells=list(game.cells.values()),
            displayedTileCounts=dict(Counter(str(c['tile']) for c in game.cells.values())),
            featureInspection=dict(cell=cell,description=description,turnFree=True,
                                   locallyPerceived=focus == 'city'),
            localArrivalPerformed=focus == 'city',
            originalBoulderCount=len(boulders),originalTerrainCounts=dict(Counter(r[2] for r in terrain)),
            focusDiagnosticEvidence=str(run/'engine.jsonl'),checkpoint=str(run))
        if focus == 'city':
            metadata['setup'].append('Focused city view: read-only original terrain/object diagnostics identify existing features and trap-free mapped room floor. Upstream wizard teleport places the viewpoint there. Original flips, lighting, actors and contents retained. Inspection verifies an actually perceived boulder without spending turns.')
        else:
            metadata['setup'].append('Graveyard review uses an independently restored mapped inspection checkpoint and engine-known grave inspection. Local graveyard floor placement was rejected by upstream in earlier preserved check clones, so this row makes no local-arrival or encounter claim. Root may crop actual displayed mapped grave terrain; no terrain or occupants changed.')
        game.finish(automatic=True)
        (run/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        row = dict(run=str(run),metadata=metadata)
        marker(row)
        checks.write(run/'metadata.json',metadata)
        print('PREPARED Orcus',focus,run,description,flush=True)
        return row
    finally:
        checks.cleanup(run,game)


def previous_city(base):
    """Reuse a successful original checkpoint after independent restore checks."""
    for path in sorted(INDEX.parent.glob('orcus-rooms-prepared-before-review-*.json'),reverse=True):
        for row in json.loads(path.read_text()):
            metadata = row['metadata']
            if metadata['case']['id'] != 'orcus-city':
                continue
            if any(metadata.get(key) != base['metadata'].get(key)
                   for key in ('engine','app','dataSHA256','identity','orcusSourceSHA256')):
                continue
            if not (Path(row['run'])/'game/save').exists():
                continue
            row = copy.deepcopy(row)
            metadata = row['metadata']
            metadata.update(shapeBounds=BOUNDS,localArrivalPerformed=True,
                            orcusRecipeSHA256=tour.digest(Path(__file__)))
            metadata['featureInspection']['locallyPerceived'] = True
            metadata['setup'].append('Reuse a previously successful original boulder/city checkpoint after independent packaged-engine restore verification. Earlier rejected floor-placement traces remain preserved; no new placement, geometry or actor changes.')
            marker(row)
            checks.write(Path(row['run'])/'metadata.json',metadata)
            print('REUSED Orcus city',row['run'],flush=True)
            return row
    return None


def main():
    ROOT.joinpath('.artifacts').mkdir(exist_ok=True)
    source = source_evidence()
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX,INDEX.with_name('orcus-rooms-prepared-before-review-'+stamp+'.json'))
    rows = []
    for mode in ('inspection','exploration'):
        rows.append(prepare(mode,source))
        checks.write(INDEX,rows)
    for focus in ('city','graveyard'):
        rows.append((previous_city(rows[0]) if focus == 'city' else None) or focused(rows[0],focus))
        checks.write(INDEX,rows)
    print('INDEX',INDEX,flush=True)


if __name__ == '__main__':
    main()
