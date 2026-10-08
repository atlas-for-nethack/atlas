#!/usr/bin/env python3
"""Run the real Cocoa/WebKit application against isolated game data.
Requires a logged-in macOS desktop session (not a headless command sandbox).
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gender', choices=['male', 'female'], default='female')
parser.add_argument('--mode', choices=['standard', 'beginner', 'explore', 'pauper'], default='standard')
parser.add_argument('--nudist', action='store_true', help='Select the Nudist start in Standard or Beginner')
parser.add_argument('--tileset', help='Exercise this bundled/imported atlas in the isolated test')
parser.add_argument('--number-pad', choices=['0', '1', '3'], default='0')
parser.add_argument('--rebind-save', action='store_true', help='Bind literal S to wait; host Save must still save')
parser.add_argument('--persisted-tileset', type=Path, help='Copy a supplied custom manifest into this disposable run')
args = parser.parse_args()
if args.nudist and args.mode not in ('standard', 'beginner'):
    parser.error('--nudist is available only with Standard or Beginner')
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.artifacts'
OUT.mkdir(exist_ok=True)
run = Path(tempfile.mkdtemp(prefix='native-', dir=OUT))
report = run / 'diagnostics.jsonl'
env = {key: value for key, value in os.environ.items() if not key.startswith('ATLAS_TEST_')}
env.update(ATLAS_TEST_GENDER=args.gender, ATLAS_TEST_MODE=args.mode,
           ATLAS_TEST_NUDIST='1' if args.nudist else '0',
           ATLAS_TEST_NUMBER_PAD=args.number_pad,
           ATLAS_DATA_DIR=str(run / 'game'),
           ATLAS_DIAGNOSTICS=str(report), ATLAS_SNAPSHOT=str(run / 'game.png'))
if args.tileset:
    env['ATLAS_TEST_TILESET'] = args.tileset
persisted_file = None
persisted_digest = None
if args.persisted_tileset:
    persisted_file = run / 'game/imported-tileset.json'
    persisted_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.persisted_tileset, persisted_file)
    persisted_digest = hashlib.sha256(persisted_file.read_bytes()).hexdigest()
if args.rebind_save:
    directory = run / 'game' / {'standard': '', 'beginner': 'Beginner', 'explore': 'Explore', 'pauper': 'Pauper'}[args.mode]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / '.nethackrc').write_text('BINDINGS=S:wait\n')
standard_files = {}
if args.mode != 'standard':
    # Preserve real same-name saves in the other mode namespaces.
    spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
    engine_test = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine_test)
    for protected_mode in [mode for mode in ['standard', 'beginner', 'explore', 'pauper'] if mode != args.mode]:
        directory = run / 'game' / {'standard': '', 'beginner': 'Beginner', 'explore': 'Explore', 'pauper': 'Pauper'}[protected_mode]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'save').mkdir()
        for name in ['nhdat', 'license', 'symbols', 'sysconf']:
            shutil.copy2(engine_test.RUNTIME / name, directory / name)
        if protected_mode == 'explore':
            config = directory / 'sysconf'
            config.write_text(config.read_text().rstrip('\n') + '\nEXPLORERS=*\n')
        for name in ['perm', 'record', 'logfile', 'xlogfile']:
            (directory / name).touch()
        previous_environment = dict(os.environ)
        try:
            os.environ.update(HOME=str(directory), NETHACKDIR=str(directory),
                              HACKDIR=str(directory), ATLAS_PLAY_MODE=protected_mode)
            seed = engine_test.Game(str(directory), role='Wizard', name='AtlasSmoke', mode=protected_mode)
            seed.start()
            seed.finish(automatic=True)
        finally:
            os.environ.clear()
            os.environ.update(previous_environment)
        for file in list((directory / 'save').iterdir()) + [directory / n for n in ['record', 'logfile', 'xlogfile', 'sysconf']]:
            standard_files[file] = hashlib.sha256(file.read_bytes()).hexdigest()
app = ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'
with (run / 'application.log').open('w') as log:
    process = subprocess.Popen([str(app), '--self-test'], env=env, stdout=log, stderr=log)
    try:
        code = process.wait(timeout=50)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
        raise SystemExit(f'FAIL: native app timed out. See {run}')
assert code == 0, f'Native application exited {code}; see {run}'
events = [json.loads(line) for line in report.read_text().splitlines()]
assert all(event.get('ok') is True for event in events), events
phases = {e['phase'] for e in events}
required = {'boot', 'alignment', 'sex', 'actions-prefix', 'actions-filter', 'actions-cancel', 'context-underfoot', 'mouse-movement', 'mouse-distance', 'direction-bar', 'direction-arrow', 'direction-cancel', 'render', 'inventory', 'arrow-movement', 'hover', 'wait', 'save', 'restore', 'complete'}
if args.mode != 'pauper':
    required |= {'read-selection', 'read-cancel'}
required.add('save-picker')
required.add('experience-status')
required |= {'yn-default-focus', 'yn-default-enter', 'yn-focused-enter'}
if args.mode == 'beginner':
    required |= {'beginner-creation', 'beginner-help', 'beginner-chest',
                 'beginner-chest-visible', 'beginner-loot-action', 'beginner-chest-contents'}
    for name in ['beginner-creation.png', 'beginner-help.png', 'beginner-chest.png']:
        assert (run / name).is_file(), f'Missing Beginner screenshot: {name}'
if args.mode == 'explore':
    required |= {'explore-creation', 'explore-help', 'explore-inventory', 'explore-restore-choice'}
    for name in ['explore-creation.png', 'explore-help.png']:
        assert (run / name).is_file(), name
if args.mode == 'pauper':
    required |= {'pauper-creation', 'pauper-help', 'pauper-inventory'}
    for name in ['pauper-creation.png', 'pauper-help.png']:
        assert (run / name).is_file(), name
if args.nudist:
    required |= {'nudist-creation', 'nudist-inventory'}
    assert (run / 'nudist-creation.png').is_file(), 'Missing Nudist creation screenshot'
assert required <= phases, f'Missing phases: {required - phases}'
if args.tileset:
    rendered = next(event for event in events if event['phase'] == 'render')
    assert f'atlas {args.tileset} loaded;' in rendered.get('detail', ''), rendered
if args.mode != 'pauper':
    assert (run / 'read.png').is_file(), 'No readable item-selection screenshot'
assert (run / 'context.png').is_file(), 'No contextual-action screenshot'
assert (run / 'actions.png').is_file(), 'No action picker screenshot'
assert (run / 'direction.png').is_file(), 'No direction prompt screenshot'
assert (run / 'game.png').is_file(), 'No rendered native screenshot'
save_folder = run / 'game' / {'standard': 'save', 'beginner': 'Beginner/save', 'explore': 'Explore/save', 'pauper': 'Pauper/save'}[args.mode]
assert any(save_folder.iterdir()), 'Final application quit did not preserve the restored game'
for file, digest in standard_files.items():
    assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, f'Other-mode data changed: {file}'
if persisted_file:
    assert hashlib.sha256(persisted_file.read_bytes()).hexdigest() == persisted_digest, 'Startup changed the supplied import file'
print('PASS: native Cocoa/WebKit start, map, inventory, inspection, save, restore and quit.')
print(f'Evidence and screenshot: {run}')
