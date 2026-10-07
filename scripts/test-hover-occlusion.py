#!/usr/bin/env python3
"""Check map hover coordinates in the native app using copies of a bug report save.

The room-shape native scenario exercises real mouse event handlers for the hero,
explicit unknown cells and blank space below the grid. web/tiles.test.js checks
that unknown focus leaves foreground opacity unchanged. No owner game is opened.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--tileset',action='append')
    args=parser.parse_args()
    report=args.report.resolve()
    assert (report/'game/save').is_dir(), 'Expected a saved report game'
    cursor=None
    for line in (report/'engine.jsonl').read_text().splitlines():
        event=json.loads(line)
        if event.get('type')=='cursor' and 'playerX' in event:
            cursor=(event['playerX'],event['playerY'])
    assert cursor,'Report contains no hero position'
    spec=importlib.util.spec_from_file_location('shapes',ROOT/'scripts/test-room-shapes.py')
    shapes=importlib.util.module_from_spec(spec);spec.loader.exec_module(shapes)
    data={'run':str(report),'metadata':{'case':{'id':report.name,'label':'Reported hover'},
        'shapeBounds':[max(1,cursor[0]-7),max(0,cursor[1]-6),16,11]}}
    results=[]
    for tileset in args.tileset or ['lantern-modern','soot-and-brass','lantern','soot-and-brass-classic']:
        result=shapes.native(data,tileset)
        events=[json.loads(line) for line in (Path(result['run'])/'diagnostics.jsonl').read_text().splitlines()]
        required={'hover-known-square','hover-unexplored-square','hover-outside-grid','hover-map-leave','hover-dialog-close','hover-toolbar-dialog-close','hover-targeting'}
        assert required <= {event['phase'] for event in events},events
        results.append(result)
        (ROOT/'.artifacts/reported-hover-native.json').write_text(json.dumps(results,indent=2)+'\n')
        print('PASS',tileset,result['run'],flush=True)

if __name__=='__main__':main()
