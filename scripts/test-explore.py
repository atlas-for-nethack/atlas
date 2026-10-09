#!/usr/bin/env python3
"""Verify native Explore semantics in isolated, non-wizard NetHack games."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('beginner', ROOT / 'scripts/test-beginner.py')
beginner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beginner)
engine = beginner.engine_test


def prepare(directory, explorers=True):
    beginner.prepare(directory)
    if explorers:
        config = directory / 'sysconf'
        config.write_text(config.read_text() + '\nEXPLORERS=*\n')


@contextmanager
def game_at(directory):
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='explore'):
        game = engine.Game(str(directory), name='AtlasExplore',
                           options=beginner.OPTIONS + ',align:neutral,playmode:explore', mode='explore')
    try:
        game.start()
        # Unix says "explore/discovery mode", Windows says "discovery mode".
        assert any('non-scoring' in e.get('text', '') for e in game.events)
        commands = next(e['commands'] for e in reversed(game.events) if e['type'] == 'commands')
        assert not any(c['name'] == 'wizwish' for c in commands)
        yield game
    finally:
        if game.process.poll() is None:
            game.process.kill()
            game.process.wait(timeout=5)


def check_refused():
    """Without EXPLORERS in sysconf, neither playmode nor #exploremode enters Explore."""
    with tempfile.TemporaryDirectory(prefix='atlas-explore-refused-') as temporary:
        directory = Path(temporary)
        prepare(directory, explorers=False)
        game = engine.Game(str(directory), name='AtlasRefused',
                           options=beginner.OPTIONS + ',align:neutral,playmode:explore', mode='explore')
        try:
            game.start()
            assert not any('non-scoring' in e.get('text', '') for e in game.events), 'Explore granted'
            game.send('command exploremode')
            game.wait_input()
            assert any('cannot access explore mode' in e.get('text', '') for e in game.events), game.events[-5:]
            game.finish(automatic=True)
        finally:
            if game.process.poll() is None:
                game.process.kill()
                game.process.wait(timeout=5)
    print('PASS: Explore refused without EXPLORERS in sysconf')


def check_restore():
    with tempfile.TemporaryDirectory(prefix='atlas-explore-restore-') as temporary:
        directory = Path(temporary)
        prepare(directory)
        with game_at(directory) as game:
            original = beginner.inventory(game)
            wishing = [i for i in original if 'wand of wishing' in i['text']]
            assert len(wishing) == 1 and '(0:3)' in wishing[0]['text'], wishing
            assert not any('magic whistle' in i['text'] for i in original)
            assert not any('Beginner supplies' in game.inspect(x, y)
                           for (x, y), c in game.cells.items() if c['char'] == '(')
            position, turn = game.cursor, game.turn
            game.finish(automatic=True)
        with game_at(directory) as game:
            assert game.cursor == position and game.turn == turn
            assert beginner.inventory(game) == original
            assert any(e.get('prompt') == 'Do you want to keep the save file?' for e in game.events)
            checkpoint = next(directory.glob('*.0'))
            game.process.kill()
            game.process.wait(timeout=5)
        recover = directory / 'recover.exe' if engine.WINDOWS else engine.RUNTIME / 'recover'
        result = subprocess.run([str(recover), checkpoint.stem],
                                cwd=directory, env=engine.engine_environment(directory, mode='explore'),
                                capture_output=True, text=True)
        assert result.returncode == 0, (result.stdout, result.stderr)
        with game_at(directory) as game:
            assert beginner.inventory(game) == original
            assert game.cursor == position and game.turn == turn
            game.finish(automatic=True)
    print('PASS: Explore starting wand, no Beginner kit or wizard commands; exact restore and checkpoint recovery')


def check_death():
    with tempfile.TemporaryDirectory(prefix='atlas-explore-death-') as temporary:
        directory = Path(temporary)
        prepare(directory)
        with game_at(directory) as game:
            deaths = 0
            resumed = False
            wait_pending = True
            game.send('key 109')  # m. permits waiting near a creature
            for _ in range(350000):
                event = game.next()
                if event['type'] == 'eof':
                    break
                if event['type'] != 'input':
                    continue
                if event.get('prompt') == 'Die?':
                    deaths += 1
                    answer = 'no' if deaths == 1 else 'yes'
                    game.send(('line ' + answer) if event['kind'] == 'line'
                              else 'key ' + str(ord(answer[0])))
                    wait_pending = False
                elif event['kind'] == 'key' and wait_pending:
                    game.send('key 46')
                    wait_pending = False
                elif event.get('command'):
                    if deaths == 1:
                        resumed = True
                        assert int(game.status[18]) > 0  # BL_HP
                    game.send('key 109')
                    wait_pending = True
                elif event['kind'] == 'menu':
                    game.send('menu')
                elif event['kind'] == 'yn':
                    game.send('key 110')
                else:
                    game.send('key 32')
            else:
                raise AssertionError('Waiting did not reach Explore death choices')
            game.process.wait(timeout=5)
            assert game.process.returncode == 0
            assert deaths == 2 and resumed
            assert any("OK, so you don't" in e.get('text', '') for e in game.events)
            assert (directory / 'record').read_bytes() == b'', 'Explore entered the high-score list'
            entries = (directory / 'xlogfile').read_text().splitlines()
            assert len(entries) == 1, entries
            fields = dict(part.split('=', 1) for part in entries[0].split('\t') if '=' in part)
            assert int(fields['flags'], 16) & 3 == 2, fields
            assert fields['death'] != 'quit'
    print('PASS: decline death and continue, accept later death, Explore log flag and no high-score entry')


if __name__ == '__main__':
    check_refused()
    check_restore()
    check_death()
