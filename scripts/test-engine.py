#!/usr/bin/env python3
"""Exercise bundled NetHack through its actual JSON window port (no fake game)."""
import json
import os
import pathlib
import queue
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNTIME = ROOT / 'engine' / 'runtime'
# Windows NetHack ignores HOME and NETHACKDIR and reads -p/-r/-@ nowhere; its
# portable sysconf keeps every file beside the executable, and an options file
# survives the second Windows options pass (see docs/protocol.md).
WINDOWS = os.name == 'nt'
OPTIONS_FILE = 'atlas.nethackrc'
OPTIONS = 'gender:female,align:neutral,color,hilite_pet,!autopickup,time,!news,checkpoint'


def engine_environment(directory, options=OPTIONS, mode='standard', fixture_environment=None):
    """Build an explicit child environment; cwd alone does not isolate NetHack."""
    target = pathlib.Path(directory).resolve(strict=True)
    assert target.is_dir(), target
    # Explicit invalid values are intentional fail-closed mode test controls.
    assert isinstance(mode, str), mode
    assert not options.startswith(('@', '/', '~')), 'Use an explicit isolated config path'
    # Keep execution/locale settings, not ambient engine options, config paths,
    # dynamic-loader overrides, save locations, wizard kits or Atlas test hooks.
    environment = {key: os.environ[key] for key in
                   ('PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', 'USER', 'LOGNAME', 'SYSTEMROOT')
                   if key in os.environ}
    environment.update(HOME=str(target), NETHACKDIR=str(target), HACKDIR=str(target),
                       NETHACKOPTIONS=options, ATLAS_PLAY_MODE=mode)
    if WINDOWS:
        environment['NETHACKOPTIONS'] = '@' + OPTIONS_FILE
    if fixture_environment:
        assert set(fixture_environment) <= {'SHOPTYPE'}, fixture_environment
        environment.update(fixture_environment)
    return environment


