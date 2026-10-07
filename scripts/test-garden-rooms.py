#!/usr/bin/env python3
"""Prepare real Garden fills and explicit woodland fixtures for item 26 review.

Garden contents and post-generation wall conversion are untouched upstream
functions. The woodland paths are declared test geometry, not a generated
campaign forest. All checkpoints and interaction checks use isolated data.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ice', ROOT/'scripts/test-ice-rooms.py')
ice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ice)
tour = ice.tour
INDEX = ROOT/'.artifacts/garden-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/garden-rooms-engine.json'
OPTIONS = ice.OPTIONS
FOREST_MAP = '''TTTTTTTTTTTTTTTT
T..............T
T..T..TTT...T..T
T..T..T.....T..T
T..T..T.TTT.T..T
T.....T.....T..T
TTTT..TTTT..T..T
T...........T..T
T..TTTT........T
TTTTTTTTTTTTTTTT'''


def prepare():
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    rows = []
    cases = [dict(id='fill-garden-'+variant, group='Gardens and trees',
                  label='Garden / '+variant, target=None, source=None,
                  branch='The Dungeons of Doom', fill='Garden', lit=True,
                  mixed=mixed)
             for variant, mixed in [('lit', False), ('mixed', True)]]
    cases += [dict(id='forest-paths-'+variant, group='Gardens and trees',
                   label='Woodland paths / '+('dark exploration' if not lit else variant), target=None, source=None,
                   branch='The Dungeons of Doom', forest=True, lit=lit)
              for variant, lit in [('lit', True), ('dark', False)]]
    for case in cases:
        run = Path(tempfile.mkdtemp(prefix='garden-rooms-', dir=ROOT/'.artifacts'))
        if case.get('forest'):
            # The ordinary source-loader handles placement, finalized terrain,
            # upstream visibility, and save creation. This source is ephemeral
            # fixture geometry; it is never packaged as a campaign generator.
            source = run/'woodland.lua'
            source.write_text('des.level_init({style="solidfill",fg=" "});\n'
                'des.level_flags("noflip");\n'
                'des.map({x=25,y=5,map=[['+FOREST_MAP+']]});\n'
                'des.region({region={0,0,15,9},lit='+str(int(case['lit']))+'});\n'
                'des.teleport_region({region={2,2,2,2}});\n'
                'des.stair("up",2,2); des.stair("down",14,8);\n'
                'des.feature("fountain",9,7);\n'
                'des.monster({id="wood nymph",x=10,y=1,asleep=true});\n')
            case['source'] = str(source)
        metadata = tour.prepare(case, 'inspection' if case['lit'] else 'exploration', run)
        if case.get('forest') and tuple(metadata['arrival']) != (27,7):
            # Upstream branch placement may displace the wizard loader's
            # arrival. Place the fixture hero through the ordinary wizard
            # teleport command, without revealing the dark map.
            game = tour.load_game_module().Game(run/'game', name='wizard', options=OPTIONS)
            try:
                tour.settle(game)
                event = tour.named(game, 'teleport')
                if event['kind'] == 'menu' and event.get('how') == 0:
                    game.send('key 32'); event = game.wait_input()
                assert event.get('targeting'), event
                game.send('position 27 7'); tour.settle(game)
                assert game.cursor == (27,7), game.cursor
                metadata['arrival'] = game.cursor
                metadata['status'] = game.status
                metadata['setup'].append('Upstream wizard teleport frames the declared fixture arrival after branch placement displaced it. No map reveal added.')
                game.finish(automatic=True)
                with (run/'preparation.jsonl').open('a') as log:
                    log.write(''.join(json.dumps(e)+'\n' for e in game.events))
            finally:
                if game.process.poll() is None:
                    game.process.kill(); game.process.wait()
        metadata['shapeBounds'] = [25,5,16,10]
        metadata['displayedCells'] = ice.displayed_cells(run/'preparation.jsonl')
        metadata['testTerrainTiles'] = sorted({c['tile'] for c in metadata['displayedCells']
                                               if c.get('tile') in [1290,1313]})
        metadata['gardenRecipe'] = tour.digest(Path(__file__))
        if case.get('forest'):
            metadata['setup'].append('Explicit woodland path fixture with interior natural trees, fountain and sleeping wood nymph. The dark variant has normal visibility and no wizard map reveal. Not a generated campaign forest.')
        else:
            metadata['setup'].append('Lit-only upstream Garden eligibility respected. Upstream post_level_generate converts room walls to trees; sleeping wood nymph and fountain randomness retained.')
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        rows.append(dict(run=str(run), metadata=metadata))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], run, flush=True)
    return rows


def oracle(game, directory):
    start = len(game.events)
    # A read-only diagnostic oracle never changes perceived player rendering.
    tour.lua(game, directory, '''local ox,oy=nh.abscoord(0,0);
for y=5,14 do for x=25,40 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("GARDEN_ORACLE:"..x..","..y..","..m.typ_name..","..tostring(m.lit));
end end;''')
    cells = [e['text'].split(':',1)[1].split(',') for e in game.events[start:]
             if e.get('text','').startswith('GARDEN_ORACLE:')]
    assert len(cells) == 160, len(cells)
    return cells


def cut_tree(game, directory, result):
    assert game.cursor == (27,7), game.cursor
    position, turn = game.cursor, game.turn
    assert game.cells[(28,7)]['tile'] == 1290, game.cells[(28,7)]
    tour.settle(game, game.command('l'))
    assert game.cursor == position, 'Walk passed through a real tree'
    result['treeCollision'] = dict(position=list(position), turnBefore=turn, turnAfter=game.turn)
    tour.lua(game, directory, 'u.giveobj(obj.new("blessed +5 axe"));')
    start = len(game.events)
    event = tour.named(game, 'apply')
    assert event['kind'] == 'menu', event
    axe = next(row for row in event['items'] if row.get('selectable') and 'axe' in row['text'])
    game.send('menu '+str(axe['id']))
    event = game.wait_input()
    # Wielding consumes the first action before the ordinary direction prompt.
    if event.get('command'):
        event = tour.named(game, 'apply')
        assert event['kind'] == 'menu', event
        axe = next(row for row in event['items'] if row.get('selectable') and 'axe' in row['text'])
        game.send('menu '+str(axe['id'])); event = game.wait_input()
    assert event.get('direction'), event
    game.send('key 108'); tour.settle(game)
    for _ in range(120):
        if game.cells.get((28,7),{}).get('tile') != 1290:
            break
        tour.settle(game, game.command('.'))
    else:
        raise AssertionError('Axe did not finish cutting the tree')
    assert any('cut down the tree' in e.get('text','') for e in game.events[start:]), game.events[start:]
    result['axeCutTree'] = True
    # Upstream cutting can leave fruit. Walk through the newly open square
    # and return, then follow the known unobstructed narrow path south.
    before = game.turn
    for key, target in [('l',(28,7)), ('h',(27,7)), ('j',(27,8)), ('j',(27,9))]:
        tour.settle(game, game.command(key))
        assert game.cursor == target, (key,target,game.cursor)
    # A fast Valkyrie can take consecutive movement actions in one displayed
    # turn. The route as a whole must advance time; every action moves legally.
    assert game.turn > before, 'The four-step route did not advance time'
    result['walkedOpenTreeSquareAndPath'] = True


def check(data):
    case = data['metadata']['case']
    run = Path(tempfile.mkdtemp(prefix='garden-rooms-check-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    config = directory/'test.nethackrc'
    config.write_text('')
    os.environ.update(NETHACKDIR=str(directory), HACKDIR=str(directory), ATLAS_PLAY_MODE='standard')
    game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS, config=config)
    result = dict(case=case['id'], run=str(run), isolatedConfiguration=True)
    events = []
    try:
        tour.settle(game)
        assert game.cursor == tuple(data['metadata']['arrival'])
        before = game.turn
        trees = [p for p,c in game.cells.items() if c.get('tile') == 1290]
        assert trees, 'No perceived trees'
        result['inspection'] = [dict(position=list(p), description=game.inspect(*p))
                                for p in [game.cursor, trees[0]]]
        assert 'tree' in result['inspection'][-1]['description'].lower()
        assert game.turn == before, 'Inspection consumed a turn'
        result['turnFreeInspection'] = True
        if case.get('forest') and not case['lit']:
            target = (37,12)
            assert game.cells.get(target,{}).get('tile',-1) < 0 or game.cells.get(target,{}).get('char',' ') == ' ', game.cells.get(target)
            text = game.inspect(*target)
            assert 'tree' not in text.lower(), text
            assert game.turn == before
            result['unknownTreeInspection'] = dict(position=list(target), description=text)
        cells = oracle(game, directory)
        if case.get('forest') and not case['lit']:
            assert next(c[2] for c in cells if (int(c[0]),int(c[1])) == (37,12)) == 'tree'
        result['terrainCounts'] = {kind:sum(c[2] == kind for c in cells)
                                  for kind in sorted({c[2] for c in cells})}
        assert result['terrainCounts'].get('tree',0) >= 48, result
        if not case.get('forest'):
            # Garden wall conversion yields the 48-cell rectangular perimeter.
            perimeter = [c for c in cells if int(c[0]) in [25,40] or int(c[1]) in [5,14]]
            assert all(c[2] == 'tree' for c in perimeter), perimeter
            result['upstreamGardenPerimeterVerified'] = True
        else:
            assert all(c[3] == str(case['lit']).lower() for c in cells), cells
            result['lightingVerified'] = True
            cut_tree(game, directory, result)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        events.extend(game.events)
        game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS, config=config)
        tour.settle(game)
        assert (game.cursor, game.turn) == (position,turn)
        if case.get('forest'):
            restored = oracle(game, directory)
            assert next(c[2] for c in restored if (int(c[0]),int(c[1])) == (28,7)) == 'room'
            result['cutTreePreservedOnRestore'] = True
        game.finish(automatic=True)
        result.update(restored=True, finalPosition=list(position), finalTurn=turn)
        print('PASS',case['label'], result['terrainCounts'],flush=True)
        return result
    finally:
        events.extend(game.events)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--engine', action='store_true')
    args = parser.parse_args()
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results = []
        for row in rows:
            results.append(check(row))
            RESULTS.write_text(json.dumps(results, indent=2)+'\n')
    print('Index:', INDEX)


if __name__ == '__main__':
    main()
