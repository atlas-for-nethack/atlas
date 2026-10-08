#!/usr/bin/env python3
"""Run the real Electron host against isolated game data.
The Electron version of test-native.py. Requires a desktop session and
`npm install` in electron/. Builds the host with the TypeScript compiler first.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gender', choices=['male', 'female'], default='female')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'electron'
OUT = ROOT / '.artifacts'
OUT.mkdir(exist_ok=True)
WINDOWS = os.name == 'nt'
# Upstream Windows NetHack creates these at startup unless its sysconf redirects it.
REAL_FOLDERS = [Path(os.environ[name]) / 'NetHack' for name in ['USERPROFILE', 'LOCALAPPDATA']
                if WINDOWS and name in os.environ] + ([Path('C:/ProgramData/NetHack')] if WINDOWS else [])
already_present = {folder for folder in REAL_FOLDERS if folder.exists()}

subprocess.run(['npm', 'run', 'build'], cwd=HOST, check=True, shell=WINDOWS)
run = Path(tempfile.mkdtemp(prefix='electron-', dir=OUT))
report = run / 'diagnostics.jsonl'
env = {key: value for key, value in os.environ.items() if not key.startswith('ATLAS_')}
env.update(ATLAS_TEST_GENDER=args.gender, ATLAS_TEST_MODE='standard', ATLAS_TEST_NUMBER_PAD='0',
           ATLAS_DATA_DIR=str(run / 'game'),
           ATLAS_DIAGNOSTICS=str(report), ATLAS_SNAPSHOT=str(run / 'game.png'))
electron = HOST / 'node_modules/electron/dist' / ('electron.exe' if WINDOWS else 'electron')
with (run / 'application.log').open('w') as log:
    process = subprocess.Popen([str(electron), str(HOST), '--self-test'], env=env, stdout=log, stderr=log)
    try:
        code = process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise SystemExit(f'FAIL: Electron host timed out. See {run}')
assert code == 0, f'Electron host exited {code}; see {run}'
events = [json.loads(line) for line in report.read_text(encoding='utf-8').splitlines()]
assert all(event.get('ok') is True for event in events), [e for e in events if e.get('ok') is not True]
phases = {e['phase'] for e in events}
required = {'boot', 'alignment', 'sex', 'actions-prefix', 'actions-filter', 'actions-cancel',
            'context-underfoot', 'mouse-movement', 'mouse-distance', 'direction-bar', 'direction-arrow',
            'direction-cancel', 'render', 'inventory', 'arrow-movement', 'hover', 'wait', 'save',
            'restore', 'complete', 'read-selection', 'read-cancel', 'save-picker', 'experience-status',
            'yn-default-focus', 'yn-default-enter', 'yn-focused-enter'}
assert required <= phases, f'Missing phases: {required - phases}'
for name in ['game.png', 'read.png', 'context.png', 'actions.png', 'direction.png']:
    assert (run / name).is_file(), f'Missing screenshot: {name}'
assert any((run / 'game').glob('*.NetHack-saved-game')), 'Final quit did not save the restored game'
for folder in REAL_FOLDERS:
    assert folder in already_present or not folder.exists(), f'The test created a real NetHack folder: {folder}'
print('PASS: Electron host start, map, inventory, inspection, save, restore and quit.')
print(f'Evidence and screenshot: {run}')
