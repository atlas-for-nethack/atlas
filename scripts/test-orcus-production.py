#!/usr/bin/env python3
"""Check exact Valley reuse on original Orcus checkpoints in isolated sessions.

Freeze --baseline before integration, then run --engine and --native on the
rebuilt package. Source saves are never opened in place. Wizard protection,
mapping and city positioning belong to the disclosed original preparation.
These presentation checks do not claim completion of the Orcus encounter.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('orcus_prepare', ROOT/'scripts/prepare-orcus-review.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
checks, tour = prepare.checks, prepare.tour
BASELINE = ART/'orcus-production-baseline.json'
INDEX = ART/'orcus-production-prepared.json'
RESULTS = ART/'orcus-production-engine.json'
FIELDS = ('tile', 'glyph', 'groundTile', 'char', 'color', 'pet')
NAMES = {'lantern-modern':'Lantern Modern', 'soot-and-brass':'Soot & Brass Modern',
         'lantern':'Lantern Classic', 'soot-and-brass-classic':'Soot & Brass Classic'}


def preserved(rows):
    paths = [prepare.INDEX]
    for row in rows:
        run = Path(row['run'])
        paths.append(run/'metadata.json')
        paths.extend(p for p in (run/'game').rglob('*') if p.is_file())
    return {str(p):tour.digest(p) for p in sorted(paths)}


def freeze(rows):
    assert not BASELINE.exists(), 'Preserve the original baseline; do not overwrite it'
    frozen = []
    for row in rows:
        run, directory, game = checks.clone(row, 'orcus-baseline')
        try:
            checks.settle(game)
            assert tour.identity(game, directory) == row['metadata']['identity']
            assert list(game.cursor) == row['metadata']['arrival']
            cells = copy.deepcopy(list(game.cells.values()))
            checks.material(cells, None)
            terrain = checks.terrain_snapshot(game, directory)
            frozen.append(dict(sourceCheckpoint=row['run'], cells=cells, terrain=terrain,
                               turn=game.turn, evidence=str(run/'engine.jsonl')))
            game.finish(automatic=True)
            print('PASS canonical baseline', row['metadata']['case']['id'], row['metadata']['mode'], flush=True)
        finally:
            checks.cleanup(run, game)
    checks.write(BASELINE, dict(engine=tour.digest(tour.RES/'engine/nethack'),
        source=prepare.source_evidence(), checkpoints=preserved(rows), restores=frozen))


def restored(row, baseline):
    run, directory, game = checks.clone(row, 'orcus-production')
    previous = []
    try:
        checks.settle(game)
        meta = copy.deepcopy(row['metadata'])
        assert tour.identity(game, directory) == meta['identity']
        assert list(game.cursor) == meta['arrival'] and game.turn == baseline['turn']
        assert any('Restoring save file' in e.get('text', '') for e in game.events)
        observed = copy.deepcopy(list(game.cells.values()))
        old = {(c['x'], c['y']):c for c in baseline['cells']}
        assert set(game.cells) == set(old), 'Displayed coordinates changed'
        for cell in observed:
            for field in FIELDS:
                assert cell.get(field) == old[cell['x'], cell['y']].get(field), (field, cell)
        perception = checks.material(observed, 'valley')
        assert checks.terrain_snapshot(game, directory) == baseline['terrain'], 'Terrain or lighting changed'
        if meta['mode'] == 'exploration':
            assert perception['hiddenCells'] > 0
        before, inspections = game.turn, []
        for category, predicate, word in (
            ('wall', lambda c:1482 <= c['tile'] <= 1492, 'wall'),
            ('door', lambda c:1284 <= c['tile'] <= 1288, 'door'),
            ('boulder', lambda c:c['tile'] == 1266, 'boulder'),
            ('grave', lambda c:c['tile'] == 1310, 'grave'),
            ('altar', lambda c:c['tile'] == 1305, 'altar'),
            ('floor', lambda c:c.get('char') == '.', ''),
            ('unknown', lambda c:c['tile'] == 1469, '')):
            cell = next((c for c in observed if predicate(c)), None)
            if cell is None:
                continue
            description = game.inspect(cell['x'], cell['y'])
            assert description.strip() and (not word or word in description.lower()), (category, description)
            if category == 'unknown':
                assert any(w in description.lower() for w in ('unknown', 'unexplored', 'nothing'))
            assert game.turn == before, 'Inspection consumed a turn'
            inspections.append(dict(category=category, position=[cell['x'],cell['y']], description=description))
        meta.update(engine=tour.digest(tour.RES/'engine/nethack'),
            app=tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas'), checkpoint=str(run),
            displayedCells=observed, expectedMaterial='valley', integratedMaterial=True,
            designPreviewOnly=False, perception=perception, originalReviewCheckpoint=row['run'])
        # Save the unchanged arrival for native presentation, before the movement check.
        game.finish(automatic=True)
        previous = list(game.events)
        checks.write(run/'metadata.json', meta)
        game = checks.open_game(directory)
        checks.settle(game)
        assert (list(game.cursor), game.turn) == (meta['arrival'], baseline['turn'])
        assert checks.terrain_snapshot(game, directory) == baseline['terrain']
        checks.material(game.cells.values(), 'valley')
        # Keep the native source checkpoint untouched by testing movement in another clone.
        game.finish(automatic=True)
        print('PASS production restore', meta['case']['id'], meta['mode'], flush=True)
        return dict(run=str(run),metadata=meta), dict(case=meta['case']['id'],mode=meta['mode'],
            evidence=str(run/'engine.jsonl'), material=perception, turnFreeInspections=inspections,
            canonicalCellsPreserved=True, exactTerrainLightingAndMemoryPreserved=True,
            saveRestore=True)
    finally:
        checks.cleanup(run, game, previous)


def movement(row):
    run, directory, game = checks.clone(row, 'orcus-movement')
    try:
        checks.settle(game)
        # Use two already perceived ordinary floor squares, with upstream teleport
        # only as disclosed positioning. The following move is an ordinary command.
        origin = tuple(game.cursor)
        pairs = [(p,(p[0]+dx,p[1]+dy),key) for p,c in game.cells.items() if c.get('char') == '.'
            for dx,dy,key in checks.STEPS if game.cells.get((p[0]+dx,p[1]+dy),{}).get('char') == '.']
        for start, end, key in sorted(pairs, key=lambda r:abs(r[0][0]-origin[0])+abs(r[0][1]-origin[1]))[:16]:
            try:
                checks.place(game, start)
            except AssertionError:
                continue
            before = game.turn
            checks.settle(game, game.command(key))
            if game.cursor == end:
                # Fast heroes can move within the same displayed engine turn.
                assert game.turn >= before
                checks.material(game.cells.values(), 'valley')
                game.finish(automatic=True)
                return dict(run=str(run),origin=start,destination=end,command=key,turns=game.turn-before)
        raise AssertionError('No successful original-floor move in the bounded candidates')
    finally:
        checks.cleanup(run, game)


def door_cycle(row):
    spec = importlib.util.spec_from_file_location('orcus_door_checks', ROOT/'scripts/test-quest-outdoors.py')
    doors = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doors)
    run, directory, game = checks.clone(row, 'orcus-door')
    previous = []
    try:
        checks.settle(game)
        terrain = checks.terrain_snapshot(game, directory)
        candidates = [r for r in terrain if r[2] == 'door' and 'closed=true' in r[7]
                      and 'locked=false' in r[7] and 'trapped=false' in r[7]]
        for candidate in candidates:
            point = tuple(map(int,candidate[:2]))
            if game.cells.get(point,{}).get('tile') not in (1287,1288):
                continue
            try:
                approach, redirects = doors.place_near(game, point, 'valley')
                break
            except AssertionError:
                continue
        else:
            raise AssertionError('No approach to an original known unlocked untrapped door')
        for attempts in range(30):
            doors.direction(game, tour.named(game,'open'), point)
            if doors.door_state(game,directory,point)['isopen']:
                break
        else:
            raise AssertionError('Original door did not open within bounded attempts')
        checks.material(game.cells.values(),'valley')
        position, turn = game.cursor, game.turn
        terrain = checks.terrain_snapshot(game,directory)
        game.finish(automatic=True); previous = list(game.events)
        game = checks.open_game(directory); checks.settle(game)
        assert (game.cursor,game.turn) == (position,turn)
        assert checks.terrain_snapshot(game,directory) == terrain
        assert doors.door_state(game,directory,point)['isopen']
        for closes in range(30):
            doors.direction(game,tour.named(game,'close'),point)
            if doors.door_state(game,directory,point)['closed']:
                break
        else:
            raise AssertionError('Original door did not close within bounded attempts')
        checks.material(game.cells.values(),'valley')
        game.finish(automatic=True)
        print('PASS original ordinary door open, exact restore and close',flush=True)
        return dict(run=str(run),door=point,approach=approach,placementRedirects=redirects,
                    ordinaryOpen=True,openDoorExactRestore=True,ordinaryClose=True,
                    openAttempts=attempts+1,closeAttempts=closes+1,materialStable=True)
    finally:
        checks.cleanup(run,game,previous)


def boundaries(row):
    run, directory, game = checks.clone(row, 'orcus-boundaries')
    records = []
    try:
        checks.settle(game)
        origin = tour.identity(game, directory)
        depth, selection = tour.gehennom_filler_depth(game)
        checks.travel_depth(game, depth)
        records.append(dict(label='Unnamed Gehennom', **checks.material(game.cells.values(),'gehennom')))
        for target, expected in (('valley','valley'),('asmodeus','asmodeus'),('juiblex','juiblex'),
                ('baalz','baalz'),('wizard1',None),('fakewiz1',None),('sanctum',None),('tower3','vlad')):
            checks.travel_special(game, target)
            records.append(dict(label=target, identity=tour.identity(game,directory),
                                **checks.material(game.cells.values(),expected)))
            print('PASS boundary', target, flush=True)
        # Numeric depth travel stays within the current branch. Leave Vlad's
        # Tower through the named-level menu before checking Gehennom depths.
        checks.travel_special(game, 'orcus')
        checks.travel_depth(game, selection['invocationExcluded'])
        records.append(dict(label='Invocation approach', **checks.material(game.cells.values(),None)))
        checks.travel_depth(game, 1)
        records.append(dict(label='Main dungeon', **checks.material(game.cells.values(),None)))
        checks.travel_special(game,'orcus')
        assert tour.identity(game,directory) == origin
        records.append(dict(label='Return to original Orcus',identity=origin,
                            **checks.material(game.cells.values(),'valley')))
        game.finish(automatic=True)
        return dict(run=str(run),checks=records,fillerSelection=selection,passed=True)
    finally:
        checks.cleanup(run, game)


def native(rows):
    spec = importlib.util.spec_from_file_location('orcus_native', ROOT/'scripts/test-room-shapes.py')
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    results, scenes = [], {}
    for original in rows:
        row = copy.deepcopy(original)
        m = row['metadata']
        assert m['engine'] == tour.digest(tour.RES/'engine/nethack')
        assert m['app'] == tour.digest(tour.APP/'Contents/MacOS/NetHackAtlas')
        cells = m['displayedCells']
        if m['case']['id'] == 'orcus-graveyard':
            focus = next(c for c in cells if c['tile'] == 1310)
            x,y = focus['x'],focus['y']
        else:
            x,y = m['arrival']
        m['shapeBounds'] = [max(1,min(66,x-6)), max(0,min(11,y-5)), 14, 10]
        left,top,w,h = m['shapeBounds']
        visible = [c for c in cells if left<=c['x']<left+w and top<=c['y']<top+h]
        m['testTerrainTiles'] = [next(c['tile'] for c in visible if c.get('char') == '.')]
        key = m['case']['id']+'-'+m['mode']
        scenes[key] = dict(label=m['case']['label']+' / '+m['mode'],width=w,height=h,
                          cells=[dict(c,x=c['x']-left,y=c['y']-top) for c in visible])
        for tileset in NAMES:
            result = capture.native(row, tileset)
            actual = checks.displayed_cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            result.update(checks.material(actual,'valley'),mode=m['mode'],
                          engine=m['engine'],app=m['app'])
            old = {(c['x'],c['y']):c for c in cells}
            assert {(c['x'],c['y']) for c in actual} == set(old)
            for c in actual:
                assert all(c.get(f) == old[c['x'],c['y']].get(f) for f in FIELDS)
            results.append(result)
            checks.write(ART/'orcus-production-native.json',results)
            print('PASS native',key,tileset,flush=True)
    checks.write(ART/'orcus-production-review-manifest.json',dict(scenes=scenes))
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Orcus production review</title>',
        '<style>body{background:#101719;color:#e5e8df;font:17px system-ui;margin:24px}img{width:100%;max-width:1600px}a{color:#d6bb84}</style>',
        '<h1>Orcus-town: exact approved Valley reuse, integrated</h1>',
        '<p>Real packaged-app captures from the unchanged original saves. All four editions. '
        'Mapped arrival, unexplored arrival, local city boulder and mapped graveyard. '
        'Camera framing changes zoom and scrolling only. Upstream terrain, occupants, lighting and rules remain intact. '
        'The mapped graveyard does not claim a local encounter or successful teleport there.</p>']
    for r in results:
        label=html.escape(r['label']+' / '+r['mode']+' / '+NAMES[r['tileset']])
        src=Path(r['screenshot']).relative_to(ART).as_posix()
        body.append('<h2>'+label+'</h2><a href="'+src+'"><img src="'+src+'" alt="'+label+'"></a>')
    body.append('</html>')
    (ART/'orcus-native-review.html').write_text('\n'.join(body)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    assert sum((args.baseline,args.engine,args.native)) == 1, 'Choose one phase'
    rows=json.loads(prepare.INDEX.read_text())
    assert len(rows) == 4 and all(r['metadata']['worldSelected'] and r['metadata']['case']['source'] is None for r in rows)
    hashes=preserved(rows)
    try:
        if args.baseline:
            freeze(rows)
        elif args.native:
            native(json.loads(INDEX.read_text()))
        else:
            baseline=json.loads(BASELINE.read_text())
            assert hashes == baseline['checkpoints']
            assert prepare.source_evidence() == baseline['source']
            integrated, results = [], []
            for row, old in zip(rows,baseline['restores']):
                assert row['run'] == old['sourceCheckpoint']
                new,result=restored(row,old)
                integrated.append(new);results.append(result)
                checks.write(INDEX,integrated)
            movement_check=movement(integrated[0])
            doors=door_cycle(integrated[0])
            boundary_check=boundaries(integrated[0])
            checks.write(RESULTS,dict(restores=results,movement=movement_check,doors=doors,boundaries=boundary_check,
                source=baseline['source'],baselineEngine=baseline['engine'],
                engine=tour.digest(tour.RES/'engine/nethack'),originalCheckpointsPreserved=True,passed=True))
    finally:
        assert preserved(rows) == hashes, 'Original checkpoints changed'


if __name__ == '__main__':
    main()
