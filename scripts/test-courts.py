#!/usr/bin/env python3
"""Real throne interaction, occupied features and save/restore in isolated data."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


terrain = module('terrain', ROOT/'scripts/test-lantern-gameplay.py')
tour = module('tour', ROOT/'scripts/playtest/prepare.py')


def inspect(game, position):
    before = game.turn
    game.inspect(*position)
    assert game.turn == before
    return next(e for e in reversed(game.events) if e['type'] == 'inspect')


def native(run, tileset):
    report = run/'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(run/'native-game'), ATLAS_TEST_TILESET=tileset,
               ATLAS_TEST_SCENARIO='court-inspection', ATLAS_DIAGNOSTICS=str(report),
               ATLAS_SNAPSHOT=str(run/'game.png'))
    with (run/'application.log').open('w') as log:
        process = subprocess.Popen([str(ROOT/'dist/Atlas.app/Contents/MacOS/NetHackAtlas'),
                                    '--self-test'], env=env, stdout=log, stderr=log)
        try:
            code = process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.terminate(); process.wait(timeout=5)
            raise AssertionError(('Native court inspection timed out', run))
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert all(e.get('ok') is True for e in events), events
    assert {'court-beneath', 'court-clear', 'complete'} <= {e['phase'] for e in events}
    trace = [json.loads(line) for line in Path(str(report)+'.engine.jsonl').read_text().splitlines()]
    assert any(e.get('type') == 'inspect' and e.get('beneath', {}).get('name') == 'Throne' for e in trace)
    assert (run/'court-beneath.png').is_file()
    print('PASS native known-throne detail and clearing on another square:', tileset, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--tileset', default='lantern-modern')
    args = parser.parse_args()
    run = Path(tempfile.mkdtemp(prefix='court-acceptance-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = terrain.context.Fixture(str(directory))
    game = fixture.game
    try:
        # Fixed arrival and stationary peaceful occupant isolate feature perception.
        # The ordinary launcher court retains its normal active encounters.
        source = ('des.reset_level();\n' + terrain.level(arrival=(2, 2)) +
                  'des.feature("throne",2,4); des.feature("throne",3,4);\n'
                  'des.feature("throne",60,16); des.monster({id="floating eye",x=60,y=16,peaceful=true,paralyzed=127});\n'
                  'des.finalize_level();\n')
        tour.lua(game, directory, source)
        empty, occupied = (12, 7), (13, 7)
        assert game.cells[empty]['tile'] == 1311, game.cells[empty]
        assert game.cells[occupied]['char'] == 'e', game.cells[occupied]
        assert game.cells[occupied]['groundTile'] == 1291, game.cells[occupied]
        assert 'sit' not in fixture.hints(), 'A nearby throne must not offer underfoot sitting'
        before = game.turn
        assert 'throne' in game.inspect(*empty).lower()
        assert inspect(game, occupied).get('beneath') == {'name':'Throne','remembered':False}
        assert 'beneath' not in inspect(game, empty)
        assert 'beneath' not in inspect(game, (70,19))
        assert game.turn == before
        fixture.walk(empty)
        fixture.hints(expected=['sit'])
        assert game.cells[empty]['char'] == '@'
        start = len(game.events)
        event = tour.named(game, 'look')
        tour.settle(game, event)
        assert any('throne' in e.get('text', '').lower() for e in game.events[start:]), game.events[start:]
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        first_events = game.events.copy()
        shutil.copytree(directory, run/'native-game')
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        assert (game.cursor, game.turn) == (position, turn)
        fixture.hints(expected=['sit'])
        assert inspect(game, empty).get('beneath') == {'name':'Throne','remembered':False}
        ground = module('ground', ROOT/'scripts/test-ground.py')
        ground.intrinsic(game, 'monster detection')
        assert 'beneath' not in inspect(game, (70,19)), 'Sensing a monster cannot reveal its hidden throne'
        event = tour.named(game, 'wizintrinsic')
        row = next(i for i in event['items'] if i['text'].strip() == 'blinded')
        game.send('menu '+str(row['id'])+':1')
        tour.settle(game)
        assert inspect(game, occupied).get('beneath') == {'name':'Throne','remembered':True}
        ground.lua(fixture, 'local ox,oy=nh.abscoord(0,0); local x,y=13-ox,7-oy; '
                   'assert(nh.getmap(x,y).typ_name == "throne"); des.terrain(x,y,"."); '
                   'assert(nh.getmap(x,y).mapchr == ".");')
        assert inspect(game, occupied).get('beneath') == {'name':'Throne','remembered':True}, 'Unseen changes must not replace memory'
        tour.settle(game, game.command('.'))
        tour.settle(game, tour.named(game, 'redraw'))
        result = inspect(game, occupied)
        assert 'beneath' not in result, (result, game.status, game.events[-18:])
        print('PASS known/hidden/remembered throne inspection and exact restore', flush=True)
        # Ordinary sitting retains all upstream outcomes. Raise HP only to keep
        # a random throne shock from ending the low-level test character.
        event = tour.named(game, 'levelchange')
        assert event['kind'] == 'line'
        game.send('line 30')
        tour.settle(game)
        before, start = game.turn, len(game.events)
        event = tour.named(game, 'sit')
        if event.get('kind') == 'line' and event.get('prompt', '').startswith('Throne sit effect'):
            game.send('line 4')  # Upstream wizard choice: restore health.
            event = game.wait_input()
        tour.settle(game, event)
        assert game.turn > before
        assert any('sit on' in e.get('text', '').lower() and 'throne' in e.get('text', '').lower()
                   for e in game.events[start:]), game.events[start:]
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in first_events + game.events))
        if args.native:
            native(run, args.tileset)
        print('PASS ordinary Sit reaches the engine throne effect and consumes a turn:', run, flush=True)
    finally:
        fixture.close()


if __name__ == '__main__':
    main()
