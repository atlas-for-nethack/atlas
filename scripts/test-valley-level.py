#!/usr/bin/env python3
"""Check original world-selected Valley levels with isolated packaged-engine saves.

Wizard travel, protection and map reveal are disclosed preparation. Inspection,
floor movement, stair crossings and save/restore use the real engine. No terrain
or occupants are replaced, and no player's save directory is used.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/valley-rooms-prepared.json'
RESULTS = ROOT/'.artifacts/valley-engine-results.json'
OPTIONS = 'color,!news,!autopickup,time,force_invmenu,menustyle:full'
STEPS = ((-1,0,'h'), (1,0,'l'), (0,-1,'k'), (0,1,'j'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def settle(game, event=None):
    """Handle documented restore, incidental naming, death refusal and paging."""
    event = event or game.wait_input()
    for _ in range(80):
        if event.get('command'):
            return event
        prompt = event.get('prompt', '')
        if event['kind'] == 'line' and prompt.lower().startswith('call '):
            game.send('key 27')
        elif event['kind'] == 'line' and 'wish' in prompt.lower():
            game.send('line nothing')
        elif event['kind'] == 'yn' and 'die' in prompt.lower():
            game.send('key 110')
        elif event['kind'] == 'yn' and prompt == 'Do you want to keep the save file?':
            # Only disposable clones are opened here; their original source
            # checkpoints remain untouched and saving publishes a new clone.
            game.send('key 110')
        elif event['kind'] in ('key', 'text') or (event['kind'] == 'menu' and event.get('how') == 0):
            game.send('key 32')
        else:
            raise RuntimeError('Unexpected Valley test prompt: '+json.dumps(event))
        event = game.wait_input()
    raise RuntimeError('Valley test did not reach an ordinary command prompt')


def displayed_cells(path):
    cells = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            cells.clear()
        elif event['type'] == 'cell':
            cells[event['x'], event['y']] = event
    return list(cells.values())


def material(cells, expected):
    values = list(cells)
    known = [c for c in values if c['tile'] not in (1469,1470)]
    hidden = [c for c in values if c['tile'] in (1469,1470)]
    assert known, 'No perceived cells'
    allowed = expected if isinstance(expected, (list, tuple)) else [expected]
    mismatched = [c for c in known if c.get('material') not in allowed]
    assert not mismatched, (expected, mismatched[:8])
    assert all('material' not in c and 'groundTile' not in c for c in hidden), 'Hidden terrain leaked'
    return dict(knownCells=len(known), hiddenCells=len(hidden),
                materialCounts=dict(Counter(c.get('material','absent') for c in values)))


def original_source():
    """Compare maintained vendor terrain with the bundled pinned upstream source."""
    source = tour.DAT/'valley.lua'
    archive = tour.RES/'Source/nethack-500-src.tgz'
    with tarfile.open(archive) as upstream:
        matches = [m for m in upstream.getmembers() if m.name.endswith('/dat/valley.lua')]
        assert len(matches) == 1, matches
        original = upstream.extractfile(matches[0]).read()
    assert source.read_bytes() == original, 'Valley source differs from pinned upstream terrain'
    return dict(sourceScript='vendor/NetHack-5.0.0/dat/valley.lua',
                valleySourceSHA256=hashlib.sha256(original).hexdigest(),
                upstreamArchiveSHA256=tour.digest(archive), unchangedUpstreamSource=True)


def open_game(directory):
    os.environ.update(NETHACKDIR=str(directory), HACKDIR=str(directory), ATLAS_PLAY_MODE='standard')
    config = directory/'valley-test.nethackrc'
    config.write_text('')
    module = tour.load_game_module()
    class ClearAwareGame(module.Game):
        def next(self):
            event = super().next()
            if event['type'] == 'clear' and event.get('window') == 'map':
                self.cells.clear()
            return event
    return ClearAwareGame(directory, name='wizard', options=OPTIONS, config=config)


def clone(data, label):
    run = Path(tempfile.mkdtemp(prefix='valley-'+label+'-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(data['run'])/'game', directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat'), 'Stale checkpoint data'
    return run, directory, open_game(directory)


def cleanup(run, game, previous=()):
    (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in [*previous, *game.events]))
    if game.process.poll() is None:
        game.process.kill()
        game.process.wait(timeout=5)


def restore_marker(data):
    run, directory, game = clone(data, 'restore-marker')
    try:
        settle(game)
        counts = Counter(c['tile'] for c in game.cells.values() if c.get('char') == '.')
        assert counts, 'No perceived plain floor after restore'
        data['metadata'].update(testTerrainTiles=[next(t for t in (1292,1291) if counts[t])],
            nativeRestoreFloorCounts=dict(counts), nativeRestoreMarkerEvidence=str(run/'engine.jsonl'))
        material(game.cells.values(), 'valley')
        game.finish(automatic=True)
    finally:
        cleanup(run, game)


def prepare():
    source = original_source()
    if INDEX.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(INDEX, INDEX.with_name('valley-rooms-prepared-before-integration-'+stamp+'.json'))
    rows = []
    for mode in ('inspection', 'exploration'):
        data = json.loads(subprocess.check_output([sys.executable,
            str(ROOT/'scripts/playtest/prepare.py'), 'prepare', '--case', 'valley', '--mode', mode], text=True))
        metadata = data['metadata']
        assert metadata['case']['source'] is None, 'World-selected Valley must not reload a terrain fixture'
        assert metadata['identity']['branch'] == 'Gehennom' and metadata['identity']['level'] == 1
        cells = displayed_cells(Path(metadata['checkpoint'])/'preparation.jsonl')
        checked = material(cells, 'valley')
        if mode == 'exploration':
            assert checked['hiddenCells'] > 0, 'Exploration must retain unknown space'
        metadata.update(source, shapeBounds=[1,0,79,21], displayedCells=cells,
            displayedTileCounts=dict(Counter(str(c['tile']) for c in cells)),
            dataSHA256=tour.digest(tour.RES/'engine/nhdat'), worldSelected=True,
            designPreviewOnly=False, gameplayPlaytestPerformed=False,
            valleyRecipeSHA256=tour.digest(Path(__file__)))
        metadata['sources']['valley.lua'] = source['valleySourceSHA256']
        metadata['setup'].append('Original world-selected Valley. Original random route walls, morgues, shrine, doors, traps and active occupants retained. Integrated Valley material uses displayed perception only.')
        restore_marker(data)
        write(Path(data['run'])/'metadata.json', metadata)
        rows.append(data)
        write(INDEX, rows)
        print('PREPARED Valley', mode, data['run'], flush=True)
    return rows


def place(game, target):
    event = tour.named(game, 'teleport')
    if event['kind'] == 'menu' and event.get('how') == 0:
        game.send('key 32')
        event = game.wait_input()
    assert event.get('targeting'), event
    game.send(f'position {target[0]} {target[1]}')
    settle(game)
    assert game.cursor == target, (target, game.cursor)


def terrain_snapshot(game, directory):
    """Original terrain and lighting diagnostics in the isolated check clone.

    These are test evidence only and never a source for the playable UI.
    Include the engine's known-ground memory independently of creature redraw.
    """
    offset = len(game.events)
    tour.lua(game,directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 local flags={}; for k,v in pairs(m.flags) do flags[#flags+1]=k.."="..tostring(v); end; table.sort(flags);
 nh.pline("VALLEY_TERRAIN:"..x..","..y..","..m.typ_name..","..tostring(m.lit)..","..tostring(m.waslit)..","..tostring(m.seenv)..","..tostring(m.horizontal)..","..table.concat(flags,"|"));
end end;''')
    rows = [e['text'].split(':',1)[1].split(',') for e in game.events[offset:]
            if e.get('text','').startswith('VALLEY_TERRAIN:')]
    assert len(rows) == 79*21, len(rows)
    return rows


def engine(data):
    run, directory, game = clone(data, 'engine')
    previous = []
    result = dict(run=str(run), source=original_source())
    try:
        settle(game)
        identity = tour.identity(game, directory)
        assert identity == data['metadata']['identity']
        result.update(identity=identity, initial=material(game.cells.values(), 'valley'))
        initial_terrain = terrain_snapshot(game,directory)
        result['originalTerrainCounts'] = dict(Counter(row[2] for row in initial_terrain))
        assert result['originalTerrainCounts'].get('iron bars',0) == 0
        result['barsInspectionUnavailable'] = 'The original Valley has no iron bars. Upstream map B means boundary crosswall; F means iron bars. Artwork bar aliases are renderer coverage, not Valley gameplay coverage.'
        before = game.turn
        observed = []
        for category, tile, word in (('grave',1310,'grave'), ('altar',1305,'altar')):
            cell = next((c for c in game.cells.values() if c['tile'] == tile), None)
            assert cell, ('No perceived Valley feature', category)
            description = game.inspect(cell['x'],cell['y'])
            assert word in description.lower(), (category, description)
            observed.append(dict(category=category, cell=cell, description=description))
        assert game.turn == before
        result.update(inspection=observed, turnFreeInspection=True)
        # Pick only displayed plain floor, nearest the real arrival. Setup
        # placement does not replace occupants; movement must actually succeed.
        pairs = [(p, (p[0]+dx,p[1]+dy), key) for p,c in game.cells.items() if c.get('char') == '.'
                 for dx,dy,key in STEPS if game.cells.get((p[0]+dx,p[1]+dy),{}).get('char') == '.']
        assert pairs, 'No perceived plain-floor pair'
        pair = min(pairs, key=lambda row:abs(row[0][0]-game.cursor[0])+abs(row[0][1]-game.cursor[1]))
        place(game, pair[0])
        before = game.turn
        settle(game, game.command(pair[2]))
        assert game.cursor == pair[1] and game.turn >= before, (pair,game.cursor,game.turn,before)
        result['plainFloorMove'] = dict(origin=pair[0], destination=pair[1], command=pair[2], turns=game.turn-before)
        material(game.cells.values(), 'valley')
        terrain = terrain_snapshot(game,directory)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        previous = list(game.events)
        game = open_game(directory)
        settle(game)
        assert (game.cursor,game.turn) == (position,turn), (position,turn,game.cursor,game.turn)
        assert tour.identity(game,directory) == identity
        restored_terrain = terrain_snapshot(game,directory)
        assert restored_terrain == terrain, 'Original terrain, ground memory or lighting changed on restore'
        result.update(restored=True, position=position, turn=turn,
                      restoredMaterial=material(game.cells.values(), 'valley'),
                      exactTerrainGroundAndLightingRestore=True,
                      terrainBeforeSave=terrain,terrainAfterRestore=restored_terrain)
        game.finish(automatic=True)
        write(RESULTS, result)
        print('PASS Valley original source, known features, turn-free inspection, floor move and exact restore', flush=True)
        return result
    finally:
        cleanup(run,game,previous)


def unknown(data):
    run, directory, game = clone(data,'unknown')
    try:
        settle(game)
        identity = tour.identity(game,directory)
        assert identity == data['metadata']['identity']
        result = dict(run=str(run),identity=identity, **material(game.cells.values(),'valley'))
        hidden = [c for c in game.cells.values() if c['tile'] == 1469]
        assert hidden, 'No unexplored cells'
        before = game.turn
        samples = [dict(cell=c,description=game.inspect(c['x'],c['y']))
                   for c in hidden[::max(1,len(hidden)//8)]]
        assert all('unexplored' in s['description'].lower() for s in samples), samples
        assert game.turn == before
        result.update(samples=samples,turnFreeInspection=True,noHiddenGround=True,noHiddenMaterial=True)
        game.finish(automatic=True)
        write(ROOT/'.artifacts/valley-engine-unknown.json',result)
        print('PASS unrevealed Valley inspection, known material and hidden-ground/material invariants',flush=True)
        return result
    finally:
        cleanup(run,game)


def travel_depth(game, depth):
    game.cells.clear()
    event = tour.named(game,'wizlevelport')
    assert event['kind'] == 'line',event
    game.send('line '+str(depth))
    settle(game)


def travel_special(game, name):
    game.cells.clear()
    event = tour.named(game,'wizlevelport')
    assert event['kind'] == 'line',event
    game.send('line ?')
    event = game.wait_input()
    assert event['kind'] == 'menu',event
    row = next((i for i in event['items'] if i.get('selectable',True) and
                re.match(r'^'+re.escape(name.rstrip('-'))+':',i['text'].strip().lstrip('* ').strip())), None)
    assert row, ('World lacks original destination',name)
    game.send('menu '+str(row['id']))
    settle(game)


def boundaries(data):
    run, directory, game = clone(data,'boundaries')
    records = []
    try:
        settle(game)
        origin = tour.identity(game,directory)
        depth, selection = tour.gehennom_filler_depth(game)
        travel_depth(game,depth)
        destinations = [('Ordinary Gehennom filler','gehennom','Gehennom',None),
            ('asmodeus','asmodeus','Gehennom','asmodeus'),('baalz','baalz','Gehennom','baalz'),
            ('juiblex','juiblex','Gehennom','juiblex'),('orcus','valley','Gehennom','orcus'),
            ('wizard1',None,'Gehennom','wizard1'),('fakewiz1',None,'Gehennom','fakewiz1'),
            ('sanctum',None,'Gehennom','sanctum'),('tower3','vlad',"Vlad's Tower",'tower3'),
            ('Minetown',['mines','mines-built'],'The Gnomish Mines','minetn-')]
        for label,expected,branch,target in destinations:
            if target:
                travel_special(game,target)
            identity = tour.identity(game,directory)
            assert identity['branch'] == branch,(label,identity)
            records.append(dict(label=label,identity=identity,expectedMaterial=expected,
                                **material(game.cells.values(),expected)))
        town = tour.identity(game,directory)
        travel_depth(game,town['depth']-1)
        assert tour.identity(game,directory)['branch'] == 'The Gnomish Mines'
        records.append(dict(label='Ordinary Mines',identity=tour.identity(game,directory),
                            expectedMaterial='mines',**material(game.cells.values(),'mines')))
        travel_depth(game,1)
        assert tour.identity(game,directory)['branch'] == 'The Dungeons of Doom'
        records.append(dict(label='Main dungeon',identity=tour.identity(game,directory),
                            expectedMaterial=None,**material(game.cells.values(),None)))
        travel_special(game,'valley')
        assert tour.identity(game,directory) == origin
        records.append(dict(label='Return to original Valley',identity=origin,
                            expectedMaterial='valley',**material(game.cells.values(),'valley')))
        game.finish(automatic=True)
        result = dict(run=str(run),fillerSelection=selection,checks=records,passed=True,
                      setup='Upstream wizard travel among original world destinations; no level regeneration or map changes.')
        write(ROOT/'.artifacts/valley-material-context.json',result)
        print('PASS Valley material boundaries across',len(records),'original world destinations',flush=True)
        return result
    finally:
        cleanup(run,game)


def stair_point(game,directory,up):
    offset = len(game.events)
    tour.lua(game,directory,'for _,s in ipairs(nh.stairways()) do if not s.ladder and s.up == '
        +('true' if up else 'false')+' then nh.pline("VALLEY_STAIR:"..s.x..","..s.y); end; end;')
    points = [tuple(map(int,e['text'].split(':',1)[1].split(','))) for e in game.events[offset:]
              if e.get('text','').startswith('VALLEY_STAIR:')]
    assert len(points) == 1,points
    return points[0]


def named_depth(game, name):
    """Read the world's original destination identity, independently of cells."""
    event = tour.named(game,'wizlevelport')
    assert event['kind'] == 'line',event
    game.send('line ?')
    event = game.wait_input()
    assert event['kind'] == 'menu',event
    names = [re.match(r'^'+re.escape(name)+r': (\d+)',i['text'].strip().lstrip('* ').strip())
             for i in event['items']]
    matches = [int(match[1]) for match in names if match]
    assert len(matches) == 1,(name,matches)
    game.send('menu cancel')
    settle(game)
    return matches[0]


