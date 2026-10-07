#!/usr/bin/env python3
"""Verify original world-selected Castle and real drawbridge actions in isolation.

Wizard travel, reveal, protection, inventory and selected placement are disclosed
preparation. Terrain and occupants are never replaced. Source checkpoints are
never opened in place. Results are engine evidence, not a completed campaign.
"""
import argparse
from collections import Counter, deque
import copy
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('castle_checks',ROOT/'scripts/test-valley-level.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
tour = checks.tour
INDEX = ART/'castle-prepared.json'
MANIFEST = ART/'castle-review-manifest.json'
RESULTS = ART/'castle-engine-results.json'
BOUNDS = [1,0,79,21]
WALLS = set(range(1273,1284))
FLOORS = set(range(1291,1297))
HIDDEN = (1469,1470)
write,settle = checks.write,checks.settle


def write_trace(path,events):
    path.write_text(''.join(json.dumps(e)+'\n' for e in events))


def source_evidence():
    archive = tour.RES/'Source/nethack-500-src.tgz'
    hashes = {}
    with tarfile.open(archive) as upstream:
        for relative in ('dat/castle.lua','src/dbridge.c','src/music.c','src/zap.c'):
            member = next(m for m in upstream.getmembers() if m.name.endswith('/'+relative))
            original = upstream.extractfile(member).read()
            assert (tour.DAT.parent/relative).read_bytes() == original,relative+' changed'
            hashes[relative] = tour.digest(tour.DAT.parent/relative)
    return dict(sourceScript='vendor/NetHack-5.0.0/dat/castle.lua',sourceSHA256=hashes,
        upstreamArchiveSHA256=tour.digest(archive),unchangedUpstreamSource=True)


def privacy(cells, mode=None):
    values = list(cells)
    hidden = [c for c in values if c['tile'] in HIDDEN]
    known = [c for c in values if c['tile'] not in HIDDEN]
    assert known and all('material' not in c for c in values),'Unexpected Castle regional material'
    assert all('groundTile' not in c for c in hidden),'Hidden ground leaked'
    if mode == 'exploration': assert hidden,'Unrevealed arrival lost hidden cells'
    return dict(knownCells=len(known),hiddenCells=len(hidden),noRegionalMaterial=True,noHiddenGround=True)


def clone(row,label):
    run = Path(tempfile.mkdtemp(prefix='castle-'+label+'-',dir=ART))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat')
    return run,directory,checks.open_game(directory)


def hashes(rows):
    return {str(p):tour.digest(p) for row in rows for p in sorted((Path(row['run'])/'game').rglob('*')) if p.is_file()}


def worker(mode):
    ART.mkdir(exist_ok=True)
    case = next(c for c in tour.catalog() if c['id']=='castle')
    assert case['source'] is None
    run = ART/('castle-original-'+mode+'-'+uuid.uuid4().hex)
    run.mkdir()
    metadata = tour.prepare(case,mode,run)
    cells = checks.displayed_cells(run/'preparation.jsonl')
    assert metadata['identity']['branch'] == 'The Dungeons of Doom'
    assert metadata['destination'].lstrip('* ').startswith('castle:')
    floors = Counter(c['tile'] for c in cells if c['tile'] in FLOORS)
    metadata.update(source_evidence(),checkpoint=str(run),shapeBounds=BOUNDS,
        displayedCells=cells,worldSelected=True,targetedLayout=False,
        designPreviewOnly=False,gameplayPlaytestPerformed=False,
        testTerrainTiles=[next(t for t in sorted(FLOORS) if floors[t])],
        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),perception=privacy(cells,mode),
        reviewRecipeSHA256=tour.digest(Path(__file__)))
    metadata['setup'].append('Original Castle world destination, random horizontal orientation, maze, moat, guards, throne, stores, loot and traps retained. No source reload or terrain/occupant replacement.')
    write(run/'metadata.json',metadata)
    print(json.dumps(dict(run=str(run),metadata=metadata)))


