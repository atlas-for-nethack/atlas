#!/usr/bin/env python3
"""Prepare all thirteen unchanged Big Room sources and real world arrivals.

This is a baseline and visual-review recipe, not a completed Big Room campaign.
Random terrain variants, lighting, contents, and active actors remain upstream.
All operations use disposable saves and an explicit empty configuration file.
"""
import argparse
import collections
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/big-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/big-rooms-engine.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
BOUNDS = [1, 0, 79, 21]


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def finish_metadata(case, mode, run, metadata):
    metadata['shapeBounds'] = BOUNDS
    metadata['displayedCells'] = displayed_cells(run/'preparation.jsonl')
    # Select stable safely perceived ground, never a monster or hidden feature.
    terrain = {c['tile'] for c in metadata['displayedCells']
               if c.get('char') == '.' and c.get('tile', -1) >= 0}
    metadata['testTerrainTiles'] = sorted(terrain)[:1]
    metadata['bigRoomRecipe'] = tour.digest(Path(__file__))
    metadata['terrainVariantCoverage'] = 'Unchanged random realizations, not every source-authorized RNG combination.'
    metadata['setup'].append('All original Big Room layout, lighting, object, trap and monster generation retained. Whole map review framing; no staged creature arrangements.')
    (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return dict(run=str(run), metadata=metadata)


def prepare(selected=None):
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    cases = [c for c in tour.catalog() if c['group'] == 'Big Room']
    recipes = [(c, 'inspection') for c in cases]
    world = next(c for c in cases if c['id'] == 'bigrm-world')
    recipes.append((dict(world, id='bigrm-world-exploration',
                         label='World-selected arrival / unrevealed'), 'exploration'))
    rows = []
    for case, mode in recipes:
        if selected and case['id'] not in selected:
            continue
        for attempt in range(20):
            run = Path(tempfile.mkdtemp(prefix='big-rooms-'+case['id']+'-', dir=ROOT/'.artifacts'))
            try:
                metadata = tour.prepare(case, mode, run)
                break
            except RuntimeError as error:
                (run/'failure.txt').write_text(str(error)+'\n')
                if 'World has no destination' not in str(error):
                    raise
        else:
            raise RuntimeError('Twenty isolated worlds lacked a Big Room; diagnostics preserved.')
        rows.append(finish_metadata(case, mode, run, metadata))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], mode, run, flush=True)
    return rows