def connections(data):
    run,directory,game = clone(data,'connections')
    crossings = []
    try:
        settle(game)
        origin = tour.identity(game,directory)
        asmodeus_depth = named_depth(game,'asmodeus')
        for up,key,back in ((True,'<','>'),(False,'>','<')):
            entry = stair_point(game,directory,up)
            place(game,entry)
            game.cells.clear()
            event = game.command(key)
            if event['kind'] == 'yn' and event.get('prompt') == 'Are you sure you want to enter?':
                assert key == '>'
                game.send('key 121')
                event = game.wait_input()
            settle(game,event)
            outside = tour.identity(game,directory)
            assert outside['depth'] == origin['depth']+(-1 if up else 1),(origin,outside)
            if up:
                assert outside['branch'] == 'The Dungeons of Doom',outside
                expected = None
            else:
                assert outside['branch'] == 'Gehennom',outside
                # The first lower floor may naturally be Asmodeus's lair.
                expected = 'asmodeus' if outside['depth'] == asmodeus_depth else 'gehennom'
            checked = material(game.cells.values(),expected)
            arrival = game.cursor
            if up:
                # Upstream dungeon.lua declares Castle/Gehennom no_down.
                # The upward stair exists, but the Castle arrival has no
                # reciprocal stairs. Preserve and verify that gameplay rule.
                before = game.turn
                offset = len(game.events)
                settle(game,game.command('>'))
                assert game.cursor == arrival and game.turn == before
                assert tour.identity(game,directory) == outside
                messages = [e['text'] for e in game.events[offset:] if e['type'] == 'message']
                assert any("can't go down here" in m.lower() for m in messages),messages
                crossings.append(dict(command=key,origin=origin,destination=outside,
                    departure=entry,arrival=arrival,outside=checked,upwardExitOnly=True,
                    refusedReciprocalStair=True,messages=messages,
                    returnSetup='Upstream no_down branch has no reciprocal Castle stair. Wizard world travel returns to Valley solely for the next isolated stair check.'))
                travel_special(game,'valley')
                assert tour.identity(game,directory) == origin
                material(game.cells.values(),'valley')
                continue
            game.cells.clear()
            settle(game,game.command(back))
            assert tour.identity(game,directory) == origin
            assert game.cursor == entry,(entry,game.cursor)
            material(game.cells.values(),'valley')
            crossings.append(dict(command=key,returnCommand=back,origin=origin,destination=outside,
                                  departure=entry,arrival=arrival,returned=True,outside=checked))
        game.finish(automatic=True)
        result = dict(run=str(run),crossings=crossings,passed=True,
            setup='Read-only upstream stairway diagnostics locate original stairs; wizard placement then ordinary stair commands. No geometry or occupants replaced.')
        write(ROOT/'.artifacts/valley-engine-connections.json',result)
        print('PASS original Valley upward-only Castle connection and lower Gehennom stair roundtrip',flush=True)
        return result
    finally:
        cleanup(run,game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('prepare','engine','unknown','boundaries','connections'):
        parser.add_argument('--'+flag,action='store_true')
    args = parser.parse_args()
    ROOT.joinpath('.artifacts').mkdir(exist_ok=True)
    rows = prepare() if args.prepare else json.loads(INDEX.read_text())
    inspection = next(row for row in rows if row['metadata']['mode'] == 'inspection')
    exploration = next(row for row in rows if row['metadata']['mode'] == 'exploration')
    if args.engine:
        engine(inspection)
    if args.unknown:
        unknown(exploration)
    if args.boundaries:
        boundaries(inspection)
    if args.connections:
        connections(inspection)


if __name__ == '__main__':
    main()
