#!/usr/bin/env python3
"""Verify real Priest review saves, perceived altars, ground and stage lighting.

Diagnostic terrain is isolated test evidence, never input to the playable UI or
review scenes. No map/actor replacement and no player saves are used. Wizard
stage travel is distinct from ordinary one-step movement and save restoration.
"""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('priest_review',ROOT/'scripts/prepare-priest-review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
shared,tour = review.shared,review.tour
outdoors = review.outdoors
RESULTS = ROOT/'.artifacts/priest-engine-results.json'


def open_game(directory):
    os.environ.update(NETHACKDIR=str(directory),HACKDIR=str(directory),ATLAS_PLAY_MODE='standard')
    config = directory/'priest-test.nethackrc'
    config.write_text('')
    module = tour.load_game_module()
    class ClearAwareGame(module.Game):
        def next(self):
            event = super().next()
            if event['type'] == 'clear' and event.get('window') == 'map':
                self.cells.clear()
            return event
    return ClearAwareGame(directory,name='wizard',options=shared.OPTIONS,config=config)


def clone(row,label,integrated=False):
    run = Path(tempfile.mkdtemp(prefix='priest-'+label+'-',dir=ROOT/'.artifacts'))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat'), 'Stale checkpoint data'
    if not integrated:
        assert row['metadata']['engine'] == tour.digest(tour.RES/'engine/nethack'), 'Prepare checkpoints for current packaged engine'
    return run,directory,open_game(directory)


def snapshot(game,directory):
    # Reuse the independently observed engine terrain/lighting probe. These
    # hidden diagnostic rows remain absent from the scene/cell manifest.
    return shared.terrain_snapshot(game,directory)


def hashes(path):
    return {str(p.relative_to(path)):tour.digest(p) for p in sorted(path.rglob('*')) if p.is_file()}


def check(row,integrated):
    m = row['metadata']
    source_hashes = hashes(Path(row['run']))
    run,directory,game = clone(row,'engine-'+m['case']['id']+'-'+m['mode'],integrated)
    previous = []
    try:
        shared.settle(game)
        assert any('Restoring save file' in e.get('text','') for e in game.events)
        identity = tour.identity(game,directory)
        assert identity == m['identity']
        assert list(game.cursor) == list(m['arrival'])
        expected = review.expected_material(m['case']['id'],integrated)
        perceived = review.privacy(list(game.cells.values()),m['mode'],expected)
        baseline_cells = {(c['x'],c['y']):c for c in m['displayedCells']}
        canonical_fields = ('tile','glyph','char','color','pet','groundTile')
        diffs = [dict(position=p,before=baseline_cells.get(p),after=c)
                 for p,c in game.cells.items() if p in baseline_cells and
                 any(c.get(k) != baseline_cells[p].get(k) for k in canonical_fields)]
        assert not diffs, ('Canonical fields changed on restoring source checkpoint',diffs[:8])
        terrain = snapshot(game,directory)
        terrain_index = {(int(r[0]),int(r[1])):r for r in terrain}
        result = dict(case=m['case']['id'],mode=m['mode'],run=str(run),
            identity=identity,material=expected,perception=perceived,
            engine=tour.digest(tour.RES/'engine/nethack'),
            data=tour.digest(tour.RES/'engine/nhdat'),sources=m['sources'],
            initialTerrainCounts=dict(Counter(r[2] for r in terrain)),
            lightingCounts=dict(Counter(r[3] for r in terrain if r[2] == 'room')),
            originalWorldSelected=True,independentRestore=True,
            sourceCheckpointEngine=m['engine'],canonicalGlyphAndGroundPreserved=True)
        floors = Counter(c['tile'] for c in game.cells.values() if c.get('char') == '.')
        assert floors
        result['nativeRestoreTerrainTiles'] = [next(t for t in (1291,1292) if floors[t])]
        if m['case']['id'] == 'Pri-strt':
            assert all(r[3] == 'true' for r in terrain if r[2] == 'room'), result['lightingCounts']
        elif m['case']['id'] == 'Pri-loca':
            assert {'true','false'} <= set(result['lightingCounts']), result['lightingCounts']
        elif m['case']['id'] == 'Pri-goal':
            assert all(r[3] == 'false' for r in terrain if r[2] == 'room'), result['lightingCounts']
            assert result['initialTerrainCounts'].get('lava pool',0), result['initialTerrainCounts']
        # Inspect exactly displayed appearances, including graves, altars and
        # undead. Unknown actual altar positions come only from the diagnostic
        # clone probe and never enter the scene or the shipped UI.
        before,position = game.turn,game.cursor
        seen_altars = [c for c in game.cells.values() if 1305 <= c['tile'] <= 1309]
        altar_observations = []
        for c in seen_altars:
            text = game.inspect(c['x'],c['y'])
            assert 'altar' in text.lower(),text
            assert not any(k in c for k in ('alignment','align','altarmask','shrine'))
            assert c.get('groundTile') not in range(1305,1310),c
            altar_observations.append(dict(cell=c,description=text))
        if m['mode'] == 'inspection' and m['case']['id'] in ('Pri-strt','Pri-loca'):
            assert seen_altars,'Mapped original altar missing'
            assert all(c['tile'] == 1305 for c in seen_altars),seen_altars
            assert all('unaligned' in o['description'].lower() for o in altar_observations),altar_observations
        unseen_altars = []
        for p,r in terrain_index.items():
            if r[2] == 'altar' and game.cells.get(p,{}).get('tile') in (1469,1470):
                cell = game.cells[p]
                text = game.inspect(*p)
                assert 'unexplored' in text.lower() or cell['tile'] == 1470,text
                assert all(word not in text.lower() for word in ('altar','unaligned','lawful','chaotic','neutral'))
                assert 'groundTile' not in cell and 'material' not in cell
                unseen_altars.append(dict(position=p,displayedCell=cell,description=text))
        if m['mode'] == 'exploration':
            assert unseen_altars,'Home arrival must keep its distant altar unknown'
        observed = []
        for category,predicate in [
            ('grave',lambda c:c['tile'] == 1310),
            ('undead',lambda c:c.get('char') in ('Z','W')),
            ('wall',lambda c:1273 <= c['tile'] <= 1283),
            ('door',lambda c:1284 <= c['tile'] <= 1290),
            ('lava',lambda c:c['tile'] == 1316)]:
            matches = [c for c in game.cells.values() if predicate(c)]
            for c in matches[:8]:
                text = game.inspect(c['x'],c['y'])
                if category == 'grave':
                    assert 'grave' in text.lower(),text
                ground = c.get('groundTile')
                if ground is not None and category == 'grave':
                    assert ground in (1291,1292,1272),c
                elif ground is not None and category == 'undead':
                    assert ground in (1291,1292,1293,1294,1272,1316),c
                    if ground == 1316:
                        assert terrain_index[(c['x'],c['y'])][2] == 'lava pool',c
                observed.append(dict(category=category,cell=c,description=text))
        assert (game.turn,game.cursor) == (before,position), 'Hover changed game'
        result.update(knownAltarInspection=altar_observations,
            hiddenAltarInspection=unseen_altars,inspection=observed,turnFreeInspection=True,
            noAltarAlignmentLeak=True,originalTerrainAndLighting=terrain)
        origin = game.cursor
        step = next(((origin[0]+dx,origin[1]+dy,key) for dx,dy,key in shared.STEPS
                     if game.cells.get((origin[0]+dx,origin[1]+dy),{}).get('tile') in (1291,1292)),None)
        if step:
            turn = game.turn
            shared.settle(game,game.command(step[2]))
            if game.cursor == tuple(step[:2]):
                assert game.turn-turn == 1,(turn,game.turn)
                result['ordinaryMove'] = dict(origin=origin,destination=game.cursor,turns=1)
            else:
                result['movementDeferred'] = 'Original occupant or condition prevented movement; no relocation used.'
        else:
            result['movementDeferred'] = 'Natural arrival has no adjacent displayed bare floor.'
        saved_terrain = snapshot(game,directory)
        saved_position,saved_turn = game.cursor,game.turn
        game.finish(automatic=True)
        previous = list(game.events)
        game = open_game(directory)
        shared.settle(game)
        assert (game.cursor,game.turn) == (saved_position,saved_turn)
        assert tour.identity(game,directory) == identity
        assert snapshot(game,directory) == saved_terrain, 'Terrain, ground memory or light changed on restore'
        review.privacy(list(game.cells.values()),m['mode'],expected)
        game.finish(automatic=True)
        result.update(exactPositionTurnIdentityRestore=True,exactTerrainGroundLightingRestore=True)
        assert hashes(Path(row['run'])) == source_hashes, 'Source checkpoint changed'
        result['sourceCheckpointPreserved'] = True
        print('PASS',m['case']['id'],m['mode'],'perception, original light, movement and independent restore',flush=True)
        return result
    finally:
        shared.cleanup(run,game,previous)


def boundaries(row,integrated):
    run,directory,game = clone(row,'boundaries',integrated)
    records = []
    try:
        shared.settle(game)
        for label,target,branch,expected in [
            ('Priest home','Pri-strt','The Quest',review.expected_material('Pri-strt',integrated)),
            ('Ordinary dungeon before locate','oracle','The Dungeons of Doom',None),
            ('Priest locate','Pri-loca','The Quest',review.expected_material('Pri-loca',integrated)),
            ('Ordinary dungeon before goal','oracle','The Dungeons of Doom',None),
            ('Priest goal','Pri-goal','The Quest','gehennom' if integrated else None),
            ('Valley','valley','Gehennom','valley'),
            ('Ordinary dungeon','oracle','The Dungeons of Doom',None),
            ('Return to Priest home','Pri-strt','The Quest',review.expected_material('Pri-strt',integrated))]:
            if label == 'Priest home':
                pass  # Already restored here; same-level travel emits no redraw.
            elif target:
                shared.travel_special(game,target)
            else:
                shared.travel_depth(game,1)
            identity = tour.identity(game,directory)
            assert identity['branch'] == branch,(label,identity)
            records.append(dict(label=label,identity=identity,
                                **outdoors.material(game.cells.values(),expected)))
        game.finish(automatic=True)
        result = dict(run=str(run),checks=records,
                      setup='Upstream wizard travel among original world destinations; this tests material scope, not ordinary quest admission or progression.')
        shared.write(ROOT/'.artifacts/priest-material-boundaries.json',result)
        print('PASS Priest material boundaries across',len(records),'original world destinations',flush=True)
        return result
    finally:
        shared.cleanup(run,game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integrated',action='store_true')
    args = parser.parse_args()
    rows = json.loads(review.INDEX.read_text())
    results = []
    for row in rows:
        results.append(check(row,args.integrated))
        shared.write(RESULTS,dict(stages=results,integrated=args.integrated))
    boundary = boundaries(rows[0],args.integrated)
    shared.write(RESULTS,dict(stages=results,boundaries=boundary,integrated=args.integrated))


if __name__ == '__main__':
    main()
