#!/usr/bin/env python3
"""Verify approved Juiblex dry-ground reuse using unchanged review saves.

Compare equal restore redraws from the original and rebuilt packaged engines,
check perceived material and turn-free inspections, and cross original world
boundaries. Optional native captures cover both modes and all four editions.
These isolated checks do not complete Juiblex's encounter or a campaign.
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
spec = importlib.util.spec_from_file_location('juiblex_prepare', ROOT/'scripts/prepare-juiblex-review.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks, tour = prepare.checks, prepare.tour
INDEX = ART/'juiblex-production-prepared.json'
RESULTS = ART/'juiblex-production-engine.json'


def checkpoint_hashes(rows):
    """Source saves and their review metadata must never be opened in place."""
    paths = [prepare.INDEX]
    for row in rows:
        run = Path(row['run'])
        paths.append(run/'metadata.json')
        paths.extend(p for p in (run/'game').rglob('*') if p.is_file())
    return {str(p): tour.digest(p) for p in sorted(paths)}


def clone(row, label):
    run = Path(tempfile.mkdtemp(prefix='juiblex-production-'+label+'-', dir=ART))
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
            for field in ('tile', 'groundTile', 'char', 'color', 'pet'):
                assert cell.get(field) == old.get(field), (metadata['mode'], field, cell, old)
        perception = checks.material(observed, 'juiblex')
        if metadata['mode'] == 'exploration':
            assert perception['hiddenCells'], 'Unrevealed arrival lost unknown cells'
        before = game.turn
        inspections = []
        for category, predicate in (
            ('water', lambda c: c['tile'] in (1314, 1315)),
            ('dry-floor', lambda c: c['tile'] in (1291, 1292)),
            ('unknown', lambda c: c['tile'] in (1469, 1470))):
            cell = next((c for c in observed if predicate(c)), None)
            if cell is None:
                continue
            description = game.inspect(cell['x'], cell['y'])
            assert description.strip(), (category, cell)
            if category == 'unknown':
                assert any(word in description.lower() for word in ('unknown', 'unexplored', 'nothing')), description
            inspections.append(dict(category=category, position=[cell['x'], cell['y']],
                displayedTile=cell['tile'], description=description))
            assert game.turn == before, ('Inspection spent turns', category)
        required = {'water', 'dry-floor'} if metadata['mode'] == 'inspection' else {'unknown', 'dry-floor'}
        assert required <= {r['category'] for r in inspections}, (metadata['mode'], inspections)
        game.finish(automatic=True)
        meta = copy.deepcopy(metadata)
        meta.update(checkpoint=str(run), displayedCells=observed, expectedMaterial='juiblex',
            integratedMaterial=True, designPreviewOnly=False,
            engine=tour.digest(tour.RES/'engine/nethack'),
            app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            originalReviewCheckpoint=row['run'], productionRestoreEvidence=str(run/'engine.jsonl'),
            restoredPerception=perception, turnFreeInspection=True, inspection=inspections)
        meta['setup'].append('Approved Juiblex dry floors reuse the exact Gehennom ground. Original world-selected geometry, water, occupants and lighting retained.')
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
            print('PASS Juiblex boundary', label, flush=True)

        record('Original Juiblex', 'juiblex', 'Gehennom')
        depth, selection = tour.gehennom_filler_depth(game)
        checks.travel_depth(game, depth)
        assert tour.identity(game, directory)['depth'] == depth
        record('Original unnamed Gehennom filler', 'gehennom', 'Gehennom')
        for target, expected in (('valley', 'valley'), ('asmodeus', 'asmodeus'),
                ('baalz', 'baalz'), ('wizard1', None), ('fakewiz1', None), ('sanctum', None)):
            checks.travel_special(game, target)
            record(target, expected, 'Gehennom')
        checks.travel_depth(game, selection['invocationExcluded'])
        record('Invocation approach', None, 'Gehennom')
        checks.travel_special(game, 'tower3')
        record('Vlad tower', 'vlad', "Vlad's Tower")
        checks.travel_special(game, 'minetn-')
        record('Minetown', 'mines', 'The Gnomish Mines')
        checks.travel_depth(game, 1)
        record('Main dungeon', None, 'The Dungeons of Doom')
        checks.travel_special(game, 'juiblex')
        assert tour.identity(game, directory) == origin
        record('Return to original Juiblex', 'juiblex', 'Gehennom')
        game.finish(automatic=True)
        return dict(run=str(run), fillerSelection=selection, checks=records, passed=True,
            setup='Original world destinations reached with upstream wizard level travel; no source reload or map regeneration.')
    finally:
        checks.cleanup(run, game)


def native(rows):
    spec = importlib.util.spec_from_file_location('juiblex_native', ROOT/'scripts/build-garden-swamp-review.py')
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    assert len(rows) == 2 and {r['metadata']['mode'] for r in rows} == {'inspection', 'exploration'}
    engine = tour.digest(tour.RES/'engine/nethack')
    app = tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')
    for row in rows:
        assert row['metadata']['engine'] == engine and row['metadata']['app'] == app, 'Stale production checkpoint'
    # The harness has a minimum zoom, so a full 79-column frame cannot fit.
    # Center a close view on the actual adventurer, not remote unknown terrain.
    capture_rows = copy.deepcopy(rows)
    for row in capture_rows:
        meta = row['metadata']
        x, y = meta['arrival']
        left, top = max(1, min(70, x - 5)), max(0, min(11, y - 5))
        meta['shapeBounds'] = [left, top, 10, 10]
        visible = [c for c in meta['displayedCells']
                   if left <= c['x'] < left + 10 and top <= c['y'] < top + 10]
        floor = next(c['tile'] for c in visible if c['tile'] in (1291, 1292))
        assert any(c['tile'] == 1314 for c in visible), 'Hero crop lacks known water'
        meta['testTerrainTiles'] = [floor, 1314]
        meta['setup'].append('Native screenshot camera framed around the actual hero; no viewpoint placement or terrain change.')
    results = review.capture('juiblex-production', classic=True, rows=capture_rows)
    assert len(results) == 8
    assert {(r['mode'], r['tileset']) for r in results} == {
        (mode, tileset) for mode in ('inspection', 'exploration') for tileset in review.review.NAMES}
    for result in results:
        assert result['engine'] == engine and result['app'] == app
        cells = review.review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
        result.update(checks.material(cells, 'juiblex'), approvedGehennomDryGroundReuse=True)
        if result['mode'] == 'exploration':
            assert result['hiddenCells'], 'Native unrevealed arrival lost unknown space'
    checks.write(ART/'juiblex-production-native.json', results)
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Juiblex production review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d6bb84}</style>',
        '<h1>Juiblex: approved Gehennom dry ground in the packaged app</h1>',
        '<p>All four editions, using the same original world-selected inspection and unrevealed arrival checkpoints as the approved review. Water, features, occupants and lighting retain upstream behavior. These checks verify presentation and restoration, not a completed encounter.</p>']
    for result in results:
        image = Path(result['screenshot']).relative_to(ART).as_posix()
        label = html.escape(result['label']+' / '+result['mode']+' / '+review.review.NAMES[result['tileset']])
        body.append('<h2>'+label+'</h2><a href="'+image+'"><img src="'+image+'" alt="'+label+'"></a>')
    body.append('</html>')
    target = ART/'juiblex-native-review.html'
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
            assert row['metadata']['juiblexSourceSHA256'] == source['juiblexSourceSHA256']
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
