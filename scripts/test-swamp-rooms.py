#!/usr/bin/env python3
"""Review real mkswamp rooms in isolated wizard-generated dungeon levels.

SHOPTYPE='}' selects upstream mkswamp through mkshop. Room geometry, lighting,
doors, occupants and pool eligibility remain upstream-generated. Native capture
is sequenced separately by the review coordinator.
"""
import argparse
import collections
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
tour = shapes.tour
INDEX = ROOT/'.artifacts/swamp-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/swamp-rooms-engine.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'


def open_game(directory):
    os.environ.update(NETHACKDIR=str(directory), HACKDIR=str(directory),
                      ATLAS_PLAY_MODE='standard', SHOPTYPE='}')
    config = directory/'swamp-test.nethackrc'
    config.write_text('')
    game = tour.load_game_module().Game(directory, name='wizard', options=OPTIONS, config=config,
                                        fixture_environment={'SHOPTYPE': '}'})
    tour.settle(game)
    return game


def stop(game, path):
    path.write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait()


def oracle(game, directory):
    """Read-only terrain diagnostics, used only in a discarded test copy."""
    start = len(game.events)
    tour.lua(game, directory, '''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 nh.pline("SWAMP_ORACLE:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..m.roomno..","..tostring(m.edge)..","..tostring(m.has_trap));
end end;''')
    cells = {}
    for e in game.events[start:]:
        if not e.get('text', '').startswith('SWAMP_ORACLE:'):
            continue
        x,y,typ,lit,room,edge,trap = e['text'].split(':', 1)[1].split(',')
        cells[int(x),int(y)] = dict(type=typ, lit=lit=='true', room=int(room),
                                     edge=edge=='true', trap=trap=='true')
    assert len(cells) == 79*21, len(cells)
    return cells


