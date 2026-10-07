#!/usr/bin/env python3
"""Exercise cold and barred upstream hellfill variants in disposable Gehennom.

Only the final random family choice in pinned hellfill.lua is fixed. Layout,
terrain placement, random contents and stairs still use upstream generators.
This is targeted fixture coverage, not naturally selected arrival coverage.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gehennom',ROOT/'scripts/test-gehennom.py')
gh=importlib.util.module_from_spec(spec);spec.loader.exec_module(gh)
tour=gh.tour
INDEX=ROOT/'.artifacts/gehennom-variants-prepared.json'
RESULTS=ROOT/'.artifacts/gehennom-variants-results.json'
SOURCE=ROOT/'vendor/NetHack-5.0.0/dat/hellfill.lua'
SELECTOR='local hellno = math.random(1, #hells);'


def assert_material(game):
    known=[c for c in game.cells.values() if c['tile'] not in (1469,1470)]
    assert known and all(c.get('material')=='gehennom' for c in known),known[:8]
    assert all('material' not in c and 'groundTile' not in c
               for c in game.cells.values() if c['tile']==1469)


def teleport(game,target):
    event=tour.named(game,'teleport')
    if event['kind']=='menu' and event.get('how')==0:
        game.send('key 32');event=game.wait_input()
    assert event.get('targeting'),event
    game.send(f'position {target[0]} {target[1]}');tour.settle(game)
    assert game.cursor==target,(target,game.cursor)


def prepare(base):
    source=SOURCE.read_text();assert source.count(SELECTOR)==1
    rows=[]
    for name,family in [('iron-bars',4),('cold',6)]:
        for attempt in range(1,13):
            run,directory,game=gh.start(base,'variant-'+name)
            try:
                identity=tour.identity(game,directory)
                assert identity['branch']=='Gehennom',identity
                code='des.reset_level();\n'+source.replace(SELECTOR,f'local hellno = {family};')+'\ndes.finalize_level();\n'
                game.cells.clear();tour.lua(game,directory,code)
                terrain=gh.terrain_inventory(game,directory)
                # Random family4 may use lava instead. Never rewrite it to bars.
                matched=(terrain.get('iron bars',0)>0 if name=='iron-bars' else
                         terrain.get('ice',0)>0 and terrain.get('pool',0)>0 and terrain.get('water',0)>0)
                if not matched:
                    gh.trace(run,game);print('RETRY',name,attempt,terrain,flush=True);continue
                hidden=[c for c in game.cells.values() if c['tile']==1469]
                assert hidden and all('groundTile' not in c and 'material' not in c for c in hidden)
                before=game.turn
                for cell in hidden[::max(1,len(hidden)//8)]:
                    assert 'unexplored' in game.inspect(cell['x'],cell['y']).lower()
                assert game.turn==before
                tour.settle(game,tour.named(game,'wizmap'))
                # Put the viewpoint on existing safe plain floor near the center;
                # do not add safe islands, remove monsters or change hazard cells.
                candidates=[p for p,c in game.cells.items() if c.get('char')=='.' and
                            any(game.cells.get((p[0]+dx,p[1]+dy),{}).get('char')=='.'
                                for dx,dy,key in gh.mines.STEPS)]
                assert candidates,'No plain floor pair available'
                target=min(candidates,key=lambda p:abs(p[0]-40)+abs(p[1]-10))
                teleport(game,target)
                metadata=copy.deepcopy(base['metadata'])
                metadata.update(case=dict(id='gehennom-'+name,label='Gehennom / '+name+' variant',group='Gehennom',branch='Gehennom'),
                    identity=identity,arrival=list(game.cursor),status=dict(game.status),
                    shapeBounds=[1,0,79,21],displayedCells=list(game.cells.values()),
                    displayedTileCounts=dict(Counter(str(c['tile']) for c in game.cells.values())),
                    terrainCounts=terrain,generatorFamily=family,
                    generatorSource=str(SOURCE.relative_to(ROOT)),generatorSha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    fixedSelector=f'local hellno = {family};',attempt=attempt,
                    noHiddenGround=True,noHiddenMaterial=True,hiddenCellCount=len(hidden))
                metadata['setup'].append('Targeted upstream hellfill family '+str(family)+': only final random family selector fixed. Geometry, hazards and contents unchanged. Ordinary Gehennom filler identity retained.')
                game.finish(automatic=True);gh.trace(run,game)
                (run/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
                rows.append(dict(run=str(run),metadata=metadata));INDEX.write_text(json.dumps(rows,indent=2)+'\n')
                print('PREPARED',name,terrain,run,flush=True);break
            finally:gh.cleanup(run,game)
        else:raise AssertionError('No requested variant within twelve upstream attempts: '+name)
    return rows


def engine(data):
    run,directory,game=gh.start(data,'variant-test')
    result=dict(case=data['metadata']['case']['id'],run=str(run))
    try:
        assert_material(game)
        identity=tour.identity(game,directory);assert identity==data['metadata']['identity']
        initial=gh.terrain_inventory(game,directory)
        result['terrainBefore']=initial
        assert initial==data['metadata']['terrainCounts'],(initial,data['metadata']['terrainCounts'])
        # Canonical glyphs must remain actual ice, pool/water or bars. The
        # regional material selector does not replace these gameplay features.
        expected={'ice':1315,'pool':1314,'water':1324,'iron bars':1289}
        samples={};before=game.turn
        for kind,tile in expected.items():
            if not initial.get(kind):continue
            cell=next((c for c in game.cells.values() if c.get('tile')==tile),None)
            assert cell,(kind,tile,'No visible expected canonical terrain')
            samples[kind]=dict(cell=cell,description=game.inspect(cell['x'],cell['y']))
            assert kind in samples[kind]['description'].lower(),samples[kind]
        assert game.turn==before
        result['inspection']=samples
        moves=[]
        for dx,dy,key in gh.mines.STEPS:
            p=(game.cursor[0]+dx,game.cursor[1]+dy)
            if game.cells.get(p,{}).get('char')=='.':
                origin=game.cursor;tour.settle(game,game.command(key))
                assert game.cursor==p,(origin,p,game.cursor)
                moves.append([origin,p]);break
        assert moves,'No safe plain floor step exercised'
        result.update(moves=moves,turnFreeInspection=True)
        position,turn=game.cursor,game.turn
        game.finish(automatic=True);gh.trace(run,game)
        game=tour.load_game_module().Game(directory,name='wizard',options=gh.OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert_material(game)
        assert tour.identity(game,directory)==identity
        after=gh.terrain_inventory(game,directory)
        assert after==initial,('Actual terrain changed',initial,after)
        result.update(restored=True,position=position,turn=turn,terrainAfter=after,
            restoredCells=list(game.cells.values()),noHiddenGround=True,noHiddenMaterial=True)
        game.finish(automatic=True)
        print('PASS',result['case'],'canonical terrain, safe step, exact restore',flush=True)
        return result
    finally:gh.cleanup(run,game)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prepare','engine','native'):parser.add_argument('--'+name,action='store_true')
    parser.add_argument('--runtime',type=Path,help='Optional engine runtime directory; default is packaged app engine')
    args=parser.parse_args()
    if args.runtime:
        original_load=tour.load_game_module
        runtime=args.runtime.resolve()
        def load_game():
            module=original_load();module.RUNTIME=runtime;return module
        tour.load_game_module=load_game
    rows=prepare(json.loads(gh.INDEX.read_text())[0]) if args.prepare else json.loads(INDEX.read_text())
    if args.engine:
        results=[]
        for row in rows:
            results.append(engine(row));RESULTS.write_text(json.dumps(results,indent=2)+'\n')
    if args.native:
        results=[]
        for row in rows:
            counts=row['metadata']['displayedTileCounts']
            row['metadata']['testTerrainTiles']=[int(t) for t in counts if int(t) in (1289,1314,1315,1316,1324)]
            for tileset in ('lantern-modern','soot-and-brass'):
                results.append(gh.mines.shapes.native(row,tileset))
                (ROOT/'.artifacts/gehennom-variants-native.json').write_text(json.dumps(results,indent=2)+'\n')
        gh.mines.shapes.gallery(results,ROOT/'.artifacts/gehennom-variants-review.html','Gehennom terrain variants')


if __name__=='__main__':main()
