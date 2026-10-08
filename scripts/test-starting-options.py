#!/usr/bin/env python3
"""Exercise NetHack 5.0 starting conditions in isolated runtimes."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('beginner', ROOT / 'scripts/test-beginner.py')
beginner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beginner)
engine = beginner.engine_test


@contextmanager
def game_at(directory, name, role='Wizard', mode='standard', extra=''):
    if mode == 'explore':
        extra += ',playmode:explore'
    game = engine.Game(directory, role=role, name=name,
                       options=beginner.OPTIONS + ',align:neutral' + extra,
                       mode=mode)
    try:
        game.start()
        yield game
    finally:
        if game.process.poll() is None:
            game.process.kill()
            game.process.wait(timeout=5)


def prepare(directory, mode):
    beginner.prepare(directory)
    if mode == 'explore':
        config = directory / 'sysconf'
        config.write_text(config.read_text() + '\nEXPLORERS=*\n')


def inventory(game):
    answer = game.command('i')
    if answer['kind'] == 'menu':
        items = [row['text'] for row in answer['items'] if row.get('key')]
        game.send('menu')
        assert game.wait_input().get('command')
        return items
    assert answer.get('command'), answer
    assert any(event.get('text') == 'Not carrying anything.' for event in game.events[-8:])
    return []


def check_pauper():
    with tempfile.TemporaryDirectory(prefix='atlas-pauper-') as temporary:
        directory = Path(temporary)
        prepare(directory, 'pauper')
        with game_at(directory, 'PauperSmoke', mode='pauper', extra=',pauper') as game:
            assert inventory(game) == []
            spells = game.command('Z')
            assert spells.get('command') and any("don't know any spells" in e.get('text', '')
                                                  for e in game.events[-8:]), spells
            game.send('command enhance')
            skills = game.wait_input()
            assert skills['kind'] == 'menu' and skills['prompt'] == 'Current skills:'
            listed = [row['text'] for row in skills['items'] if '[' in row['text']]
            assert listed and all('[Unskilled]' in row for row in listed), listed
            game.send('menu')
            assert game.wait_input().get('command')
            assert not any('Beginner supplies' in game.inspect(x, y)
                           for (x, y), cell in game.cells.items() if cell['char'] == '(')
            position, turn = game.cursor, game.turn
            game.finish(automatic=True)
        # The engine restores its saved conduct without a fresh pauper option.
        with game_at(directory, 'PauperSmoke', mode='pauper') as game:
            assert game.cursor == position and game.turn == turn
            assert inventory(game) == []
            game.send('command conduct')
            conduct = game.wait_input()
            assert conduct['kind'] in ('menu', 'text'), conduct
            text = ' '.join(row['text'] for row in conduct.get('items', [])) + ' '.join(conduct.get('lines', []))
            assert 'without possessions' in text, text
            checkpoint = next(directory.glob('*.0'))
            game.process.kill()
            game.process.wait(timeout=5)
        recovered = subprocess.run([str(engine.RUNTIME / 'recover'), checkpoint.stem],
                                   cwd=directory, env=engine.engine_environment(directory, mode='pauper'),
                                   capture_output=True, text=True)
        assert recovered.returncode == 0, (recovered.stdout, recovered.stderr)
        with game_at(directory, 'PauperSmoke', mode='pauper') as game:
            assert game.cursor == position and game.turn == turn
            assert inventory(game) == []
            game.finish(automatic=True)
    print('PASS: Pauper has no possessions, spells or trained skills; conduct and position survive restore and recovery')


def check_nudist(mode):
    with tempfile.TemporaryDirectory(prefix=f'atlas-{mode}-nudist-') as temporary:
        directory = Path(temporary)
        prepare(directory, mode)
        with game_at(directory, 'NudistSmoke', role='Valkyrie', mode=mode, extra=',nudist') as game:
            items = inventory(game)
            assert any('spear' in item for item in items), items
            assert any('food ration' in item or 'gunyoki' in item for item in items), items
            assert not any('shield' in item or 'armor' in item or 'being worn' in item
                           for item in items), items
            if mode == 'beginner':
                assert any('Beginner supplies' in game.inspect(x, y)
                           for (x, y), cell in game.cells.items() if cell['char'] == '(')
            position, turn = game.cursor, game.turn
            game.finish(automatic=True)
        with game_at(directory, 'NudistSmoke', role='Valkyrie', mode=mode) as game:
            assert game.cursor == position and game.turn == turn
            assert inventory(game) == items
            game.finish(automatic=True)
    print(f'PASS: {mode.title()} Nudist starts without armor and retains equipment on restore')


def check_blind_deaf(mode):
    with tempfile.TemporaryDirectory(prefix=f'atlas-{mode}-blind-deaf-') as temporary:
        directory = Path(temporary)
        prepare(directory, mode)
        with game_at(directory, 'BlindDeafSmoke', mode=mode, extra=',blind,deaf') as game:
            assert int(game.status[22]) & 18 == 18, game.status[22]
            assert len([cell for cell in game.cells.values() if cell['char'] != ' ']) <= 1
            game.send('command conduct')
            conduct = game.wait_input()
            text = ' '.join(row['text'] for row in conduct.get('items', [])) + ' '.join(conduct.get('lines', []))
            assert 'blind from birth' in text and 'deaf from birth' in text, text
            game.send('menu' if conduct['kind'] == 'menu' else 'key 32')
            assert game.wait_input().get('command')
            position, turn = game.cursor, game.turn
            game.finish(automatic=True)
        with game_at(directory, 'BlindDeafSmoke', mode=mode) as game:
            assert game.cursor == position and game.turn == turn
            assert int(game.status[22]) & 18 == 18, game.status[22]
            game.finish(automatic=True)
    print(f'PASS: {mode.title()} Blind and Deaf conditions, perception, conduct and restore')


def check_no_starting_pet(mode):
    with tempfile.TemporaryDirectory(prefix=f'atlas-{mode}-petless-') as temporary:
        directory = Path(temporary)
        prepare(directory, mode)
        with game_at(directory, 'PetlessSmoke', mode=mode, extra=',pettype:none') as game:
            assert not any(cell.get('pet') for cell in game.cells.values()), 'Starting pet was displayed'
            position, turn = game.cursor, game.turn
            game.finish(automatic=True)
        with game_at(directory, 'PetlessSmoke', mode=mode) as game:
            assert game.cursor == position and game.turn == turn
            assert not any(cell.get('pet') for cell in game.cells.values()), 'Pet appeared on restore'
            game.finish(automatic=True)
    print(f'PASS: {mode.title()} starts and restores without an initial pet')


if __name__ == '__main__':
    check_pauper()
    for mode in ('standard', 'beginner', 'explore'):
        check_nudist(mode)
    for mode in ('standard', 'beginner', 'explore', 'pauper'):
        check_blind_deaf(mode)
        check_no_starting_pet(mode)