def audit_copy(source):
    run = Path(tempfile.mkdtemp(prefix='swamp-oracle-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(source/'game', directory)
    game = open_game(directory)
    try:
        return oracle(game, directory)
    finally:
        stop(game, run/'oracle.jsonl')


def teleport_to(game, p):
    event = tour.named(game, 'teleport')
    if event['kind']=='menu' and event.get('how')==0:
        game.send('key 32')
        event = game.wait_input()
    assert event.get('targeting'), event
    game.send(f'position {p[0]} {p[1]}')
    tour.settle(game)
    assert game.cursor == p, (p, game.cursor)


def prepare():
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    rows = []
    for variant, depths, desired_lit in [('lit', [1,2,3,4], True),
                                       ('unlit', [16,17,18,19], False),
                                       ('second-layout', [10,11,12,13], None)]:
        case = dict(id='swamp-rooms-'+variant, group='Swamp rooms',
                    label='Swamp / '+variant, target=None, source=None,
                    branch='The Dungeons of Doom')
        selected = None
        # SHOPTYPE chooses the original C generator, including all its failed
        # room selections. Bounded retries never rewrite pool/monster placement.
        for attempt in range(3):
            run = Path(tempfile.mkdtemp(prefix='swamp-rooms-'+variant+'-', dir=ROOT/'.artifacts'))
            os.environ['SHOPTYPE'] = '}'
            metadata = tour.prepare(case, 'inspection', run, fixture_environment={'SHOPTYPE': '}'})
            for depth in depths:
                game = open_game(run/'game')
                try:
                    if depth != 1:
                        event = tour.named(game, 'wizlevelport')
                        assert event['kind']=='line', event
                        game.send('line '+str(depth))
                        tour.settle(game)
                        tour.settle(game, tour.named(game, 'wizmap'))
                    metadata['identity'] = tour.identity(game, run/'game')
                    game.finish(automatic=True)
                finally:
                    stop(game, run/'generation.jsonl')
                cells = audit_copy(run)
                rooms = collections.defaultdict(list)
                for p,c in cells.items():
                    if c['room'] >= 3 and not c['edge']:
                        rooms[c['room']].append((p,c))
                candidates = []
                for room, entries in rooms.items():
                    pools = [p for p,c in entries if c['type']=='pool']
                    floors = [p for p,c in entries if c['type']=='room' and not c['trap']]
                    if len(pools)<5 or len(floors)<4 or not all((x+y)%2 for x,y in pools):
                        continue
                    if desired_lit is not None and not all(c['lit']==desired_lit for _,c in entries):
                        continue
                    candidates.append((len(pools), room, entries, floors))
                if candidates:
                    _, room, entries, floors = max(candidates, key=lambda c:c[0])
                    selected = run, metadata, room, entries, floors, cells
                    break
            if selected:
                break
        assert selected, ('No eligible upstream swamp room', variant)
        run, metadata, room, entries, floors, cells = selected
        game = open_game(run/'game')
        try:
            # Center the native review on known, unoccupied, trap-free land.
            # Original occupants remain active and may attack from nearby water.
            target = next((p for p in floors if game.cells.get(p,{}).get('char')=='.'), None)
            assert target, ('No displayed safe arrival land', run)
            teleport_to(game, target)
            event = tour.named(game, 'wizintrinsic')
            detection = next(i for i in event['items'] if i['text'].strip().lower()=='monster detection')
            game.send('menu '+str(detection['id'])+':1000000')
            tour.settle(game)
            xs = [p[0] for p,c in entries]
            ys = [p[1] for p,c in entries]
            bounds = [min(xs)-1, min(ys)-1, max(xs)-min(xs)+3, max(ys)-min(ys)+3]
            displayed = [dict(c) for c in game.cells.values()]
            metadata.update(shapeBounds=bounds, arrival=game.cursor, status=game.status,
                            displayedCells=displayed, roomNumber=room,
                            terrainCounts=dict(collections.Counter(c['type'] for _,c in entries)),
                            lighting=sorted({c['lit'] for _,c in entries}),
                            testTerrainTiles=sorted({c['tile'] for c in displayed
                                if bounds[0]<=c['x']<bounds[0]+bounds[2]
                                and bounds[1]<=c['y']<bounds[1]+bounds[3]
                                and c.get('tile') in (1291,1292,1314)}))
            metadata['sources'] = {name:tour.digest(ROOT/'vendor/NetHack-5.0.0'/name)
                                   for name in ('src/mklev.c','src/mkroom.c','src/sp_lev.c')}
            metadata['swampRecipe'] = tour.digest(Path(__file__))
            metadata['setup'].append('Upstream wizard SHOPTYPE=}: natural dungeon geometry and mkswamp C generator, with original randomized pool eligibility, door margins and aquatic/fungal occupants. No hand-authored swamp map. Pool diagnostics run in discarded copies. Inspection arrival moved by ordinary wizard teleport onto already mapped plain land.')
            metadata['setup'].append('Timed upstream monster detection (1,000,000 turns) reveals original underwater occupants for inspection; ordinary visibility and darkness otherwise remain engine-owned.')
            game.finish(automatic=True)
        finally:
            stop(game, run/'inspection.jsonl')
        (run/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        rows.append(dict(run=str(run), metadata=metadata))
        INDEX.write_text(json.dumps(rows, indent=2)+'\n')
        print('PREPARED', case['label'], metadata['identity'], metadata['terrainCounts'], flush=True)
    return rows


def check(data):
    run = Path(tempfile.mkdtemp(prefix='swamp-check-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    game = open_game(directory)
    result = dict(case=data['metadata']['case']['id'], run=str(run))
    try:
        assert game.cursor == tuple(data['metadata']['arrival'])
        initial = {p:dict(c) for p,c in game.cells.items()}
        terrain = oracle(game, directory)
        room = data['metadata']['roomNumber']
        pools = {p for p,c in terrain.items() if c['room']==room and c['type']=='pool'}
        assert len(pools)>=5 and all((x+y)%2 for x,y in pools)
        assert all(not terrain[p]['trap'] for p in pools)
        # Rendering may supply water ground only when perceived or remembered.
        known_pool = [p for p in pools if initial.get(p,{}).get('tile')==1314]
        assert known_pool, 'No mapped water visible in selected room'
        under_occupants = [dict(position=list(p), cell=c) for p,c in initial.items()
                           if p in pools and c.get('tile')!=1314 and c.get('groundTile')==1314]
        assert under_occupants, ('No known pool under a perceived occupant', run)
        before = game.turn
        inspect_positions = [known_pool[0], tuple(under_occupants[0]['position'])]
        result['inspections'] = [dict(position=p, text=game.inspect(*p)) for p in inspect_positions]
        unknown = next((p for p,c in initial.items() if c.get('tile')==1469), None)
        if unknown:
            assert 'unexplored' in game.inspect(*unknown).lower()
            c=initial[unknown]
            assert c.get('groundTile',-1)<0 and not c.get('material'), c
        assert game.turn == before
        boundary = [(p,q) for p in pools for q in [(p[0]-1,p[1]),(p[0]+1,p[1]),
                                                   (p[0],p[1]-1),(p[0],p[1]+1)]
                    if terrain.get(q,{}).get('room')==room and terrain[q]['type']=='room']
        assert boundary
        safe = {p for p,c in terrain.items() if c['room']==room and c['type']=='room'
                and not c['trap'] and initial.get(p,{}).get('char')=='.'}
        choices = []
        # Detected nearby occupants remain active. Prefer an open pair with
        # space around it; if a creature holds the hero, retain that evidence
        # and try another original pair rather than deleting the creature.
        occupants = [p for p,c in initial.items() if c.get('char',' ').strip()
                     and c.get('tile',9999)<500 and p!=game.cursor]
        for p in safe:
            for dx,dy,key in [(-1,-1,'y'),(1,-1,'u'),(-1,1,'b'),(1,1,'n'),
                              (-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j')]:
                q=p[0]+dx,p[1]+dy
                if q in safe:
                    clearance=min((max(abs(t[0]-o[0]),abs(t[1]-o[1]))
                                   for t in (p,q) for o in occupants),default=99)
                    choices.append((clearance,p,q,key))
        assert choices, ('No legal plain land movement pair', run)
        attempts=[]
        for _,p,q,key in sorted(choices,reverse=True)[:8]:
            teleport_to(game,p)
            if game.cells.get(q,{}).get('char')!='.':
                continue
            turn=game.turn
            start=len(game.events)
            tour.settle(game,game.command(key))
            attempts.append(dict(start=p,destination=q,key=key,actual=game.cursor,
                                 messages=[e['text'] for e in game.events[start:]
                                           if e['type']=='message']))
            if game.cursor==q:
                assert game.turn>=turn
                break
        else:
            raise AssertionError(('Active occupants prevented bounded dry-ground movement',attempts,run))
        position,turn=game.cursor,game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game=open_game(directory)
        assert (game.cursor,game.turn)==(position,turn)
        restored=oracle(game,directory)
        assert {p for p,c in restored.items() if c['room']==room and c['type']=='pool'}==pools
        game.finish(automatic=True)
        result.update(poolCount=len(pools), boundaryCount=len(boundary), knownWaterUnderOccupants=under_occupants,
                      unknownChecked=unknown, turnFreeInspection=True,
                      dryLandMovement=dict(start=p,destination=q,key=key),movementAttempts=attempts,
                      restored=True, poolsPreservedOnRestore=True,
                      hazards='Swimming, drowning, water walking and levitation were not exercised.')
        print('PASS', data['metadata']['case']['label'], len(pools), 'pools', flush=True)
        return result
    finally:
        stop(game,run/'latest-engine.jsonl')


def check_unexplored():
    run=Path(tempfile.mkdtemp(prefix='swamp-unexplored-',dir=ROOT/'.artifacts'))
    os.environ['SHOPTYPE']='}'
    case=dict(id='swamp-unexplored',group='Swamp rooms',label='Unrevealed swamp level',
              target=None,source=None,branch='The Dungeons of Doom')
    metadata=tour.prepare(case,'exploration',run,fixture_environment={'SHOPTYPE': '}'})
    game=open_game(run/'game')
    try:
        hidden=[c for c in game.cells.values() if c.get('tile')==1469]
        assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
        turn=game.turn
        descriptions=[game.inspect(c['x'],c['y']) for c in hidden[::max(1,len(hidden)//8)]]
        assert game.turn==turn and all('unexplored' in s.lower() for s in descriptions)
        terrain=oracle(game,run/'game')
        pools=[p for p,c in terrain.items() if c['type']=='pool']
        assert pools, 'Unrevealed test world did not generate actual swamp water'
        game.finish(automatic=True)
        print('PASS ordinary unrevealed swamp visibility',flush=True)
        return dict(case=case['id'],run=str(run),unknownCells=len(hidden),poolCount=len(pools),
                    descriptions=descriptions,turnFreeInspection=True,noHiddenGround=True,
                    noHiddenMaterial=True,engine=metadata['engine'],app=metadata['app'])
    finally:
        stop(game,run/'engine.jsonl')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    args=parser.parse_args()
    rows=prepare() if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results=[]
        for row in rows:
            results.append(check(row))
            RESULTS.write_text(json.dumps(results,indent=2)+'\n')
        results.append(check_unexplored())
        RESULTS.write_text(json.dumps(results,indent=2)+'\n')
    print('Index:',INDEX)


if __name__=='__main__':
    main()
