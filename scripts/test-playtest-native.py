#!/usr/bin/env python3
"""Owner launcher integration: real native restore, report/resume, close, and reset copy."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parent.parent
APP=ROOT/'dist/Atlas.app/Contents/MacOS/NetHackAtlas'


def wait_for(check,process,seconds=35):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        result=check()
        if result:return result
        assert process.poll() is None,('App exited',process.returncode)
        time.sleep(.15)
    raise AssertionError('Native test timed out')


def events(run):
    try: lines=(run/'engine.jsonl').read_text().splitlines()
    except FileNotFoundError:return []
    result=[]
    for line in lines:
        try: result.append(json.loads(line))
        except json.JSONDecodeError:pass
    return result


def request(run,action,**kw):
    path=run/'request.tmp';path.write_text(json.dumps(dict(action=action,**kw)));path.replace(run/'request.json')


def start(run,tileset):
    log=open(run/'native.log','a')
    process=subprocess.Popen([str(APP),'--playtest'],env=dict(os.environ,ATLAS_PLAYTEST_RUN=str(run),ATLAS_TEST_TILESET=tileset),stdout=log,stderr=log)
    return process


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='minetn-7');parser.add_argument('--tileset',default='lantern-modern');args=parser.parse_args()
    data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),'prepare','--case',args.case,'--mode','inspection'],text=True))
    run=Path(data['run']);current=run;process=start(run,args.tileset)
    try:
        if args.case.startswith('tut-'):
            wait_for(lambda:any(e['type']=='status' and e.get('name')=='dungeon-level' and 'Tutorial' in e.get('value','') for e in events(run)),process)
        else:
            wait_for(lambda:any(e['type']=='input' and e.get('command') for e in events(run)),process)
        time.sleep(2) # Allow asynchronous tile decoding and layout before the image capture.
        before=len(events(run));request(run,'report',notes='Automated native report/resume verification; not a visual defect.')
        report=wait_for(lambda:json.loads((run/'report-status.json').read_text()) if (run/'report-status.json').exists() else None,process)
        folder=Path(report['report']);assert (folder/'screen.png').stat().st_size>10000
        display=json.loads((folder/'display.json').read_text());assert display['tileset']==args.tileset,display
        if args.case.startswith('tut-'):
            assert not report['hasSave'] and (folder/'NO-TUTORIAL-SAVE.txt').exists()
        else:
            assert report['hasSave'] and any((folder/'game/save').iterdir())
            wait_for(lambda:any(e['type']=='hello' for e in events(run)[before:]),process)
        request(run,'close');process.wait(timeout=15);assert process.returncode==0
        # Reset copies the pristine checkpoint into a new run without replacing old progress.
        reset=run.parent/uuid.uuid4().hex;reset.mkdir()
        shutil.copytree(Path(data['metadata']['checkpoint'])/'game',reset/'game')
        shutil.copy2(run/'metadata.json',reset/'metadata.json')
        current=reset;process=start(reset,args.tileset)
        wait_for(lambda:any(e['type']=='input' and e.get('command') for e in events(reset)),process)
        request(reset,'close');process.wait(timeout=15);assert process.returncode==0
        print(json.dumps(dict(passed=True,case=args.case,tileset=args.tileset,run=str(run),reset=str(reset),report=str(folder)),indent=2))
    finally:
        if process.poll() is None:
            request(current,'close')
            try:process.wait(timeout=12)
            except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':main()
