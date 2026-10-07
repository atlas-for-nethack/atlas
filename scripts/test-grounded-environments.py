#!/usr/bin/env python3
"""Bounded actual-engine material checks using preserved original environments.

Visible landmark/room assertions do not read hidden room types. Diagnostic
terrain is captured only to prove original terrain, memory and light unchanged;
it is never supplied to renderer fixtures or used to classify presentation.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('grounded_prepare',ROOT/'scripts/prepare-grounded-environments.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
shared,tour=prep.shared,prep.tour
ART=prep.ART
RESULTS=ART/'grounded-environments-engine-results.json'
OUTDOORS={'Arc-strt','Arc-loca','Kni-strt','Bar-strt','Bar-loca','Ran-strt','Ran-fila','Tou-strt','Sam-strt','Sam-loca','Wiz-strt','Wiz-loca'}
CAVES={'Kni-fila','Kni-loca','Kni-filb','Kni-goal','Bar-fila','Bar-filb','Bar-goal','Ran-loca','Ran-filb','Ran-goal','Tou-fila','Tou-filb'}
WALLS=set(range(1273,1284))|set(range(1471,1482))
DOORS=set(range(1284,1289))
HIDDEN={1469,1470}


def policy(identifier):
    if identifier.startswith('minetn-'):return ['mines','mines-built']
    if identifier.startswith('medusa-'):return ['medusa','quest-earth']
    if identifier in CAVES:return ['caveman']
    if identifier in OUTDOORS:return ['samurai' if identifier.startswith('Sam-') else None,'quest-earth']
    if identifier.startswith('fill-garden') or identifier.startswith('forest-paths'):return [None,'quest-earth']
    return [None]


def perception(cells,identifier,mode,named_main=None):
    allowed=[None] if named_main and identifier.startswith('fill-garden') else policy(identifier);known=[c for c in cells if c['tile'] not in HIDDEN]
    hidden=[c for c in cells if c['tile'] in HIDDEN]
    assert known
    assert all('material' not in c and 'groundTile' not in c for c in hidden),'Hidden ground/material exposed'
    bad=[c for c in known if c.get('material') not in allowed]
    assert not bad,(identifier,allowed,bad[:8])
    if mode=='exploration':assert hidden,'Unrevealed arrival has no unknown cells'
    earth=[c for c in known if c.get('material')=='quest-earth']
    assert all(c['tile'] not in WALLS|DOORS|{1289,1290,1314,1315,1316,1317,1318,1319,1324} for c in earth),'Earth context on architecture/hazard'
    return dict(allowedMaterials=allowed,counts=dict(Counter(c.get('material','absent') for c in cells)),hiddenCells=len(hidden),unknownMetadataAbsent=True)


def known_floor(cell):
    return bool(cell and (cell['tile'] in prep.FLOORS or cell.get('groundTile') in prep.FLOORS) and cell['tile'] not in WALLS|DOORS|HIDDEN)


def visible_interior(cell):
    # Original visible pools/trees inside a complete stone perimeter do not
    # turn its remaining floor into an outdoor shore.
    return known_floor(cell) or bool(cell and cell['tile'] in (1290,1314,1315,1316,1317,1318,1319))


def bounded_rooms(cells):
    """Independent visible-room witnesses: four straight sightlines to walls.

    Require the complete perimeter and displayed floor support inside it. This
    deliberately checks only unambiguous existing rectangles, not general cave
    components or unknown geometry. No diagnostic terrain or room type is used.
    """
    grid={(c['x'],c['y']):c for c in cells}; rooms={}
    for c in cells:
        if c['tile'] not in prep.FLOORS:continue
        x,y=c['x'],c['y'];edges=[]
        for dx,dy,_ in shared.STEPS:
            edge=None
            for distance in range(1,25):
                p=x+dx*distance,y+dy*distance;n=grid.get(p)
                if not n:break
                if n['tile'] in WALLS|DOORS:edge=p;break
                if not visible_interior(n):break
            if edge is None:break
            edges.append(edge)
        if len(edges)!=4:continue
        left,right,top,bottom=edges[0][0],edges[1][0],edges[2][1],edges[3][1]
        if right-left<3 or bottom-top<3:continue
        perimeter=[(px,py) for px in range(left,right+1) for py in range(top,bottom+1) if px in (left,right) or py in (top,bottom)]
        interior=[grid.get((px,py)) for px in range(left+1,right) for py in range(top+1,bottom)]
        if all(grid.get(p,{}).get('tile') in WALLS|DOORS for p in perimeter) and all(visible_interior(n) for n in interior):
            rooms[left,top,right,bottom]=[n for n in interior if known_floor(n)]
    return rooms


def landmarks(cells,identifier,mode,named_main=None):
    if mode!='inspection':return dict(unrevealedArrival=True)
    floors=[c for c in cells if c['tile'] in prep.FLOORS]; rooms=bounded_rooms(cells)
    evidence=dict(visibleRectangularRooms=len(rooms))
    if identifier.startswith('minetn-'):
        assert any(c.get('material')=='mines' for c in floors),'Original cave/street lacks dirt context'
        for rectangle,inside in rooms.items():
            assert all(c.get('material')=='mines-built' for c in inside),('Visible enclosed room still dirt',identifier,rectangle,inside[:5])
        assert all(c.get('material')=='mines' for c in cells if c['tile'] in WALLS|DOORS),'Minetown wall/threshold context differs'
        evidence['enclosedRoomFloorsChecked']=sum(len(v) for v in rooms.values())
        evidence['caveStreetFloorSamples']=[c for c in floors if c.get('material')=='mines'][:4]
    elif named_main and identifier.startswith('fill-garden'):
        assert all(c.get('material') is None for c in cells),'Named main dungeon boundary gained Garden material'
        evidence.update(namedSpecialBoundary=named_main,retainsCanonicalMaterial=True)
    elif identifier in OUTDOORS or identifier.startswith(('medusa-','fill-garden','forest-paths')):
        earth=[c for c in floors if c.get('material')=='quest-earth']
        assert earth,('Original outdoor environment lacks earth',identifier)
        edge_floors=[c for c in floors if c['x'] in (1,79) or c['y'] in (0,20)]
        assert all(c.get('material')=='quest-earth' for c in edge_floors),('Actual visible map-edge ground lacks earth',identifier,edge_floors[:6])
        evidence['mapEdgeFloorSamples']=edge_floors[:6]
        base='medusa' if identifier.startswith('medusa-') else 'samurai' if identifier.startswith('Sam-') else None
        for rectangle,inside in rooms.items():
            assert all(c.get('material')==base for c in inside),('Visible enclosed room lacks stone',identifier,rectangle,inside[:5])
        assert all(c.get('material')==base for c in cells if c['tile'] in WALLS|DOORS),'Outdoor context leaked to architecture'
        evidence.update(exteriorFloorSamples=earth[:6],enclosedRoomFloorsChecked=sum(len(v) for v in rooms.values()),interiorFloorSamples=[c for c in floors if c.get('material')==base][:4])
    elif identifier in CAVES:
        assert all(c.get('material')=='caveman' for c in floors)
        evidence['naturalCaveFloorSamples']=floors[:4]
    else:
        assert all(c.get('material') is None for c in floors)
        evidence['retainedStoneFloorSamples']=floors[:4]
    return evidence


def move(game):
    """Try bounded original displayed bare floor pairs; retain active occupants."""
    pairs=[(p,(p[0]+dx,p[1]+dy),key) for p,c in game.cells.items() if c['tile'] in prep.FLOORS for dx,dy,key in shared.STEPS if game.cells.get((p[0]+dx,p[1]+dy),{}).get('tile') in prep.FLOORS]
    pairs.sort(key=lambda v:abs(v[0][0]-game.cursor[0])+abs(v[0][1]-game.cursor[1]))
    failures=[]
    for origin,target,key in pairs[:20]:
        try:shared.place(game,origin)
        except AssertionError:
            failures.append(dict(origin=origin,target=target,reason='Upstream placement redirected'));continue
        before=game.turn;shared.settle(game,game.command(key))
        if game.cursor==target and game.turn>=before:
            return dict(origin=origin,destination=target,command=key,turns=game.turn-before,preparation='Wizard placement on original displayed bare floor',priorAttempts=failures)
        failures.append(dict(origin=origin,target=target,actual=game.cursor,reason='Original occupants/traps blocked or redirected movement'))
    raise AssertionError(('No successful ordinary adjacent floor movement in 20 attempts',failures))


def check(row,movement):
    m=row['metadata'];identifier=m['case']['id'];mode=m['mode'];hashes=prep.save_hashes(row)
    run,directory,game=prep.clone(row,identifier+'-'+mode);previous=[]
    try:
        shared.settle(game);identity=tour.identity(game,directory);assert identity==m['identity']
        if identifier[:3] in (*prep.ROLES,'Sam','Wiz'):
            assert identity['branch']=='The Quest' and identity['role']==tour.ROLES[identifier[:3]],identity
        elif identifier.startswith('minetn-'):assert identity['branch']=='The Gnomish Mines',identity
        else:assert identity['branch']=='The Dungeons of Doom',identity
        cells=list(game.cells.values());old={(c['x'],c['y']):c for c in m['canonicalBaselineCells']}
        assert set(game.cells)==set(old)
        differences=[(p,k) for p,c in game.cells.items() for k in prep.CANONICAL if c.get(k)!=old[p].get(k)]
        assert not differences,('Original canonical fields changed',identifier,differences[:10])
        assert shared.terrain_snapshot(game,directory)==m['originalBaselineTerrainLightingMemory']
        named_main=prep.named_main_level(game,identity) if m['case'].get('fill')=='Garden' else None
        assert named_main==m.get('namedMainLevel')
        seen=perception(cells,identifier,mode,named_main);observed=landmarks(cells,identifier,mode,named_main)
        before=game.turn;inspections=[]
        candidates=[c for c in cells if c['tile'] in HIDDEN][:5] if mode=='exploration' else [c for c in cells if c['tile'] in prep.FLOORS][:3]
        for c in candidates:
            text=game.inspect(c['x'],c['y'])
            if c['tile'] in HIDDEN:assert 'unexplored' in text.lower() or 'nothing' in text.lower(),text
            inspections.append(dict(cell=c,description=text))
        assert game.turn==before
        moved=move(game) if movement and mode=='inspection' else None
        terrain=shared.terrain_snapshot(game,directory);position,turn=game.cursor,game.turn
        tags={(c['x'],c['y']):c.get('material') for c in game.cells.values()}
        game.finish(automatic=True);previous=list(game.events)
        game=prep.open_game(directory);shared.settle(game)
        assert (game.cursor,game.turn)==(position,turn)
        assert tour.identity(game,directory)==m['identity']
        assert shared.terrain_snapshot(game,directory)==terrain,'Terrain/memory/light changed on restore'
        assert {(c['x'],c['y']):c.get('material') for c in game.cells.values()}==tags,'Materials changed on restore'
        perception(list(game.cells.values()),identifier,mode,named_main)
        game.finish(automatic=True);assert prep.save_hashes(row)==hashes
        result=dict(case=identifier,mode=mode,run=str(run),identity=m['identity'],engine=tour.digest(prep.PACKAGED_RES/'engine/nethack'),canonicalOldNewIdentical=True,originalTerrainLightingMemoryUnchanged=True,perception=seen,landmarks=observed,turnFreeInspection=True,inspections=inspections,ordinaryMovement=moved,exactSaveRestore=True,materialStableAcrossRestore=True,sourceSavePreserved=True)
        print('PASS grounded',identifier,mode,flush=True);return result
    finally:shared.cleanup(run,game,previous)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',action='append');parser.add_argument('--no-movement',action='store_true');args=parser.parse_args()
    rows=json.loads(prep.INDEX.read_text());results=[]
    for row in rows:
        if args.case and row['metadata']['case']['id'] not in args.case:continue
        results.append(check(row,not args.no_movement));shared.write(RESULTS,results)
    print('Results:',RESULTS)

if __name__=='__main__':main()
