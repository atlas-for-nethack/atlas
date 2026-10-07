#!/usr/bin/env python3
"""Capture real perceived iron bars and check ordinary human collision.

Uses NetHack's own isolated wizard-level lifecycle. Images can be composed
from the recorded cells; no synthetic renderer events or orientation fields
are generated. Requires the engine's perceived IRONBARS ground support.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lantern_gameplay', ROOT / 'scripts/test-lantern-gameplay.py')
lantern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lantern)
context, actions = lantern.context, lantern.actions
ORIGIN = lantern.ORIGIN


def cases():
    horizontal = {(x, 6) for x in range(4, 9)}
    vertical = {(6, y) for y in range(4, 9)}
    result = [
        ('north-edge', {(x, 0) for x in range(5, 8)}, (6, 1), (6, 0)),
        ('east-edge', {(12, y) for y in range(5, 8)}, (11, 6), (12, 6)),
        ('south-edge', {(x, 12) for x in range(5, 8)}, (6, 11), (6, 12)),
        ('west-edge', {(0, y) for y in range(5, 8)}, (1, 6), (0, 6)),
        ('horizontal-run', horizontal, (6, 5), (6, 6)),
        ('vertical-run', vertical, (5, 6), (6, 6)),
    ]
    for name, dx, dy in [('north-west-corner', -1, -1), ('north-east-corner', 1, -1),
                         ('south-west-corner', -1, 1), ('south-east-corner', 1, 1)]:
        bars = {(6 + dx * n, 6) for n in range(3)} | {(6, 6 + dy * n) for n in range(3)}
        result.append((name, bars, (6 - dx, 6), (6, 6)))
    result.extend([
        ('tee', horizontal | {(6, 4), (6, 5)}, (6, 3), (6, 4)),
        ('cross', horizontal | vertical, (6, 3), (6, 4)),
        ('partial-unknown', {(x, 6) for x in [4, 5, 6, 8, 9, 10]}, (5, 5), (5, 6)),
    ])
    return result


def source(bars, arrival, partial):
    rows = [['-' if y in (0, 12) else '|' if x in (0, 12) else '.'
             for x in range(13)] for y in range(13)]
    for x, y in bars:
        rows[y][x] = 'F'
    if partial:
        for y in range(13):
            rows[y][7] = '|'
    return '''des.reset_level();
des.level_init({style="solidfill",fg=" "});
des.level_flags("noflip","nomongen");
des.map({x=10,y=3,lit=true,map=[[\n''' + '\n'.join(''.join(row) for row in rows) + '''
]]});
des.stair("up",1,1); des.stair("down",10,10);
''' + ('des.teleport_region({region={%d,%d,%d,%d}});\n' % (arrival * 2)) + '''
des.finalize_level();
'''


def absolute(position):
    return tuple(a + b for a, b in zip(position, ORIGIN))


def capture(fixture, output, name, bars, arrival, target):
    game = fixture.game
    partial = name == 'partial-unknown'
    lua = source(bars, arrival, partial)
    (fixture.directory / 'bars.lua').write_text(lua)
    assert actions.named(game, 'wizloadlua')['kind'] == 'line'
    game.cells.clear()
    game.send('line bars.lua')
    assert game.wait_input().get('command')
    assert game.cursor == absolute(arrival)
    start = max(i for i, e in enumerate(game.events) if e['type'] == 'clear')
    expected = {absolute(p) for p in bars if not partial or p[0] < 7}
    actual = {p for p, cell in game.cells.items() if cell['tile'] == 1289}
    assert actual == expected, (name, 'perceived bars', actual, expected)
    for position in actual:
        cell = game.cells[position]
        assert cell['groundTile'] == 1291, (name, cell)
        # The engine provides one visual glyph, not a hidden topology channel.
        assert not {'horizontal', 'orientation', 'connections'} & cell.keys(), cell
    assert 'groundTile' not in game.cells.get((70, 19), {})
    turn = game.turn
    assert 'iron bars' in game.inspect(*absolute(target)).lower()
    if partial:
        hidden = absolute((8, 6))
        assert game.cells.get(hidden, {}).get('tile') != 1289
        assert 'groundTile' not in game.cells.get(hidden, {})
        assert 'unexplored' in game.inspect(*hidden).lower()
    assert game.turn == turn
    dx, dy = target[0] - arrival[0], target[1] - arrival[1]
    command = {(0, -1): 'movenorth', (1, 0): 'moveeast',
               (0, 1): 'movesouth', (-1, 0): 'movewest'}[(dx, dy)]
    assert actions.named(game, command).get('command')
    assert game.cursor == absolute(arrival), (name, 'human crossed iron bars')
    assert game.turn == turn, (name, 'blocked movement consumed a turn', turn, game.turn)
    assert game.cells[absolute(target)]['tile'] == 1289
    (output / f'{name}.lua').write_text(lua)
    (output / f'{name}-events.json').write_text(json.dumps(game.events[start:], indent=2) + '\n')
    snapshot = {'name': name, 'hero': list(game.cursor), 'turn': game.turn,
                'target': list(absolute(target)), 'cells': list(game.cells.values())}
    (output / f'{name}-cells.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    return {'name': name, 'events': f'{name}-events.json',
            'snapshot': f'{name}-cells.json', 'setup': f'{name}.lua'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='Restore the compact real fixture in the rebuilt app')
    parser.add_argument('--tileset', default='lantern', help='Bundled atlas to exercise in the native app')
    args = parser.parse_args()
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='lantern-bars-', dir=ROOT / '.artifacts'))
    directory = run / 'game'
    directory.mkdir()
    output = run / 'views'
    output.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = context.Fixture(str(directory))
    try:
        views = [capture(fixture, output, *case) for case in cases()]
        (output / 'index.json').write_text(json.dumps(
            {'source': 'real NetHack 5.0 engine', 'views': views}, indent=2) + '\n')
    finally:
        fixture.close()
    print(f'PASS {len(views)} iron-bar views: one glyph, perceived ground, '
          'blocked ordinary human movement, turn-free inspection and unknown-area non-disclosure')
    print(f'Actual cell snapshots and events: {output / "index.json"}')
    directory = prepare_native(run)
    if args.native:
        native(run, directory, args.tileset)


def prepare_native(run):
    directory = run / 'native-game'
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = context.Fixture(str(directory))
    game = fixture.game
    try:
        lua = '''des.reset_level();
des.level_init({style="solidfill",fg=" "});
des.level_flags("noflip","nomongen");
des.map({x=10,y=3,lit=true,map=[[
---FFF---
|.......|
F.......F
F..FFF..F
F.......F
|.......|
---FFF---
]]});
des.stair("up",1,1); des.stair("down",7,5);
des.teleport_region({region={4,2,4,2}});
des.finalize_level();
'''
        (directory / 'bars-native.lua').write_text(lua)
        assert actions.named(game, 'wizloadlua')['kind'] == 'line'
        game.cells.clear()
        game.send('line bars-native.lua')
        assert game.wait_input().get('command')
        assert game.cursor == (14, 5)
        locations = [(14, 3), (18, 6), (14, 9), (10, 6), (14, 6)]
        for position in locations:
            assert game.cells[position]['tile'] == 1289, game.cells[position]
            assert game.cells[position]['groundTile'] == 1291
        before = game.turn
        assert actions.named(game, 'movesouth').get('command')
        assert game.cursor == (14, 5) and game.turn == before
        (run / 'native-fixture.json').write_text(json.dumps(
            {'hero': [14, 5], 'turn': game.turn, 'bars': locations}, indent=2) + '\n')
        game.finish(automatic=True)
        assert any((directory / 'save').iterdir())
    finally:
        fixture.close()
    print(f'PASS compact native fixture prepared at {directory}')
    return directory


def native(run, directory, tileset="lantern"):
    report = run / 'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(directory), ATLAS_TEST_TILESET=tileset,
               ATLAS_TEST_SCENARIO='lantern-bars', ATLAS_DIAGNOSTICS=str(report),
               ATLAS_SNAPSHOT=str(run / 'game.png'))
    app = ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'
    with (run / 'application.log').open('w') as log:
        process = subprocess.Popen([str(app), '--self-test'], env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
            raise AssertionError(f'Native bars fixture timed out: {run}')
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert events and all(e.get('ok') is True for e in events), events
    rendered = next(e for e in events if e['phase'] == 'lantern-bars-fixture')
    assert json.loads(rendered['detail'])['atlas'] == tileset, rendered
    assert {'lantern-bars-fixture', 'lantern-bars-blocked', 'complete'} <= {e['phase'] for e in events}
    assert (run / 'lantern-bars-fixture.png').is_file()
    # Validate real native-launched engine boundaries independently of UI claims.
    expected = json.loads((run / 'native-fixture.json').read_text())
    trace = [json.loads(line) for line in Path(str(report) + '.engine.jsonl').read_text().splitlines()]
    cells, position, turn, boundaries = {}, None, None, []
    for event in trace:
        if event['type'] == 'clear':
            cells.clear()
        elif event['type'] == 'cell':
            cells[(event['x'], event['y'])] = event
        elif event['type'] == 'cursor':
            position = [event['x'], event['y']]
        elif event['type'] == 'status' and event.get('field') == 16:
            turn = int(event['value'].strip())
        elif event['type'] == 'input' and event.get('command'):
            boundaries.append((position, turn, cells.copy()))
    assert len(boundaries) >= 2
    for position, turn, perceived in boundaries[:2]:
        assert position == expected['hero'] and turn == expected['turn'], (position, turn, expected)
        for bar in expected['bars']:
            assert perceived[tuple(bar)]['tile'] == 1289
            assert perceived[tuple(bar)]['groundTile'] == 1291
        assert 'groundTile' not in perceived.get((70, 19), {})
    assert any((directory / 'save').iterdir())
    print(f'PASS packaged {tileset} bars restore, blocked movement and save; screenshot: {run / "lantern-bars-fixture.png"}')


if __name__ == '__main__':
    main()