def extra_ice(rows):
    """Retain the first original layout-2 roll containing perceived ice.

    Inspecting a known result to select a review sample does not replace source
    randomness or add terrain. Unselected original rolls remain in artifacts.
    """
    catalog = json.loads((ROOT/'assets/tiles/lantern/catalog.json').read_text())
    ice_tiles = set(next(row['slots'] for row in catalog['art_keys'] if row['key'] == 'terrain/ice'))
    if any(c.get('tile') in ice_tiles for row in rows for c in row['metadata']['displayedCells']):
        return rows
    original = next(c for c in tour.catalog() if c['id'] == 'bigrm-2')
    case = dict(original, id='bigrm-2-ice-sample', label='Layout 2 / original ice roll')
    for attempt in range(40):
        run = Path(tempfile.mkdtemp(prefix='big-rooms-ice-roll-', dir=ROOT/'.artifacts'))
        try:
            metadata = tour.prepare(case, 'inspection', run)
        except RuntimeError as error:
            (run/'failure.txt').write_text(str(error)+'\n')
            if 'World has no destination' in str(error):
                continue
            raise
        row = finish_metadata(case, 'inspection', run, metadata)
        if any(c.get('tile') in ice_tiles for c in metadata['displayedCells']):
            metadata['setup'].append('Extra original layout-2 realization selected after observing perceived ice. No random override, forced terrain or source edits.')
            (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
            rows.append(row)
            INDEX.write_text(json.dumps(rows, indent=2)+'\n')
            print('PREPARED extra original ice sample', run, flush=True)
            return rows
    raise RuntimeError('No perceived ice in forty unchanged layout-2 worlds; all original rolls retained.')


def actual_terrain(game, directory):
    start = len(game.events)
    # Diagnostic oracle in the check clone only. It never enters a capture or
    # player checkpoint, and is never used to select a hidden safe route.
    tour.lua(game, directory, '''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("BIGROOM_ORACLE:"..x..","..y..","..m.typ_name..","..tostring(m.lit));
end end;''')
    cells = [e['text'].split(':', 1)[1].split(',') for e in game.events[start:]
             if e.get('text', '').startswith('BIGROOM_ORACLE:')]
    assert len(cells) == 79*21, len(cells)
    return cells


def open_game(directory):
    config = directory/'test.nethackrc'
    config.write_text('')
    os.environ.update(NETHACKDIR=str(directory), HACKDIR=str(directory), ATLAS_PLAY_MODE='standard')
    module = tour.load_game_module()
    class ClearAwareGame(module.Game):
        def next(self):
            event = super().next()
            if event['type'] == 'clear' and event.get('window') == 'map':
                self.cells.clear()
            return event
    return ClearAwareGame(directory, name='wizard', options=OPTIONS, config=config)


def check(data):
    metadata = data['metadata']
    case = metadata['case']
    assert metadata['engine'] == tour.digest(tour.RES/'engine/nethack'), 'Prepared engine changed'
    assert metadata['app'] == tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'), 'Prepared app changed'
    if case.get('source'):
        assert metadata['sources'][case['source']] == tour.digest(tour.DAT/case['source']), 'Pinned layout source changed'
    run = Path(tempfile.mkdtemp(prefix='big-rooms-check-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    game = open_game(directory)
    events = []
    result = dict(case=case['id'], label=case['label'], mode=metadata['mode'], run=str(run),
                  isolatedConfiguration=True, source=case.get('source'),
                  sourceIdentityVerified=bool(case.get('source')),
                  originalActorsRetained=True, movement=[],
                  exclusions=['No exhaustive RNG variants, trap activation, water/lava crossing, ice sliding, boulder pushing, combat, or full stairs playthrough.'])
    try:
        tour.settle(game)
        assert game.cursor == tuple(metadata['arrival']), (game.cursor, metadata['arrival'])
        assert game.turn == int(metadata['status'].get('16', metadata['status'].get(16)).strip())
        before = game.turn
        samples = [game.cursor]
        for char in ['.', '}', 'L', 'I', 'T', '#', '-', '|']:
            p = next((p for p,c in game.cells.items() if c.get('char') == char), None)
            if p is not None and p not in samples:
                samples.append(p)
        result['inspection'] = [dict(position=list(p), description=game.inspect(*p)) for p in samples]
        assert game.turn == before, 'Inspection consumed a turn'
        result['turnFreeInspection'] = True
        # Upstream unexplored/dark/stone glyphs have valid canonical tiles.
        # Blank glyphs must still carry no supplemental ground or material.
        unknown = [(p,c) for p,c in game.cells.items() if c.get('char') == ' ']
        for p,c in unknown:
            assert 'groundTile' not in c and 'material' not in c, (p,c)
        result['unknownMetadataChecked'] = len(unknown)
        if metadata['mode'] == 'exploration':
            assert unknown, 'Unrevealed arrival has no unknown map cells'
            p, description = next((p, description) for p,c in unknown
                                  if 'unexplored' in (description := game.inspect(*p)).lower())
            assert game.turn == before
            result['unknownInspection'] = dict(position=list(p), description=description)
        assert all('material' not in c for c in game.cells.values()), 'Big Room received unrelated regional material'
        result['ordinaryDungeonMaterialVerified'] = True
        catalog = json.loads((ROOT/'assets/tiles/lantern/catalog.json').read_text())
        boulder_tiles = set(next(row['slots'] for row in catalog['art_keys']
                                 if row['key'] == 'object/large-rock/boulder'))
        result['perceivedBoulderCount'] = sum(c.get('tile') in boulder_tiles for c in game.cells.values())
        if case.get('source') == 'bigrm-11.lua':
            assert result['perceivedBoulderCount'] > 0, 'Original boulder maze has no perceived boulders'
        cells = actual_terrain(game, directory)
        result['terrainCounts'] = dict(sorted(collections.Counter(c[2] for c in cells).items()))
        result['lightingCounts'] = dict(sorted(collections.Counter(c[3] for c in cells).items()))
        assert result['terrainCounts'].get('room', 0) > 200, result['terrainCounts']
        result['observedTerrainCombination'] = sorted(kind for kind in result['terrainCounts']
                                                     if kind not in ('stone', 'room', 'stairs') and 'wall' not in kind)
        result['observedHazardWallTypes'] = sorted(kind for kind in result['terrainCounts']
                                                 if kind in ('water', 'lava wall'))
        # A displayed floor may contain an undiscovered trap. Attempt only one
        # ordinary legal step and record upstream consequences, without querying
        # hidden traps, moving monsters, or forcing a hazard-free fixture.
        position, turn = game.cursor, game.turn
        directions = [(-1,0,'h'), (1,0,'l'), (0,-1,'k'), (0,1,'j')]
        movement = next((d for d in directions if game.cells.get((position[0]+d[0], position[1]+d[1]), {}).get('char') == '.'), None)
        if movement:
            expected = (position[0]+movement[0], position[1]+movement[1])
            start = len(game.events)
            tour.settle(game, game.command(movement[2]))
            messages = [e['text'] for e in game.events[start:] if e['type'] == 'message']
            result['movement'].append(dict(key=movement[2], start=list(position), expected=list(expected),
                                           observed=list(game.cursor), turnBefore=turn, turnAfter=game.turn, messages=messages))
            assert game.cursor == expected or game.turn > turn, ('Ordinary step neither moved nor advanced time', game.cursor, messages)
            result['ordinaryStepReachedDisplayedFloor'] = game.cursor == expected
        else:
            result['movementDeferred'] = 'No adjacent displayed plain floor at this original arrival.'
        position, turn = game.cursor, game.turn
        terrain_before = actual_terrain(game, directory)
        game.finish(automatic=True)
        events.extend(game.events)
        game = open_game(directory)
        tour.settle(game)
        assert (game.cursor, game.turn) == (position, turn), (game.cursor, game.turn, position, turn)
        assert any('Restoring save' in e.get('text', '') for e in game.events)
        assert actual_terrain(game, directory) == terrain_before, 'Actual terrain or lighting changed on restore'
        game.finish(automatic=True)
        result.update(restored=True, exactTerrainAndLightingRestore=True, finalPosition=list(position), finalTurn=turn)
        print('PASS', case['label'], metadata['mode'], result['observedTerrainCombination'], flush=True)
        return result
    finally:
        events.extend(game.events)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        if game.process.poll() is None:
            game.process.kill()
            game.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    parser.add_argument('--extra-ice', action='store_true', help='Append an original layout-2 ice realization if missing')
    parser.add_argument('--case', action='append', help='Restrict to these case IDs')
    args = parser.parse_args()
    rows = prepare(args.case) if args.prepare else json.loads(INDEX.read_text())
    if args.extra_ice:
        rows = extra_ice(rows)
    if args.engine:
        results = []
        for row in rows:
            if args.case and row['metadata']['case']['id'] not in args.case:
                continue
            results.append(check(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
