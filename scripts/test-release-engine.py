#!/usr/bin/env python3
"""Release regressions for host Save and UTF-8 using isolated real games.

The serializer boundary corpus supplements ordinary pet/object naming. It builds
only the maintained serializer functions, without introducing engine test hooks.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('targeting', ROOT / 'scripts/test-targeting.py')
targeting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(targeting)
items = targeting.items
actions = items.actions
Game = actions.Game


def close(game):
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait(timeout=5)


def assert_save(directory):
    saves = list((directory / 'save').iterdir())
    assert saves and all(p.is_file() and p.stat().st_size > 0 for p in saves), saves


def save_test(directory, bindings, prompt):
    directory.mkdir()
    actions.prepare(directory)
    config = directory / 'test.nethackrc'
    config.write_text('BINDINGS=' + bindings + '\n' if bindings else '')
    name = 'AtlasReleaseSave'
    game = Game(directory, name=name, config=config)
    try:
        game.start()
        catalog = actions.catalog(game)
        if bindings == 'S:wait':
            assert 'S' in catalog['wait']['keys'] and not catalog['save']['keys'], catalog['save']
        elif bindings == 'S:nothing':
            assert not catalog['save']['keys'], catalog['save']
        elif bindings == 'S:wait,Z:save':
            assert 'Z' in catalog['save']['keys'], catalog['save']
        original = (game.turn, game.cursor)
        # Manual Save retains ordinary refusal and Escape cancellation.
        for response in ('n', '\x1b'):
            event = actions.named(game, 'save')
            assert event['kind'] == 'yn' and event['prompt'] == 'Really save?', event
            assert game.command(response).get('command')
            assert (game.turn, game.cursor) == original
            assert not list((directory / 'save').iterdir())
        if prompt == 'direction':
            assert actions.named(game, 'kick').get('direction')
        elif prompt == 'menu':
            assert items.menu(game, 'name', 'name')['kind'] == 'menu'
        elif prompt == 'line':
            event = game.command('#')
            assert event['kind'] == 'line', event
        game.finish(automatic=True)
        assert_save(directory)
    finally:
        close(game)
    restored = Game(directory, name=name, config=config)
    try:
        restored.start()
        assert (restored.turn, restored.cursor) == original
        restored.finish(automatic=True)
        assert_save(directory)
    finally:
        close(restored)
    print(f'PASS host Save bindings={bindings or "default"}, pending={prompt}: refusal, Escape, nonempty save, exact restore')


def object_menu(game):
    event = actions.named(game, 'inventory')
    assert event['kind'] == 'menu', event
    return event


def unicode_test(directory):
    fixture = targeting.prepare(directory, '0')
    game = fixture.game
    object_name = '雪🐈"\\\x01'
    pet_name = 'Café'
    try:
        pet = next(p for p, c in game.cells.items() if c.get('pet'))
        original = (game.turn, game.cursor)
        targeting.target_pet(game)
        game.send(f'position {pet[0]} {pet[1]}')
        assert game.wait_input()['kind'] == 'line'
        game.send('line ' + pet_name)
        assert game.wait_input().get('command')
        assert pet_name in game.inspect(*pet)
        targeting.target_pet(game)
        game.send(f'position {pet[0]} {pet[1]}')
        assert pet_name in game.wait_input()['prompt']
        game.send('line \x1b')
        assert game.wait_input().get('command')

        # Upstream's 62-byte name limit may split a UTF-8 sequence. The port
        # must emit valid JSON without changing that engine-owned limit.
        targeting.target_pet(game)
        game.send(f'position {pet[0]} {pet[1]}')
        assert game.wait_input()['kind'] == 'line'
        game.send('line ' + 'A' * 61 + 'é')
        assert game.wait_input().get('command')
        assert 'A' * 61 + '\ufffd' in game.inspect(*pet)
        targeting.target_pet(game)
        game.send(f'position {pet[0]} {pet[1]}')
        assert 'A' * 61 + '\ufffd' in game.wait_input()['prompt']
        game.send('line ' + pet_name)
        assert game.wait_input().get('command')

        event = items.menu(game, 'name', 'name')
        event = items.pick(game, event, lambda i: i['text'] == 'a particular object in inventory')
        event = items.pick(game, event, lambda i: 'dagger' in i['text'])
        assert event['kind'] == 'line'
        game.send('line ' + object_name)
        assert game.wait_input().get('command')
        event = object_menu(game)
        assert any(object_name in i['text'] for i in event['items']), event
        assert actions.dismiss(game, event).get('command')
        assert (game.turn, game.cursor) == original
        # Host Save also unwinds an active map-targeting prompt.
        targeting.target_pet(game)
        game.finish(automatic=True)
        assert_save(directory)
    finally:
        fixture.close()
    restored = Game(directory, name='AtlasItemMenus', options=items.BASE_OPTIONS + items.FULL)
    try:
        restored.start()
        assert (restored.turn, restored.cursor) == original
        assert pet_name in restored.inspect(*pet)
        event = object_menu(restored)
        assert any(object_name in i['text'] for i in event['items']), event
        assert actions.dismiss(restored, event).get('command')
        event = items.menu(restored, 'drop', 'drop')
        first = len(restored.events)
        event = items.pick(restored, event, lambda i: object_name in i['text'])
        assert event.get('command'), event
        assert any(object_name in e.get('text', '') for e in restored.events[first:]
                   if e['type'] == 'message'), restored.events[first:]
        restored.finish(automatic=True)
    finally:
        close(restored)
    print('PASS ordinary UTF-8 pet/object naming: prompts, menus, messages, hover, quotes/backslash/control, targeting Save and exact restoration')


def serializer_test(directory):
    source = (ROOT / 'engine/winatelier.c').read_text()
    functions = source[source.index('static int utf8_length('):source.index('static void eventtext(')]
    cases = [
        (b'', ''),
        ('Café 雪 🐈'.encode(), 'Café 雪 🐈'),
        (bytes(range(1, 32)) + b'"\\\x7f', ''.join(chr(i) for i in range(1, 32)) + '"\\\x7f'),
        (b'\\G1234ABCD', '\\G1234ABCD'),
        (b'\xc2\x80\xdf\xbf\xe0\xa0\x80\xed\x9f\xbf\xef\xbf\xbf\xf0\x90\x80\x80\xf4\x8f\xbf\xbf',
         '\u0080\u07ff\u0800\ud7ff\uffff\U00010000\U0010ffff'),
        (b'\x80\xbf\xc0\xaf\xc1\xbf\xf5\xff', '\ufffd' * 8),
        (b'\xe0\x80\xaf\xed\xa0\x80\xf0\x80\x80\xaf\xf4\x90\x80\x80', '\ufffd' * 14),
        (b'A\xc3Z\xe2\x82', 'A\ufffdZ\ufffd\ufffd'),
    ]
    # Exercise truncation at every possible byte boundary of each UTF-8 width.
    for raw in ('é'.encode(), '雪'.encode(), '🐈'.encode()):
        for count in range(1, len(raw)):
            cases.append((raw[:count], '\ufffd' * count))
    declarations = []
    for index, (raw, _) in enumerate(cases):
        declarations.append('unsigned char s%d[] = {%s}; jstr((char *)s%d); putchar(10);'
                            % (index, ','.join(str(b) for b in raw + b'\0'), index))
    cfile = directory / 'serializer.c'
    cfile.write_text('#include <stdio.h>\n' + functions + '\nint main(void) {\n'
                     + '\n'.join(declarations) + '\nreturn 0;\n}\n')
    executable = directory / 'serializer'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(executable)], check=True)
    lines = subprocess.check_output([str(executable)]).decode('utf-8', errors='strict').splitlines()
    assert len(lines) == len(cases)
    for line, (raw, expected) in zip(lines, cases):
        assert json.loads(line) == expected, (raw, line, expected)
    print('PASS serializer boundary corpus: strict UTF-8 JSON, control escaping, glyph text, malformed-byte replacement')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serializer-only', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='atlas-release-engine-') as temporary:
        directory = Path(temporary)
        serializer_test(directory)
        if not args.serializer_only:
            for index, (bindings, prompt) in enumerate([
                ('', 'command'), ('S:wait', 'direction'),
                ('S:nothing', 'menu'), ('S:wait,Z:save', 'line'),
            ]):
                save_test(directory / f'save-{index}', bindings, prompt)
            unicode_test(directory / 'unicode')


if __name__ == '__main__':
    main()
