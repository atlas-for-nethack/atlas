#!/usr/bin/env python3
"""Capture upstream room shapes in isolated native sessions for visual review.

First generate the fixtures with --prepare. --native captures both Modern sets;
all source checkpoints and owner sessions are preserved.
"""
import argparse
import collections
import html
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tour', ROOT/'scripts/playtest/prepare.py')
tour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tour)
INDEX = ROOT/'.artifacts/room-shapes-prepared.json'


def prepare():
    prepared = []
    for case in tour.catalog():
        if not case.get('shape'):
            continue
        data = json.loads(subprocess.check_output([sys.executable, str(ROOT/'scripts/playtest/prepare.py'),
            'prepare', '--case', case['id'], '--mode', 'inspection'], text=True))
        prepared.append(data)
        print('PREPARED', case['label'], flush=True)
    INDEX.write_text(json.dumps(dict(prepared=prepared, failed=[]), indent=2)+'\n')


def native(data, tileset):
    run = Path(tempfile.mkdtemp(prefix='room-shape-native-', dir=ROOT/'.artifacts'))
    shutil.copytree(Path(data['run'])/'game', run/'game')
    report = run/'diagnostics.jsonl'
    env = dict(os.environ, ATLAS_DATA_DIR=str(run/'game'), ATLAS_TEST_TILESET=tileset,
        ATLAS_TEST_SCENARIO='room-shape', ATLAS_TEST_ROOM_BOUNDS=json.dumps(data['metadata']['shapeBounds']),
        ATLAS_TEST_TERRAIN_TILES=json.dumps(data['metadata'].get('testTerrainTiles', [])),
        ATLAS_DIAGNOSTICS=str(report), ATLAS_SNAPSHOT=str(run/'game.png'))
    with (run/'application.log').open('w') as log:
        p = subprocess.Popen([str(tour.APP/'Contents/MacOS/NetHackAtlas'), '--self-test'],
                             env=env, stdout=log, stderr=log)
        try:
            code = p.wait(timeout=45)
        except subprocess.TimeoutExpired:
            p.terminate(); p.wait(timeout=10)
            raise AssertionError(('Native shape timed out', run))
    assert code == 0, (code, run)
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert events and all(e.get('ok') is True for e in events), (events, run)
    assert {'room-shape', 'complete'} <= {e['phase'] for e in events}, (events, run)
    assert (run/'room-shape.png').is_file(), run
    return dict(case=data['metadata']['case']['id'], label=data['metadata']['case']['label'],
                tileset=tileset, run=str(run), screenshot=str(run/'room-shape.png'))


def gallery(results, path=None, title="Room shapes"):
    path = path or ROOT/'.artifacts/room-shapes-review.html'
    body = ['<!doctype html><meta charset="utf-8"><title>'+html.escape(title)+': native captures</title>',
        '<style>body{background:#101719;color:#e3e5df;font:16px system-ui;margin:24px} '
        '.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:36px} '
        'img{width:100%}a{color:#d1b27a}h2{margin-bottom:8px}</style>',
        '<h1>'+html.escape(title)+': real native-app captures</h1><p>Left: Lantern Modern. Right: Soot &amp; Brass Modern. '
        'Inspection fixtures use the upstream named generators with random contents and lighting. '
        'Click a capture to inspect it at full size. These are review evidence, not approval.</p>']
    labels = dict.fromkeys(r['label'] for r in results)
    for label in labels:
        body.append('<h2>'+html.escape(label)+'</h2><div class="pair">')
        for r in results:
            if r['label'] != label: continue
            url = Path(r['screenshot']).relative_to(path.parent).as_posix()
            body.append(f'<a href="{url}"><img src="{url}" alt="{html.escape(label)}: {r["tileset"]}"></a>')
        body.append('</div>')
    path.write_text('\n'.join(body))
    return path


