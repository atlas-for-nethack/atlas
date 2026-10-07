#!/usr/bin/env python3
"""Build real disposable checkpoints and verify they restore in the bundled engine."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('tour',ROOT/'scripts/playtest/prepare.py')
tour=importlib.util.module_from_spec(spec);spec.loader.exec_module(tour)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    ids=[c['id'] for c in tour.catalog()] if args.all else [
        'dungeon-1','mines-1','gehennom-1','minetn-7','soko1-2','medusa-4','castle',
        'Arc-fila','Wiz-goal','water','air','astral','room-temple','terrain-trees','tut-1']
    failures=[]; results=[]
    for id in ids:
        for mode in ['exploration','inspection']:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),'prepare','--case',id,'--mode',mode],capture_output=True,text=True,timeout=90)
            if result.returncode:
                failures.append([id,mode,result.stderr[-1800:]])
                print('FAIL',id,mode,result.stderr[-300:],flush=True);continue
            prepared=json.loads(result.stdout); run=Path(prepared['run']); metadata=prepared['metadata']
            directory=run/'game'
            for key in ['HOME','NETHACKDIR','HACKDIR']: os.environ[key]=str(directory)
            os.environ['ATLAS_PLAY_MODE']='standard'
            module=tour.load_game_module()
            # Wizard mode owns the upstream player name, as recorded in the save.
            game=module.Game(directory,name='wizard',options='color,!news,!autopickup,force_invmenu,menustyle:full')
            try:
                tour.settle(game)
                actual=tour.identity(game,directory)
                assert actual==metadata['identity'],(actual,metadata['identity'])
                # Inspection cannot advance time or discover additional cells.
                before=game.turn
                game.inspect(*game.cursor)
                assert game.turn==before
                game.finish(automatic=True)
                assert any((directory/'save').iterdir())
                results.append(dict(case=id,mode=mode,run=str(run),identity=actual))
                print('PASS',id,mode,actual,flush=True)
            except Exception as error:
                failures.append([id,mode,str(error)]); print('FAIL restore',id,mode,str(error),flush=True)
            finally:
                if game.process.poll() is None: game.process.kill();game.process.wait()
    output=tour.BASE/'verification.json'
    output.write_text(json.dumps(dict(passed=results,failed=failures),indent=2)+'\n')
    print(f'{len(results)} passed; {len(failures)} failed. {output}')
    assert not failures,failures

if __name__=='__main__':main()
