#!/usr/bin/env python3
"""Verify approved Baalzebub Gehennom wall/floor reuse using unchanged saves.

Compare equal restore redraws from the original and rebuilt packaged engines,
check perceived material and turn-free inspections, and cross original world
boundaries. Optional native captures cover both modes and all four editions.
These isolated checks do not complete Baalzebub's encounter or a campaign.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('baalz_prepare', ROOT/'scripts/prepare-baalz-review.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks, tour = prepare.checks, prepare.tour
INDEX = ART/'baalz-production-prepared.json'
RESULTS = ART/'baalz-production-engine.json'


def checkpoint_hashes(rows):
    """Source saves and their review metadata must never be opened in place."""
    paths = [prepare.INDEX]
    for row in rows:
        run = Path(row['run'])
        paths.append(run/'metadata.json')
        paths.extend(p for p in (run/'game').rglob('*') if p.is_file())
    return {str(p): tour.digest(p) for p in sorted(paths)}


def clone(row, label):
    run = Path(tempfile.mkdtemp(prefix='baalz-production-'+label+'-', dir=ART))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game', directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat'), 'Stale checkpoint data'
    return run, directory, checks.open_game(directory)


def baseline_restore(row):
    """Restore with the exact review engine, avoiding pre-save actor memory."""
    digest = row['metadata']['engine']
    candidates = [tour.RES/'engine/nethack',
        *sorted((ROOT/'.build').glob('previous-app.*/Atlas.app/Contents/Resources/engine/nethack'))]
    engine = next((p for p in candidates if p.is_file() and tour.digest(p) == digest), None)
    assert engine, 'Original packaged review engine unavailable for equal restore comparison'
    current, game = tour.RES, None
    try:
        tour.RES = engine.parent.parent
        run, directory, game = clone(row, 'original-engine-'+row['metadata']['mode'])
        checks.settle(game)
        assert any('Restoring save file' in e.get('text', '') for e in game.events)
        assert tour.identity(game, directory) == row['metadata']['identity']
        assert list(game.cursor) == list(row['metadata']['arrival'])
        cells = copy.deepcopy(game.cells)
        perception = prepare.privacy(cells.values(), row['metadata']['mode'])
        game.finish(automatic=True)
        return cells, dict(engineSHA256=digest, run=str(run), perception=perception,
            restoreEvidence=str(run/'engine.jsonl'))
    finally:
        tour.RES = current
        if game is not None:
            checks.cleanup(run, game)


def restore(row):
    metadata = row['metadata']
    baseline, original = baseline_restore(row)
    run, directory, game = clone(row, 'restore-'+metadata['mode'])
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text', '') for e in game.events)
        assert tour.identity(game, directory) == metadata['identity']
        assert list(game.cursor) == list(metadata['arrival'])
        observed = copy.deepcopy(list(game.cells.values()))
        assert set(game.cells) == set(baseline), 'Restore changed displayed coordinates'
        for cell in observed:
            old = baseline[cell['x'], cell['y']]
            for field in ('tile', 'glyph', 'groundTile', 'char', 'color', 'pet'):
                assert cell.get(field) == old.get(field), (metadata['mode'], field, cell, old)
        perception = checks.material(observed, 'baalz')
        if metadata['mode'] == 'exploration':
            assert perception['hiddenCells'], 'Unrevealed arrival lost unknown cells'
        before = game.turn
        inspections = []
        for category, predicate in (
            ('wall', lambda c: c['tile'] in prepare.WALLS),
            ('bars', lambda c: c['tile'] == 1289),
            ('floor', lambda c: c['tile'] in prepare.FLOORS),
            ('unknown', lambda c: c['tile'] in (1469, 1470))):
            cell = next((c for c in observed if predicate(c)), None)
            if cell is None:
                continue
            description = game.inspect(cell['x'], cell['y'])
            assert description.strip(), (category, cell)
            if category == 'unknown':
                assert any(word in description.lower() for word in ('unknown', 'unexplored', 'nothing')), description
            if category == 'wall':
                assert any(word in description.lower() for word in ('wall', 'stone')), description
            if category == 'bars':
                assert 'bars' in description.lower(), description
            inspections.append(dict(category=category, position=[cell['x'], cell['y']],
                displayedTile=cell['tile'], description=description))
            assert game.turn == before, ('Inspection spent turns', category)
        required = {'wall', 'bars', 'floor'} if metadata['mode'] == 'inspection' else {'unknown', 'floor'}
        assert required <= {r['category'] for r in inspections}, (metadata['mode'], inspections)
        game.finish(automatic=True)
        meta = copy.deepcopy(metadata)
        meta.update(checkpoint=str(run), displayedCells=observed, expectedMaterial='baalz',
            integratedMaterial=True, designPreviewOnly=False,
            engine=tour.digest(tour.RES/'engine/nethack'),
            app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            originalReviewCheckpoint=row['run'], productionRestoreEvidence=str(run/'engine.jsonl'),
            originalReviewPerception=metadata['perception'], perception=perception,
            reviewTreatment='Approved exact existing Gehennom walls and ground, tagged only in perceived Baalzebub cells.',
            restoredPerception=perception, turnFreeInspection=True, inspection=inspections)
        meta['setup'].append('Approved Baalzebub walls and floors reuse the exact existing Gehennom architecture and ground. Original world-selected geometry, doors, bar eyes, features, occupants and lighting retained.')
        checks.write(run/'metadata.json', meta)
        result = dict(mode=metadata['mode'], run=str(run), material=perception,
            canonicalForegroundAndGroundPreserved=True, originalEngineRestore=original,
            turnFreeInspection=inspections, restoredIdentity=meta['identity'], sourceCheckpoint=row['run'])
        print('PASS production restore', metadata['mode'], flush=True)
        return dict(run=str(run), metadata=meta), result
    finally:
        checks.cleanup(run, game)


def boundaries(row):
    run, directory, game = clone(row, 'boundaries')
    try:
        checks.settle(game)
        origin = tour.identity(game, directory)
        records = []

        def record(label, expected, branch):
            identity = tour.identity(game, directory)
            assert identity['branch'] == branch, (label, identity)
            records.append(dict(label=label, identity=identity, expectedMaterial=expected,
                **checks.material(game.cells.values(), expected)))
            print('PASS Baalzebub boundary', label, flush=True)

        record('Original Baalzebub', 'baalz', 'Gehennom')
        depth, selection = tour.gehennom_filler_depth(game)
        checks.travel_depth(game, depth)
        assert tour.identity(game, directory)['depth'] == depth
        record('Original unnamed Gehennom filler', 'gehennom', 'Gehennom')
        for target, expected in (('valley', 'valley'), ('asmodeus', 'asmodeus'),
                ('juiblex', 'juiblex'), ('orcus', 'valley'), ('wizard1', None), ('fakewiz1', None), ('sanctum', None)):
            checks.travel_special(game, target)
            record(target, expected, 'Gehennom')
        checks.travel_depth(game, selection['invocationExcluded'])
        record('Invocation approach', None, 'Gehennom')
        checks.travel_special(game, 'tower3')
        record('Vlad tower', 'vlad', "Vlad's Tower")
        checks.travel_special(game, 'minetn-')
        record('Minetown', ['mines', 'mines-built'], 'The Gnomish Mines')
        checks.travel_special(game, 'medusa')
        record('Medusa', ['medusa', 'quest-earth'], 'The Dungeons of Doom')
        checks.travel_depth(game, 1)
        record('Main dungeon', None, 'The Dungeons of Doom')
        checks.travel_special(game, 'baalz')
        assert tour.identity(game, directory) == origin
        record('Return to original Baalzebub', 'baalz', 'Gehennom')
        game.finish(automatic=True)
        return dict(run=str(run), fillerSelection=selection, checks=records, passed=True,
            setup='Original world destinations reached with upstream wizard level travel; no source reload or map regeneration.')
    finally:
        checks.cleanup(run, game)


def native(rows):
    spec = importlib.util.spec_from_file_location('baalz_native', ROOT/'scripts/build-garden-swamp-review.py')
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    assert len(rows) == 2 and {r['metadata']['mode'] for r in rows} == {'inspection', 'exploration'}
    engine = tour.digest(tour.RES/'engine/nethack')
    app = tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')
    for row in rows:
        assert row['metadata']['engine'] == engine and row['metadata']['app'] == app, 'Stale production checkpoint'
    # The capture harness changes only the renderer's zoom and scrolling.
    # Choose camera bounds from displayed terrain, never source coordinates,
    # terrain diagnostics, hidden actors, or a moved adventurer.
    capture_rows = copy.deepcopy(rows)
    for row in capture_rows:
        meta = row['metadata']
        if meta['mode'] == 'inspection':
            bars = [c for c in meta['displayedCells'] if c['tile'] == 1289]
            assert len(bars) == 2, 'Inspection lacks the two displayed bar eyes'
            x = (min(c['x'] for c in bars) + max(c['x'] for c in bars)) // 2
            y = (min(c['y'] for c in bars) + max(c['y'] for c in bars)) // 2
            note = 'Displayed fortress bar eyes and surrounding perceived entrance architecture'
        else:
            x, y = meta['arrival']
            note = 'Actual adventurer and normally perceived arrival terrain'
        left, top = max(1, min(70, x - 5)), max(0, min(11, y - 5))
        meta['shapeBounds'] = [left, top, 10, 10]
        visible = [c for c in meta['displayedCells']
                   if left <= c['x'] < left + 10 and top <= c['y'] < top + 10]
        floor = next(c['tile'] for c in visible if c['tile'] in prepare.FLOORS)
        meta['testTerrainTiles'] = [floor]
        if meta['mode'] == 'inspection':
            assert sum(c['tile'] == 1289 for c in visible) == 2, 'Camera lacks displayed bar eyes'
            assert any(c['tile'] in prepare.WALLS for c in visible), 'Camera lacks fortress walls'
            meta['testTerrainTiles'].append(1289)
        meta['nativeCameraFrame'] = note
        meta['setup'].append('Native screenshot camera framing only: ' + note +
            '. Renderer zoom and scrolling change; hero position, terrain and perceived occupants do not.')
    results = review.capture('baalz-production', classic=True, rows=capture_rows)
    assert len(results) == 8
    assert {(r['mode'], r['tileset']) for r in results} == {
        (mode, tileset) for mode in ('inspection', 'exploration') for tileset in review.review.NAMES}
    rows_by_mode = {r['metadata']['mode']: r for r in capture_rows}
    for result in results:
        assert result['engine'] == engine and result['app'] == app
        cells = review.review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
        meta = rows_by_mode[result['mode']]['metadata']
        baseline = {(c['x'], c['y']): c for c in meta['displayedCells']}
        assert {(c['x'], c['y']) for c in cells} == set(baseline), 'Native restore changed displayed coordinates'
        for cell in cells:
            old = baseline[cell['x'], cell['y']]
            for field in ('tile', 'glyph', 'groundTile', 'char', 'color', 'pet'):
                assert cell.get(field) == old.get(field), (result['mode'], result['tileset'], field, cell, old)
        result.update(checks.material(cells, 'baalz'), approvedExactGehennomWallAndFloorReuse=True,
            cameraFramingOnly=True, cameraFrame=meta['nativeCameraFrame'],
            canonicalForegroundAndGroundPreserved=True, noHiddenGroundOrMaterial=True)
        if result['mode'] == 'exploration':
            assert result['hiddenCells'], 'Native unrevealed arrival lost unknown space'
    checks.write(ART/'baalz-production-native.json', results)
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Baalzebub production review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d6bb84}</style>',
        '<h1>Baalzebub: approved exact Gehennom walls and floors in the packaged app</h1>',
        '<p>All four editions, using the same original world-selected inspection and unrevealed arrival checkpoints as the approved review. Original fortress geometry, doors, bar eyes, features, occupants and lighting retain upstream behavior. Inspection camera framing shows displayed fortress architecture; arrival camera framing shows the actual adventurer. Camera changes affect renderer zoom and scrolling only. These checks verify presentation and restoration, not a completed encounter.</p>']
    for result in results:
        image = Path(result['screenshot']).relative_to(ART).as_posix()
        label = html.escape(result['label']+' / '+result['mode']+' / '+review.review.NAMES[result['tileset']])
        body.append('<h2>'+label+'</h2><a href="'+image+'"><img src="'+image+'" alt="'+label+'"></a>')
    body.append('</html>')
    target = ART/'baalz-native-review.html'
    target.write_text('\n'.join(body)+'\n')
    print('REVIEW', target, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    originals = json.loads(prepare.INDEX.read_text())
    assert len(originals) == 2 and {r['metadata']['mode'] for r in originals} == {'inspection', 'exploration'}
    assert all(r['metadata']['case']['source'] is None and r['metadata']['worldSelected'] for r in originals)
    preserved = checkpoint_hashes(originals)
    try:
        source = prepare.source_evidence()
        for row in originals:
            for key in ('baalzSourceSHA256', 'mkmazeSourceSHA256', 'upstreamArchiveSHA256'):
                assert row['metadata'][key] == source[key], (row['metadata']['mode'], key)
            assert row['metadata']['dataSHA256'] == tour.digest(tour.RES/'engine/nhdat')
        if args.native:
            native(json.loads(INDEX.read_text()))
            return
        rows, results = [], []
        for original in originals:
            row, result = restore(original)
            rows.append(row)
            results.append(result)
            checks.write(INDEX, rows)
            checks.write(RESULTS, dict(source=source, restores=results))
        selected = next(r for r in rows if r['metadata']['mode'] == 'inspection')
        records = boundaries(selected)
        assert checkpoint_hashes(originals) == preserved, 'Original review checkpoints changed'
        checks.write(RESULTS, dict(source=source, restores=results, boundaries=records,
            originalCheckpointsPreserved=True, passed=True))
    finally:
        assert checkpoint_hashes(originals) == preserved, 'Original review checkpoints changed'


if __name__ == '__main__':
    main()
