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
    if args.quit_timeout:
        check_quit_timeout(process, run / 'application.log')
        print('PASS: a close with a frozen engine was canceled after 8 seconds and the app stayed open.')
        raise SystemExit(f'Evidence: {run}')
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
saves = (run / 'game').glob('*.NetHack-saved-game' if WINDOWS else f'save/{os.getuid()}*')
assert any(saves), 'Final quit did not save the restored game'
for folder in REAL_FOLDERS:
    assert folder in already_present or not folder.exists(), f'The test created a real NetHack folder: {folder}'
for path in REAL_FILES:
    assert fingerprint(path) == real_before[path], f'The test changed the player\'s real {path}'
print('PASS: Electron host start, map, inventory, inspection, save, restore and quit.')
print(f'Evidence and screenshot: {run}')
