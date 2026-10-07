#!/usr/bin/env python3
"""Real-engine regional material boundaries, using isolated copied test saves.

Run after build-engine.sh finishes. This reads the current engine/runtime engine
by default. It never launches native UI or touches an owner's running save.
"""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gehennom',ROOT/'scripts/test-gehennom.py')
gehennom=importlib.util.module_from_spec(spec);spec.loader.exec_module(gehennom)
tour=gehennom.tour


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,default=ROOT/'engine/runtime')
    parser.add_argument('--prepared',type=Path,default=ROOT/'.artifacts/gehennom-engine-prepared.json')
    args=parser.parse_args()
    runtime=args.runtime.resolve()
    data=json.loads(args.prepared.read_text())[0]
    run=Path(tempfile.mkdtemp(prefix='gehennom-material-context-',dir=ROOT/'.artifacts'))
    directory=run/'game'
    shutil.copytree(Path(data['run'])/'game',directory)
    assert tour.digest(directory/'nhdat')==tour.digest(runtime/'nhdat'),'Checkpoint game data differs from test engine data'
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    module=tour.load_game_module();module.RUNTIME=runtime
    game=module.Game(directory,name='wizard',options=gehennom.OPTIONS)
    records=[]
    result=dict(run=str(run),engine=str(runtime/'nethack'),engineSHA256=tour.digest(runtime/'nethack'),
        checks=records,setup='Existing isolated Gehennom inspection checkpoint copied into a fresh directory. Upstream wizard level teleport only; no geometry changes.')
    output=ROOT/'.artifacts/gehennom-material-context.json'
    try:
        tour.settle(game)
        origin=tour.identity(game,directory)
        _,selection=tour.gehennom_filler_depth(game)
        assert origin['depth'] in selection['candidates'],(origin,selection)
        result['fillerSelection']=selection

        def check(label,expected,branch):
            identity=tour.identity(game,directory)
            assert identity['branch']==branch,(label,identity)
            known=[c for c in game.cells.values() if c['tile'] not in (1469,1470)]
            assert known,(label,'No known cells')
            assert all(c.get('material')==expected for c in known),(label,expected,
                [c for c in known if c.get('material')!=expected][:5])
            hidden=[c for c in game.cells.values() if c['tile'] in (1469,1470)]
            assert all('material' not in c and 'groundTile' not in c for c in hidden),(label,'Hidden terrain leaked')
            records.append(dict(label=label,identity=identity,expectedMaterial=expected,
                knownCells=len(known),hiddenCells=len(hidden),
                materialCounts=dict(Counter(c.get('material','absent') for c in game.cells.values()))))
            output.write_text(json.dumps(result,indent=2)+'\n')
            print('PASS',label,expected,identity['depth'],flush=True)

        def depth(number):
            game.cells.clear()
            event=tour.named(game,'wizlevelport');assert event['kind']=='line',event
            game.send('line '+str(number));tour.settle(game)

        def special(name):
            game.cells.clear();tour.teleport(game,name)

        check('Original unnamed Gehennom filler','gehennom','Gehennom')
        for name in ('valley','asmodeus','juiblex','baalz','orcus','wizard1','wizard2','wizard3','fakewiz1','fakewiz2','sanctum'):
            special(name);check(name+' excludes regional material',None,'Gehennom')
        depth(selection['invocationExcluded']);check('Invocation approach excludes regional material',None,'Gehennom')
        depth(origin['depth']);check('Return to original filler restores Gehennom material','gehennom','Gehennom')
        assert tour.identity(game,directory)==origin
        special('minetn-');check('Minetown uses Mines material','mines','The Gnomish Mines')
        town=tour.identity(game,directory)
        depth(town['depth']-1);check('Random Mines preserves Mines material','mines','The Gnomish Mines')
        special('minend-');check('Mines End uses Mines material','mines','The Gnomish Mines')
        depth(1);check('Main dungeon excludes regional material',None,'The Dungeons of Doom')
        special('valley');depth(origin['depth'])
        check('Return from other branches restores Gehennom material','gehennom','Gehennom')
        position,turn=game.cursor,game.turn
        game.finish(automatic=True);gehennom.trace(run,game,'before-restore.jsonl')
        game=module.Game(directory,name='wizard',options=gehennom.OPTIONS);tour.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        check('Exact save restore retains Gehennom material','gehennom','Gehennom')
        assert tour.identity(game,directory)==origin
        game.finish(automatic=True)
        result.update(passed=True,exactRestore=True,checkCount=len(records),position=position,turn=turn)
        output.write_text(json.dumps(result,indent=2)+'\n')
    finally:
        gehennom.cleanup(run,game)


if __name__=='__main__':main()
