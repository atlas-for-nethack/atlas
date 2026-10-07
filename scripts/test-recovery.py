#!/usr/bin/env python3
"""Compile the native recovery helper and verify it against real checkpoints."""
import importlib.util
import pathlib
import shutil
import struct
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)

HARNESS = '''
import Foundation
@main struct Main {
    static func main() {
        for report in Recovery.recoverInterruptedGames(in: URL(fileURLWithPath: CommandLine.arguments[1]), using: URL(fileURLWithPath: CommandLine.arguments[2])) {
            print(report.checkpoint + ":" + report.disposition.rawValue + ":" + report.detail)
        }
    }
}
'''

with tempfile.TemporaryDirectory(prefix='atlas-recovery-test-') as temporary:
    work = pathlib.Path(temporary)
    source = work / 'RecoveryHarness.swift'
    source.write_text(HARNESS)
    harness = work / 'recovery-test'
    subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(ROOT / '.build/module-cache'),
                    str(ROOT / 'native/Recovery.swift'), str(source), '-o', str(harness)], check=True)
    directory = work / 'game'
    directory.mkdir()
    for name in ['nhdat', 'license', 'symbols', 'sysconf']:
        shutil.copy2(engine_test.RUNTIME / name, directory / name)
    for name in ['record', 'logfile', 'xlogfile', 'perm']:
        (directory / name).touch()
    (directory / 'save').mkdir()
    game = engine_test.Game(str(directory))
    game.start()
    turn, position = game.turn, game.cursor
    command = [str(harness), str(directory), str(engine_test.RUNTIME / 'recover')]
    active = subprocess.check_output(command, text=True)
    assert ':active:' in active, active
    assert list(directory.glob('*.0')) and not list((directory / 'save').iterdir())
    game.process.kill()
    game.process.wait()
    recovered = subprocess.check_output(command, text=True)
    assert ':recovered:' in recovered, recovered
    assert list((directory / 'Recovered Checkpoints').glob('*/*.0'))
    assert not list(directory.glob('*.0'))
    restored = engine_test.Game(str(directory))
    restored.start()
    assert (restored.turn, restored.cursor) == (turn, position)
    restored.finish(automatic=True)
    broken = directory / (str(__import__('os').getuid()) + 'Incomplete.0')
    original = struct.pack('i', game.process.pid)
    broken.write_bytes(original)
    skipped = subprocess.check_output(command, text=True)
    assert ':skipped:' in skipped and broken.read_bytes() == original
    print('PASS native recovery: live PID untouched; dead game recovered; originals archived; exact turn/position restored; incomplete checkpoint preserved')
