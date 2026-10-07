#!/usr/bin/env python3
"""Prepare original Mines' End layouts for visual review, without playtesting.

Four disposable packaged-engine games retain original source randomness and
active occupants: the three pinned layouts and one world-selected arrival.
The shared inspection recipe reveals the map and supplies inspection protection.
This script checks source identity, display framing and current material setup;
it does not exercise movement, traps, combat or a gameplay save/restore suite.
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mines_end_tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/mines-end-rooms-prepared.json'
BOUNDS = [1, 0, 79, 21]
MINES_WALL_TILES = set(range(1471, 1482))
LAYOUTS = {
    'minend-1': ('Mimic of the Mines', 'Irregular mine passages and locked treasure niches.'),
    'minend-2': ("Gnome King's Wine Cellar", 'Constructed cellar and rectilinear corridors, with an irregular eastern treasure gallery.'),
    'minend-3': ('Catacombs', 'Wallified maze and enclosed chambers with fountains and doors.'),
}


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def finish_metadata(run, metadata):
    case = metadata['case']
    cells = displayed_cells(run/'preparation.jsonl')
    # Anchors come only from displayed ordinary terrain, never hidden contents.
    terrain = {c['tile'] for c in cells
               if c.get('char') in ('.', '-', '|') and c.get('tile', -1) >= 0}
    floors = sorted({c['tile'] for c in cells if c.get('char') == '.' and c.get('tile', -1) >= 0})
    metadata.update(shapeBounds=BOUNDS, displayedCells=cells,
                    testTerrainTiles=floors[:1] or sorted(terrain)[:1],
                    minesEndReviewRecipe=tour.digest(Path(__file__)),
                    sourceRandomness='One unchanged realization per original source; source RNG combinations are not exhaustive.',
                    canonicalMinesWallTiles=sorted({c['tile'] for c in cells if c.get('char') in ('-', '|')}),
                    materialReview='All Mines levels use the Mines regional material: approved rock/support walls and dirt/gravel floors. Canonical tiles and gameplay are unchanged; no per-cell classification.',
                    gameplayPlaytestPerformed=False)
    if case.get('source'):
        name, description = LAYOUTS[case['id']]
        metadata['sourceLabel'] = name
        metadata['sourceGeometry'] = description
    else:
        metadata['sourceLabel'] = 'World-selected Mines\u2019 End'
        metadata['sourceGeometry'] = 'Original world-selected layout; no layout source was replaced.'
        # Preserve provenance for the complete source pool without claiming that
        # the wizard destination menu identifies the selected source suffix.
        metadata['worldSourcePool'] = {f'minend-{i}.lua': tour.digest(tour.DAT/f'minend-{i}.lua')
                                       for i in range(1, 4)}
    metadata['setup'].append('Whole-level screenshot framing. Original terrain, lighting, secret doors, traps, objects and active occupants retained. No gameplay playtest requested or performed.')
    (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return dict(run=str(run), metadata=metadata)


def check(row):
    """Validate recorded evidence only; do not restore or operate the game."""
    metadata = row['metadata']
    case = metadata['case']
    assert metadata['engine'] == tour.digest(tour.RES/'engine/nethack'), 'Prepared engine changed'
    assert metadata['app'] == tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'), 'Prepared app changed'
    assert metadata['recipe'] == tour.digest(ROOT/'scripts/playtest/prepare.py'), 'Shared preparation recipe changed'
    assert metadata['minesEndReviewRecipe'] == tour.digest(Path(__file__)), 'Review recipe changed'
    assert metadata['identity']['branch'] == 'The Gnomish Mines', metadata['identity']
    destination = re.search(r'minend:\s*(-?\d+)', metadata['destination'])
    assert destination and int(destination[1]) == metadata['identity']['depth'], metadata['destination']
    for source, digest in {**metadata['sources'], **metadata.get('worldSourcePool', {})}.items():
        assert digest == tour.digest(tour.DAT/source), 'Original source changed: '+source
    if case.get('source'):
        assert case['source'] == case['id']+'.lua' and case['source'] in metadata['sources']
    directory = Path(row['run'])/'game'
    assert (directory/'playtest.nethackrc').read_text() == '', 'Preparation configuration was not isolated and empty'
    assert any((directory/'save').iterdir()), 'No prepared inspection checkpoint'
    cells = metadata['displayedCells']
    assert cells and metadata['testTerrainTiles'], 'Missing safely perceived terrain anchor'
    assert metadata['shapeBounds'] == BOUNDS
    known = [c for c in cells if c['tile'] not in (1469, 1470)]
    assert known and all(c.get('material') == 'mines' for c in known), 'Missing Mines material on named level'
    walls = {c['tile'] for c in cells if c.get('char') in ('-', '|')}
    assert walls and walls <= MINES_WALL_TILES, ('Canonical Mines walls changed', walls)
    assert metadata['canonicalMinesWallTiles'] == sorted(walls), 'Recorded wall slots changed'
    unknown = [c for c in cells if c.get('tile') in (1469, 1470)]
    assert all('groundTile' not in c and 'material' not in c for c in unknown), 'Blank cell exposed supplemental metadata'
    return dict(case=case['id'], source=case.get('source'), identity=metadata['identity'],
                sourceDigestsVerified=True, explicitEmptyConfiguration=True,
                displayedCells=len(cells), perceivedTerrainAnchors=metadata['testTerrainTiles'],
                materialCounts=dict(collections.Counter(c.get('material', 'canonical-branch-artwork') for c in cells)),
                canonicalMinesWallTiles=sorted(walls),
                blankMetadataChecked=len(unknown), originalActorsRetained=True,
                gameplayPlaytestPerformed=False)


def prepare(selected=None):
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    cases = [c for c in tour.catalog() if c['group'] == 'Mines\u2019 End']
    rows = []
    for original in cases:
        if selected and original['id'] not in selected:
            continue
        case = dict(original)
        if case['id'] in LAYOUTS:
            case['label'] = LAYOUTS[case['id']][0]
        run = Path(tempfile.mkdtemp(prefix='mines-end-review-'+case['id']+'-', dir=ROOT/'.artifacts'))
        metadata = tour.prepare(case, 'inspection', run)
        row = finish_metadata(run, metadata)
        check(row)
        rows.append(row)
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['id'], metadata['identity'], run, flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Prepare four fresh isolated inspection examples')
    parser.add_argument('--check', action='store_true', help='Check recorded sources, display and material setup without gameplay')
    parser.add_argument('--case', action='append', help='Restrict to these case IDs')
    args = parser.parse_args()
    rows = prepare(args.case) if args.prepare else json.loads(INDEX.read_text())
    if args.check:
        for row in rows:
            if not args.case or row['metadata']['case']['id'] in args.case:
                print(json.dumps(check(row)), flush=True)
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
