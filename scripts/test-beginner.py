#!/usr/bin/env python3
"""Verify Beginner supplies and ordinary mortality against the real engine."""
from contextlib import contextmanager
from collections import deque
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)
OPTIONS = ','.join(['gender:female', '!autopickup', 'time', '!news', 'checkpoint',
                    'force_invmenu', 'menustyle:full', '!implicit_uncursed',
                    '!bones', 'disclose:-i -a -v -g -c -o'])
ALIGNMENTS = {'Knight': 'lawful', 'Samurai': 'lawful', 'Rogue': 'chaotic'}


def prepare(directory):
    engine_test.prepare_runtime(directory)


@contextmanager
def game_at(directory, mode='beginner', role='Valkyrie'):
    # Set these only while spawning; never inherit a player's config or mode.
    environment = dict(HOME=str(directory), NETHACKDIR=str(directory),
                       HACKDIR=str(directory), ATLAS_PLAY_MODE=mode)
    with patch.dict(os.environ, environment):
        game = engine_test.Game(directory, role=role, name='AtlasBeginner',
            options=OPTIONS + ',align:' + ALIGNMENTS.get(role, 'neutral'), mode=mode)
    try:
        game.start()
        yield game
    finally:
        if game.process.poll() is None:
            game.process.kill()
            game.process.wait(timeout=5)


def inventory(game):
    event = game.command('i')
    assert event['kind'] == 'menu', event
    items = [item for item in event['items'] if item.get('key')]
    game.send('menu')
    assert game.wait_input().get('command')
    return items


def count(items, name):
    total = 0
    for item in items:
        if name in item['text']:
            match = re.match(r'(\d+)\b', item['text'])
            total += int(match[1]) if match else 1
    return total


def approach_chest(game):
    """Find the visible named supply chest and walk to it using ordinary keys."""
    start = game.cursor
    context = next(e for e in reversed(game.events) if e['type'] == 'context')
    assert any(c['name'] == 'up' for c in context['commands']), context
    candidates = sorted((p for p, cell in game.cells.items() if cell['char'] == '('),
                        key=lambda p: max(abs(p[0] - start[0]), abs(p[1] - start[1])))
    targets = [p for p in candidates if 'Beginner supplies' in game.inspect(*p)]
    assert len(targets) == 1, ('Expected one visible supply chest', targets)
    target = targets[0]
    assert target != start, 'Supply chest still covers the upstairs'
    directions = [(1, 0, 'l'), (-1, 0, 'h'), (0, 1, 'j'), (0, -1, 'k'),
                  (1, 1, 'n'), (-1, 1, 'b'), (1, -1, 'u'), (-1, -1, 'y')]
    queue = deque([(start, [])])
    seen = {start}
    path = None
    while queue:
        position, steps = queue.popleft()
        if position == target:
            path = steps
            break
        for dx, dy, key in directions:
            p = (position[0] + dx, position[1] + dy)
            cell = game.cells.get(p, {})
            if p in seen or cell.get('pet') or (p != target and cell.get('char') != '.'):
                continue
            seen.add(p)
            queue.append((p, steps + [(key, p)]))
    assert path, ('Chest has no visible floor route', start, target)
    for key, p in path:
        event = game.command(key)
        assert event.get('command') and game.cursor == p, ('Could not reach chest', p, event)
    context = next(e for e in reversed(game.events) if e['type'] == 'context')
    assert any(c['name'] == 'loot' for c in context['commands']), context
    assert not any(c['name'] == 'up' for c in context['commands']), 'Chest is on a staircase'
    return target


def chest_contents(game):
    """Return the engine's take-out menu; caller cancels or selects its contents."""
    game.send('command loot')
    event = game.wait_input()
    if event['kind'] == 'yn':
        assert 'chest' in event['prompt'], event
        game.send('key 121')
        event = game.wait_input()
    assert event['kind'] == 'menu', ('Starting chest inaccessible or locked', event)
    take = next(i for i in event['items'] if i.get('key') == 'o')
    game.send('menu ' + str(take['id']))
    event = game.wait_input()
    assert event['kind'] == 'menu', event
    if 'type of objects' in event.get('prompt', ''):
        all_types = next(i for i in event['items'] if i['text'] == 'All types')
        game.send('menu ' + str(all_types['id']))
        event = game.wait_input()
    assert event['kind'] == 'menu' and 'Take out' in event.get('prompt', ''), event
    return [i for i in event['items'] if i.get('selectable')]


def finish_looting(game, response='menu cancel'):
    game.send(response)
    for _ in range(10):
        event = game.wait_input()
        if event.get('command'):
            return
        if event['kind'] == 'menu':
            game.send('menu cancel')
        elif event['kind'] == 'yn':
            game.send('key 110')
        else:
            game.send('key 32')
    raise AssertionError(('Did not finish looting', event))


