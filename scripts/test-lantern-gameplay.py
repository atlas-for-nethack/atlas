#!/usr/bin/env python3
"""Exercise Lantern's terrain cases using a real, isolated NetHack save.

The engine supplies every cell and perceived ground layer. Wizard Lua only
constructs the level. Movement and door changes use ordinary game commands.
Artifacts include the actual event stream and a restorable native fixture.
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
spec = importlib.util.spec_from_file_location('context_test', ROOT / 'scripts/test-context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
actions = context.actions
ORIGIN = (10, 3)
DEFAULT_DOORS = [(3, 0, 'closed'), (6, 3, 'closed'), (3, 6, 'open'),
                 (6, 9, 'open'), (12, 3, 'nodoor')]


def level(doors=DEFAULT_DOORS, arrival=(2, 2)):
    # Four rooms share a cross and four tees. A corridor exits to the east.
    rows = [[' ' for _ in range(18)] for _ in range(13)]
    for y in range(13):
        for x in range(13):
            rows[y][x] = '-' if y in (0, 6, 12) else '|' if x in (0, 6, 12) else '.'
    for x in range(13, 18):
        rows[3][x] = '#'
    return '''des.level_init({style="solidfill", fg=" "});
des.level_flags("noflip", "nomongen");
des.map({x=10,y=3,lit=true,map=[[\n''' + '\n'.join(''.join(r) for r in rows) + '''
]]});
des.stair("up",1,1); des.stair("down",10,10);
''' + ('des.teleport_region({region={%d,%d,%d,%d}});\n' % (arrival * 2)) + ''.join(
        'des.door({x=%d,y=%d,state="%s"});\n' % item for item in doors) + '''
des.object({id="chest",x=4,y=2,locked=false,contents=function() end});
des.object({id="ruby",x=4,y=3});
des.monster({id="floating eye",x=3,y=4,peaceful=true,paralyzed=127});
des.feature("fountain",4,4);
'''


def load(fixture, doors=DEFAULT_DOORS, arrival=(2, 2)):
    path = fixture.directory / 'lantern.lua'
    # Explicit upstream test lifecycle avoids wizloaddes finalizing twice and
    # treating a generated CROSSWALL as a special-level boundary marker.
    path.write_text('des.reset_level();\n' + level(doors, arrival) + '\ndes.finalize_level();\n')
    assert actions.named(fixture.game, 'wizloadlua')['kind'] == 'line'
    fixture.game.cells.clear()
    fixture.game.send('line lantern.lua')
    assert fixture.game.wait_input().get('command')
    assert fixture.game.cursor == (arrival[0] + ORIGIN[0], arrival[1] + ORIGIN[1])


def at(game, x, y):
    return game.cells[(x + ORIGIN[0], y + ORIGIN[1])]


def door(game, command, direction, x, y, expected):
    before = game.turn
    position = game.cursor
    for _ in range(20):  # Upstream can report a resisting door.
        event = actions.named(game, command)
        assert event.get('direction'), event
        assert game.command(direction).get('command')
        assert game.cursor == position
        if at(game, x, y)['tile'] == expected:
            break
    else:
        raise AssertionError(('Door never changed', command, at(game, x, y)))
    assert game.turn > before


def prepare(run):
    directory = run / 'game'
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = context.Fixture(str(directory))
    game = fixture.game
    try:
        load(fixture)
        fixture.walk((12, 5))
        assert at(game, 4, 2)['char'] == '(' and at(game, 4, 2)['groundTile'] == 1291
        assert at(game, 3, 4)['char'] == 'e' and at(game, 3, 4)['groundTile'] == 1291
        assert game.cells[game.cursor]['groundTile'] == 1291
        assert at(game, 3, 0)['tile'] == 1288
        assert at(game, 6, 3)['tile'] == 1287
        unknown = game.cells.get((70, 19), {})
        assert 'groundTile' not in unknown
        before = game.turn
        assert 'unexplored' in game.inspect(70, 19).lower()
        assert game.turn == before
        # Actual one-cell movement, not a scripted position update.
        assert actions.named(game, 'moveeast').get('command')
        assert game.cursor == (13, 5) and game.turn == before + 1
        fixture.walk((13, 4))
        door(game, 'open', 'k', 3, 0, 1286)
        door(game, 'close', 'k', 3, 0, 1288)
        fixture.walk((15, 6))
        door(game, 'open', 'l', 6, 3, 1285)
        door(game, 'close', 'l', 6, 3, 1287)
        print('PASS real movement, both door orientations, perceived creature/object/hero floor, unknown edge')

        # Mapping is an actual upstream wizard command and reveals terrain for
        # topology coverage. It is deliberately separate from the native save.
        assert actions.named(game, 'wizmap').get('command')
        wall_tiles = {c['tile'] for c in game.cells.values() if 1273 <= c['tile'] <= 1283}
        assert wall_tiles == set(range(1273, 1284)), ('Missing wall shapes', sorted(wall_tiles), at(game, 6, 6))
        assert {1284, 1285, 1286, 1287, 1288} <= {c['tile'] for c in game.cells.values()}
        assert any(c['tile'] in (1294, 1295) for c in game.cells.values()), 'Corridor missing'
        (run / 'topology-events.json').write_text(json.dumps(game.events, indent=2) + '\n')
        print('PASS all 11 engine wall topologies, shared walls, corridor and five door appearances')

        # Fresh unmapped room preserves an unexplored edge for native review.
        load(fixture)
        fixture.walk((12, 5))
        native_start = {'x': 12, 'y': 5, 'turn': game.turn, 'next': {'x': 13, 'y': 5}}
        (run / 'fixture.json').write_text(json.dumps(native_start, indent=2) + '\n')
        # Only events since this final map clear are needed for a faithful replay.
        last_clear = max(i for i, e in enumerate(game.events) if e['type'] == 'clear')
        (run / 'room-events.json').write_text(json.dumps(game.events[last_clear:], indent=2) + '\n')
        game.finish(automatic=True)
        assert any((directory / 'save').iterdir())
    finally:
        fixture.close()
    return directory


def native(run, directory, tileset="lantern"):
    report = run / 'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(directory), ATLAS_TEST_TILESET=tileset,
               ATLAS_TEST_SCENARIO='lantern-gameplay', ATLAS_DIAGNOSTICS=str(report),
               ATLAS_SNAPSHOT=str(run / 'game.png'))
    app = ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'
    with (run / 'application.log').open('w') as log:
        process = subprocess.Popen([str(app), '--self-test'], env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
            raise AssertionError(f'Native {tileset} fixture timed out: {run}')
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert events and all(e.get('ok') is True for e in events), events
    rendered = next(e for e in events if e['phase'] == 'lantern-fixture')
    assert json.loads(rendered['detail'])['atlas'] == tileset, rendered
    assert {'lantern-fixture', 'lantern-move', 'complete'} <= {e['phase'] for e in events}
    assert (run / 'lantern-fixture.png').is_file()
    # Independently check the actual native-launched engine stream, rather than
    # accepting only the frontend's self-reported diagnostic phases.
    trace = [json.loads(line) for line in Path(str(report) + '.engine.jsonl').read_text().splitlines()]
    boundaries, cells, position, turn = [], {}, None, None
    for event in trace:
        if event['type'] == 'cell':
            cells[(event['x'], event['y'])] = event
        elif event['type'] == 'clear':
            cells.clear()
        elif event['type'] == 'cursor':
            position = (event['x'], event['y'])
        elif event['type'] == 'status' and event.get('field') == 16:
            turn = int(event['value'].strip())
        elif event['type'] == 'input' and event.get('command'):
            boundaries.append((position, turn, cells.copy()))
    start = json.loads((run / 'fixture.json').read_text())
    assert len(boundaries) >= 2, boundaries
    assert boundaries[0][:2] == ((12, 5), start['turn']), boundaries[0][:2]
    assert boundaries[1][:2] == ((13, 5), start['turn'] + 1), boundaries[1][:2]
    for position, _, visible in boundaries[:2]:
        assert visible[position]['groundTile'] == 1291
        assert visible[(14, 5)]['groundTile'] == 1291
        assert 'groundTile' not in visible.get((70, 19), {})
    assert any((directory / 'save').iterdir())
    print(f'PASS packaged native {tileset} fixture restore, actual arrow movement and automatic save')


def door_review(run):
    """Capture actual perceived cells from every door-facing context.

    Each view starts on an unmapped level. Both faces of the shared wall are
    included because north/south glyph orientation alone cannot encode which
    adjacent floor cells the adventurer has perceived.
    """
    directory = run / 'door-review-game'
    directory.mkdir()
    output = run / 'door-review'
    output.mkdir()
    cases = [
        ('north', (3, 0), (3, 1), 'k', 1288, 1286),
        ('east', (12, 3), (11, 3), 'l', 1287, 1285),
        ('south', (3, 12), (3, 11), 'j', 1288, 1286),
        ('west', (0, 3), (1, 3), 'h', 1287, 1285),
        ('shared-west-face', (6, 3), (5, 3), 'l', 1287, 1285),
        ('shared-east-face', (6, 3), (7, 3), 'h', 1287, 1285),
    ]
    doors = [(x, y, 'closed') for x, y in [(3, 0), (12, 3), (3, 12), (0, 3), (6, 3)]]
    views = []
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = context.Fixture(str(directory))
    game = fixture.game
    try:
        for name, (x, y), arrival, direction, closed_tile, open_tile in cases:
            load(fixture, doors, arrival)
            start = max(i for i, e in enumerate(game.events) if e['type'] == 'clear')
            for state, expected in [('closed', closed_tile), ('open', open_tile)]:
                if state == 'open':
                    door(game, 'open', direction, x, y, expected)
                cell = at(game, x, y)
                assert cell['tile'] == expected and cell['groundTile'] == 1291, cell
                assert game.cells[game.cursor]['groundTile'] == 1291
                assert 'groundTile' not in game.cells.get((70, 19), {})
                key = f'{name}-{state}'
                (output / f'{key}-events.json').write_text(json.dumps(game.events[start:], indent=2) + '\n')
                snapshot = {'name': key, 'hero': list(game.cursor), 'turn': game.turn,
                            'door': dict(cell), 'cells': list(game.cells.values())}
                (output / f'{key}-cells.json').write_text(json.dumps(snapshot, indent=2) + '\n')
                views.append({'name': key, 'events': f'{key}-events.json', 'snapshot': f'{key}-cells.json'})
            door(game, 'close', direction, x, y, closed_tile)
        (output / 'index.json').write_text(json.dumps({'source': 'real NetHack 5.0 engine', 'views': views}, indent=2) + '\n')
    finally:
        fixture.close()
    print('PASS north/east/south/west and both shared-wall faces: closed/open/closed; 12 real-cell review views')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='Exercise the rebuilt packaged app')
    parser.add_argument('--tileset', default='lantern', help='Bundled atlas to exercise in the native app')
    args = parser.parse_args()
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='lantern-gameplay-', dir=ROOT / '.artifacts'))
    directory = prepare(run)
    door_review(run)
    if args.native:
        native(run, directory, args.tileset)
    print(f'Evidence and isolated saved fixture: {run}')


if __name__ == '__main__':
    main()
