#!/usr/bin/env python3
"""Prove engine tests ignore ambient save/config paths using disposable decoys."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def prepare(directory):
    directory.mkdir()
    for name in ('nhdat', 'license', 'symbols', 'sysconf'):
        shutil.copy2(engine.RUNTIME / name, directory / name)
    for name in ('perm', 'record', 'logfile', 'xlogfile'):
        (directory / name).touch()
    (directory / 'save').mkdir()


def snapshot(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-isolation-') as temporary:
        root = Path(temporary)
        intended = root / 'intended'
        prepare(intended)
        decoys = [root / name for name in ('ambient-home', 'ambient-nethack', 'ambient-hack')]
        for directory in decoys:
            prepare(directory)
            (directory / '.nethackrc').write_text('OPTIONS=number_pad:1\n')
            (directory / 'save/sentinel').write_bytes(b'disposable save sentinel\x00')
            (directory / 'sentinel.0').write_bytes(b'disposable lock sentinel\x00')
            for name in ('record', 'logfile', 'xlogfile'):
                (directory / name).write_bytes(b'disposable score sentinel\x00')
        before = [snapshot(directory) for directory in decoys]
        hostile = dict(HOME=str(decoys[0]), NETHACKDIR=str(decoys[1]), HACKDIR=str(decoys[2]),
                       NETHACKOPTIONS='@' + str(decoys[0] / '.nethackrc'),
                       HACKOPTIONS='number_pad:1', WIZKIT=str(decoys[0] / 'save/sentinel'),
                       ATLAS_PLAY_MODE='beginner', SHOPTYPE='}', DEBUGFILES='*')
        with patch.dict(os.environ, hostile):
            env = engine.engine_environment(intended)
            assert all(env[key] == str(intended.resolve()) for key in ('HOME', 'NETHACKDIR', 'HACKDIR'))
            assert env['ATLAS_PLAY_MODE'] == 'standard'
            assert not any(key in env for key in ('HACKOPTIONS', 'WIZKIT', 'SHOPTYPE', 'DEBUGFILES'))
            assert engine.engine_environment(intended, mode='explore')['ATLAS_PLAY_MODE'] == 'explore'
            assert engine.engine_environment(intended, fixture_environment={'SHOPTYPE': '}'})['SHOPTYPE'] == '}'
            game = engine.Game(intended, name='AtlasIsolation')
            try:
                game.start()
                turn, position = game.turn, game.cursor
                assert game.command('\x04')['directionKeys'] == 'hykulnjb><'
                game.finish(automatic=True)
                saves = list((intended / 'save').iterdir())
                assert len(saves) == 1 and saves[0].stat().st_size > 0, saves
                restored = engine.Game(intended, name='AtlasIsolation')
                game = restored
                restored.start()
                assert (restored.turn, restored.cursor) == (turn, position)
                checkpoint = next(intended.glob('*.0'))
                restored.process.kill()
                restored.process.wait(timeout=5)
                result = subprocess.run([str(engine.RUNTIME / 'recover'), checkpoint.stem],
                                        cwd=intended, env=engine.engine_environment(intended),
                                        capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (result.stdout, result.stderr)
                recovered = engine.Game(intended, name='AtlasIsolation')
                game = recovered
                recovered.start()
                assert (recovered.turn, recovered.cursor) == (turn, position)
                recovered.finish(automatic=True)
                # The independent direct character-creation launch uses the
                # same environment constructor, rather than Game's Popen.
                spec = importlib.util.spec_from_file_location('character_test', ROOT / 'scripts/test-character-rules.py')
                character = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(character)
                character.engine_character('Valkyrie', 'human', 'female', 'neutral', character.upstream_rules())
            finally:
                if game.process.poll() is None:
                    game.process.kill()
                    game.process.wait(timeout=5)
        assert [snapshot(directory) for directory in decoys] == before, 'A decoy was changed or received test output'
        artifact = ROOT / '.artifacts/release-remediation/isolation.json'
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({'result': 'pass', 'decoyFiles': before,
            'checks': ['new game', 'direct character launch', 'restore', 'checkpoint recovery',
                       'explicit mode and fixture overrides', 'byte-identical decoys'],
            'engineSha256': hashlib.sha256((engine.RUNTIME / 'nethack').read_bytes()).hexdigest()}, indent=2) + '\n')
    print('PASS: ambient config/save/lock/score paths remain byte-identical through new game, direct launch, restore and recovery')
    print(artifact)


if __name__ == '__main__':
    main()