class Game:
    def __init__(self, directory, role="Valkyrie", name="AtelierSmoke", options=OPTIONS, config=None,
                 mode='standard', fixture_environment=None):
        arguments = [str(RUNTIME / 'nethack'), '-u', name, '-p', role, '-r', 'human', '-@']
        if config is not None:
            config = pathlib.Path(config).resolve(strict=True)
            assert config.is_relative_to(pathlib.Path(directory).resolve()), config
            arguments.append('-nethackrc='+str(config))
        if WINDOWS:
            # Role and race become options; a config file is merged before them.
            arguments = [str(pathlib.Path(directory) / 'nethack.exe'), '-u', name]
            prefix = config.read_text() + '\n' if config is not None else ''
            (pathlib.Path(directory) / OPTIONS_FILE).write_text(
                prefix + f'OPTIONS=role:{role},race:human,{options}\n')
        self.process = subprocess.Popen(
            arguments,
            cwd=directory, env=engine_environment(directory, options, mode, fixture_environment),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        self.events = []
        self.queue = queue.Queue()
        self.cells = {}
        self.status = {}
        self.cursor = None

        def read():
            for line in self.process.stdout:
                try:
                    self.queue.put(json.loads(line))
                except json.JSONDecodeError:
                    self.queue.put({'type': 'invalidJSON', 'text': line})
            self.queue.put({'type': 'eof'})
        threading.Thread(target=read, daemon=True).start()

    def send(self, command):
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()

    def next(self):
        try:
            event = self.queue.get(timeout=10)
        except queue.Empty:
            raise AssertionError(f'Engine stalled. Recent events: {self.events[-5:]}')
        self.events.append(event)
        kind = event['type']
        assert kind != 'invalidJSON', event
        if kind == 'cell':
            self.cells[(event['x'], event['y'])] = event
        elif kind == 'cursor':
            self.cursor = (event['x'], event['y'])
        elif kind == 'status':
            self.status[event['field']] = event['value']
        return event

    def wait_input(self):
        for _ in range(10000):
            e = self.next()
            assert e['type'] != 'eof', ('Unexpected exit', self.process.poll(), self.events[-10:])
            if e['type'] == 'input':
                return e
        raise AssertionError('Too many events without input')

    def start(self):
        for _ in range(20):
            e = self.wait_input()
            if e['kind'] == 'key' and e.get('command'):
                assert self.status[18].strip().isdigit(), self.status
                assert self.cursor, 'Missing player position'
                assert any(c['tile'] >= 0 for c in self.cells.values())
                return e
            if e['kind'] == 'menu':
                key = 'n' if 'tutorial' in e['prompt'] else 'y'
                selection = next(i['id'] for i in e['items'] if i['key'] == key)
                self.send('menu ' + str(selection))
            elif e['kind'] == 'yn':
                self.send('key 110')
            elif e['kind'] == 'line':
                self.send('line AtelierSmoke')
            else:
                self.send('key 32')
        raise AssertionError('Unexpected character creation loop')

    @property
    def turn(self):
        return int(self.status[16].strip())

    def inspect(self, x, y):
        before = len(self.events)
        turn = self.turn
        self.send(f'inspect {x} {y}')
        while True:
            e = self.next()
            if e['type'] == 'inspect':
                assert (e['x'], e['y']) == (x, y)
                assert self.turn == turn
                assert not any(e['type'] == 'status' for e in self.events[before:])
                return e['text']

    def command(self, character):
        self.send('key ' + str(ord(character)))
        return self.wait_input()

    def finish(self, automatic=False):
        invalid_response_sent = False
        reprompt_verified = False
        if automatic:
            self.send('save')
        else:
            self.send('key 83')
        for _ in range(20000):
            e = self.next()
            if e['type'] == 'eof':
                break
            if e['type'] == 'input':
                if automatic:
                    # Events describe the engine state even when save resolves
                    # that wait internally; do not queue extra keys.
                    continue
                if e['kind'] == 'yn':
                    assert e['prompt'] == 'Really save?' and not e.get('direction'), e
                    if not invalid_response_sent:
                        self.send('key 120')  # invalid x must advertise a new wait
                        invalid_response_sent = True
                    else:
                        reprompt_verified = True
                        self.send('key 121')
                elif e['kind'] == 'key':
                    self.send('key 32')
                else:
                    raise AssertionError(e)
        self.process.wait(timeout=5)
        assert self.process.returncode == 0, (self.process.returncode, self.process.stderr.read())
        assert any('Saving' in e.get('text', '') for e in self.events)
        if not automatic:
            assert reprompt_verified, 'Invalid yes/no answer did not emit a new input event'


def prepare_runtime(target):
    """Populate an isolated runtime; Windows needs its own executable copy."""
    if WINDOWS:
        for path in RUNTIME.iterdir():
            if path.is_file() and path.suffix != '.nethackrc' and not path.name.startswith('.'):
                shutil.copy2(path, target / path.name)
        return
    for name in ['nhdat', 'license', 'symbols', 'sysconf']:
        shutil.copy2(RUNTIME / name, target / name)
    for name in ['perm', 'record', 'logfile', 'xlogfile']:
        (target / name).touch()
    (target / 'save').mkdir()


def saved_games(target):
    if WINDOWS:
        return [p for p in target.iterdir() if p.name.endswith('.NetHack-saved-game')]
    return list((target / 'save').iterdir())


def main():
    with tempfile.TemporaryDirectory(prefix='atelier-engine-') as directory:
        target = pathlib.Path(directory)
        prepare_runtime(target)

        game = Game(directory)
        game.start()
        assert 'Valkyrie' in game.status[0] or 'Stripling' in game.status[0], game.status[0]
        before = game.turn
        description = game.inspect(*game.cursor)
        assert 'human' in description.lower() and 'valkyrie' in description.lower(), description
        unknown = next((p for p, c in game.cells.items() if c['char'] == ' ' and p[0] > 0), (0, 0))
        assert 'unexplored' in game.inspect(*unknown).lower()
        inventory = game.command('i')
        assert inventory['kind'] in ('menu', 'text'), inventory
        assert any('dagger' in i['text'] or 'sword' in i['text'] for i in inventory.get('items', [])), inventory
        game.send('menu' if inventory['kind'] == 'menu' else 'key 32')
        assert game.wait_input().get('command')
        assert game.turn == before, 'Inspection/inventory spent a turn'

        # Choose a displayed neighboring floor rather than relying on a seed.
        x, y = game.cursor
        directions = [(-1, 0, 'h'), (1, 0, 'l'), (0, -1, 'k'), (0, 1, 'j')]
        movement = next((d for d in directions if game.cells.get((x+d[0], y+d[1]), {}).get('char') == '.'), None)
        assert movement, 'Starting room has no adjacent floor'
        e = game.command(movement[2])
        assert e.get('command'), e
        assert game.cursor == (x + movement[0], y + movement[1]), (game.cursor, movement)
        assert game.turn > before, 'Movement failed to advance turn'
        position, saved_turn = game.cursor, game.turn
        (ROOT / '.artifacts').mkdir(exist_ok=True)
        (ROOT / '.artifacts' / 'game-events.json').write_text(json.dumps(game.events, indent=2))
        game.finish()
        assert saved_games(target), 'No save file'
        print(f'PASS new game, inventory, safe hover, movement, save (turn {saved_turn}; {len(game.events)} JSON events)')

        restored = Game(directory)
        restored.start()
        assert restored.turn == saved_turn and restored.cursor == position
        assert any('Restoring save' in e.get('text', '') for e in restored.events)
        assert restored.command('i')['kind'] in ('menu', 'text')
        restored.finish(automatic=True)
        print('PASS exact turn/position restore and automatic save from inventory')

        direction = Game(directory)
        direction.start()
        e = direction.command('\x04')  # kick asks for a direction
        assert e['kind'] == 'yn' and e.get('direction') and not e.get('targeting'), e
        assert e['directionKeys'] == 'hykulnjb><' and e['selfKey'] == '.', e
        direction.finish(automatic=True)
        print('PASS automatic save cancels direction prompt without a game action')

        disconnected = Game(directory)
        disconnected.start()
        disconnected.process.stdin.close()
        disconnected.process.wait(timeout=5)
        assert disconnected.process.returncode == 0
        assert saved_games(target), 'EOF did not save'
        print('PASS parent EOF safely saves using upstream hangup handling')

        crashed = Game(directory)
        crashed.start()
        checkpoint = next(target.glob('*.0'))
        assert struct.unpack('i', checkpoint.read_bytes()[:4])[0] == crashed.process.pid
        crashed.process.kill()
        crashed.process.wait(timeout=5)
        recover = target / 'recover.exe' if WINDOWS else RUNTIME / 'recover'
        recovery = subprocess.run([str(recover), checkpoint.stem], cwd=directory,
                                  env=engine_environment(directory), capture_output=True, text=True)
        assert recovery.returncode == 0 and saved_games(target), (recovery.stdout, recovery.stderr)
        recovered = Game(directory)
        recovered.start()
        assert recovered.turn == saved_turn and recovered.cursor == position
        recovered.finish(automatic=True)
        print('PASS interrupted-game recovery from real checkpoint, with exact turn/position')

        quantity = Game(directory, role='Ranger', name='QuantitySmoke', options=OPTIONS + ',menustyle:traditional')
        quantity.start()
        prompt = quantity.command('D')
        assert prompt['kind'] == 'line'
        quantity.send('line )')  # traditional drop: query weapons
        for _ in range(10):
            prompt = quantity.wait_input()
            assert prompt['kind'] == 'yn', prompt
            if '#' in prompt['choices']:
                break
            quantity.send('key 110')
        match = re.match(r'([A-Za-z]) - (\d+) ', prompt['prompt'])
        assert match and int(match[2]) > 2, prompt
        letter, count = match[1], int(match[2])
        quantity.send('key 50')  # entering a digit opens an editable count
        numeric = quantity.wait_input()
        assert numeric['kind'] == 'line' and numeric['purpose'] == 'count' and numeric['default'] == '2'
        quantity.send('line -1')
        assert quantity.wait_input().get('purpose') == 'count', 'Invalid quantity was accepted'
        quantity.send('line 2')
        following = quantity.wait_input()
        if following['kind'] == 'yn':
            quantity.send('key 113')
            assert quantity.wait_input().get('command')
        else:
            assert following.get('command'), following
        contents = quantity.command('i')
        changed_stack = next(item for item in contents['items'] if item['key'] == letter)
        assert changed_stack['text'].startswith(str(count - 2) + ' '), changed_stack
        quantity.finish(automatic=True)
        print('PASS numeric quantity prompt, invalid-count reprompt, and exact two-item stack split')

        caster = Game(directory, role='Wizard', name='SpellDirectionSmoke')
        caster.start()
        spells = caster.command('Z')
        assert spells['kind'] == 'menu', spells
        force_bolt = next(item for item in spells['items'] if 'force bolt' in item['text'])
        caster.send('menu ' + str(force_bolt['id']))
        aim = caster.wait_input()
        assert aim['kind'] == 'yn' and aim.get('direction') and not aim.get('targeting'), aim
        assert aim['directionKeys'] == 'hykulnjb><' and aim['selfKey'] == '.', aim
        caster.send('key 62')  # downward: exercise vertical direction without self-zapping
        normal = caster.wait_input()
        assert normal.get('command') and not normal.get('direction'), normal
        time_before_targeting = caster.turn
        target = caster.command(';')
        if target['kind'] == 'menu' and target['how'] == 0:  # first-use farlook tip
            caster.send('menu')
            target = caster.wait_input()
        assert target['kind'] == 'key' and target.get('targeting') and not target.get('direction'), target
        caster.send('key 27')
        assert caster.wait_input().get('command') and caster.turn == time_before_targeting
        caster.finish(automatic=True)

        keypad = Game(directory, name='KeypadDirectionSmoke', options=OPTIONS + ',number_pad:1')
        keypad.start()
        aim = keypad.command('\x04')
        assert aim.get('direction') and aim['directionKeys'] == '47896321><', aim
        keypad.finish(automatic=True)
        print('PASS spell/kick direction context, vertical direction, distinct turn-free targeting, and current numpad bindings')


if __name__ == '__main__':
    main()
