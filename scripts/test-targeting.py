#!/usr/bin/env python3
"""Real pet naming and location selection, with isolated wizard setup only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('items', ROOT / 'scripts/test-item-menus.py')
items = importlib.util.module_from_spec(spec)
spec.loader.exec_module(items)


def prepare(directory, numpad):
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = items.Fixture(str(directory), items.FULL + f',number_pad:{numpad}')
    game = fixture.game
    assert items.actions.named(game, 'wizgenesis')['kind'] == 'line'
    game.send('line tame sleeping kitten')
    assert game.wait_input().get('command')
    assert any(c.get('pet') for c in game.cells.values())
    return fixture


def target_pet(game):
    event = items.menu(game, 'name', 'name')
    event = items.pick(game, event, lambda i: i['text'] == 'a monster')
    if event['kind'] == 'menu' and event['how'] == 0:
        game.send('menu')
        event = game.wait_input()
    assert event.get('targeting') and not event.get('command'), event
    return event


def engine_test(directory, numpad):
    fixture = prepare(directory, numpad)
    game = fixture.game
    try:
        pet = next(p for p, c in game.cells.items() if c.get('pet'))
        hero, turn = game.cursor, game.turn
        # A stale click at a command/menu wait must not move or select anything.
        game.send(f'position {pet[0]} {pet[1]}')
        event = items.menu(game, 'name', 'name')
        game.send(f'position {pet[0]} {pet[1]}')
        event = items.pick(game, event, lambda i: i['text'] == 'a monster')
        if event['kind'] == 'menu':
            game.send('menu')
            event = game.wait_input()
        assert event.get('targeting'), event
        assert event['directionKeys'] == {'0': 'hykulnjb><', '1': '47896321><', '3': '41236987><'}[numpad]
        # Invalid locations are ignored without consuming the pending choice.
        game.send('position 0 0')
        game.send('position 80 21')
        game.send(f'position {pet[0]} {pet[1]}')
        event = game.wait_input()
        assert event['kind'] == 'line' and 'kitten' in event['prompt'], event
        game.send('line Mochi')
        assert game.wait_input().get('command')
        assert 'Mochi' in game.inspect(*pet)
        assert game.turn == turn and game.cursor == hero

        event = target_pet(game)
        for _ in range(80):
            if game.cursor == pet:
                break
            dx = (pet[0] > game.cursor[0]) - (pet[0] < game.cursor[0])
            dy = (pet[1] > game.cursor[1]) - (pet[1] < game.cursor[1])
            direction = {(-1, 0): 0, (-1, -1): 1, (0, -1): 2, (1, -1): 3,
                         (1, 0): 4, (1, 1): 5, (0, 1): 6, (-1, 1): 7}[dx, dy]
            event = game.command(event['directionKeys'][direction])
            assert event.get('targeting')
            cursor = next(e for e in reversed(game.events) if e['type'] == 'cursor')
            assert (cursor['playerX'], cursor['playerY']) == hero
        assert game.cursor == pet
        event = game.command('.')
        assert event['kind'] == 'line' and 'Mochi' in event['prompt'], event
        game.send('line Juniper')
        assert game.wait_input().get('command')
        assert 'Juniper' in game.inspect(*pet)
        target_pet(game)
        assert game.command('\x1b').get('command')
        assert 'Juniper' in game.inspect(*pet)
        assert game.turn == turn and game.cursor == hero
        # Farlook uses the same coordinate path and remains turn-free.
        event = items.actions.named(game, 'glance')
        assert event.get('targeting'), event
        game.send(f'position {pet[0]} {pet[1]}')
        assert game.wait_input().get('command')
        assert game.turn == turn
        # Saving from targeting safely unwinds the pending selection.
        target_pet(game)
        game.finish(automatic=True)
        assert list((directory / 'save').iterdir())
        print(f'PASS keypad {numpad}: click/keyboard naming, cursor/hero separation, '
              'cancellation, ignored stale/invalid clicks, farlook and save during selection')
    finally:
        fixture.close()


def native_test(run, numpad):
    directory = run / 'game'
    fixture = prepare(directory, numpad)
    try:
        fixture.game.finish(automatic=True)
    finally:
        fixture.close()
    report = run / 'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(directory),
               ATLAS_TEST_NUMBER_PAD=numpad,
               ATLAS_TEST_SCENARIO='pet-target', ATLAS_DIAGNOSTICS=str(report),
               ATLAS_SNAPSHOT=str(run / 'game.png'))
    app = ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'
    with (run / 'application.log').open('w') as log:
        process = subprocess.Popen([str(app), '--self-test'], env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
            raise AssertionError(f'Native targeting test timed out: {run}')
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert all(event.get('ok') is True for event in events), events
    bindings = {'0': 'hykulnjb><', '1': '47896321><', '3': '41236987><'}[numpad]
    assert any(e['phase'] == 'pet-target-visible' and bindings in e['detail'] for e in events)
    assert {'pet-name-click', 'pet-target-keyboard', 'pet-name-keyboard',
            'pet-target-cancel', 'complete'} <= {e['phase'] for e in events}
    assert (run / 'pet-target.png').is_file()
    assert (run / 'pet-name.png').is_file()
    assert list((directory / 'save').iterdir())
    print(f'PASS native keypad {numpad}: kitten named with mouse and keyboard, '
          f'cancellation preserves name/turn/hero. Evidence: {run}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--numpad', choices=['0', '1', '3'], default='0')
    args = parser.parse_args()
    if args.native:
        (ROOT / '.artifacts').mkdir(exist_ok=True)
        native_test(Path(tempfile.mkdtemp(prefix='native-target-', dir=ROOT / '.artifacts')), args.numpad)
    else:
        with tempfile.TemporaryDirectory(prefix='atlas-targeting-') as temporary:
            for numpad in ['0', '1', '3']:
                engine_test(Path(temporary) / numpad, numpad)
