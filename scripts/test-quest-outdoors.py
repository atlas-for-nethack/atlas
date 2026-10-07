#!/usr/bin/env python3
"""Behavioral checks for approved remembered outdoor Quest ground selection.

The assertions use original engine checkpoints and independently known exterior
landmarks and enclosed altars. They do not reproduce the renderer's flood or
provide diagnostic terrain to the playable interface. Original saves remain
read-only sources; wizard placement is disclosed and does not replace terrain.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'.artifacts'
spec = importlib.util.spec_from_file_location('outdoor_shared',ROOT/'scripts/test-valley-level.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
tour = shared.tour
CHANGED = {'Mon-strt':None,'Pri-strt':None,'Pri-loca':'priest-temple',
           'Hea-strt':None,'Hea-loca':None}
FLOORS = (1291,1292,1293,1294,1295,1296)
CANONICAL = ('tile','glyph','char','color','pet','groundTile')


def expected(identifier, integrated, otherwise=None):
    """Lists describe permitted mixed tags, not a single engine material value."""
    if integrated and identifier in CHANGED:
        return [CHANGED[identifier],'quest-earth']
    return otherwise


def material(cells, policy, mode=None):
    cells = list(cells)
    allowed = policy if isinstance(policy,(list,tuple)) else [policy]
    known = [c for c in cells if c['tile'] not in (1469,1470)]
    hidden = [c for c in cells if c['tile'] in (1469,1470)]
    assert known
    bad = [c for c in known if c.get('material') not in allowed]
    assert not bad,(allowed,bad[:8])
    assert all('material' not in c and 'groundTile' not in c for c in hidden),'Unknown terrain metadata disclosed'
    earth = [c for c in known if c.get('material') == 'quest-earth']
    assert all(not (1273<=c['tile']<=1290 or c['tile'] in (1314,1315,1316,1317,1318,1319,1324)) for c in earth),'Ground-only outdoors context on architectural/hazard terrain'
    if mode == 'exploration':
        assert hidden
    return dict(knownCells=len(known),hiddenCells=len(hidden),expectedMaterial=policy,
                materialCounts=dict(Counter(c.get('material','absent') for c in cells)),
                noHiddenGround=True,noHiddenMaterial=True)


def save_hashes(row):
    p = Path(row['run'])/'game/save'
    return {str(f.relative_to(p)):tour.digest(f) for f in sorted(p.rglob('*')) if f.is_file()}


def clone(row,label):
    run = Path(tempfile.mkdtemp(prefix='quest-outdoors-'+label+'-',dir=ART))
    directory = run/'game'
    shutil.copytree(Path(row['run'])/'game',directory)
    assert tour.digest(directory/'nhdat') == tour.digest(tour.RES/'engine/nhdat')
    return run,directory,shared.open_game(directory)


def tagged(cells):
    return {(c['x'],c['y']):c.get('material') for c in cells
            if c['tile'] not in (1469,1470)}


def baseline_cells(identifier,mode):
    role = {'Mon':'monk','Pri':'priest','Hea':'healer'}[identifier.split('-')[0]]
    path = ART/({'monk':'monk-canonical-review-prepared.json',
                 'priest':'priest-baseline-review-prepared.json',
                 'healer':'healer-canonical-review-prepared.json'}[role])
    if not path.exists() and role == 'monk':
        # Monk embeds its frozen ordinary-restore baseline in the live index.
        path = ART/'monk-review-prepared.json'
    rows = json.loads(path.read_text())
    m = next(r['metadata'] for r in rows if r['metadata']['case']['id']==identifier and r['metadata']['mode']==mode)
    return m.get('canonicalBaselineCells',m['displayedCells'])


def check(row):
    m = row['metadata']; identifier = m['case']['id']; mode = m['mode']
    original = save_hashes(row)
    run,directory,game = clone(row,identifier+'-'+mode)
    previous = []
    try:
        shared.settle(game)
        assert tour.identity(game,directory) == m['identity']
        actual = list(game.cells.values())
        checked = material(actual,expected(identifier,True),mode)
        frozen = {(c['x'],c['y']):c for c in baseline_cells(identifier,mode)}
        # Source fixtures can redraw foregrounds across initial magic-map and
        # ordinary restore. Compare Priest exact canonical fields; other roles
        # use their frozen ordinary-restore boundary, including known support.
        differences = [dict(position=(c['x'],c['y']),old=frozen.get((c['x'],c['y'])),new=c)
                       for c in actual if (c['x'],c['y']) in frozen and
                       any(c.get(k)!=frozen[c['x'],c['y']].get(k) for k in CANONICAL)]
        assert not differences,('Original canonical fields changed',differences[:8])
        terrain = shared.terrain_snapshot(game,directory)
        before = game.turn
        observations = []
        if mode == 'inspection':
            base = CHANGED[identifier]
            # Exterior landmarks are independently visible trees, water or
            # actual open map edges, not an independently reimplemented flood.
            seeds = [c for c in actual if c['tile'] in FLOORS and
                     (c['x'] in (1,79) or c['y'] in (0,20) or
                      any(n['tile'] in (1290,1314) and abs(n['x']-c['x'])+abs(n['y']-c['y'])==1 for n in actual))]
            assert seeds,'No original exterior landmarks'
            assert all(c.get('material') == 'quest-earth' for c in seeds),('Exterior still stone',seeds[:10])
            observations.extend(dict(category='exterior-landmark',cell=c,description=game.inspect(c['x'],c['y'])) for c in seeds[:8])
            altars = [c for c in actual if 1305<=c['tile']<=1309]
            assert altars,'Original enclosed altar missing'
            assert all(c.get('material') == base for c in altars),('Temple altar became earth',altars)
            observations.extend(dict(category='enclosed-altar',cell=c,description=game.inspect(c['x'],c['y'])) for c in altars)
            walls = [c for c in actual if 1273<=c['tile']<=1283]
            doors = [c for c in actual if 1285<=c['tile']<=1288]
            assert walls and doors
            assert all(c.get('material') == base for c in walls+doors),('Architecture picked outdoor ground context',base)
            interiors = [c for c in actual if c['tile'] in FLOORS and c.get('material') == base]
            assert interiors,'No original stone interior'
            observations.extend(dict(category='interior-stone',cell=c,description=game.inspect(c['x'],c['y'])) for c in interiors[:4])
            if identifier == 'Pri-loca':
                graves = [c for c in actual if c['tile'] == 1310]
                assert graves and any(c.get('material') == 'quest-earth' for c in graves),'Original graveyard lacks earth support'
                observations.extend(dict(category='graveyard',cell=c,description=game.inspect(c['x'],c['y'])) for c in graves[:4])
        else:
            hidden = [c for c in actual if c['tile'] == 1469]
            for c in hidden[::max(1,len(hidden)//6)]:
                text = game.inspect(c['x'],c['y'])
                assert 'unexplored' in text.lower()
                observations.append(dict(category='unknown',cell=c,description=text))
        assert game.turn == before
        position,turn = game.cursor,game.turn
        remembered = tagged(game.cells.values())
        game.finish(automatic=True); previous = list(game.events)
        game = shared.open_game(directory); shared.settle(game)
        assert (game.cursor,game.turn) == (position,turn)
        assert tour.identity(game,directory) == m['identity']
        assert shared.terrain_snapshot(game,directory) == terrain
        assert tagged(game.cells.values()) == remembered,'Earth/stone tags changed on restore'
        material(game.cells.values(),expected(identifier,True),mode)
        game.finish(automatic=True)
        assert save_hashes(row) == original,'Original source save changed'
        result = dict(case=identifier,mode=mode,run=str(run),perception=checked,
                      canonicalGroundAndForegroundUnchanged=True,observations=observations,
                      turnFreeInspection=True,exactTerrainLightingMemoryRestore=True,
                      materialStableAcrossRestore=True,sourceSavePreserved=True,
                      engine=tour.digest(tour.RES/'engine/nethack'))
        print('PASS outdoors',identifier,mode,flush=True)
        return result
    finally:
        shared.cleanup(run,game,previous)




def door_state(game,directory,target):
    """Independent engine state for a known adjacent doorway, not renderer data.

    Active original gas effects can cover its foreground glyph. A window-port
    tile alone cannot establish whether the ordinary command opened/closed it.
    """
    marker = 'ATLAS_KNOWN_DOOR:'
    tour.lua(game,directory,'local ox,oy=nh.abscoord(0,0); local d=nh.getmap('+str(target[0])+'-ox,'+str(target[1])+'-oy); nh.pline("'+marker+'"..d.typ_name..","..tostring(d.flags.isopen)..","..tostring(d.flags.closed));')
    text = next(e['text'] for e in reversed(game.events) if e.get('text','').startswith(marker))
    typ,opened,closed = text.split(':',1)[1].split(',')
    return dict(type=typ,isopen=opened=='true',closed=closed=='true')

def direction(game,event,target):
    assert event.get('direction'),event
    dx,dy = target[0]-game.cursor[0],target[1]-game.cursor[1]
    index = {(-1,0):0,(0,-1):2,(1,0):4,(0,1):6}.get((dx,dy))
    assert index is not None,(game.cursor,target)
    game.send('key '+str(ord(event['directionKeys'][index])))
    shared.settle(game)


def place_near(game,target,wanted):
    """Place only on an original displayed bare adjacent surface."""
    choices = [(target[0]+dx,target[1]+dy) for dx,dy,_ in shared.STEPS
               if game.cells.get((target[0]+dx,target[1]+dy),{}).get('tile') in FLOORS
               and game.cells[target[0]+dx,target[1]+dy].get('material') == wanted]
    failures = []
    for point in choices:
        try:
            shared.place(game,point)
            return point,failures
        except AssertionError:
            failures.append(dict(requested=point,actual=game.cursor,
                reason='Upstream placement redirected; occupants and geometry remain unchanged.'))
    raise AssertionError(('No independently displayed adjacent approach',target,wanted,failures))


def door_memory(row):
    """Original Healer locate closed doorway and undiscovered inner threshold.

    Diagnostic terrain chooses existing test candidates only. Ordinary open,
    close and search commands perform transitions. No door flags or terrain are
    replaced. Wizard placement is recorded, and source save files are preserved.
    """
    original = save_hashes(row)
    run,directory,game = clone(row,'healer-locate-doors')
    previous = []
    result = dict(run=str(run),setup='Copied original Healer locate save. Diagnostic selection of an original untrapped unlocked doorway, disclosed wizard placement to original displayed floor; ordinary direction-bound open/close/search. No terrain, occupants or door flags replaced.')
    try:
        shared.settle(game)
        initial = shared.terrain_snapshot(game,directory)
        doors = [r for r in initial if r[2] == 'door' and 'closed=true' in r[7] and 'locked=false' in r[7] and 'trapped=false' in r[7]]
        assert doors,'No original closed unlocked untrapped outer door'
        attempts = []
        for row_terrain in doors:
            point = tuple(map(int,row_terrain[:2]))
            if game.cells.get(point,{}).get('tile') not in (1287,1288):
                continue
            try:
                approach,redirects = place_near(game,point,'quest-earth')
                break
            except AssertionError as error:
                attempts.append(str(error))
        else:
            raise AssertionError(('No reachable original outside doorway',attempts))
        closed = dict(game.cells[point])
        assert closed.get('material') is None,'Outer threshold must keep stone'
        before_tags = tagged(game.cells.values())
        for openings in range(30):
            direction(game,tour.named(game,'open'),point)
            if door_state(game,directory,point)['isopen']:
                break
        else:
            raise AssertionError(('Original door resisted bounded open attempts',point))
        opened = dict(game.cells[point])
        assert opened.get('material') is None
        assert game.cells[approach].get('material') == 'quest-earth'
        after_tags = tagged(game.cells.values())
        assert all(after_tags.get(p) == tag for p,tag in before_tags.items() if p in after_tags),'Opening leaked soil into interior'
        turn,position = game.turn,game.cursor
        terrain = shared.terrain_snapshot(game,directory)
        game.finish(automatic=True);previous = list(game.events)
        game = shared.open_game(directory);shared.settle(game)
        assert (game.cursor,game.turn) == (position,turn)
        assert door_state(game,directory,point)['isopen']
        assert shared.terrain_snapshot(game,directory) == terrain
        assert tagged(game.cells.values()) == after_tags,'Open doorway material changed on restore'
        for closes in range(30):
            direction(game,tour.named(game,'close'),point)
            if door_state(game,directory,point)['closed']:
                break
        else:
            raise AssertionError(('Original door resisted bounded close attempts',point,game.cells[point]))
        closed_again = dict(game.cells[point])
        assert closed_again.get('material') is None
        assert game.cells[approach].get('material') == 'quest-earth'
        result['ordinaryDoorCycle'] = dict(door=point,approach=approach,closed=closed,
            opened=opened,closedAgain=closed_again,closedState=door_state(game,directory,point),openAttempts=openings+1,
            placementRedirects=redirects,closeAttempts=closes+1,openDoorExactRestore=True,
            interiorExteriorTagsStable=True)
        secret_rows = [r for r in initial if r[2] == 'secret door']
        assert secret_rows,'No original secret inner door'
        errors = []
        for secret in secret_rows:
            target = tuple(map(int,secret[:2]))
            if not (1273<=game.cells.get(target,{}).get('tile',-1)<=1283):
                continue
            try:
                secret_approach,redirects = place_near(game,target,None)
                break
            except AssertionError as error:
                errors.append(str(error))
        else:
            raise AssertionError(('No original displayed stone approach to secret wall',errors))
        concealed = dict(game.cells[target])
        assert concealed.get('material') is None
        description = game.inspect(*target)
        assert description.lower().rstrip().endswith('(wall)') and 'secret door' not in description.lower(),description
        tags_before_search = tagged(game.cells.values())
        for searches in range(100):
            if game.cells[target]['tile'] in (1287,1288):
                break
            # The engine's ordinary m-prefix permits search beside creatures.
            game.command('m')
            shared.settle(game,game.command('s'))
        else:
            raise AssertionError(('Original secret door not discovered',target))
        discovered = dict(game.cells[target])
        assert discovered.get('material') is None
        assert 'door' in game.inspect(*target).lower()
        tags_after_search = tagged(game.cells.values())
        assert all(tags_after_search.get(p) == tag for p,tag in tags_before_search.items() if p in tags_after_search),'Secret-door discovery merged exterior and interior'
        position,turn = game.cursor,game.turn
        terrain = shared.terrain_snapshot(game,directory)
        game.finish(automatic=True);previous.extend(game.events)
        game = shared.open_game(directory);shared.settle(game)
        assert (game.cursor,game.turn) == (position,turn)
        assert shared.terrain_snapshot(game,directory) == terrain
        assert game.cells[target]['tile'] in (1287,1288)
        assert tagged(game.cells.values()) == tags_after_search
        material(game.cells.values(),expected('Hea-loca',True),'inspection')
        game.finish(automatic=True)
        result['ordinarySecretDiscovery'] = dict(target=target,approach=secret_approach,
            concealed=concealed,concealedInspection=description,discovered=discovered,
            searchCommands=searches,placementRedirects=redirects,
            originalHiddenDoorNotDisclosed=True,materialStableAcrossDiscoveryAndRestore=True)
        assert save_hashes(row) == original
        result['sourceSavePreserved'] = True
        print('PASS original Healer locate open/close, secret discovery, soil/stone memory and restore',flush=True)
        return result
    finally:
        shared.cleanup(run,game,previous)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--doors',action='store_true',help='Exercise original Healer locate doors and secret-door memory')
    args = parser.parse_args()
    rows = []
    for role in ('monk','priest','healer'):
        rows.extend(r for r in json.loads((ART/(role+'-review-prepared.json')).read_text())
                    if r['metadata']['case']['id'] in CHANGED)
    results = []
    for row in rows:
        results.append(check(row))
        shared.write(ART/'quest-outdoors-engine-results.json',dict(checks=results))
    if args.doors:
        healer_locate = next(r for r in rows if r['metadata']['case']['id']=='Hea-loca' and r['metadata']['mode']=='inspection')
        door_checks = door_memory(healer_locate)
        shared.write(ART/'quest-outdoors-engine-results.json',dict(checks=results,doors=door_checks))


if __name__ == '__main__':
    main()
