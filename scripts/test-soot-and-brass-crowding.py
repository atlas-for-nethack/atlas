#!/usr/bin/env python3
"""Record perceived large neighbors at room rims for projected-renderer review.

Wizard Lua constructs an isolated lit room. NetHack supplies all appearances,
perceived ground, descriptions and turns. This checks engine/native plumbing;
visual overlap and selection-outline readability require screenshot inspection.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('crowding_gameplay', ROOT / 'scripts/test-lantern-gameplay.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
original_level, original_load = fixture.level, fixture.load

# Leave the existing hero movement and both door-operation routes clear. The
# north pair borders the doorway; the south row sits before an open door.
SUBJECTS = [
    (2, 1, 'red dragon', (300, 301)),
    (1, 1, 'blue dragon', (308, 309)),
    (5, 4, 'titan', (360, 361)),
    (1, 2, 'white dragon', (302, 303)),
    (1, 5, 'stone giant', (348, 349)),
    (2, 5, 'ettin', (356, 357)),
    (3, 5, 'mastodon', (178, 179)),
    (4, 5, 'baluchitherium', (176, 177)),
    (5, 5, 'minotaur', (362, 363)),
]


def crowding_level(*args, **kwargs):
    # The harness reaches the east door along the clear northeast room rim.
    # Move only the test stair away from the adjacent northern dragon pair.
    room = original_level(*args, **kwargs).replace(
        'des.stair("up",1,1);', 'des.stair("up",10,1);')
    return room + ''.join(
        'des.monster({id="%s",x=%d,y=%d,peaceful=true,paralyzed=127});\n' % (name, x, y)
        for x, y, name, _ in SUBJECTS)


def assert_perceived(cells):
    for x, y, name, slots in SUBJECTS:
        position = (x + fixture.ORIGIN[0], y + fixture.ORIGIN[1])
        cell = cells.get(position, {})
        assert cell.get('tile') in slots, (name, position, cell)
        assert cell.get('groundTile') == 1291, (name, 'missing perceived floor', cell)
    assert 'groundTile' not in cells.get((70, 19), {}), 'Unknown terrain leaked into the fixture'


def load_with_checks(run, *args, **kwargs):
    original_load(run, *args, **kwargs)
    assert_perceived(run.game.cells)
    turn = run.game.turn
    for x, y, name, _ in SUBJECTS:
        description = run.game.inspect(x + fixture.ORIGIN[0], y + fixture.ORIGIN[1])
        assert name in description.lower(), (name, description)
    assert run.game.turn == turn, 'Crowded-cell inspection consumed a turn'


def restored_subjects(run):
    """Check the first native command boundary, not any historic appearance."""
    cells = {}
    for event in map(json.loads, (run / 'diagnostics.jsonl.engine.jsonl').read_text().splitlines()):
        if event['type'] == 'clear':
            cells.clear()
        elif event['type'] == 'cell':
            cells[(event['x'], event['y'])] = event
        elif event['type'] == 'input' and event.get('command'):
            assert_perceived(cells)
            return
    raise AssertionError('No restored native command boundary')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='Restore in the rebuilt packaged app and capture the projected room')
    parser.add_argument('--tileset', default='soot-and-brass', help='Projected tileset to review')
    args = parser.parse_args()
    fixture.level, fixture.load = crowding_level, load_with_checks
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='soot-crowding-', dir=ROOT / '.artifacts'))
    directory = fixture.prepare(run)
    # prepare() records only actual engine events after the last level clear,
    # saves the isolated game, and closes the engine before optional app launch.
    events = json.loads((run / 'room-events.json').read_text())
    cells = {}
    for event in events:
        if event['type'] == 'clear':
            cells.clear()
        elif event['type'] == 'cell':
            cells[(event['x'], event['y'])] = event
    assert_perceived(cells)
    (run / 'crowding-cells.json').write_text(json.dumps({
        'source': 'real NetHack 5.0 engine, no inferred or synthetic cells',
        'hero': [12, 5],
        'subjects': [{'position': [x + fixture.ORIGIN[0], y + fixture.ORIGIN[1]], 'name': name}
                     for x, y, name, _ in SUBJECTS],
        'cells': list(cells.values()),
    }, indent=2) + '\n')
    if args.native:
        fixture.native(run, directory, args.tileset)
        restored_subjects(run)
        print('PASS crowded subjects present at the first native restore boundary; ordinary one-step movement and save')
    print('PASS nine real large-monster appearances, perceived floors, turn-free inspection, both door orientations and isolated save')
    print(f'Review actual projected overlap and outlines in the captured image; artifacts: {run}')


if __name__ == '__main__':
    main()
