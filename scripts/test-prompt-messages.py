#!/usr/bin/env python3
"""Verify actual item effects precede naming, optionally in the packaged app.

Wizard commands provision isolated fixtures only. Read, Quaff and naming use
ordinary engine handling. No player saves or generated event fixtures are used.
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
spec = importlib.util.spec_from_file_location('items', ROOT / 'scripts/test-item-menus.py')
items = importlib.util.module_from_spec(spec)
spec.loader.exec_module(items)
CASES = [
    ('uncursed scroll of scare monster', 'read', 'PromptScroll', 'maniacal laughter'),
    ('uncursed potion of fruit juice', 'quaff', 'PromptPotion', 'tastes like'),
    ('cursed spellbook of force bolt', 'read', 'PromptBook', 'crumbles to dust'),
]


def prepare(directory):
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = items.Fixture(str(directory))
    for description, _, marker, _ in CASES:
        fixture.wish(description + ' named ' + marker)
    return fixture


def settle(game, event):
    for _ in range(30):
        if event.get('command') or event['kind'] == 'line':
            return event
        if event['kind'] == 'menu':
            game.send('menu cancel')
        elif event.get('targeting'):
            game.send('key 27')
        elif event['kind'] == 'yn':
            game.send('key 110')
        else:
            game.send('key 32')
        event = game.wait_input()
    raise AssertionError(('Unexpected follow-up loop', event))


def engine_test(directory):
    fixture = prepare(directory)
    game = fixture.game
    try:
        for index, (_, command, marker, effect) in enumerate(CASES):
            for _ in range(30):
                first = len(game.events)
                event = items.menu(game, command, 'read' if command == 'read' else 'drink')
                event = items.pick(game, event, lambda i: marker in i['text'])
                event = settle(game, event)
                if event['kind'] == 'line':
                    break
            else:
                raise AssertionError('Book did not reach naming prompt')
            assert event['prompt'].startswith('Call '), event
            preceding = [e['text'] for e in game.events[first:] if e['type'] == 'message']
            assert any(effect in text for text in preceding), preceding
            assert not any('You can move again' in text for text in preceding), preceding
            # Naming, Escape, and a blank answer all continue normal gameplay.
            game.send(['line startling sound', 'line \x1b', 'line '][index])
            assert settle(game, game.wait_input()).get('command')
            print(f'PASS: {marker} effects precede naming; response completes normally')
    finally:
        fixture.close()


def native_test(run):
    directory = run / 'game'
    fixture = prepare(directory)
    try:
        fixture.game.finish(automatic=True)
    finally:
        fixture.close()
    report = run / 'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(directory),
               ATLAS_TEST_SCENARIO='prompt-messages', ATLAS_DIAGNOSTICS=str(report),
               ATLAS_SNAPSHOT=str(run / 'game.png'))
    app = ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'
    with (run / 'application.log').open('w') as log:
        process = subprocess.Popen([str(app), '--self-test'], env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
            raise AssertionError(f'Native prompt test timed out: {run}')
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert all(event.get('ok') is True for event in events), events
    phases = {event['phase'] for event in events}
    assert {'prompt-scroll', 'prompt-potion', 'prompt-book', 'prompt-context-reset', 'complete'} <= phases, phases
    for phase in ['scroll', 'potion', 'book']:
        assert (run / f'prompt-{phase}.png').is_file(), phase
    assert list((directory / 'save').iterdir()), 'Quit did not save fixture'
    print('PASS: packaged app shows real effects before all three naming prompts, '
          'clears old context, and accepts name/Escape/blank answers')
    print(f'Evidence: {run}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='Use logged-in macOS desktop')
    args = parser.parse_args()
    if args.native:
        artifacts = ROOT / '.artifacts'
        artifacts.mkdir(exist_ok=True)
        native_test(Path(tempfile.mkdtemp(prefix='native-prompts-', dir=artifacts)))
    else:
        with tempfile.TemporaryDirectory(prefix='atlas-prompt-messages-') as temporary:
            engine_test(Path(temporary) / 'game')
