#!/usr/bin/env python3
"""Prepare unchanged Minetown sources and world arrivals for artwork review.

These real-engine inspection checkpoints preserve source randomization and
actors. This recipe does not perform gameplay playtesting. All saves use an
isolated directory and the shared preparation helper's explicit empty rc.
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/minetown-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/minetown-review-validation.json'
BOUNDS = [1, 0, 79, 21]
MATERIALS = ['mines', 'mines-built']
NAMES = ['Orcish Town', 'Town Square', 'Alley Town', 'College Town',
         'Grotto Town', 'Bustling Town', 'Bazaar Town']


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def canonical_terrain_counts(cells):
    return dict(minesWallCells=sum(1471 <= c.get('tile', -1) <= 1481 for c in cells),
                mainWallCells=sum(1273 <= c.get('tile', -1) <= 1283 for c in cells),
                roomFloorCells=sum(c.get('tile') == 1291 for c in cells),
                darkRoomFloorCells=sum(c.get('tile') == 1292 for c in cells))


def finish_metadata(run, metadata):
    cells = displayed_cells(run/'preparation.jsonl')
    metadata.update(shapeBounds=BOUNDS, displayedCells=cells, expectedMaterial=MATERIALS,
                    minetownRecipe=tour.digest(Path(__file__)),
                    data=tour.digest(tour.RES/'engine/nhdat'),
                    terrainVariantCoverage='One unchanged realization per source; optional rooms, doors, cavern fill, actors and lighting retain upstream randomness.')
    # Capture checks select directly perceived floor and walls only. Ground
    # under an actor or object cannot prove the displayed terrain artwork.
    metadata['testTerrainTiles'] = sorted({c['tile'] for c in cells
        if c.get('char') in ('.', '-', '|') and c.get('tile', -1) >= 0})
    metadata['displayedMaterialCounts'] = dict(collections.Counter(
        c.get('material', 'none') for c in cells if c.get('char', '').strip()))
    metadata['canonicalTerrainCounts'] = canonical_terrain_counts(cells)
    metadata['setup'].append('Whole-level artwork review framing. Original Minetown actors, objects, traps, lighting, optional rooms and cavern fill retained. No gameplay checks or staged creature arrangements.')
    (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return dict(run=str(run), metadata=metadata)


def validate(row):
    metadata = row['metadata']
    case = metadata['case']
    run = Path(row['run'])
    assert metadata['engine'] == tour.digest(tour.RES/'engine/nethack'), 'Prepared engine changed'
    assert metadata['app'] == tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'), 'Prepared app changed'
    assert metadata['data'] == tour.digest(tour.RES/'engine/nhdat'), 'Prepared level data changed'
    assert metadata['identity']['branch'] == 'The Gnomish Mines', metadata['identity']
    assert metadata['destination'].lstrip('* ').startswith('minetn:'), metadata['destination']
    assert metadata['shapeBounds'] == BOUNDS
    assert (run/'game/playtest.nethackrc').read_text() == '', 'Preparation configuration was not empty'
    assert any((run/'game/save').iterdir()), 'Missing real-engine checkpoint'
    if case.get('source'):
        assert metadata['sources'][case['source']] == tour.digest(tour.DAT/case['source']), 'Pinned source changed'
    cells = displayed_cells(run/'preparation.jsonl')
    assert cells == metadata['displayedCells'], 'Stored displayed cells differ from engine trace'
    terrain_counts = canonical_terrain_counts(cells)
    assert terrain_counts == metadata['canonicalTerrainCounts'], 'Stored canonical terrain counts differ from trace'
    assert terrain_counts['minesWallCells'] > 0 and terrain_counts['mainWallCells'] == 0, 'Unexpected canonical Minetown wall tiles'
    assert terrain_counts['roomFloorCells'] > 0, 'Missing perceived ordinary floor'
    assert metadata['testTerrainTiles'], 'No directly perceived stable ground/wall tile'
    assert all(1 <= c['x'] <= 79 and 0 <= c['y'] <= 20 for c in cells), 'Displayed cell outside map'
    blank = [c for c in cells if c.get('tile') in (1469, 1470)]
    assert all('material' not in c and 'groundTile' not in c for c in blank), 'Unexplored cell leaked regional ground'
    known = [c for c in cells if c['tile'] not in (1469, 1470)]
    assert known and all(c.get('material') in MATERIALS for c in known), 'Unexpected material on named Minetown level'
    result = dict(case=case['id'], mode=metadata['mode'],
        branch=metadata['identity'], destination=metadata['destination'],
        sourceIdentityVerified=bool(case.get('source')),
        isolatedEmptyConfiguration=True, originalActorsRetained=True,
        displayedCells=len(cells), stableTerrainTiles=metadata['testTerrainTiles'],
        displayedMaterialCounts=metadata['displayedMaterialCounts'],
        canonicalTerrainCounts=terrain_counts,
        unknownMetadataChecked=len(blank), gameplayPlaytestPerformed=False)
    print('VALIDATED', case['label'], metadata['mode'], flush=True)
    return result


def prepare(selected=None):
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    cases = [dict(c) for c in tour.catalog() if c['group'] == 'Minetown']
    for case in cases:
        if case.get('source'):
            case['label'] = NAMES[int(case['id'].rsplit('-', 1)[1])-1]
    recipes = [(c, 'inspection') for c in cases]
    world = next(c for c in cases if c['id'] == 'minetn-world')
    recipes.append((dict(world, id='minetn-world-exploration',
                         label='World-selected arrival / unrevealed'), 'exploration'))
    rows = []
    for case, mode in recipes:
        if selected and case['id'] not in selected:
            continue
        # Minetown normally exists in every world. Bound only genuine missing
        # destination retries, with failures preserved for diagnosis.
        for attempt in range(3):
            run = Path(tempfile.mkdtemp(prefix='minetown-'+case['id']+'-', dir=ROOT/'.artifacts'))
            try:
                metadata = tour.prepare(case, mode, run)
                break
            except RuntimeError as error:
                (run/'failure.txt').write_text(str(error)+'\n')
                if 'World has no destination' not in str(error):
                    raise
        else:
            raise RuntimeError('Three isolated worlds lacked Minetown; diagnostics preserved.')
        row = finish_metadata(run, metadata)
        validate(row)
        rows.append(row)
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], mode, run, flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--case', action='append', help='Restrict preparation/validation to these case IDs')
    args = parser.parse_args()
    rows = prepare(args.case) if args.prepare else json.loads(INDEX.read_text())
    if args.validate:
        results = [validate(row) for row in rows
                   if not args.case or row['metadata']['case']['id'] in args.case]
        RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