def check_starts():
    # Exact opt-in: unknown values must retain ordinary starting equipment.
    for mode in ['standard', '', 'BEGINNER', 'unknown']:
        with tempfile.TemporaryDirectory(prefix='atlas-standard-') as temporary:
            directory = Path(temporary)
            prepare(directory)
            with game_at(directory, mode=mode) as game:
                items = inventory(game)
                assert count(items, 'magic whistle') == 0, items
                assert count(items, 'potion of healing') == 0, items
                # Upstream mksobj can randomly double an initial food stack.
                assert 1 <= count(items, 'food ration') <= 2, items
                assert count(items, 'gold piece') == 0, items
                prior = len(game.events)
                event = game.command(':')
                assert event.get('command'), event
                assert not any('Beginner supplies' in e.get('text', '')
                               for e in game.events[prior:]), game.events[prior:]
    print('PASS: Standard and invalid modes retain normal Valkyrie starting supplies')

    roles = ['Archeologist', 'Barbarian', 'Caveman', 'Healer', 'Knight', 'Monk',
             'Priest', 'Ranger', 'Rogue', 'Samurai', 'Tourist', 'Valkyrie', 'Wizard']
    for role in roles:
        with tempfile.TemporaryDirectory(prefix='atlas-beginner-') as temporary:
            directory = Path(temporary)
            prepare(directory)
            with game_at(directory, role=role) as game:
                assert not game.status.get(9, '').strip(), (role, game.status)
                original = inventory(game)
                gold = count(original, 'gold piece')
                if role == 'Healer':
                    assert 1001 <= gold <= 2000, (role, gold, original)
                elif role == 'Tourist':
                    assert 1 <= gold <= 1000, (role, gold, original)
                else:
                    assert gold == 0, (role, gold, original)
                approach_chest(game)
                hp = game.status.get(18)
                items = chest_contents(game)
                assert count(items, 'magic whistle') == 1, (role, items)
                ration_name = 'gunyoki' if role == 'Samurai' else 'food ration'
                assert count(items, ration_name) == 2, (role, items)
                assert count(items, 'potion of healing') == 1, (role, items)
                assert any('uncursed magic whistle' in i['text'] for i in items), (role, items)
                assert any('uncursed potion of healing' in i['text'] for i in items), (role, items)
                assert count(items, 'gold piece') == 1000, (role, items)
                assert len(items) == 4, ('Chest has random or missing contents', role, items)
                assert game.status.get(18) == hp, ('Opening chest caused damage', role)
                finish_looting(game)
                assert inventory(game) == original, ('Inspecting chest altered role inventory', role)
    print('PASS: all 13 roles start unburdened with unchanged role gold and '
          'a reachable chest off the stairs containing exactly the four promised supply stacks')


def check_restore():
    with tempfile.TemporaryDirectory(prefix='atlas-beginner-restore-') as temporary:
        directory = Path(temporary)
        prepare(directory)
        with game_at(directory) as game:
            original_rations = count(inventory(game), 'food ration')
            location = approach_chest(game)
            contents = chest_contents(game)
            whistle = next(i for i in contents if 'magic whistle' in i['text'])
            ration = next(i for i in contents if 'food ration' in i['text'])
            finish_looting(game, f'menu {whistle["id"]},{ration["id"]}:1')
            before = inventory(game)
            assert count(before, 'magic whistle') == 1, before
            assert count(before, 'food ration') == original_rations + 1, before
            remaining = chest_contents(game)
            assert count(remaining, 'magic whistle') == 0, remaining
            assert count(remaining, 'food ration') == 1, remaining
            finish_looting(game)
            game.finish(automatic=True)
        with game_at(directory) as game:
            assert game.cursor == location, 'Restore moved hero away from supply chest'
            assert inventory(game) == before, 'Restore changed or regranted inventory'
            assert any('Restoring save' in e.get('text', '') for e in game.events)
            assert chest_contents(game) == remaining, 'Restore replaced chest supplies'
            finish_looting(game)
            # Save the inspected state, then restore before crashing so recovery
            # has a complete insurance checkpoint for exactly this state.
            game.finish(automatic=True)
        with game_at(directory) as game:
            checkpoint = next(directory.glob('*.0'))
            game.process.kill()
            game.process.wait(timeout=5)
        result = subprocess.run([str(engine_test.RUNTIME / 'recover'), checkpoint.stem],
                                cwd=directory, env=engine_test.engine_environment(directory, mode='beginner'),
                                capture_output=True, text=True)
        assert result.returncode == 0, (result.stdout, result.stderr)
        with game_at(directory) as game:
            assert inventory(game) == before, 'Checkpoint recovery regranted inventory'
            assert chest_contents(game) == remaining, 'Recovery replaced chest supplies'
            finish_looting(game)
            game.finish(automatic=True)
    print('PASS: save restoration and real checkpoint recovery preserve a partially looted chest')


def check_mortality():
    with tempfile.TemporaryDirectory(prefix='atlas-beginner-death-') as temporary:
        directory = Path(temporary)
        prepare(directory)
        with game_at(directory) as game:
            # NetHack 5 can refuse a bare wait near a monster. Its ordinary
            # m-prefix permits waiting anyway, so this checks real mortality
            # rather than relying on a random room with no nearby threats.
            game.send('key 109')
            wait_pending = True
            commands = 0
            for _ in range(300000):
                event = game.next()
                if event['type'] == 'eof':
                    break
                if event['type'] != 'input':
                    continue
                assert event.get('prompt') != 'Die?', 'Beginner incorrectly allows refusing death'
                if event['kind'] == 'key' and wait_pending:
                    game.send('key 46')
                    wait_pending = False
                elif event.get('command'):
                    commands += 1
                    assert commands < 5000, 'Waiting did not reach ordinary death'
                    game.send('key 109')
                    wait_pending = True
                elif event['kind'] == 'menu':
                    game.send('menu')
                elif event['kind'] == 'yn':
                    game.send('key 110')
                else:
                    game.send('key 32')
            else:
                raise AssertionError('Too many events while waiting for death')
            game.process.wait(timeout=5)
            assert game.process.returncode == 0, game.process.stderr.read()
            entries = (directory / 'xlogfile').read_text().splitlines()
            assert len(entries) == 1, entries
            fields = dict(part.split('=', 1) for part in entries[0].split('\t') if '=' in part)
            assert int(fields['flags'], 16) & 3 == 0, fields
            assert fields['death'] != 'quit', fields
            assert not list((directory / 'save').iterdir()), 'Death left a resumable save'
    print('PASS: Beginner dies normally, cannot refuse death, and records neither explore nor wizard mode')


if __name__ == '__main__':
    check_starts()
    check_restore()
    check_mortality()
