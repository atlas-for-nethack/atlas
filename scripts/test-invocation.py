#!/usr/bin/env python3
"""Exercise the original vibrating square and invocation using real engine saves.

Setup uses disclosed upstream wizard travel, protection, positioning and wishes.
Discovery, candle attachment, Apply/Apply/Read and Sanctum stair travel are
ordinary commands. No map reveal, terrain/actor replacement or invocation flag
mutation is used. Read-only Lua diagnostics remain test evidence, never UI data.
"""
import argparse
from collections import deque
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('invocation_checks', ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'invocation-prepared.json'
RESULTS = ART/'invocation-engine-results.json'
STATES = ART/'invocation-states.json'
STEPS = [*checks.STEPS, (-1,-1,'y'), (1,-1,'u'), (-1,1,'b'), (1,1,'n')]


def source_evidence():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    paths = ('src/mkmaze.c', 'src/mklev.c', 'src/spell.c', 'src/apply.c',
             'src/trap.c', 'src/detect.c', 'dat/dungeon.lua', 'dat/sanctum.lua')
    hashes = {}
    with tarfile.open(archive) as upstream:
        for path in paths:
            member = next(m for m in upstream.getmembers() if m.name.endswith('/'+path))
            original = upstream.extractfile(member).read()
            assert (tour.DAT.parent/path).read_bytes() == original, path
            hashes[path] = tour.digest(tour.DAT.parent/path)
    return dict(unchangedPinnedSource=True, hashes=hashes,
                upstreamArchive=tour.digest(archive))


def files_hashes(directory):
    return {str(p.relative_to(directory)):tour.digest(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


def prepare():
    assert not INDEX.exists(), 'Preserve prior invocation evidence before preparing another source'
    run = Path(tempfile.mkdtemp(prefix='invocation-source-', dir=ART))
    case = next(c for c in tour.catalog() if c['id'] == 'invocation-approach')
    metadata = tour.prepare(case, 'exploration', run)
    assert metadata['case']['source'] is None
    assert metadata['identity']['branch'] == 'Gehennom'
    assert not any('map reveal' in s.lower() for s in metadata['setup'])
    metadata.update(sourceEvidence=source_evidence(), worldSelected=True,
        shapeBounds=[1,0,79,21], dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
        designPreviewOnly=False, invocationRecipeSHA256=tour.digest(Path(__file__)))
    metadata['setup'].append('Original world-selected invocation floor, selected as the actual floor above Sanctum. Exploration recipe: no wizard map reveal and no source-level reload. Original occupants and generated terrain retained.')
    checks.write(run/'metadata.json', metadata)
    row = dict(run=str(run), metadata=metadata,
               originalGameSHA256=files_hashes(run/'game'))
    checks.write(INDEX, row)
    print('PREPARED original invocation exploration source', run, flush=True)
    return row


def settle(game, event=None):
    event = event or game.wait_input()
    for _ in range(100):
        if event.get('command'): return event
        prompt = event.get('prompt', '')
        if event['kind'] == 'yn' and prompt == 'Override?': game.send('key 121')
        elif event['kind'] == 'yn' and ('die' in prompt.lower() or prompt == 'Do you want to keep the save file?'): game.send('key 110')
        elif event['kind'] == 'line' and prompt.lower().startswith('call '): game.send('key 27')
        elif event['kind'] == 'line' and 'wish' in prompt.lower(): game.send('line nothing')
        elif event.get('targeting'):
            assert any('Where do you want to be teleported?' in e.get('text','') for e in game.events[-30:]), event
            game.send(f'position {game.cursor[0]} {game.cursor[1]}')
        elif event['kind'] in ('key', 'text') or (event['kind'] == 'menu' and event.get('how') == 0): game.send('key 32')
        else: raise AssertionError(('Unexpected invocation prompt', event))
        event = game.wait_input()
    raise AssertionError('Invocation did not settle')


def lua(game, directory, source):
    (directory/'setup.lua').write_text(source)
    offset = len(game.events)
    event = tour.named(game, 'wizloadlua'); assert event['kind'] == 'line', event
    game.send('line setup.lua'); settle(game)
    errors = [e for e in game.events[offset:] if any(w in e.get('text','').lower()
        for w in ('lua error','impossible','error in','stack traceback'))]
    assert not errors, errors


def diagnostics(game, directory):
    """Read terrain, saved glyph memory, light, traps and stairs without turns."""
    before = game.turn; offset = len(game.events)
    lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 local flags={}; for k,v in pairs(m.flags) do flags[#flags+1]=k.."="..tostring(v); end; table.sort(flags);
 nh.pline("INV_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..tostring(m.waslit)..","..m.seenv..","..m.glyph..","..tostring(m.horizontal)..","..table.concat(flags,"|"));
 if m.has_trap then local t=nh.gettrap(x-ox,y-oy);
  nh.pline("INV_TRAP:"..x..","..y..","..t.ttyp_name..","..tostring(t.tseen));
 end;
end end;
for _,s in ipairs(nh.stairways()) do
 nh.pline("INV_STAIR:"..s.x..","..s.y..","..tostring(s.up)..","..tostring(s.ladder)..","..s.dnum..","..s.dlevel);
end;''')
    terrain = {}; traps = {}; stairs = []
    for e in game.events[offset:]:
        line = e.get('text','')
        if not line.startswith('INV_'): continue
        tag, rest = line.split(':',1); r = rest.split(','); p = tuple(map(int,r[:2]))
        if tag == 'INV_TERRAIN': terrain[p] = dict(type=r[2],lit=r[3]=='true',waslit=r[4]=='true',seenv=int(r[5]),glyph=int(r[6]),horizontal=r[7]=='true',flags=r[8])
        elif tag == 'INV_TRAP': traps[p] = dict(type=r[2],seen=r[3]=='true')
        elif tag == 'INV_STAIR': stairs.append(dict(position=list(p),up=r[2]=='true',ladder=r[3]=='true',dnum=int(r[4]),dlevel=int(r[5])))
    assert len(terrain) == 1659 and game.turn == before
    stairs.sort(key=lambda s:(s['position'],s['up'],s['ladder'],s['dnum'],s['dlevel']))
    return dict(terrain=terrain,traps=traps,stairs=stairs)


def serial(diagnostic):
    return dict(terrain=[dict(position=list(p),**d) for p,d in sorted(diagnostic['terrain'].items())],
                traps=[dict(position=list(p),**d) for p,d in sorted(diagnostic['traps'].items())],
                stairs=diagnostic['stairs'])


def perception(game):
    result = checks.material(game.cells.values(), None)
    assert result['hiddenCells'] > 0, 'Invocation exploration lost unknown space'
    return result


def wish(game, item):
    event = tour.named(game, 'wizwish'); assert event['kind'] == 'line', event
    game.send('line '+item); settle(game)


def protect(game,directory):
    event = tour.named(game, 'levelchange'); assert event['kind'] == 'line'
    game.send('line 30'); settle(game)
    event = tour.named(game, 'wizintrinsic'); assert event['kind'] == 'menu'
    wanted = ('invulnerable', 'stealthy', 'water walking', 'fire resistance',
              'magical breathing', 'hp regeneration', 'invisible')
    rows = [i for i in event['items'] if i['text'].strip().lower() in wanted]
    assert len(rows) == len(wanted), rows
    game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows)); settle(game)
    lua(game,directory,'nh.debug_flags({hunger=false});')
    for item in ('uncursed Bell of Opening (0:3)', 'uncursed Candelabrum of Invocation',
                 'uncursed Book of the Dead', '7 uncursed wax candles', 'blessed +50 long sword',
                 'uncursed scroll of scare monster'):
        wish(game,item)
    event = tour.named(game, 'wizidentify'); assert event['kind'] == 'menu'
    game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key') != '_')); settle(game)
    select_item(game,'w','+50 long sword')


def select_item(game, command, text, attachment=False):
    before = game.turn; offset = len(game.events)
    event = game.command(command); assert event['kind'] == 'menu', event
    rows = [i for i in event['items'] if i.get('selectable',True) and text.lower() in i['text'].lower()]
    assert len(rows) == 1, (text,event)
    game.send('menu '+str(rows[0]['id'])); event = game.wait_input()
    if attachment:
        assert event['kind'] == 'yn' and event['prompt'].startswith('Attach ') and 'candelabrum' in event['prompt'].lower(), event
        game.send('key 121'); event = game.wait_input()
    settle(game,event)
    return dict(command=command,selected=rows[0]['text'],turns=game.turn-before,
                messages=[e['text'] for e in game.events[offset:] if e['type']=='message'])


def place(game,target):
    event = tour.named(game, 'teleport')
    if event['kind'] == 'yn' and event.get('prompt') == 'Override?':
        game.send('key 121'); event = game.wait_input()
    if event['kind'] == 'menu' and event.get('how') == 0:
        game.send('key 32'); event = game.wait_input()
    assert event.get('targeting'), event
    game.send(f'position {target[0]} {target[1]}'); settle(game)
    assert game.cursor == target, (target,game.cursor)


def step(game,target):
    origin=game.cursor; before = game.turn; offset = len(game.events); commands=[]
    for attempt in range(80):
        dx,dy = target[0]-game.cursor[0],target[1]-game.cursor[1]
        if abs(dx)+abs(dy)>1:
            # Powerful original monsters can knock the protected hero backward.
            # Follow known floor from the actual landing square; repeating an
            # old key here would walk away from the intended feature.
            queue=deque([game.cursor]); previous={game.cursor:None}
            while queue and target not in previous:
                p=queue.popleft()
                for sx,sy,k in checks.STEPS:
                    q=p[0]+sx,p[1]+sy; cell=game.cells.get(q,{})
                    ground=cell.get('groundTile',cell.get('tile'))
                    if q not in previous and (q==target or ground in (*range(1291,1297),1297,1298,*range(1324,1348))):
                        previous[q]=p;queue.append(q)
            assert target in previous, ('Knockback has no known-floor route back',game.cursor,target)
            p=target
            while previous[p]!=game.cursor: p=previous[p]
            dx,dy=p[0]-game.cursor[0],p[1]-game.cursor[1]
        key = next(k for x,y,k in STEPS if (x,y)==(dx,dy));commands.append(key)
        event = game.command(key)
        if event['kind'] == 'yn' and event.get('prompt','').startswith('Really step '):
            game.send('key 121'); event = game.wait_input()
        settle(game,event)
        if game.cursor == target: break
    else: raise AssertionError(('Ordinary discovery approach blocked',target,game.cursor))
    return dict(command=commands[0],commands=commands,origin=list(origin),destination=list(target),
                turns=game.turn-before,attempts=attempt+1,
                messages=[e['text'] for e in game.events[offset:] if e['type']=='message'])


def repel_attackers(game,square):
    """Ordinary forced sword attacks against displayed adjacent attackers.

    Some original humans or unique forms ignore scare scrolls. They can still
    interrupt Book reading through wizard invulnerability. No monster is
    deleted or replaced by setup; ordinary combat resolves any such blockers.
    """
    before=game.turn;offset=len(game.events);attacks=[]
    for _ in range(80):
        if game.cursor!=square: step(game,square)
        nearby=[(p,c) for p,c in game.cells.items() if p!=game.cursor
                and max(abs(p[i]-game.cursor[i]) for i in (0,1))<=1
                and 0<=c.get('glyph',-1)<800 and c.get('char','').strip()]
        if not nearby: break
        p,c=nearby[0]
        dx,dy=p[0]-game.cursor[0],p[1]-game.cursor[1]
        key=next(k for x,y,k in STEPS if (x,y)==(dx,dy))
        event=game.command('F');assert event.get('command'),event
        event=game.command(key)
        if event['kind']=='yn' and event.get('prompt','').startswith('Really attack '):
            game.send('key 121');event=game.wait_input()
        settle(game,event);attacks.append(dict(position=list(p),cell=copy.deepcopy(c),command='F'+key))
    else: raise AssertionError('Original adjacent attackers did not leave or fall to ordinary sword combat')
    return dict(commands=attacks,turns=game.turn-before,
        messages=[e['text'] for e in game.events[offset:] if e['type']=='message'])


def snapshot(row,game,directory,label):
    """Keep a native-review save, then prove exact restoration on the working copy."""
    run = Path(tempfile.mkdtemp(prefix='invocation-state-'+label+'-', dir=ART))
    identity = tour.identity(game,directory); position = game.cursor; turn = game.turn
    memory = diagnostics(game,directory); cells = copy.deepcopy(list(game.cells.values()))
    perceived = perception(game)
    game.finish(automatic=True)
    (run/'before-restore.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
    shutil.copytree(directory,run/'game')
    game = checks.open_game(directory); settle(game)
    assert (game.cursor,game.turn) == (position,turn), (position,turn,game.cursor,game.turn)
    assert tour.identity(game,directory) == identity
    restored_memory=diagnostics(game,directory)
    checks.write(run/'terrain-memory.json',serial(memory))
    checks.write(run/'terrain-memory-restored.json',serial(restored_memory))
    assert restored_memory == memory, 'Terrain, known glyph, lighting or trap memory changed on restore'
    before = {(c['x'],c['y']):c for c in cells}
    for p,c in game.cells.items():
        assert all(c.get(f)==before[p].get(f) for f in ('tile','glyph','char','color','pet','groundTile','material')), (p,before[p],c)
    assert set(game.cells) == set(before)
    metadata = copy.deepcopy(row['metadata'])
    metadata.update(case={**metadata['case'],'id':label,'label':label.replace('-',' ').title()},
        identity=identity,arrival=list(position),mode='exploration',checkpoint=str(run),
        displayedCells=copy.deepcopy(list(game.cells.values())),perception=perceived,
        engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
        nativeBounds=[max(1,min(60,position[0]-9)),max(0,min(8,position[1]-6)),20,13],
        exactTerrainLightingGlyphTrapRestore=True,turn=turn,
        originalSourceCheckpoint=row['run'])
    checks.write(run/'metadata.json',metadata)
    checks.write(run/'terrain-memory.json',serial(memory))
    lua(game,directory,'nh.debug_flags({hunger=false});')
    return game,dict(run=str(run),metadata=metadata)


def ritual_rings(center):
    rings = {0:[center]}; x,y = center
    for dist in range(1,7):
        h = dist if dist < 3 else dist-1
        positions = []
        if dist != 3:
            positions += [(i,y-h) for i in range(x-dist+1,x+dist)]
            positions += [(i,y+h) for i in range(x-dist+1,x+dist)]
        positions += [(x-dist,j) for j in range(y-h,y+h+1)]
        positions += [(x+dist,j) for j in range(y-h,y+h+1)]
        rings[dist] = positions
    return rings


def engine(row):
    source = Path(row['run'])/'game'
    assert files_hashes(source) == row['originalGameSHA256'], 'Original invocation source changed'
    run = Path(tempfile.mkdtemp(prefix='invocation-engine-',dir=ART)); directory=run/'game'
    shutil.copytree(source,directory)
    game = checks.open_game(directory); states=[]; records=[]; previous=[]
    result = dict(run=str(run),sourceEvidence=source_evidence(),passed=False)
    try:
        settle(game); origin=tour.identity(game,directory)
        assert origin == row['metadata']['identity']
        initial=diagnostics(game,directory)
        squares=[p for p,t in initial['traps'].items() if t['type']=='vibrating square']
        assert len(squares)==1, squares
        square=squares[0]
        assert not initial['traps'][square]['seen'], 'Source square already revealed'
        assert len(initial['stairs'])==1 and initial['stairs'][0]['up'], initial['stairs']
        protect(game,directory)
        row=copy.deepcopy(row)
        row['metadata']['setup'].append('Targeted ritual setup: upstream wizard experience 30; timed invulnerability, stealth, invisibility, water walking, fire resistance, magical breathing and regeneration; debug hunger disabled. Ordinary wizard wishes supply identified uncursed Bell of Opening (three charges), uncursed Candelabrum, uncursed Book of the Dead, seven uncursed wax candles, a +50 sword and a scare-monster scroll. No actor removed by setup and no terrain or invocation state assigned.')
        records.append(select_item(game,'a','wax candles',attachment=True))
        assert any('attach 7' in m.lower() for m in records[-1]['messages']), records[-1]
        # Choose one original adjacent traversable square by read-only diagnostics.
        # The coordinates are disclosed test setup, never playable inspection data.
        adjacent=[(square[0]+dx,square[1]+dy) for dx,dy,k in STEPS
                  if initial['terrain'].get((square[0]+dx,square[1]+dy),{}).get('type') in ('room','corridor')]
        assert adjacent, ('No original adjacent floor',square)
        placed=False
        for target in adjacent:
            try: place(game,target); placed=True; break
            except AssertionError as error:
                if game.cursor != target: continue
                raise error
        assert placed, 'Active occupants blocked every original approach'
        undiscovered=diagnostics(game,directory)
        assert not undiscovered['traps'][square]['seen'], 'Square discovered during setup rather than ordinary approach'
        turn=game.turn; unseen_description=game.inspect(*square)
        assert game.turn==turn and 'vibrating' not in unseen_description.lower(),unseen_description
        unseen_cell=copy.deepcopy(game.cells[square])
        assert unseen_cell.get('tile')!=1347 and unseen_cell.get('groundTile')!=1347,unseen_cell
        row['metadata']['setup'].append('Wizard teleport placed the protected adventurer on existing floor adjacent to the diagnostic vibrating-square location. No wizard mapping. The square remains unseen before the ordinary discovery step; original actors remain active.')
        game,state=snapshot(row,game,directory,'invocation-undiscovered'); states.append(state); checks.write(STATES,states)
        discovery=step(game,square); records.append(discovery)
        discovered=diagnostics(game,directory)
        assert discovered['traps'][square]['seen']
        assert any('vibrat' in m.lower() for m in discovery['messages']), discovery
        records.append(step(game,tuple(discovery['origin'])))
        turn=game.turn; description=game.inspect(*square)
        assert 'vibrating square' in description.lower() and game.turn==turn, description
        row['metadata']['setup'].append('Ordinary movement onto the original square discovered its vibration and trap memory. Hover inspection of that known feature consumes no turn.')
        game,state=snapshot(row,game,directory,'invocation-discovered'); states.append(state); checks.write(STATES,states)
        records.append(step(game,square))
        records.append(select_item(game,'d','scroll of scare monster'))
        assert game.cursor==square, ('Attack displaced hero during protective scroll drop',game.cursor)
        row['metadata']['setup'].append('A wished uncursed scare-monster scroll is dropped using ordinary Drop on the square to deter original attackers while the multi-turn Book reading completes. Original actors remain active; no freeze, removal or replacement is performed.')
        combat=repel_attackers(game,square);records.append(combat)
        if combat['commands']:
            row['metadata']['setup'].append('Displayed adjacent attackers which ignored or approached the scare scroll were fought by ordinary F + direction sword commands before priming the relics. This can kill original occupants through normal gameplay; no wizard actor deletion is used.')
        pre_ritual=diagnostics(game,directory)
        records.append(select_item(game,'a','Candelabrum of Invocation'))
        assert any('strange light' in m.lower() for m in records[-1]['messages']), records[-1]
        for ritual_attempt in range(8):
            records.append(repel_attackers(game,square))
            records.append(select_item(game,'a','Bell of Opening'))
            records.append(select_item(game,'r','Book of the Dead'))
            if any('top of a stairwell leading down' in m.lower() for m in records[-1]['messages']): break
            assert any('stop studying' in m.lower() for m in records[-1]['messages']),records[-1]
        else: raise AssertionError(('Original attackers repeatedly interrupted normal Book reading',records[-1]))
        transformed=diagnostics(game,directory)
        assert square not in transformed['traps']
        new_stairs=[s for s in transformed['stairs'] if not s['up']]
        assert len(new_stairs)==1 and new_stairs[0]['position']==list(square)
        assert new_stairs[0]['dlevel']==origin['level']+1
        rings=ritual_rings(square); checked=[]
        for dist,positions in rings.items():
            for p in positions:
                # The upstream ritual clips the outer rings at maze boundaries.
                if not (2<=p[0]<=78 and 2<=p[1]<=20): continue
                cell=transformed['terrain'][p]
                expected='stairs' if dist==0 else 'moat' if dist in (4,5) else 'room'
                assert cell['type']==expected,(dist,p,cell)
                if dist==1:
                    assert transformed['traps'][p]==dict(type='fire',seen=True),(p,transformed['traps'].get(p))
                elif dist!=0: assert p not in transformed['traps'],(dist,p)
                if dist<6:
                    assert cell['lit'] and cell['waslit'],(dist,p,cell)
                else:
                    # mkinvpos does not set outer-ring lit. Its temporary
                    # waslit/vision override can be superseded by normal
                    # vision recalculation before the command prompt.
                    assert cell['lit']==pre_ritual['terrain'][p]['lit'],(dist,p,cell)
                checked.append(dict(ring=dist,position=list(p),type=expected))
        assert sum(t['type']=='fire' for t in transformed['traps'].values())>=8
        assert any(p['type']=='moat' for p in checked)
        row['metadata']['setup'].append('The actual Apply Candelabrum, Apply Bell, Read Book sequence performed the upstream invocation. Original engine transmutation created its fire traps, lit cleared floor, double moat and downward stair. No map reveal was used; visible ritual terrain is the engine animation and normal perception.')
        game,state=snapshot(row,game,directory,'invocation-transformed'); states.append(state); checks.write(STATES,states)
        before=game.turn; settle(game,game.command('>')); sanctum=tour.identity(game,directory)
        assert sanctum['branch']=='Gehennom' and sanctum['level']==new_stairs[0]['dlevel'], (origin,sanctum)
        arrival=game.cursor
        row['metadata']['setup'].append('Ordinary > command on the invocation-created stair reached the actual Sanctum. This is protected route verification, not proof of an unprotected campaign encounter.')
        game,state=snapshot(row,game,directory,'sanctum-arrival'); states.append(state); checks.write(STATES,states)
        upstairs=next(s for s in diagnostics(game,directory)['stairs'] if s['up'] and s['dlevel']==origin['level'])
        if game.cursor!=tuple(upstairs['position']):
            # Arrival may be displaced by an original actor. Ordinary movement
            # from that adjacent landing square uses the real reciprocal stair.
            assert max(abs(game.cursor[i]-upstairs['position'][i]) for i in (0,1))<=1
            records.append(step(game,tuple(upstairs['position'])))
        settle(game,game.command('<'))
        assert tour.identity(game,directory)==origin
        assert game.cursor==square
        returned=diagnostics(game,directory)
        assert all(returned['terrain'][p]['type']==cell['type'] for p,cell in transformed['terrain'].items())
        assert returned['traps']==transformed['traps'] and returned['stairs']==transformed['stairs'], 'Invocation topology/traps/stairs changed during Sanctum roundtrip'
        perception(game); game.finish(automatic=True)
        assert files_hashes(source)==row['originalGameSHA256'], 'Original source mutated by tests'
        result.update(passed=True,identity=origin,vibratingSquare=list(square),
            originalTerrain=serial(initial),beforeRitual=serial(pre_ritual),
            transformedTerrain=serial(transformed),checkedRings=checked,
            records=records,discovery=discovery,knownSquareInspection=description,
            undiscoveredInspection=dict(description=unseen_description,cell=unseen_cell,turnFree=True,noVibratingMarker=True),
            originalSaveUnchanged=True,exactStateRestores=True,
            ordinarySanctumRoundtrip=dict(down='>',up='<',destination=sanctum,arrival=list(arrival),returned=list(game.cursor),turns=game.turn-before),
            states=[s['run'] for s in states])
        checks.write(RESULTS,result)
        print('PASS unseen source, ordinary discovery, uncursed ritual, actual fire/moat/stair transmutation, Sanctum roundtrip and four exact state restores',flush=True)
        return result
    finally:
        checks.cleanup(run,game,previous)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--engine',action='store_true')
    args=parser.parse_args(); ART.mkdir(exist_ok=True)
    if args.prepare: prepare()
    if args.engine: engine(json.loads(INDEX.read_text()))
    assert args.prepare or args.engine, 'Choose --prepare or --engine'


if __name__=='__main__': main()
