#!/usr/bin/env python3
"""Action catalog and dispatch regression checks against the real engine."""
import collections
import importlib.util
import pathlib
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('engine_test', pathlib.Path(__file__).with_name('test-engine.py'))
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)
Game, RUNTIME, OPTIONS = engine_test.Game, engine_test.RUNTIME, engine_test.OPTIONS


def prepare(directory):
    target = pathlib.Path(directory)
    for name in ['nhdat', 'license', 'symbols', 'sysconf']:
        shutil.copy2(RUNTIME / name, target / name)
    for name in ['perm', 'record', 'logfile', 'xlogfile']:
        (target / name).touch()
    (target / 'save').mkdir()


def named(game, name):
    game.send('command ' + name)
    return game.wait_input()


def reject(game, name):
    before = game.turn
    game.send('command ' + name)
    event = game.next()
    assert event['type'] == 'commandRejected' and event['name'] == name, event
    assert game.turn == before


def dismiss(game, event):
    if event['kind'] == 'menu':
        game.send('menu cancel')
    else:
        game.send('key 27')
    return game.wait_input()


def catalog(game):
    event = next(e for e in reversed(game.events) if e['type'] == 'commands')
    return {c['name']: c for c in event['commands']}


def context(game):
    event = next(e for e in reversed(game.events) if e['type'] == 'context')
    return {c['name']: c for c in event['commands']}


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-actions-') as directory:
        prepare(directory)
        game = Game(directory, name='AtlasActions')
        try:
            game.start()
            commands = catalog(game)
            assert len(commands) > 90, len(commands)
            assert commands['kick']['keys'] == ['Ctrl+D'], commands['kick']
            assert commands['sit']['selectable'] and commands['wait']['selectable']
            assert commands['movenorthwest']['movement'] and 'y' in commands['movenorthwest']['keys']
            assert commands['fight']['prefix']
            assert commands['toggle']['selectable'] is False
            assert not {'wizwish', 'wizidentify', 'clicklook', 'mouseaction', 'shell', 'sleep'} & commands.keys()
            assert not commands['lookaround']['keys'] and commands['lookaround']['selectable']
            before = game.turn
            reject(game, 'not-a-command')
            reject(game, 'wizwish')
            reject(game, 'toggle')
            assert named(game, 'lookaround').get('command')
            assert game.turn == before, 'Unbound inspection advanced time'
            event = named(game, 'inventory')
            assert event['kind'] in ('menu', 'text'), event
            reject(game, 'wait')
            assert dismiss(game, event).get('command')
            assert game.turn == before, 'Rejected action ran after menu closed'
            event = named(game, 'kick')
            assert event.get('direction'), event
            reject(game, 'wait')
            assert dismiss(game, event).get('command')
            assert game.turn == before
            event = named(game, 'glance')
            if event['kind'] in ('menu', 'text'):
                event = dismiss(game, event)  # first-use farlook tip
            assert event.get('targeting'), event
            reject(game, 'wait')
            assert dismiss(game, event).get('command')
            assert game.turn == before
            assert named(game, 'wait').get('command')
            assert game.turn == before + 1, 'Named wait must take precisely one turn'
            before = game.turn
            event = named(game, 'fight')
            assert event.get('command'), event
            assert game.command('\x1b').get('command')
            assert game.turn == before, 'Canceling prefix took a turn'
            assert named(game, 'fight').get('command')
            assert named(game, 'lookaround').get('command')  # core rejects # after F
            event = game.command('#')
            assert event['kind'] == 'line', 'A rejected prefix left a stale named action'
            game.send('line \x1b')
            assert game.wait_input().get('command')
            assert game.turn == before
            game.finish(automatic=True)
        finally:
            if game.process.poll() is None:
                game.process.kill()
                game.process.wait()
        print('PASS authoritative catalog, bound/unbound actions, prefix cancel, prompt rejection, exact turns')

    with tempfile.TemporaryDirectory(prefix='atlas-actions-keypad-') as directory:
        prepare(directory)
        game = Game(directory, name='AtlasKeypad', options=OPTIONS + ',number_pad:1')
        try:
            game.start()
            commands = catalog(game)
            assert '7' in commands['movenorthwest']['keys'], commands['movenorthwest']
            assert 'y' not in commands['movenorthwest']['keys']
            assert named(game, 'inventory')['kind'] in ('menu', 'text')
            game.finish(automatic=True)
        finally:
            if game.process.poll() is None:
                game.process.kill()
                game.process.wait()
        print('PASS live numeric-keypad catalog and named actions')

    # Approach a displayed door through known floor. This checks recommendations
    # against actual rendering and movement, without peeking at hidden terrain.
    offsets = [(-1, 0, 'movewest'), (1, 0, 'moveeast'), (0, -1, 'movenorth'), (0, 1, 'movesouth')]
    verified = False
    for attempt in range(8):
        with tempfile.TemporaryDirectory(prefix='atlas-actions-context-') as directory:
            prepare(directory)
            game = Game(directory, name='AtlasContext')
            try:
                game.start()
                doors = {pos for pos, cell in game.cells.items() if cell['char'] == '+'}
                pending = collections.deque([(game.cursor, [])])
                visited = {game.cursor}
                path = None
                while pending:
                    pos, route = pending.popleft()
                    if any(max(abs(pos[0] - d[0]), abs(pos[1] - d[1])) == 1 for d in doors):
                        path = route
                        break
                    for dx, dy, action in offsets:
                        nxt = (pos[0] + dx, pos[1] + dy)
                        if nxt not in visited and game.cells.get(nxt, {}).get('char') in ('.', '<', '>'):
                            visited.add(nxt)
                            pending.append((nxt, route + [action]))
                if path is not None:
                    for action in path:
                        assert named(game, action).get('command')
                    hints = context(game)
                    if 'open' in hints:
                        assert 'kick' in hints and 'close' not in hints, hints
                        verified = True
                        before = game.turn
                        assert named(game, 'open').get('direction')
                        game.command('\x1b')
                        assert game.turn == before
                game.finish(automatic=True)
            finally:
                if game.process.poll() is None:
                    game.process.kill()
                    game.process.wait()
        if verified:
            break
    assert verified, 'Could not exercise adjacent door hints in eight starting rooms'
    print('PASS nearby-door suggestions from rendered cells and ordinary direction prompt')


if __name__ == '__main__':
    main()
