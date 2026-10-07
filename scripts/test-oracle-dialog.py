#!/usr/bin/env python3
"""Native Oracle dialogs using disposable copies of a prepared adjacent save.

The fixture is a wizard save at (41,10), northeast of the peaceful Oracle at
(40,11), carrying enough gold for both consultations. --game is copied before
launch, so the supplied save is never opened or changed by the native test.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--tileset', default='lantern-modern')
    args = parser.parse_args()
    assert (args.game / 'save').is_dir(), args.game
    run = Path(tempfile.mkdtemp(prefix='oracle-dialog-native-', dir=ROOT / '.artifacts'))
    shutil.copytree(args.game, run / 'game')
    report = run / 'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(run / 'game'),
               ATLAS_TEST_TILESET=args.tileset, ATLAS_TEST_SCENARIO='oracle-dialog',
               ATLAS_DIAGNOSTICS=str(report), ATLAS_SNAPSHOT=str(run / 'game.png'))
    with (run / 'application.log').open('w') as log:
        process = subprocess.Popen(
            [str(ROOT / 'dist/Atlas.app/Contents/MacOS/NetHackAtlas'), '--self-test'],
            env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
            raise AssertionError(f'Oracle native test timed out: {run}')
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert events and all(e.get('ok') is True for e in events), (events, run)
    required = {'oracle-direction', 'oracle-minor-prompt', 'oracle-major-prompt',
                'oracle-reading', 'complete'} | {f'oracle-result-{i}' for i in range(4)}
    assert required <= {e['phase'] for e in events}, (events, run)
    trace = [json.loads(line) for line in Path(str(report) + '.engine.jsonl').read_text().splitlines()]
    gold = [int(e['value'].split(':')[-1]) for e in trace
            if e.get('type') == 'status' and e.get('name') == 'gold']
    assert gold and gold[0] - gold[-1] == 2050, (gold, run)  # Level 30: 50 + 2000.
    assert any(e.get('kind') == 'text' and 'The Oracle meditates' in ' '.join(e.get('lines', []))
               for e in trace), run
    for name in ('oracle-minor.png', 'oracle-major.png', 'oracle-reading.png'):
        assert (run / name).is_file(), (name, run)
    print(f'PASS Oracle native dialogs, cancellation, payment and return to map: {args.tileset}\n{run}')


if __name__ == '__main__':
    main()
