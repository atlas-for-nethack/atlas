#!/usr/bin/env python3
"""Prepare unchanged world-selected Juiblex displays in isolated engine saves.

Wizard travel and inspection setup are disclosed. Neither checkpoint reloads
level source, rewrites terrain, moves the local viewpoint or replaces actors.
These are frozen art-review examples, not campaign or encounter verification.
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
spec = importlib.util.spec_from_file_location('juiblex_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'juiblex-review-prepared.json'
MANIFEST = ART/'juiblex-review-manifest.json'
BOUNDS = [1, 0, 79, 21]


def source_evidence():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    source = tour.DAT/'juiblex.lua'
    with tarfile.open(archive) as upstream:
        matches = [m for m in upstream.getmembers() if m.name.endswith('/dat/juiblex.lua')]
        assert len(matches) == 1, matches
        original = upstream.extractfile(matches[0]).read()
    assert source.read_bytes() == original, 'Juiblex source differs from pinned upstream'
    text = original.decode()
    assert 'style = "swamp", lit = 0' in text
    assert '"shortsighted"' in text and 'type="swamp", filled=2' in text
    return dict(sourceScript='vendor/NetHack-5.0.0/dat/juiblex.lua',
        juiblexSourceSHA256=tour.digest(source), upstreamArchiveSHA256=tour.digest(archive),
        unchangedUpstreamSource=True, originalSourceFeatures=dict(
            generator='Unlit swamp, not a masonry palace.',
            lair='Original water-ringed dry islands, pools, fountains and fountain-appearing giant mimics.',
            population='Original Juiblex, lemures, blob/jelly/pudding/fungus classes, jellyfish and mimics.',
            flags='mazelevel, shortsighted, noflip, temperate'))


def privacy(cells, mode):
    cells = list(cells)
    assert cells and len({(c['x'], c['y']) for c in cells}) == len(cells)
    hidden = [c for c in cells if c['tile'] in (1469, 1470)]
    known = [c for c in cells if c['tile'] not in (1469, 1470)]
    assert known and all(c.get('material') in (None, 'juiblex') for c in known), 'Unexpected regional material'
    assert all('material' not in c for c in hidden), 'Hidden regional material disclosed'
    assert all('groundTile' not in c for c in hidden), 'Hidden ground disclosed'
    if mode == 'exploration':
        assert hidden, 'Unrevealed arrival must retain unknown cells'
    else:
        assert any(c['tile'] in (1314, 1315) for c in cells), 'Missing original water'
        assert any(c['tile'] in (1291, 1292) for c in cells), 'Missing dry floor'
    return dict(knownCells=len(known), hiddenCells=len(hidden),
        noRegionalMaterial=all('material' not in c for c in cells), noHiddenGround=True)


def worker(mode):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == 'juiblex'))
    assert case['source'] is None and case['target'] == 'juiblex'
    run = ART/('juiblex-original-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case, mode, run)
    assert metadata['identity']['branch'] == 'Gehennom'
    assert metadata['case']['source'] is None
    assert metadata['destination'].lstrip('* ').startswith('juiblex:')
    cells = checks.displayed_cells(run/'preparation.jsonl')
    floors = Counter(c['tile'] for c in cells if c.get('char') == '.')
    assert floors, 'No displayed dry floor for restored native readiness'
    metadata.update(source_evidence(), checkpoint=str(run), displayedCells=cells,
        shapeBounds=BOUNDS, worldSelected=True, targetedLayout=False,
        designPreviewOnly=True, gameplayPlaytestPerformed=False,
        perception=privacy(cells, mode),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        testTerrainTiles=[next(t for t in (1291, 1292) if floors[t])],
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    metadata['sources']['juiblex.lua'] = metadata['juiblexSourceSHA256']
    metadata['setup'].append(
        'Original world-selected unrevealed Juiblex arrival. No source reset/reload, map reveal, extra protection, supplied inventory or viewpoint placement.'
        if mode == 'exploration' else
        'Original world-selected Juiblex level with upstream swamp generation, original dry ground, water, stairs, fountains, disguised mimics, traps, loot and active occupants retained. No source reset/reload or viewpoint placement. Wizard reveal supplies remembered remote terrain, not hidden occupants or local encounters.')
    checks.write(run/'metadata.json', metadata)
    print(json.dumps(dict(run=str(run), metadata=metadata)))


def restore(row):
    run = Path(tempfile.mkdtemp(prefix='juiblex-independent-restore-', dir=ART))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game', directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat')
    game = checks.open_game(directory)
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text', '') for e in game.events)
        assert tour.identity(game, directory) == row['metadata']['identity']
        assert list(game.cursor) == list(row['metadata']['arrival'])
        perception = privacy(game.cells.values(), row['metadata']['mode'])
        inspections = []
        before = game.turn
        for category, predicate in (
            ('water', lambda c: c['tile'] in (1314, 1315)),
            ('dry-floor', lambda c: c['tile'] in (1291, 1292)),
            ('unknown', lambda c: c['tile'] in (1469, 1470))):
            cell = next((c for c in game.cells.values() if predicate(c)), None)
            if not cell:
                continue
            description = game.inspect(cell['x'], cell['y'])
            assert description.strip(), (category, cell)
            if category == 'unknown':
                assert any(word in description.lower() for word in ('unknown', 'unexplored', 'nothing')), description
            inspections.append(dict(category=category, position=[cell['x'], cell['y']],
                displayedTile=cell['tile'], description=description))
        assert game.turn == before, 'Inspection spent turns'
        if row['metadata']['mode'] == 'inspection':
            assert {'water', 'dry-floor'} <= {r['category'] for r in inspections}
        else:
            assert 'unknown' in {r['category'] for r in inspections}
        row['metadata'].update(independentRestoreVerified=True,
            independentRestoreEvidence=str(run/'engine.jsonl'),
            restoredPerception=perception, turnFreeInspection=True,
            inspection=inspections,
            nativeRestoreFloorCounts=dict(Counter(c['tile'] for c in game.cells.values()
                if c.get('char') == '.')))
        game.finish(automatic=True)
        checks.write(Path(row['run'])/'metadata.json', row['metadata'])
    finally:
        checks.cleanup(run, game)


def scene(row, label):
    m = row['metadata']
    x, y, w, h = BOUNDS
    return dict(label=label, width=w, height=h,
        cells=[dict(c, x=c['x']-x, y=c['y']-y) for c in m['displayedCells']
            if x <= c['x'] < x+w and y <= c['y'] < y+h],
        sourceCheckpoint=row['run'], engine=m['engine'], app=m['app'],
        identity=m['identity'], setup=m['setup'], originalBounds=BOUNDS,
        reviewOnly=True, worldSelected=True, targetedLayout=False,
        mode=m['mode'], perception=m['perception'])


def detail(base):
    # Prefer a dense actual water/dry boundary, using only displayed terrain.
    # No hidden occupants, source-map guesses or forced local placement.
    w, h = 26, 17
    cells = {(c['x'], c['y']): c for c in base['cells']}
    water = {p for p, c in cells.items() if c['tile'] in (1314, 1315)}
    dry = {p for p, c in cells.items() if c['tile'] in (1291, 1292)}
    shores = {p for p in dry if any((p[0]+dx, p[1]+dy) in water
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)))}
    assert shores, 'No displayed water/dry shoreline'
    candidates = [(sum(x <= px < x+w and y <= py < y+h for px, py in shores), x, y)
        for x in range(base['width']-w+1) for y in range(base['height']-h+1)]
    _, x, y = max(candidates, key=lambda r: (r[0], -r[1], -r[2]))
    return dict(base, label='Actual engine Juiblex: dense displayed shoreline detail',
        width=w, height=h, cropBounds=[x, y, w, h],
        cells=[dict(c, x=c['x']-x, y=c['y']-y) for c in base['cells']
            if x <= c['x'] < x+w and y <= c['y'] < y+h])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=('inspection', 'exploration'))
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX, INDEX.with_name('juiblex-review-prepared-before-'+stamp+'.json'))
    rows, scenes = [], {}
    for mode in ('inspection', 'exploration'):
        row = json.loads(subprocess.check_output([sys.executable, str(Path(__file__)),
            '--worker', mode], text=True))
        restore(row)
        rows.append(row)
        if mode == 'inspection':
            scenes['swamp'] = scene(row, 'Actual engine Juiblex swamp (world-selected, revealed for review)')
            scenes['swamp-detail'] = detail(scenes['swamp'])
        else:
            scenes['arrival'] = scene(row, 'Actual unrevealed world-selected Juiblex arrival')
        checks.write(INDEX, rows)
        checks.write(MANIFEST, dict(scenes=scenes, reviewOnly=True,
            note='Unchanged world-selected Juiblex inspection and unrevealed arrival. Frozen engine display; no terrain or occupant replacement, source reload or campaign playthrough.'))
        print('PREPARED Juiblex', mode, row['run'], flush=True)
    print('MANIFEST', MANIFEST, flush=True)


if __name__ == '__main__':
    main()