def terrain(game,directory):
    offset = len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 local flags={}; for k,v in pairs(m.flags) do flags[#flags+1]=k.."="..tostring(v); end; table.sort(flags);
 nh.pline("CASTLE_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..tostring(m.waslit)..","..tostring(m.seenv)..","..tostring(m.horizontal)..","..table.concat(flags,"|"));
end end;''')
    rows = [e['text'].split(':',1)[1].split(',') for e in game.events[offset:] if e.get('text','').startswith('CASTLE_TERRAIN:')]
    assert len(rows)==79*21,len(rows)
    return {(int(r[0]),int(r[1])):dict(type=r[2],lit=r[3],waslit=r[4],seenv=r[5],horizontal=r[6],flags=r[7]) for r in rows}


def topology(mapping):
    counts = Counter(r['type'] for r in mapping.values())
    assert counts['drawbridge up']==1 and counts['drawbridge wall']==1,counts
    span = next(p for p,r in mapping.items() if r['type']=='drawbridge up')
    wall = next(p for p,r in mapping.items() if r['type']=='drawbridge wall')
    delta = (wall[0]-span[0],wall[1]-span[1])
    assert delta in ((1,0),(-1,0)),delta
    return dict(span=list(span),portcullis=list(wall),direction='east' if delta[0]>0 else 'west',
        outside=[span[0]-delta[0],span[1]],inside=[wall[0]+delta[0],wall[1]],
        originalTerrainCounts=dict(counts))


def inspect(game,points):
    before = game.turn
    result = [dict(position=list(p),cell=copy.deepcopy(game.cells[p]),description=game.inspect(*p)) for p in points]
    assert game.turn==before
    return result


def redraw(game):
    offset=len(game.events)
    before=game.turn
    game.send('key 18')
    settle(game)
    events=game.events[offset:]
    assert any(e['type']=='clear' and e.get('window')=='map' for e in events),'No canonical map clear'
    assert game.turn==before,'Redraw spent turns'
    return dict(eventOffset=offset,eventCount=len(events),mapClear=True,turnFree=True,cells=copy.deepcopy(list(game.cells.values())))


def scene(row,label):
    m=row['metadata']
    return dict(label=label,width=79,height=21,cells=[dict(c,x=c['x']-1) for c in m['displayedCells']],
        sourceCheckpoint=row['run'],engine=m['engine'],app=m['app'],identity=m['identity'],
        setup=m['setup'],originalBounds=BOUNDS,reviewOnly=True,worldSelected=True,targetedLayout=False,
        mode=m['mode'],perception=m['perception'])


def snapshot(row,game,directory,label,topo,tests):
    run=Path(tempfile.mkdtemp(prefix='castle-state-'+label+'-',dir=ART))
    capture=redraw(game)
    mapping=terrain(game,directory)
    metadata=copy.deepcopy(row['metadata'])
    metadata.update(mode='inspection',scene=label,checkpoint=str(run),arrival=list(game.cursor),
        displayedCells=capture['cells'],perception=privacy(capture['cells']),gameplayPlaytestPerformed=True,
        bridgeState=label,bridgeTopology=topo,canonicalMapCapture=capture,
        stateTerrain={str(p):mapping[p] for p in (tuple(topo['span']),tuple(topo['portcullis']))},
        testResults=copy.deepcopy(tests),stateTurn=game.turn)
    metadata['stateEvidence']=str(run/'engine.jsonl')
    metadata['setup'].append('Targeted gameplay clone: supplied and debug-identified charged opening, locking and striking wands, plus +50 long sword wielded and +50 gray dragon scale mail worn by ordinary actions; wizard exterior placement then ordinary courtyard steps beside the original drawbridge. All transitions use ordinary zap commands. Timed upstream wizard invulnerability, invisibility and stealth protect the targeted bridge tests. An ordinary put-on action equips a supplied see-invisible ring so the hero remains self-visible. If original restricted teleport rejects placement, timed water walking allows an ordinary route over original moat to the courtyard. Original checkpoints remain unchanged.')
    game.finish(automatic=True)
    write_trace(run/'engine.jsonl',game.events)
    shutil.copytree(directory,run/'game')
    write(run/'metadata.json',metadata)
    return dict(run=str(run),metadata=metadata),checks.open_game(directory)


def wand(game,word,direction):
    offset=len(game.events)
    before=game.turn
    event=game.command('z')
    assert event['kind']=='menu',event
    row=next(i for i in event['items'] if word in i['text'].lower())
    game.send('menu '+str(row['id']))
    event=game.wait_input()
    assert event.get('direction'),event
    game.send('key '+str(ord(direction)))
    settle(game)
    messages=[e['text'] for e in game.events[offset:] if e['type']=='message']
    assert game.turn>=before,(before,game.turn,messages)
    # Fast heroes can spend an action without advancing the displayed world turn.
    assert any(word in m.lower() for m in messages for word in ('drawbridge','gears','chains')),messages
    return dict(action='zap wand of '+word,direction=direction,turns=game.turn-before,messages=messages,
        changedCells=[e for e in game.events[offset:] if e['type']=='cell'])


def original_restore(row):
    run,directory,game=clone(row,'restore-'+row['metadata']['mode'])
    try:
        settle(game)
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        assert tour.identity(game,directory)==row['metadata']['identity']
        assert list(game.cursor)==row['metadata']['arrival']
        capture=redraw(game)
        cells=capture['cells']
        meta=row['metadata']
        privacy(cells,meta['mode'])
        points=[]
        for pred in (lambda c:c['tile'] in WALLS,lambda c:c['tile'] in FLOORS,lambda c:c['tile'] in HIDDEN):
            c=next((c for c in cells if pred(c)),None)
            if c: points.append((c['x'],c['y']))
        samples=inspect(game,points)
        for sample in samples:
            if sample['cell']['tile'] in HIDDEN:
                assert 'unexplored' in sample['description'].lower(),sample
        meta.setdefault('originalEngine',meta['engine'])
        meta.setdefault('originalApp',meta['app'])
        meta.update(engine=tour.digest(tour.RES/'engine/nethack'),app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'),
            displayedCells=cells,independentRestoreVerified=True,canonicalMapCapture=capture,
            restoredPerception=privacy(cells,meta['mode']),turnFreeInspection=True,inspection=samples,
            independentRestoreEvidence=str(run/'engine.jsonl'))
        if meta['mode']=='inspection':
            mapping=terrain(game,directory)
            meta['bridgeTopology']=topology(mapping)
            counts=Counter(r['type'] for r in mapping.values())
            assert counts['throne']==1 and counts['fountain']==1 and counts['moat']>100,counts
            assert counts['stairs']==1,'Original Castle must retain upward-only stairs'
            features=[]
            for name in ('throne','fountain','moat','stairs','door'):
                point=next((p for p,r in mapping.items() if r['type']==name and game.cells[p]['tile'] not in HIDDEN),None)
                assert point,('Original Castle feature missing from perceived map',name)
                samples=inspect(game,[point])
                assert samples[0]['description'].strip(),samples
                features.extend(samples)
            meta['featureInspection']=features
            meta['originalTerrainCounts']=dict(counts)
        game.finish(automatic=True)
        write(Path(row['run'])/'metadata.json',meta)
        return dict(run=str(run),mode=meta['mode'],passed=True,turnFreeInspection=samples,canonicalMapClear=True)
    finally: checks.cleanup(run,game)


def walk_to(game,target,water=False):
    """Choose perceived passable ground, then verify every ordinary step."""
    start=game.cursor
    queue=deque([start]); routes={start:[]}
    while queue:
        point=queue.popleft()
        if point==target: break
        for dx,dy,key in checks.STEPS:
            next_point=(point[0]+dx,point[1]+dy)
            cell=game.cells.get(next_point,{})
            if next_point not in routes and cell.get('char') in (('.', '#', '<', '>', '}') if water else ('.','#','<','>')):
                routes[next_point]=routes[point]+[(key,next_point)]
                queue.append(next_point)
    assert target in routes,('No perceived open path',start,target)
    steps=[]
    for key,destination in routes[target]:
        before=game.turn
        offset=len(game.events)
        for attempt in range(60):
            settle(game,game.command(key))
            if game.cursor==destination: break
            messages=[e['text'] for e in game.events[offset:] if e['type']=='message']
            assert any(word in m.lower() for m in messages for word in ('hit ','miss ','kill ','attack ','swings','bites')),('Original route obstructed',destination,game.cursor,messages)
        assert game.cursor==destination,('Original route did not clear by ordinary actions',destination,game.cursor)
        steps.append(dict(command=key,destination=list(destination),turns=game.turn-before,messages=[e['text'] for e in game.events[offset:] if e['type']=='message']))
    return steps


def bridge_tests(row):
    run,directory,game=clone(row,'drawbridge')
    records=[]
    states=[]
    try:
        settle(game)
        identity=tour.identity(game,directory)
        initial=terrain(game,directory)
        topo=topology(initial)
        span,wall,outside,inside=[tuple(topo[n]) for n in ('span','portcullis','outside','inside')]
        direction='l' if topo['direction']=='east' else 'h'
        reverse='h' if direction=='l' else 'l'
        tour.lua(game,directory,'u.giveobj(obj.new("blessed wand of opening (0:20)")); u.giveobj(obj.new("blessed wand of locking (0:20)")); u.giveobj(obj.new("blessed wand of striking (0:20)")); u.giveobj(obj.new("blessed +50 gray dragon scale mail")); u.giveobj(obj.new("blessed +50 long sword")); u.giveobj(obj.new("uncursed ring of see invisible"));')
        event=tour.named(game,'wizidentify')
        assert event['kind']=='menu',event
        game.send('menu '+','.join(str(i['id']) for i in event['items'] if i.get('selectable') and i.get('key')!='_'))
        settle(game)
        event=game.command('P'); assert event['kind']=='menu',event
        ring=next(i for i in event['items'] if 'ring of see invisible' in i['text'])
        game.send('menu '+str(ring['id'])); event=game.wait_input()
        assert event['kind']=='yn' and 'finger' in event['prompt'].lower(),event
        game.send('key 108'); settle(game)
        event=game.command('w'); assert event['kind']=='menu',event
        sword=next(i for i in event['items'] if '+50 long sword' in i['text'])
        game.send('menu '+str(sword['id'])); settle(game)
        event=game.command('W')
        assert event['kind']=='menu',event
        armor=next(i for i in event['items'] if 'gray dragon scale mail' in i['text'])
        game.send('menu '+str(armor['id'])); settle(game)
        event=tour.named(game,'wizintrinsic')
        protection=[i for i in event['items'] if i['text'].strip().lower() in ('invisible','stealthy','invulnerable')]
        assert len(protection)==3,protection
        game.send('menu '+','.join(str(i['id'])+':1000000' for i in protection)); settle(game)
        exterior=(outside[0]-4 if direction=='l' else outside[0]+4,outside[1])
        event=tour.named(game,'teleport')
        if event['kind']=='menu' and event.get('how')==0:
            game.send('key 32'); event=game.wait_input()
        assert event.get('targeting'),event
        game.send(f'position {exterior[0]} {exterior[1]}'); settle(game)
        actual=game.cursor
        water_route=actual!=exterior
        if water_route:
            event=tour.named(game,'wizintrinsic')
            walking=next(i for i in event['items'] if i['text'].strip().lower()=='water walking')
            game.send('menu '+str(walking['id'])+':1000000'); settle(game)
        records.append(dict(check='ordinary original courtyard route after upstream wizard placement',requestedWizardPlacement=list(exterior),actualWizardPlacement=list(actual),
            waterWalkingSetup=water_route,steps=walk_to(game,outside,water=water_route)))
        closed,game=snapshot(row,game,directory,'raised',topo,records)
        settle(game)
        closed_cells=copy.deepcopy(game.cells)
        before_open=terrain(game,directory)
        action=wand(game,'opening',direction)
        opened=terrain(game,directory)
        assert opened[span]['type']=='drawbridge down' and opened[wall]['type']=='door',(opened[span],opened[wall])
        assert 'nodoor=true' in opened[wall]['flags']
        changed=[list(p) for p in before_open if before_open[p]['type']!=opened[p]['type']]
        assert {span,wall}<={tuple(p) for p in changed},changed
        action.update(check='real opening lowers span and opens portcullis',terrainChanged=changed,inspection=inspect(game,[span,wall]))
        records.append(action)
        hero_lowered=None
        for key,target in ((direction,span),(direction,wall),(reverse,span),(reverse,outside)):
            before=game.turn
            offset=len(game.events)
            for attempt in range(60):
                settle(game,game.command(key))
                if game.cursor==target: break
            assert game.cursor==target,(target,game.cursor)
            assert game.turn>=before
            occupant=copy.deepcopy(game.cells[target])
            if target==span:
                assert occupant.get('groundTile') in (1318,1319),occupant
                assert occupant.get('char')=='@' and occupant['tile']!=788,'Hero is not self-visible'
            records.append(dict(check='ordinary safe lowered bridge traversal',command=key,destination=list(target),turns=game.turn-before,heroCell=occupant,
                messages=[e['text'] for e in game.events[offset:] if e['type']=='message']))
            if target==span and hero_lowered is None:
                hero_lowered,game=snapshot(row,game,directory,'lowered-hero',topo,records)
                settle(game)
        lowered,game=snapshot(row,game,directory,'lowered',topo,records)
        settle(game)
        # Walk across the real bridge to stand safely behind its portcullis.
        for key,target in ((direction,span),(direction,wall),(direction,inside)):
            for attempt in range(60):
                settle(game,game.command(key))
                if game.cursor==target: break
            assert game.cursor==target,(target,game.cursor)
        action=wand(game,'locking',reverse)
        mapping=terrain(game,directory)
        assert mapping[span]['type']=='drawbridge up' and mapping[wall]['type']=='drawbridge wall'
        action.update(check='real locking raises span and restores closed portcullis',inspection=inspect(game,[span,wall]))
        records.append(action)
        before,position=game.turn,game.cursor
        settle(game,game.command(reverse))
        assert game.cursor==position and game.turn==before,(position,game.cursor,before,game.turn)
        records.append(dict(check='raised portcullis blocks ordinary movement',position=list(position),command=reverse,turns=game.turn-before,inspection=inspect(game,[wall,span])))
        reraised,game=snapshot(row,game,directory,'reraised',topo,records)
        settle(game)
        # Striking the portcullis from inside avoids zapping only raised moat.
        # Entered through the actual lowered bridge before closing it.
        action=wand(game,'striking',reverse)
        destroyed=terrain(game,directory)
        assert destroyed[span]['type']=='moat' and destroyed[wall]['type']=='door',(destroyed[span],destroyed[wall])
        assert 'nodoor=true' in destroyed[wall]['flags']
        action.update(check='real striking destroys bridge into original moat',inspection=inspect(game,[span,wall]))
        records.append(action)
        ruined,game=snapshot(row,game,directory,'destroyed',topo,records)
        settle(game)
        # This last clone checks exact terrain/lighting and remembered ground after restore.
        assert terrain(game,directory)==destroyed,'Destroyed bridge terrain or memory changed on restore'
        assert tour.identity(game,directory)==identity
        records.append(dict(check='destroyed bridge exact terrain, lighting, flags and seen-vector restore',passed=True))
        privacy(game.cells.values())
        event=tour.named(game,'wizintrinsic')
        levitation=next(i for i in event['items'] if i['text'].strip().lower()=='levitating')
        game.send('menu '+str(levitation['id'])+':1000000'); settle(game)
        for target in (wall,span,outside):
            for attempt in range(60):
                settle(game,game.command(reverse))
                if game.cursor==target: break
            assert game.cursor==target,(target,game.cursor)
        # An active guard may freeze the destroyed span with its actual wand.
        # Use a separately observed unchanged moat cell beside dry courtyard.
        shoreline=(outside[0],outside[1]+2)
        moat=(outside[0],outside[1]+3)
        walk_to(game,shoreline)
        current=terrain(game,directory)
        assert current[moat]['type']=='moat',current[moat]
        for attempt in range(60):
            settle(game,game.command('j'))
            if game.cursor==moat: break
        assert game.cursor==moat,(moat,game.cursor)
        hero=copy.deepcopy(game.cells[moat])
        assert hero.get('groundTile')==1314,hero
        assert hero.get('char')=='@' and hero['tile']!=788,'Moat hero is not self-visible'
        records.append(dict(check='known original moat ground under levitating hero after real bridge destruction',heroCell=hero,
            setup='Timed levitation conferred by upstream wizard intrinsic menu, then ordinary movement. No water or occupant replacement.',inspection=inspect(game,[moat]),position=list(moat)))
        moat_hero,game=snapshot(row,game,directory,'destroyed-moat-hero',topo,records)
        settle(game)
        assert game.cells[moat].get('groundTile')==1314,game.cells[moat]
        records.append(dict(check='moat under hero survives independent restore',passed=True))
        game.finish(automatic=True)
        states=[closed,lowered,hero_lowered,reraised,ruined,moat_hero]
        return states,dict(run=str(run),identity=identity,topology=topo,checks=records,passed=True,
            setup='Original Castle clone, supplied charged wands and upstream wizard placement. Ordinary zap and movement commands create every tested state. No direct terrain mutation or occupant replacement.')
    finally: checks.cleanup(run,game)


def blind_memory(row):
    run,directory,game=clone(row,'blind-memory')
    try:
        settle(game)
        topo=row['metadata']['bridgeTopology']
        span,wall=[tuple(topo[name]) for name in ('span','portcullis')]
        direction='l' if topo['direction']=='east' else 'h'
        assert game.cursor==tuple(topo['outside'])
        assert terrain(game,directory)[span]['type']=='drawbridge down'
        initial=copy.deepcopy(game.cells[span])
        assert initial.get('groundTile') in (1318,1319),initial
        tour.lua(game,directory,'u.giveobj(obj.new("uncursed blindfold"));')
        event=game.command('a'); assert event['kind']=='menu',event
        item=next(i for i in event['items'] if 'blindfold' in i['text'].lower())
        game.send('menu '+str(item['id'])); settle(game)
        before_close=copy.deepcopy(game.cells[span])
        action=wand(game,'locking',direction)
        changed=terrain(game,directory)
        assert changed[span]['type']=='drawbridge up' and changed[wall]['type']=='drawbridge wall'
        blind_cells=redraw(game)['cells']
        displayed=next(c for c in blind_cells if (c['x'],c['y'])==span)
        assert displayed.get('groundTile') not in (1314,1315),'Current unseen raised moat leaked into ground'
        assert displayed.get('groundTile') in (None,initial['groundTile']),displayed
        samples=inspect(game,[span,wall])
        # Remove the same actual blindfold by ordinary apply and verify refreshed sight.
        event=game.command('a'); assert event['kind']=='menu',event
        item=next(i for i in event['items'] if 'blindfold' in i['text'].lower())
        game.send('menu '+str(item['id'])); settle(game)
        seen=copy.deepcopy(game.cells[span])
        assert terrain(game,directory)[span]['type']=='drawbridge up'
        # Invisible-occupant marks can suppress terrain until perception has
        # actually resolved it. The safe bridge fallback may omit that ground.
        assert seen.get('groundTile') in (None,1314),seen
        assert game.cells[wall]['tile'] in (1320,1321),game.cells[wall]
        result=dict(run=str(run),passed=True,setup='Supplied an uncursed blindfold, ordinary apply to blind/unblind and actual locking zap; no terrain mutation.',
            action=action,initial=initial,beforeClose=before_close,blindDisplay=displayed,afterSight=seen,
            currentUnseenMoatNotDisclosed=True,inspection=samples)
        game.finish(automatic=True)
        write(ART/'castle-blind-memory-results.json',result)
        return result
    finally: checks.cleanup(run,game)


def music(row):
    run,directory,game=clone(row,'music')
    try:
        settle(game)
        topo=row['metadata']['bridgeTopology']
        span,wall=[tuple(topo[name]) for name in ('span','portcullis')]
        event=tour.named(game,'wizwhere')
        assert event['kind']=='text',event
        tune=next(match.group(1) for line in event['lines'] if (match:=re.search(r'\(tune ([A-G]{5})\)',line)))
        game.send('key 32'); settle(game)
        tour.lua(game,directory,'u.giveobj(obj.new("uncursed wooden harp"));')
        actions=[]
        for expected in ('drawbridge down','drawbridge up'):
            offset=len(game.events); before=game.turn
            event=game.command('a'); assert event['kind']=='menu',event
            item=next(i for i in event['items'] if 'harp' in i['text'].lower())
            game.send('menu '+str(item['id'])); event=game.wait_input()
            assert event['kind']=='yn' and 'improvise' in event['prompt'].lower(),event
            game.send('key 110'); event=game.wait_input()
            if event['kind']=='yn' and 'passtune' in event['prompt'].lower():
                game.send('key 121')
            else:
                assert event['kind']=='line' and 'tune' in event['prompt'].lower(),event
                game.send('line '+tune)
            settle(game)
            mapping=terrain(game,directory)
            assert mapping[span]['type']==expected,(expected,mapping[span])
            actions.append(dict(action='ordinary apply wooden harp with original Castle tune',expected=expected,
                turns=game.turn-before,messages=[e['text'] for e in game.events[offset:] if e['type']=='message'],inspection=inspect(game,[span,wall])))
        result=dict(run=str(run),passed=True,actions=actions,tune=tune,
            setup='Original passtune read from upstream wizard level-location display, wooden harp supplied. Ordinary apply and tune prompts toggle the actual original drawbridge twice. No tune or terrain patched.')
        game.finish(automatic=True)
        write(ART/'castle-music-results.json',result)
        return result
    finally: checks.cleanup(run,game)


def flipped(original):
    """Generate real additional worlds until the other original orientation appears."""
    wanted='west' if original['metadata']['bridgeTopology']['direction']=='east' else 'east'
    attempts=[]
    for attempt in range(8):
        row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__)), '--worker','inspection'],text=True))
        original_restore(row)
        direction=row['metadata']['bridgeTopology']['direction']
        attempts.append(dict(run=row['run'],direction=direction,worldSelected=True))
        if direction==wanted:
            before=hashes([row])
            states,result=bridge_tests(row)
            assert hashes([row])==before
            result.update(oppositeOriginalOrientation=True,attempts=attempts,
                nativeCapturesPerformed=False,originalCheckpointUnchanged=True,states=[s['run'] for s in states])
            write(ART/'castle-opposite-orientation-results.json',result)
            return result
    raise AssertionError(('No opposite Castle orientation in eight original worlds',attempts))


def crop(base,label,bounds):
    x,y,w,h=bounds
    return dict(base,label=label,width=w,height=h,cropBounds=bounds,
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in base['cells'] if x<=c['x']<x+w and y<=c['y']<y+h])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',choices=('inspection','exploration'))
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    if args.worker: worker(args.worker); return
    ART.mkdir(exist_ok=True)
    if args.prepare or not INDEX.exists():
        rows=[json.loads(subprocess.check_output([sys.executable,str(Path(__file__)), '--worker',mode],text=True)) for mode in ('inspection','exploration')]
        write(INDEX,rows)
    else:
        rows=[r for r in json.loads(INDEX.read_text()) if 'bridgeState' not in r['metadata']]
    original_hashes=hashes(rows)
    restores=[original_restore(row) for row in rows]
    inspection=next(r for r in rows if r['metadata']['mode']=='inspection')
    states,bridge=bridge_tests(inspection)
    musical=music(next(s for s in states if s['metadata']['bridgeState']=='raised'))
    opposite=flipped(inspection)
    blind=blind_memory(next(s for s in states if s['metadata']['bridgeState']=='lowered'))
    assert hashes(rows)==original_hashes,'Original source checkpoints changed'
    scenes={}
    for row in rows+states:
        name=row['metadata'].get('bridgeState','full' if row['metadata']['mode']=='inspection' else 'arrival')
        scenes[name]=scene(row,'Actual engine Castle: '+name)
        if name=='full':
            walls=[c for c in scenes[name]['cells'] if c['tile'] in WALLS]
            x=max(0,min(c['x'] for c in walls)-1); y=max(0,min(c['y'] for c in walls)-1)
            right=min(79,max(c['x'] for c in walls)+2); bottom=min(21,max(c['y'] for c in walls)+2)
            scenes['fortress-detail']=crop(scenes[name],'Actual engine Castle fortress detail',[x,y,right-x,bottom-y])
        if name in ('raised','lowered','lowered-hero','reraised','destroyed','destroyed-moat-hero'):
            span=row['metadata']['bridgeTopology']['span']
            scenes[name+'-detail']=crop(scenes[name],'Actual engine Castle drawbridge: '+name,[max(0,span[0]-6),max(0,span[1]-4),11,9])
    results=dict(source=source_evidence(),originalCheckpointHashes=original_hashes,originalCheckpointsUnchanged=True,
        restores=restores,bridge=bridge,blindMemory=blind,music=musical,oppositeOrientation=opposite,passed=True,
        limits=['Targeted protected wizard sessions, not a campaign or loot/guard-clearance playthrough.','No stochastic drawbridge crushing/drowning outcomes asserted.','Both east and west orientations tested in separately generated original worlds; no artificial rotated Castle.','Native app rendering and Intel execution are separate verification.'])
    write(INDEX,rows+states)
    write(RESULTS,results)
    write(MANIFEST,dict(scenes=scenes,tests=results,reviewOnly=True,note='Actual canonical engine redraws and preserved isolated saves from unchanged world-selected Castle; actions create bridge states.'))
    print('PASS Castle original source, unrevealed privacy, canonical redraw, raised blocking, opening/locking/striking, traversal and restore',flush=True)
    print('MANIFEST',MANIFEST,flush=True)


if __name__=='__main__': main()
