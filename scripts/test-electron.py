#!/usr/bin/env python3
"""Run the real Electron host against isolated game data.
The Electron version of test-native.py. Requires a desktop session and
`npm install` in electron/. Builds the host with the TypeScript compiler first.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gender', choices=['male', 'female'], default='female')
parser.add_argument('--mode', choices=['standard', 'beginner', 'explore', 'pauper'], default='standard')
parser.add_argument('--quit-timeout', action='store_true',
                    help='Freeze the engine, close the window and expect the 8-second quit cancel')
args = parser.parse_args()
if args.quit_timeout and os.name != 'nt':
    # ponytail: Windows only; Linux can use SIGSTOP and a window manager close.
    parser.error('--quit-timeout runs on Windows only')
ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'electron'
OUT = ROOT / '.artifacts'
OUT.mkdir(exist_ok=True)
WINDOWS = os.name == 'nt'
# Upstream Windows NetHack creates these at startup unless its sysconf redirects it.
REAL_FOLDERS = [Path(os.environ[name]) / 'NetHack' for name in ['USERPROFILE', 'LOCALAPPDATA']
                if WINDOWS and name in os.environ] + ([Path('C:/ProgramData/NetHack')] if WINDOWS else [])
already_present = {folder for folder in REAL_FOLDERS if folder.exists()}
# On Linux the host sets HOME to the mode folder, so the player's own files stay untouched.
REAL_FILES = [] if WINDOWS else [Path.home() / 'nethack', Path.home() / '.nethackrc']


def fingerprint(path):
    if not path.exists():
        return None
    if path.is_dir():
        return sorted((str(item.relative_to(path)), item.stat().st_mtime_ns) for item in path.rglob('*'))
    return path.stat().st_mtime_ns, path.read_bytes()


real_before = {path: fingerprint(path) for path in REAL_FILES}


def check_quit_timeout(process, log_path):
    """Close the window while the engine cannot answer, as Alt+F4 does."""
    import ctypes
    import re
    import time
    from ctypes import wintypes
    kernel, user, ntdll = ctypes.windll.kernel32, ctypes.windll.user32, ctypes.windll.ntdll
    log = lambda: log_path.read_text(errors='replace')
    deadline = time.time() + 30
    while not (found := re.search(r'Atlas engine pid (\d+)', log())):
        assert time.time() < deadline and process.poll() is None, 'No engine started'
        time.sleep(0.2)
    time.sleep(2)
    engine = kernel.OpenProcess(0x0800 | 0x1000, False, int(found[1]))  # suspend/resume, query
    try:
        ntdll.NtSuspendProcess(engine)
        windows = []
        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(
            lambda hwnd, _: windows.append(hwnd) or True)
        user.EnumWindows(callback, 0)
        owner = wintypes.DWORD()
        for hwnd in windows:
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == process.pid and user.IsWindowVisible(hwnd):
                user.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        time.sleep(9.5)
        assert process.poll() is None, 'The app closed although the engine never saved'
        assert 'Atlas error: Finish the current game prompt' in log(), 'No quit-cancel message'
        # The queued save still runs once the engine resumes; the canceled quit stays canceled.
        ntdll.NtResumeProcess(engine)
        time.sleep(3)
        assert process.poll() is None, 'The late save closed the app after the quit was canceled'
    finally:
        ntdll.NtResumeProcess(engine)
        kernel.CloseHandle(engine)
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)], capture_output=True)

def mode_folder(mode):
    return run / 'game' / {'standard': '', 'beginner': 'Beginner', 'explore': 'Explore', 'pauper': 'Pauper'}[mode]


def seed_save(directory, mode, name):
    """Play and save a real game in a mode folder, as an earlier session would."""
    seed = engine_test.Game(str(directory), role='Wizard', name=name, mode=mode)
    seed.start()
    seed.finish(automatic=True)


subprocess.run(['npm', 'run', 'build'], cwd=HOST, check=True, shell=WINDOWS)
run = Path(tempfile.mkdtemp(prefix='electron-', dir=OUT))
report = run / 'diagnostics.jsonl'
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)
# The other modes hold same-name saves that must survive untouched. Their
# Explore folder is the only one that authorizes Explore (ADR 0001).
protected_files = {}
engine_copy = 'nethack.exe' if WINDOWS else 'nhdat'
for protected_mode in [mode for mode in ['standard', 'beginner', 'explore', 'pauper'] if mode != args.mode]:
    directory = mode_folder(protected_mode)
    directory.mkdir(parents=True, exist_ok=True)
    engine_test.prepare_runtime(directory)
    if protected_mode == 'explore':
        config = directory / 'sysconf'
        config.write_text(config.read_text().rstrip('\n') + '\nEXPLORERS=*\n')
    seed_save(directory, protected_mode, 'AtlasSmoke')
    for file in engine_test.saved_games(directory) + [directory / n for n in ['record', 'logfile', 'xlogfile', 'sysconf', engine_copy]]:
        protected_files[file] = hashlib.sha256(file.read_bytes()).hexdigest()
# The tested mode folder holds an earlier save and an outdated engine copy (ADR 0002).
tested = mode_folder(args.mode)
tested.mkdir(parents=True, exist_ok=True)
engine_test.prepare_runtime(tested)
seed_save(tested, args.mode, 'AtlasKeep')
kept_save = engine_test.saved_games(tested)[0]
kept_digest = hashlib.sha256(kept_save.read_bytes()).hexdigest()
with (tested / engine_copy).open('ab') as stale:
    stale.write(b'outdated')
env = {key: value for key, value in os.environ.items() if not key.startswith('ATLAS_')}
env.update(ATLAS_TEST_GENDER=args.gender, ATLAS_TEST_MODE=args.mode, ATLAS_TEST_NUMBER_PAD='0',
           ATLAS_DATA_DIR=str(run / 'game'),
           ATLAS_DIAGNOSTICS=str(report), ATLAS_SNAPSHOT=str(run / 'game.png'))
electron = HOST / 'node_modules/electron/dist' / ('electron.exe' if WINDOWS else 'electron')
with (run / 'application.log').open('w') as log:
    process = subprocess.Popen([str(electron), str(HOST), '--self-test'], env=env, stdout=log, stderr=log)
    if args.quit_timeout:
        check_quit_timeout(process, run / 'application.log')
        print('PASS: a close with a frozen engine was canceled after 8 seconds and the app stayed open.')
        raise SystemExit(f'Evidence: {run}')
    try:
        code = process.wait(timeout=120)
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
            'restore', 'complete', 'save-picker', 'experience-status',
            'yn-default-focus', 'yn-default-enter', 'yn-focused-enter'}
screenshots = ['game.png', 'context.png', 'actions.png', 'direction.png']
if args.mode != 'pauper':
    required |= {'read-selection', 'read-cancel'}
    screenshots.append('read.png')
if args.mode == 'beginner':
    required |= {'beginner-creation', 'beginner-help', 'beginner-chest', 'beginner-chest-visible',
                 'beginner-loot-action', 'beginner-chest-contents'}
    screenshots += ['beginner-creation.png', 'beginner-help.png', 'beginner-chest.png']
if args.mode == 'explore':
    required |= {'explore-creation', 'explore-help', 'explore-inventory', 'explore-restore-choice'}
    screenshots += ['explore-creation.png', 'explore-help.png']
if args.mode == 'pauper':
    required |= {'pauper-creation', 'pauper-help', 'pauper-inventory'}
    screenshots += ['pauper-creation.png', 'pauper-help.png']
assert required <= phases, f'Missing phases: {required - phases}'
for name in screenshots:
    assert (run / name).is_file(), f'Missing screenshot: {name}'
saves = [save for save in engine_test.saved_games(tested) if 'AtlasSmoke' in save.name]
assert saves, 'Final quit did not save the restored game'
assert (tested / engine_copy).read_bytes() == (engine_test.RUNTIME / engine_copy).read_bytes(), \
    'The outdated engine copy was not replaced'
assert hashlib.sha256(kept_save.read_bytes()).hexdigest() == kept_digest, 'The engine refresh changed a save'
assert bool(re.search(r'^\s*EXPLORERS\s*=', (tested / 'sysconf').read_text(), re.M)) == (args.mode == 'explore'), \
    'Explore is authorized outside the Explore mode folder'
for file, digest in protected_files.items():
    assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, f'Other-mode data changed: {file}'
for folder in REAL_FOLDERS:
    assert folder in already_present or not folder.exists(), f'The test created a real NetHack folder: {folder}'
for path in REAL_FILES:
    assert fingerprint(path) == real_before[path], f'The test changed the player\'s real {path}'
print(f'PASS: Electron host {args.mode} start, map, inventory, inspection, save, restore and quit; '
      'engine copy refreshed and other modes untouched.')
print(f'Evidence and screenshot: {run}')
