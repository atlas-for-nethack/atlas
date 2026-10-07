#!/usr/bin/env python3
"""Survey upstream dry room fills using disposable engine saves and native captures."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
tour = shapes.tour
INDEX = ROOT/'.artifacts/dry-themed-prepared.json'


def prepare():
    rows = []
    for case in tour.catalog():
        if not case.get('fill'):
            continue
        for mode in ('inspection', 'exploration'):
            row = json.loads(subprocess.check_output([sys.executable,
                str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case', case['id'],
                '--mode', mode], text=True))
            rows.append(row)
            INDEX.write_text(json.dumps(rows, indent=2)+'\n')
            print('PREPARED', case['label'], mode, flush=True)


def engine(data):
    run = Path(tempfile.mkdtemp(prefix='dry-themed-engine-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    os.environ.update(HOME=str(directory), NETHACKDIR=str(directory), HACKDIR=str(directory))
    game = tour.load_game_module().Game(directory, name='wizard',
        options='color,!news,!autopickup,time,force_invmenu,menustyle:full')
    case = data['metadata']['case']
    result = dict(case=case['id'], mode=data['metadata']['mode'], run=str(run))
    try:
        tour.settle(game)
        before = game.turn
        descriptions = {}
        for p,c in list(game.cells.items()):
            if 26 <= p[0] <= 39 and 6 <= p[1] <= 13 and c.get('char',' ') not in ' .@':
                descriptions[str(p)] = game.inspect(*p)
        assert game.turn == before, 'Inspection spent a turn'
        result['descriptions'] = descriptions
        # Independent engine oracle, used only inside this disposable test.
        # Never copied back into the launcher checkpoint or production UI.
        start = len(game.events)
        tour.lua(game, directory, '''
local ox,oy=nh.abscoord(0,0);
for y=6,13 do for x=26,39 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("FILL_LIGHT:"..x..","..y..","..tostring(m.lit));
 local t=m.has_trap and nh.gettrap(x-ox,y-oy) or nil;
 if t then nh.pline("FILL_TRAP:"..x..","..y..","..t.ttyp_name..","..tostring(t.tseen)); end;
 local o=obj.at(x-ox,y-oy);
 while o and not o:totable().NO_OBJ do
  local v=o:totable();
  nh.pline("FILL_OBJECT:"..x..","..y..","..v.otyp_name..","..v.lamplit);
  o=o:next(true);
 end;
end end;
''')
        messages = [e.get('text','') for e in game.events[start:]]
        lights = [s.split(':',1)[1].split(',') for s in messages if s.startswith('FILL_LIGHT:')]
        traps = [s.split(':',1)[1].split(',') for s in messages if s.startswith('FILL_TRAP:')]
        objects = [s.split(':',1)[1].split(',') for s in messages if s.startswith('FILL_OBJECT:')]
        assert len(lights)==112 and all(v[2]==str(case['lit']).lower() for v in lights), lights
        name = case['fill']
        expected = {'Massacre':'corpse', 'Statuary':'statue', 'Light source':'oil lamp'}
        if name in expected:
            assert any(o[2]==expected[name] for o in objects), (name, objects)
        if name == 'Light source':
            assert any(o[2]=='oil lamp' and o[3]=='1' for o in objects), objects
        if name in ('Spider nest','Trap room','Statuary'):
            assert traps, (name, 'No generated traps')
        if name == 'Spider nest':
            assert any(t[2]=='web' for t in traps), traps
        hidden = 0
        for x,y,kind,seen in traps:
            if seen != 'true':
                description = game.inspect(int(x),int(y)).lower()
                trap_label = kind if 'trap' in kind or kind in ('web', 'magic portal') else kind+' trap'
                assert trap_label not in description, ('Hidden trap leaked', kind, description)
                hidden += 1
        result.update(objects=objects, traps=traps, hiddenTrapChecks=hidden,
                      lightingVerified=True, turnFreeInspection=True)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game = tour.load_game_module().Game(directory, name='wizard',
            options='color,!news,!autopickup,time,force_invmenu,menustyle:full')
        tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        game.finish(automatic=True)
        result['restored'] = True
        print('PASS', case['label'], result['mode'], flush=True)
        return result
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    rows = json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(engine(row))
            (ROOT/'.artifacts/dry-themed-engine.json').write_text(json.dumps(results, indent=2)+'\n')
    if args.native:
        results = []
        for row in rows:
            if row['metadata']['mode'] != 'inspection':
                continue
            for tileset in ('lantern-modern','soot-and-brass'):
                result = shapes.native(row, tileset)
                results.append(result)
                (ROOT/'.artifacts/dry-themed-native.json').write_text(json.dumps(results, indent=2)+'\n')
                print('CAPTURED', result['label'], tileset, flush=True)
        print(shapes.gallery(results, ROOT/'.artifacts/dry-themed-review.html', 'Dry themed rooms'))


if __name__ == '__main__':
    main()
