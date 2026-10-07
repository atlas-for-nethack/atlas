#!/usr/bin/env python3
"""Capture unchanged Medusa variants and a natural arrival for art review.

The four variants are targeted upstream Lua reloads at a real Medusa depth.
The unrevealed arrival is world-selected and never source-reloaded. Wizard
travel, reveal, protection and supplied inventory are recorded explicitly.
No production artwork or engine source is changed by this recipe.
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
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('medusa_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'medusa-review-prepared.json'
MANIFEST = ART/'medusa-review-manifest.json'
BOUNDS = [1, 0, 79, 21]
MATERIALS = ['medusa', 'quest-earth']


def source_evidence():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    sources = {}
    with tarfile.open(archive) as upstream:
        for number in range(1, 5):
            name = f'medusa-{number}.lua'
            matches = [m for m in upstream.getmembers() if m.name.endswith('/dat/'+name)]
            assert len(matches) == 1, matches
            original = upstream.extractfile(matches[0]).read()
            assert original == (tour.DAT/name).read_bytes(), name+' differs from bundled upstream'
            sources[name] = tour.digest(tour.DAT/name)
    return dict(sources=sources, unchangedUpstreamSource=True,
                upstreamArchiveSHA256=tour.digest(archive))


def privacy(cells, mode, expected=None):
    assert cells and len({(c['x'], c['y']) for c in cells}) == len(cells)
    hidden = [c for c in cells if c['tile'] in (1469, 1470)]
    known = [c for c in cells if c['tile'] not in (1469, 1470)]
    allowed = expected if isinstance(expected, (list, tuple)) else [expected]
    assert all(c.get('material') in allowed for c in known), 'Wrong Medusa context'
    assert all(c['tile'] in (1291, 1292) or c.get('groundTile') in (1291, 1292)
               for c in known if c.get('material') == 'quest-earth'), 'Exterior earth requires safely known dry support'
    assert all('material' not in c for c in hidden), 'Hidden material disclosed'
    assert known and all('groundTile' not in c for c in hidden), 'Hidden ground disclosed'
    if mode == 'exploration':
        assert hidden, 'Unrevealed arrival must retain unknown terrain'
    else:
        assert any(1273 <= c['tile'] <= 1283 for c in cells), 'Missing canonical dungeon walls'
        assert any(c['tile'] in (1314, 1315) for c in cells), 'Missing original water'
    return dict(knownCells=len(known), hiddenCells=len(hidden),
                expectedMaterial=expected, noRegionalMaterial=expected is None, noHiddenGround=True)


def worker(case_id, expected):
    ART.mkdir(exist_ok=True)
    case = dict(next(c for c in tour.catalog() if c['id'] == case_id))
    mode = 'exploration' if case_id == 'medusa-world' else 'inspection'
    run = ART/('medusa-original-'+case_id+'-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case, mode, run)
    assert metadata['identity']['branch'] == 'The Dungeons of Doom'
    assert metadata['case']['source'] == (None if case_id == 'medusa-world' else case_id+'.lua')
    cells = checks.displayed_cells(run/'preparation.jsonl')
    world_selected = case_id == 'medusa-world'
    metadata.update(source_evidence(), checkpoint=str(run), displayedCells=cells,
        shapeBounds=BOUNDS, worldSelected=world_selected, targetedLayout=not world_selected,
        designPreviewOnly=expected is None, integratedMaterial=expected is not None, expectedMaterial=expected,
        gameplayPlaytestPerformed=False, perception=privacy(cells, mode, expected),
        displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    floors = Counter(c['tile'] for c in cells if c.get('char') == '.')
    assert floors, 'No displayed plain floor for restore readiness'
    metadata['testTerrainTiles'] = [next(t for t in (1291, 1292) if floors[t])]
    metadata['setup'].append(
        'World-selected unrevealed Medusa arrival: no source reload, map reveal, extra protection or supplied inventory.'
        if world_selected else
        'Targeted Medusa variant: unchanged bundled upstream Lua loaded with des.reset_level and des.finalize_level into a real Medusa branch/depth. Original terrain, water, doors, lighting, traps, statues, random contents and active occupants retained. No local viewpoint placement. Mapped remote terrain does not establish local perception or encounters.')
    checks.write(run/'metadata.json', metadata)
    print(json.dumps(dict(run=str(run), metadata=metadata)))


def restore(row):
    run, directory, game = checks.clone(row, 'medusa-review-restore')
    try:
        checks.settle(game)
        assert any('Restoring save file' in e.get('text', '') for e in game.events)
        assert tour.identity(game, directory) == row['metadata']['identity']
        assert list(game.cursor) == list(row['metadata']['arrival'])
        privacy(list(game.cells.values()), row['metadata']['mode'], row['metadata']['expectedMaterial'])
        row['metadata'].update(independentRestoreVerified=True,
            independentRestoreEvidence=str(run/'engine.jsonl'))
        game.finish(automatic=True)
        checks.write(Path(row['run'])/'metadata.json', row['metadata'])
    finally:
        checks.cleanup(run, game)


def scene(row, label):
    m = row['metadata']
    x, y, w, h = m['shapeBounds']
    return dict(label=label, width=w, height=h,
        cells=[dict(c, x=c['x']-x, y=c['y']-y) for c in m['displayedCells']
               if x <= c['x'] < x+w and y <= c['y'] < y+h],
        sourceCheckpoint=row['run'], engine=m['engine'], app=m['app'],
        identity=m['identity'], setup=m['setup'], originalBounds=m['shapeBounds'],
        reviewOnly=True, worldSelected=m['worldSelected'], targetedLayout=m['targetedLayout'],
        mode=m['mode'], perception=m['perception'])


def detail(base, number):
    # Use only actually displayed walls, never hidden occupants or source-map
    # coordinates. Select the densest 26 by 17 masonry window after map flips.
    width, height = 26, 17
    walls = [c for c in base['cells'] if 1273 <= c['tile'] <= 1283]
    assert walls, 'No mapped building walls'
    choices = [(sum(x <= c['x'] < x+width and y <= c['y'] < y+height for c in walls), x, y)
               for x in range(base['width']-width+1)
               for y in range(base['height']-height+1)]
    _, x, y = max(choices, key=lambda choice: (choice[0], -choice[1], -choice[2]))
    return dict(base, label=f'Layout {number}: original island building detail',
        width=width, height=height, cropBounds=[x, y, width, height],
        cells=[dict(c, x=c['x']-x, y=c['y']-y) for c in base['cells']
               if x <= c['x'] < x+width and y <= c['y'] < y+height])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=[f'medusa-{i}' for i in range(1, 5)]+['medusa-world'])
    parser.add_argument('--material', choices=('none','medusa'), default='medusa')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, None if args.material=='none' else MATERIALS)
        return
    ART.mkdir(exist_ok=True)
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX, INDEX.with_name('medusa-review-prepared-before-'+stamp+'.json'))
    rows, scenes = [], {}
    for case_id in [f'medusa-{i}' for i in range(1, 5)]+['medusa-world']:
        row = json.loads(subprocess.check_output([sys.executable, str(Path(__file__)),
            '--worker', case_id, '--material', args.material], text=True))
        restore(row)
        rows.append(row)
        if case_id == 'medusa-world':
            scenes['arrival'] = scene(row, 'Actual unrevealed world-selected Medusa arrival')
        else:
            number = int(case_id.rsplit('-', 1)[1])
            key = f'layout-{number}'
            scenes[key] = scene(row, f'Actual engine Medusa layout {number} (targeted upstream reload)')
            scenes[key+'-detail'] = detail(scenes[key], number)
        checks.write(INDEX, rows)
        checks.write(MANIFEST, dict(scenes=scenes, reviewOnly=True,
            expectedMaterial=None if args.material=='none' else MATERIALS,
            note='Four unchanged upstream targeted Medusa variants plus unrevealed world-selected arrival. Frozen engine display, not a campaign playthrough. Material integration is recorded separately.'))
        print('PREPARED', case_id, row['run'], flush=True)
    print('MANIFEST', MANIFEST, flush=True)


if __name__ == '__main__':
    main()
