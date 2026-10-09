#!/usr/bin/env python3
"""Verify the Electron host's checkpoint recovery against a killed engine.

Runs the compiled electron/dist/recovery.js with Node in an isolated folder on
Windows or Linux. Build the host first (npm run build in electron/).
"""
import importlib.util
import json
import os
import pathlib
import struct
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)
WINDOWS = engine_test.WINDOWS
MODULE = ROOT / 'electron' / 'dist' / 'recovery.js'
# The host's own options; checkpointing is the engine default.
HOST_OPTIONS = 'gender:female,align:neutral,color,hilite_pet,!autopickup,time,!news,force_invmenu,menustyle:full'
assert MODULE.exists(), 'Build the Electron host first: cd electron && npm run build'


def recover(directory, executable):
    script = ('const [module, directory, executable] = process.argv.slice(1);'
              'console.log(JSON.stringify(require(module).recoverInterruptedGames(directory, executable)));')
    output = subprocess.check_output(['node', '-e', script, str(MODULE), str(directory), str(executable)], text=True)
    return json.loads(output)


def checkpoint_files(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir()
            if path.is_file() and path.suffix[1:].isdigit()}


with tempfile.TemporaryDirectory(prefix='atlas-electron-recovery-') as temporary:
    directory = pathlib.Path(temporary)
    engine_test.prepare_runtime(directory)
    executable = directory / 'recover.exe' if WINDOWS else engine_test.RUNTIME / 'recover'
    game = engine_test.Game(str(directory), options=HOST_OPTIONS)
    game.start()
    turn, position = game.turn, game.cursor
    before = checkpoint_files(directory)
    assert any(name.endswith('.0') for name in before), 'The engine wrote no checkpoint'

    active = recover(directory, executable)
    assert [report['disposition'] for report in active] == ['active'], active
    assert checkpoint_files(directory) == before and not engine_test.saved_games(directory)

    game.process.kill()
    game.process.wait(timeout=5)
    interrupted = checkpoint_files(directory)
    missing = directory / ('missing-recover.exe' if WINDOWS else 'missing-recover')
    failed = recover(directory, missing)
    assert [report['disposition'] for report in failed] == ['failed'], failed
    assert checkpoint_files(directory) == interrupted and not engine_test.saved_games(directory)
    assert not list(directory.glob('.recovery-*')), 'Staging folder left behind'

    recovered = recover(directory, executable)
    assert [report['disposition'] for report in recovered] == ['recovered'], recovered
    archived = list((directory / 'Recovered Checkpoints').glob('*/*'))
    assert {path.name for path in archived} == set(interrupted), archived
    assert not any(name.endswith('.0') for name in checkpoint_files(directory))
    assert not list(directory.glob('.recovery-*')), 'Staging folder left behind'
    restored = engine_test.Game(str(directory), options=HOST_OPTIONS)
    restored.start()
    assert (restored.turn, restored.cursor) == (turn, position), (restored.turn, restored.cursor, turn, position)
    restored.finish(automatic=True)

    prefix = '' if WINDOWS else str(os.getuid())
    broken = directory / (prefix + 'Incomplete.0')
    original = struct.pack('i', game.process.pid)
    broken.write_bytes(original)
    skipped = recover(directory, executable)
    assert [report['disposition'] for report in skipped] == ['skipped'], skipped
    assert broken.read_bytes() == original

print('PASS Electron recovery: live engine untouched; failed recovery kept checkpoints; '
      'killed game recovered with exact turn/position; originals archived; incomplete checkpoint preserved')
