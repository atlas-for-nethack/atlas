#!/usr/bin/env python3
"""Reproduce vault escort cleanup on an unmodified generated dungeon level."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('buried',ROOT/'scripts/test-vaults-buried.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
tour=b.tour

def survey(r):
    # Read-only wizard survey locates a candidate in the generated level.
    # It does not author terrain or reveal hidden information in the app.
    start=len(r.game.events)
    tour.lua(r.game,r.directory,'''local ox,oy=nh.abscoord(0,0);
for y=0,20 do for x=1,79 do
 local m=nh.getmap(x-ox,y-oy);
 if m.mapchr=="." or m.mapchr=="#" then
  local gold=false;local o=obj.at(x-ox,y-oy);
  while o and not o:totable().NO_OBJ do
   if o:totable().otyp_name=="gold piece" then gold=true;end;o=o:next(true);
  end;
  nh.pline("CELL:"..x..":"..y..":"..m.roomno..":"..m.mapchr..":"..tostring(gold));
 end;
end end;''')
    groups={};corridors=set()
    for e in r.game.events[start:]:
        if not e.get('text','').startswith('CELL:'):continue
        _,x,y,room,char,gold=e['text'].split(':');p=(int(x),int(y))
        corridors.add(p)
        if char=='.' and int(room)>=3:groups.setdefault(room,[]).append((p,gold=='true'))
    for cells in groups.values():
        if len(cells)==4:
            points=[p for p,_ in cells]
            if len({p[0] for p in points})==len({p[1] for p in points})==2:return points,corridors-set(points)
    return None,corridors

def rest(g):
    g.command('m')
    return g.command('.')

def run(explore):
    r=b.Review();result={'run':str(r.run),'mode':'explore' if explore else 'debug'}
    try:
        config=r.directory/'sysconf'
        config.write_text(config.read_text()+'\nEXPLORERS=*\n')
        g=r.game;e=tour.named(g,'wizlevelport');g.send('line 3');tour.settle(g)
        for attempt in range(30):
            points,corridors=survey(r)
            if points:break
            e=tour.named(g,'wizmakemap')
            if e['kind']=='yn':g.send('key 121');e=g.wait_input()
            tour.settle(g,e)
        else:raise AssertionError('No natural vault in 30 generated levels')
        result.update(generations=attempt+1,vault=points)
        r.teleport(points[0])
        if explore:
            e=tour.named(g,'exploremode')
            while not e.get('command'):
                if e['kind']=='yn':g.send('key 121')
                elif e['kind']=='line':g.send('line yes')
                elif e['kind']=='menu':g.send('menu cancel')
                else:g.send('key 32')
                e=g.wait_input()
            assert any('now in non-scoring explore mode' in e.get('text','').lower() for e in g.events[-80:])
        start=len(g.events)
        for _ in range(100):
            e=rest(g)
            if e['kind']=='line':break
            tour.settle(g,e)
        else:raise AssertionError(('No natural guard',r.messages(start)))
        assert 'who are you' in e['prompt'].lower(),e
        g.send('line wizard');tour.settle(g)
        target=None;visited={g.cursor};keys={(-1,-1):'y',(0,-1):'k',(1,-1):'u',(-1,0):'h',(1,0):'l',(-1,1):'b',(0,1):'j',(1,1):'n'}
        for _ in range(200):
            if 'corridor disappears' in r.messages(start).lower() or (g.cursor in corridors and 'guard disappears' in r.messages(start).lower()):break
            guards=[p for p,c in g.cells.items() if p!=g.cursor and c.get('char')=='@' and 'guard' in g.inspect(*p).lower()]
            if guards:target=guards[0]
            if not guards and 'guard disappears' in r.messages(start).lower():
                destinations=sorted((p for p,c in g.cells.items() if (c.get('char') in ('.','#','<','>','+') or c.get('groundTile') in (1291,1292,1294,1295)) and p not in visited and p not in points and p!=g.cursor),key=lambda p:abs(p[0]-g.cursor[0])+abs(p[1]-g.cursor[1]))
                assert destinations,('No perceived exit',g.cursor)
                for destination in destinations:
                    try:b.walk(g,destination);break
                    except AssertionError as error:
                        if 'No perceived route' not in str(error):raise
                else:raise AssertionError(('No reachable exit',g.cursor))
                visited.add(g.cursor);continue
            assert target and target!=g.cursor,('Lost guard',g.cursor,r.messages(start))
            dx=target[0]-g.cursor[0];dy=target[1]-g.cursor[1]
            key='.' if guards and max(abs(dx),abs(dy))<=1 else keys[(max(-1,min(1,dx)),max(-1,min(1,dy)))]
            tour.settle(g,rest(g) if key=='.' else g.command(key))
        else:raise AssertionError(('Escort stalled',g.cursor,r.messages(start)))
        end=g.turn
        for _ in range(10):
            tour.settle(g,rest(g))
        assert g.turn>end
        assert 'corridor disappears' in r.messages(start).lower(),r.messages(start)
        result.update(messages=r.messages(start),exit=g.cursor,continuedTurns=g.turn-end)
        r.snapshot('Natural vault: escort finished',[1,0,79,21])
        result['restored']=True
        return result
    finally:r.close()

def main():
    results=[]
    for explore in (False,True):
        result=run(explore);results.append(result)
        (ROOT/'.artifacts/natural-vault-check.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
