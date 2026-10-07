#!/usr/bin/env python3
"""Check unchanged Fort Ludios in isolated worlds with the packaged engine.

Wizard level travel prepares review checkpoints. Portal verification uses the
original portals and ordinary movement, with disclosed wizard positioning.
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
INDEX = ROOT/'.artifacts/fort-ludios-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/fort-ludios-engine.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
BOUNDS = [1, 0, 79, 21]
DIRECTIONS = [(-1, 0, 'h'), (1, 0, 'l'), (0, -1, 'k'), (0, 1, 'j')]


def displayed_cells(events):
    cells = {}
    for event in events:
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def settle_encounter(game, event):
    # Original active court soldiers can use unidentified potions while the
    # test moves. Cancel optional naming without changing their encounter.
    while event.get('kind') == 'line' and event.get('prompt', '').startswith('Call a '):
        game.send('key 27')
        event = game.wait_input()
    return tour.settle(game, event)


def fallback(game):
    assert all('material' not in cell for cell in game.cells.values()), 'Unexpected regional material'
    unknown = [c for c in game.cells.values() if c.get('tile') in (1469, 1470)]
    assert all('groundTile' not in c for c in unknown), 'Unknown ground exposed'
    return len(unknown)


def prepare():
    ROOT.joinpath('.artifacts').mkdir(exist_ok=True)
    case = next(c for c in tour.catalog() if c['id'] == 'knox')
    rows = []
    for mode in ('inspection', 'exploration'):
        for attempt in range(20):
            run = Path(tempfile.mkdtemp(prefix='fort-ludios-'+mode+'-', dir=ROOT/'.artifacts'))
            try:
                metadata = tour.prepare(case, mode, run)
                break
            except RuntimeError as error:
                (run/'failure.txt').write_text(str(error)+'\n')
                if 'World has no destination' not in str(error):
                    raise
        else:
            raise RuntimeError('Twenty isolated worlds lacked a Fort Ludios connection')
        events = [json.loads(line) for line in (run/'preparation.jsonl').read_text().splitlines()]
        cells = displayed_cells(events)
        metadata['case'] = dict(case, id='knox-'+mode,
            label='Fort Ludios / '+('mapped keep' if mode == 'inspection' else 'unrevealed arrival'))
        metadata.update(shapeBounds=BOUNDS, displayedCells=cells,
            fortLudiosRecipe=tour.digest(Path(__file__)), data=tour.digest(tour.RES/'engine/nhdat'))
        metadata['sources']['knox.lua'] = tour.digest(tour.DAT/'knox.lua')
        # One perceived floor suffices for the native frame assertion. All
        # other terrain remains in the engine trace and review screenshot.
        metadata['testTerrainTiles'] = sorted({c['tile'] for c in cells if c.get('char') == '.'})[:1]
        metadata['setup'].append('Original world-generated Fort Ludios. Source geometry, active occupants, traps, treasury, randomized throne and secret doors retained. Whole-map review framing; unchanged court/barracks dungeon artwork.')
        assert metadata['identity']['branch'] == 'Fort Ludios'
        assert metadata['testTerrainTiles']
        assert all('material' not in c for c in cells)
        if mode == 'inspection':
            assert any(1493 <= c['tile'] <= 1503 for c in cells), 'Missing canonical Knox walls'
            assert not any(1471 <= c['tile'] <= 1481 for c in cells), 'Mines walls appeared in Fort Ludios'
            assert any(c['tile'] == 1291 for c in cells), 'Missing ordinary room floor'
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        rows.append(dict(run=str(run), metadata=metadata))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', metadata['case']['label'], run, flush=True)
    for focus in ('throne', 'barracks'):
        rows.append(focused(rows[0], focus))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
    for row in rows:
        restored_marker(row)
    INDEX.write_text(json.dumps(rows, indent=2)+'\n')
    return rows


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


def clone(row, suffix):
    run = Path(tempfile.mkdtemp(prefix='fort-ludios-'+suffix+'-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game', directory)
    return run, directory, open_game(directory)


def cleanup(run, game, previous=()):
    (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in [*previous, *game.events]))
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait(timeout=5)


def restored_marker(row):
    """Choose native readiness from the actual restored foreground display.

    A remembered floor can render as dark room after restore even if its
    preparation display used the visible room appearance. This is an engine
    perception appearance, not a change to the saved terrain or lighting.
    """
    run, directory, game = clone(row, 'restore-marker')
    try:
        tour.settle(game)
        x,y,w,h = row['metadata']['shapeBounds']
        counts = collections.Counter(c['tile'] for p,c in game.cells.items()
            if x <= p[0] < x+w and y <= p[1] < y+h and c.get('char') == '.')
        assert counts
        chosen = next(tile for tile in (1292, 1291) if counts[tile])
        row['metadata']['testTerrainTiles'] = [chosen]
        row['metadata']['nativeRestoreFloorCounts'] = dict(counts)
        row['metadata']['nativeRestoreMarkerEvidence'] = str(run/'engine.jsonl')
        (Path(row['run'])/'metadata.json').write_text(json.dumps(row['metadata'], indent=2)+'\n')
        game.finish(automatic=True)
        print('RESTORE MARKER', row['metadata']['case']['id'], chosen, dict(counts), flush=True)
    finally:
        cleanup(run, game)


def oracle(game, directory):
    """Read-only check-clone diagnostics, never exposed to player UI/captures."""
    before = len(game.events)
    tour.lua(game, directory, '''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("LUDIOS_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit));
 if m.has_trap then local t=nh.gettrap(x-ox,y-oy);
  if t.ttyp_name=="magic portal" then nh.pline("LUDIOS_PORTAL:"..x..","..y); end;
 end;
end end;''')
    terrain = [e['text'].split(':',1)[1].split(',') for e in game.events[before:]
               if e.get('text','').startswith('LUDIOS_TERRAIN:')]
    portals = [tuple(map(int,e['text'].split(':',1)[1].split(','))) for e in game.events[before:]
               if e.get('text','').startswith('LUDIOS_PORTAL:')]
    assert len(terrain) == 79*21
    return terrain, portals


def place(game, position):
    event = tour.named(game, 'teleport')
    if event['kind'] == 'menu' and event.get('how') == 0:
        game.send('key 32')
        event = game.wait_input()
    assert event.get('targeting'), event
    game.send(f'position {position[0]} {position[1]}')
    tour.settle(game)
    assert game.cursor == position, (game.cursor, position)


def focused(row, focus):
    run, directory, game = clone(row, 'focus-'+focus)
    try:
        tour.settle(game)
        terrain, portals = oracle(game, directory)
        assert len(portals) == 1
        portal = portals[0]
        # The original Lua branch portal is (8,16). Its actual coordinates
        # identify upstream map flips and translation for source room framing.
        def source_point(x, y):
            return (portal[0]+(8-x if portal[0]>40 else x-8),
                    portal[1]+(y-16 if portal[1]>10 else 16-y))
        if focus == 'throne':
            throne = next(p for p,c in game.cells.items() if c.get('char') == '\\')
            a,b = source_point(37,8), source_point(46,11)
            left,right = sorted((a[0],b[0])); top,bottom = sorted((a[1],b[1]))
            targets = [p for p,c in game.cells.items() if c.get('char') == '.'
                and left <= p[0] <= right and top <= p[1] <= bottom]
            targets.sort(key=lambda p:abs(p[0]-throne[0])+abs(p[1]-throne[1]))
            bounds = [max(1, throne[0]-8), max(0, throne[1]-5), 17, 11]
        else:
            a,b = source_point(62,3), source_point(71,7)
            left,right = sorted((a[0],b[0])); top,bottom = sorted((a[1],b[1]))
            targets = [p for p,c in game.cells.items() if c.get('char') == '.'
                and left <= p[0] <= right and top <= p[1] <= bottom]
            doorway = source_point(66,6)
            targets.sort(key=lambda p:abs(p[0]-doorway[0])+abs(p[1]-doorway[1]))
            bounds = [max(1,left-2), max(0,top-2), 15, 8]
        assert targets, (focus, portal)
        for target in targets:
            try:
                place(game, target)
                break
            except AssertionError:
                # Original unseen occupants can reject a targeted teleport.
                # Try another mapped floor from a fresh checkpoint copy, so
                # failed placement does not advance the final scene's actors.
                cleanup(run, game)
                run, directory, game = clone(row, 'focus-'+focus+'-retry')
                tour.settle(game)
        else:
            raise AssertionError('No accepted mapped-floor placement in '+focus)
        metadata = json.loads(json.dumps(row['metadata']))
        metadata.update(case=dict(metadata['case'], id='knox-'+focus,
            label='Fort Ludios / '+('throne room and court' if focus == 'throne' else 'barracks and soldiers')),
            shapeBounds=bounds, arrival=list(game.cursor), status=game.status,
            displayedCells=list(game.cells.values()), fortLudiosRecipe=tour.digest(Path(__file__)))
        x,y,w,h=bounds
        metadata['testTerrainTiles'] = sorted({c['tile'] for p,c in game.cells.items()
            if x <= p[0] < x+w and y <= p[1] < y+h and c.get('char') == '.'})[:1]
        assert metadata['testTerrainTiles']
        turn = game.turn
        metadata['perceivedOccupants'] = [dict(position=list(p), description=game.inspect(*p))
            for p,c in game.cells.items() if x <= p[0] < x+w and y <= p[1] < y+h
            and (c.get('char', '').isalpha() or c.get('char') == '@') and p != game.cursor]
        assert game.turn == turn
        if focus == 'barracks':
            assert any(any(name in i['description'].lower() for name in ('soldier','sergeant','lieutenant','captain'))
                for i in metadata['perceivedOccupants']), metadata['perceivedOccupants']
        else:
            assert metadata['perceivedOccupants'], 'No perceived court occupants'
        metadata['setup'].append('Focused '+focus+' view: test-only upstream wizard teleport to existing mapped room floor. Source portal coordinates identify original map flips; no actors moved or added. Active encounters and original room contents retained.')
        game.finish(automatic=True)
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        (run/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        print('PREPARED', metadata['case']['label'], run, flush=True)
        return dict(run=str(run), metadata=metadata)
    finally:
        cleanup(run, game)


def check(row):
    metadata = row['metadata']
    assert metadata['engine'] == tour.digest(tour.RES/'engine/nethack')
    assert metadata['app'] == tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')
    assert metadata['data'] == tour.digest(tour.RES/'engine/nhdat')
    assert metadata['sources']['knox.lua'] == tour.digest(tour.DAT/'knox.lua')
    run, directory, game = clone(row, 'check')
    previous = []
    result = dict(case=metadata['case']['id'], mode=metadata['mode'], run=str(run),
        originalActorsRetained=True, engine=metadata['engine'], app=metadata['app'])
    try:
        tour.settle(game)
        assert game.cursor == tuple(metadata['arrival'])
        assert game.turn == int(metadata['status'].get('16', metadata['status'].get(16)).strip())
        result['identity'] = tour.identity(game, directory)
        assert result['identity'] == metadata['identity']
        result['unknownMetadataChecked'] = fallback(game)
        terrain, portals = oracle(game, directory)
        assert len(portals) == 1
        turn = game.turn
        samples = [game.cursor]
        for character in ('.', '-', '|', '}', '\\', '^'):
            position = next((p for p,c in game.cells.items() if c.get('char') == character), None)
            if position is not None and position not in samples:
                samples.append(position)
        result['inspection'] = [dict(position=list(p), description=game.inspect(*p)) for p in samples]
        if metadata['mode'] == 'exploration':
            unknown, description = next((p, description) for p,c in game.cells.items()
                if c.get('char') == ' ' and 'unexplored' in (description := game.inspect(*p)).lower())
            result['unknownInspection'] = dict(position=list(unknown), description=description)
        assert game.turn == turn
        result['turnFreeInspection'] = True
        if metadata['mode'] == 'inspection':
            assert any(c['tile'] == 1291 for c in game.cells.values())
            assert any(1493 <= c['tile'] <= 1503 for c in game.cells.values())
            assert not any(1471 <= c['tile'] <= 1481 for c in game.cells.values())
            throne = next((p for p,c in game.cells.items()
                           if c.get('tile') == 1311), None)
            if throne:
                assert 'throne' in game.inspect(*throne).lower()
            # Known barracks cells are inspected as remembered room floor;
            # remote wizard mapping does not disclose unseen soldier identities.
            portal = portals[0]
            a = (portal[0]+(8-62 if portal[0]>40 else 62-8),
                 portal[1]+(3-16 if portal[1]>10 else 16-3))
            b = (portal[0]+(8-71 if portal[0]>40 else 71-8),
                 portal[1]+(4-16 if portal[1]>10 else 16-4))
            left,right = sorted((a[0],b[0])); top,bottom = sorted((a[1],b[1]))
            candidates = [p for p,c in game.cells.items() if left <= p[0] <= right
                and top <= p[1] <= bottom and c.get('char') not in (' ', '-', '|')]
            assert candidates, 'No remembered/perceived barracks cell'
            barracks = candidates[0]
            result['barracksInspection'] = dict(position=list(barracks), description=game.inspect(*barracks))
            assert game.turn == turn
        result['ordinaryDungeonMaterialVerified'] = True
        result['terrainCounts'] = dict(collections.Counter(c[2] for c in terrain))
        assert result['terrainCounts'].get('throne') == 1, result['terrainCounts']
        assert result['terrainCounts'].get('pool', 0) + result['terrainCounts'].get('moat', 0) > 50
        position, turn = game.cursor, game.turn
        direction = next((d for d in DIRECTIONS if game.cells.get((position[0]+d[0], position[1]+d[1]), {}).get('char') == '.'), None)
        if direction:
            expected = (position[0]+direction[0], position[1]+direction[1])
            messages_start = len(game.events)
            settle_encounter(game, game.command(direction[2]))
            assert game.cursor == expected or game.turn > turn, (game.cursor, expected, game.turn, turn)
            result['ordinaryStep'] = dict(start=list(position), expected=list(expected), destination=list(game.cursor), turnBefore=turn, turnAfter=game.turn,
                reachedExpectedFloor=game.cursor == expected,
                messages=[e['text'] for e in game.events[messages_start:] if e['type'] == 'message'])
        else:
            assert metadata['case']['id'] in ('knox-throne','knox-barracks')
            result['ordinaryStepDeferred'] = 'Original court/barracks actors occupy all adjacent floor. Floor movement checked in baseline arrivals.'
        terrain, portals = oracle(game, directory)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        previous.extend(game.events)
        game = open_game(directory)
        tour.settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        assert oracle(game, directory)[0] == terrain, 'Terrain or lighting changed on restore'
        fallback(game)
        game.finish(automatic=True)
        result.update(exactRestore=True, exactTerrainAndLightingRestore=True, finalPosition=list(position), finalTurn=turn)
        print('PASS', metadata['case']['label'], 'material, inspection, step and exact restore', flush=True)
        return result
    finally:
        cleanup(run, game, previous)


def portals(row):
    run, directory, game = clone(row, 'portals')
    try:
        tour.settle(game)
        ludios = tour.identity(game, directory)
        terrain, exits = oracle(game, directory)
        assert len(exits) == 1
        portal = exits[0]
        # Position next to the existing portal, then walk onto it. Diagnostic
        # portal coordinates are test-only, never player perception evidence.
        def enter(portal, terrain):
            # Original portals cause three turns of stunning, which can
            # redirect movement. Let that upstream effect expire naturally.
            recovery_turns = 0
            for _ in range(12):
                if not int(game.status.get(22, '0')) & (1 << 22):
                    break
                settle_encounter(game, game.command('.'))
                recovery_turns += 1
            assert not int(game.status.get(22, '0')) & (1 << 22)
            plain = {(int(c[0]),int(c[1])) for c in terrain if c[2] == 'room'}
            direction = next(d for d in DIRECTIONS if (portal[0]-d[0], portal[1]-d[1]) in plain)
            start = (portal[0]-direction[0], portal[1]-direction[1])
            place(game, start)
            before = game.turn
            messages_start = len(game.events)
            event = game.command(direction[2])
            if event['kind'] == 'yn' and event.get('prompt') == 'Really step into that magic portal?':
                game.send('key 121')
                event = game.wait_input()
            settle_encounter(game, event)
            assert any('portal' in e.get('text','').lower() for e in game.events[messages_start:]), game.events[messages_start:]
            return dict(portal=list(portal), approach=list(start), key=direction[2], turnBefore=before, turnAfter=game.turn,
                waitCommandsForPortalStunning=recovery_turns)
        returned = enter(portal, terrain)
        parent = tour.identity(game, directory)
        assert parent['branch'] == 'The Dungeons of Doom', parent
        terrain, entries = oracle(game, directory)
        assert len(entries) == 1
        assert game.cursor == entries[0], (game.cursor, entries)
        fallback(game)
        entered = enter(entries[0], terrain)
        assert tour.identity(game, directory) == ludios
        assert game.cursor == portal, (game.cursor, portal)
        fallback(game)
        # A second ordinary portal walk proves returning after actual entry.
        returned_again = enter(portal, oracle(game, directory)[0])
        assert tour.identity(game, directory) == parent
        assert game.cursor == entries[0]
        fallback(game)
        game.finish(automatic=True)
        result = dict(run=str(run), ludios=ludios, parent=parent, entry=entered,
            initialReturn=returned, returnAfterEntry=returned_again, originalPortalRoundtrip=True,
            setup='Read-only portal oracle and upstream wizard positioning next to each original portal. Ordinary direction keys activate both portals. No portal, terrain, actor or branch replacement.')
        print('PASS original portal entry into Ludios and return to exact parent portal', flush=True)
        return result
    finally:
        cleanup(run, game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    parser.add_argument('--portals', action='store_true')
    parser.add_argument('--refresh-markers', action='store_true', help='Check restored displays and refresh native capture readiness only')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.refresh_markers:
        for row in rows:
            restored_marker(row)
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
    results = dict(checks=[])
    if args.engine:
        for row in rows:
            results['checks'].append(check(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    if args.portals:
        results['portals'] = portals(rows[0])
        RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