def movement(data):
    name=data['metadata']['case']['label'];run=Path(tempfile.mkdtemp(prefix='room-shape-movement-',dir=ROOT/'.artifacts'));directory=run/'game';shutil.copytree(Path(data['run'])/'game',directory)
    os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
    game=tour.load_game_module().Game(directory,name='wizard',options='color,!news,!autopickup,time,force_invmenu,menustyle:full')
    result={'shape':name,'run':str(run),'moves':[]}
    try:
        tour.settle(game);before=game.turn;assert game.cursor==tuple(data['metadata']['arrival'])
        game.inspect(*game.cursor);assert game.turn==before
        bounds=data['metadata']['shapeBounds']
        def inside(p):
            x,y,w,h=bounds
            return x<=p[0]<x+w and y<=p[1]<y+h
        vault = data['metadata']['case']['id'] == 'shape-water-surrounded-vault'
        if vault:
            result['movementDeferred'] = 'Phase 30: upstream vault excludes teleport arrival; visual and save/restore checks only.'
        if not inside(game.cursor) and not vault:
            target=next(p for p,c in game.cells.items() if inside(p) and c.get('char')=='.')
            event=tour.named(game,'teleport')
            if event['kind']=='menu' and event.get('how')==0:
                game.send('key 32');event=game.wait_input()
            assert event.get('targeting'),event
            game.send(f'position {target[0]} {target[1]}');tour.settle(game)
            assert game.cursor==target,(name,target,game.cursor)
            result['wizardPlacement']=target
        result['movementStart']=game.cursor
        # Route only through displayed plain floor inside this shape.
        for dx,dy,key in [(-1,-1,'y'),(1,-1,'u'),(-1,1,'b'),(1,1,'n')]:
            pending=collections.deque([(game.cursor,[])] if inside(game.cursor) else []);seen={game.cursor};chosen=None
            while pending:
                p,path=pending.popleft();x,y=p
                dest=(x+dx,y+dy)
                if all(inside(q) and game.cells.get(q,{}).get('char')=='.' for q in [dest,(x+dx,y),(x,y+dy)]):chosen=(path,key,dest);break
                if len(path)>=12:continue
                for mx,my,k in [(-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j')]:
                    q=(x+mx,y+my)
                    if inside(q) and q not in seen and game.cells.get(q,{}).get('char')=='.':seen.add(q);pending.append((q,path+[(k,q)]))
            if chosen:
                for k,dest in chosen[0]+[(chosen[1],chosen[2])]:
                    tour.settle(game,game.command(k));assert game.cursor==dest,(name,k,dest,game.cursor)
                result['moves'].append(key)
        if not result['moves'] and not vault:
            result['movementDeferred'] = 'No reachable plain-floor 2x2 area from arrival; contents/hazards are deferred to later phases.'
        p=game.cursor
        for dx,dy,k in [(-1,0,'h'),(1,0,'l'),(0,-1,'k'),(0,1,'j')]:
            if 1273<=game.cells.get((p[0]+dx,p[1]+dy),{}).get('tile',-1)<=1283:
                turn=game.turn;tour.settle(game,game.command(k));assert game.cursor==p and game.turn==turn
                result['blockedWall']=True;break
        result['finalPosition']=game.cursor;result['finalTurn']=game.turn
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        game=tour.load_game_module().Game(directory,name='wizard',options='color,!news,!autopickup,time,force_invmenu,menustyle:full');tour.settle(game)
        assert game.cursor==tuple(result['finalPosition']) and game.turn==result['finalTurn']
        game.finish(automatic=True);result['restored']=True
        print('PASS',name,result['moves'],flush=True)
    finally:
        (run/'latest-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:game.process.kill();game.process.wait()
    return result



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--movement', action='store_true', help='Check real diagonal moves inside each shape and save/restore')
    parser.add_argument('--case', action='append', help='Limit captures to these case IDs')
    args = parser.parse_args()
    if args.prepare: prepare()
    if args.movement:
        movements = []
        for data in json.loads(INDEX.read_text())['prepared']:
            if args.case and data['metadata']['case']['id'] not in args.case: continue
            movements.append(movement(data))
            (ROOT/'.artifacts/room-shapes-movement.json').write_text(json.dumps(movements, indent=2)+'\n')
    if not args.native: return
    results = []
    for data in json.loads(INDEX.read_text())['prepared']:
        if args.case and data['metadata']['case']['id'] not in args.case: continue
        for tileset in ('lantern-modern', 'soot-and-brass'):
            result = native(data, tileset)
            results.append(result)
            (ROOT/'.artifacts/room-shapes-native.json').write_text(json.dumps(results, indent=2)+'\n')
            print('PASS', result['label'], tileset, result['run'], flush=True)
    print('Gallery:', gallery(results))


if __name__ == '__main__':
    main()
