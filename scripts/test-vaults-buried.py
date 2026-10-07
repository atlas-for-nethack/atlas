#!/usr/bin/env python3
"""Real-engine vault and excavation checks in isolated saves; native review captures."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
shapes=module('shapes',ROOT/'scripts/test-room-shapes.py');tour=shapes.tour
terrain=module('terrain',ROOT/'scripts/test-lantern-gameplay.py')
walk=module('walking',ROOT/'scripts/test-dungeon-baseline.py').walk_to
OPTIONS='color,!news,!autopickup,time,force_invmenu,menustyle:full'

class Review:
    def __init__(self):
        self.run=Path(tempfile.mkdtemp(prefix='vault-buried-',dir=ROOT/'.artifacts'))
        self.directory=self.run/'game';self.directory.mkdir()
        os.environ.update(HOME=str(self.directory),NETHACKDIR=str(self.directory),HACKDIR=str(self.directory))
        self.fixture=terrain.context.Fixture(str(self.directory));self.game=self.fixture.game
        self.snapshots=[];self.checks=[];self.events=[]
        tour.lua(self.game,self.directory,'nh.parse_config("OPTIONS=force_invmenu,menustyle:full");')
        e=tour.named(self.game,'levelchange');self.game.send('line 30');tour.settle(self.game)
        self.fixture.wish('blessed +5 pick-axe')
        self.fixture.wish('blessed wand of digging (0:50)')
        self.fixture.wish('blessed ring of slow digestion')
        e=tour.named(self.game,'puton')
        row=next(i for i in e['items'] if i.get('selectable') and 'ring' in i['text'])
        self.game.send('menu '+str(row['id']));e=self.game.wait_input()
        if e['kind']=='yn':self.game.send('key 108');e=self.game.wait_input()
        tour.settle(self.game,e)
        self.fixture.wish('blessed magic lamp')
        e=tour.named(self.game,'apply')
        row=next(i for i in e['items'] if i.get('selectable') and 'lamp' in i['text'])
        self.game.send('menu '+str(row['id']));tour.settle(self.game)
    def load(self,code):
        self.game.cells.clear();tour.lua(self.game,self.directory,code)
    def snapshot(self,label,bounds):
        g=self.game;p,t=g.cursor,g.turn;g.finish(automatic=True);self.events+=g.events
        stage=self.run/('stage-'+str(len(self.snapshots)));shutil.copytree(self.directory,stage/'game')
        self.snapshots.append(dict(run=str(stage),metadata=dict(case=dict(id='vault-buried-'+str(len(self.snapshots)),label=label),shapeBounds=bounds)))
        self.fixture.game=self.game=tour.load_game_module().Game(self.directory,name='wizard',options=OPTIONS)
        tour.settle(self.game);assert (self.game.cursor,self.game.turn)==(p,t), ((p,t),(self.game.cursor,self.game.turn))
    def apply_pick(self,direction):
        e=tour.named(self.game,'apply');assert e['kind']=='menu',e
        row=next(i for i in e['items'] if i.get('selectable') and 'pick-axe' in i['text'])
        self.game.send('menu '+str(row['id']));e=self.game.wait_input();assert e.get('direction'),e
        tour.settle(self.game,self.game.command(direction))
    def zap(self,direction):
        e=tour.named(self.game,'zap');assert e['kind']=='menu',e
        row=next(i for i in e['items'] if i.get('selectable') and 'wand' in i['text'])
        self.game.send('menu '+str(row['id']));e=self.game.wait_input();assert e.get('direction'),e
        tour.settle(self.game,self.game.command(direction))
    def messages(self,start):return ' '.join(e.get('text','') for e in self.game.events[start:] if e['type']=='message')
    def aside(self,target):
        for _ in range(30):
            if self.game.cursor!=target:return
            tour.settle(self.game,self.game.command('h'))
        raise AssertionError('Could not climb out of pit')
    def teleport(self,p):
        e=tour.named(self.game,'teleport')
        if e['kind']=='menu' and e.get('how')==0:self.game.send('key 32');e=self.game.wait_input()
        assert e.get('targeting'),e
        self.game.send(f'position {p[0]} {p[1]}');tour.settle(self.game)
        assert self.game.cursor==p,(p,self.game.cursor)
    def close(self):
        self.events+=self.game.events
        (self.run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.events))
        self.fixture.close()

BURIAL_MAP='''des.reset_level();des.level_init({style="solidfill",fg=" "});des.level_flags("noflip","nomongen");
des.map({x=25,y=5,lit=1,map=[[
----------------
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
----------------
]]});des.region({region={1,1,14,8},type="ordinary",lit=1});
des.teleport_region({region={2,2,2,2}});des.stair("up",1,1);des.stair("down",14,8);
'''
VAULT_MAP='''des.reset_level();des.level_init({style="solidfill",fg=" "});des.level_flags("noflip","nomongen");
des.map({x=10,y=3,map=[[
----------                  
|........|                  
|........|              ----
|.........###########   |..|
|........|              |..|
|........|              ----
----------                  
]]});
des.region({region={1,1,8,5},type="ordinary",lit=1,irregular=true});
des.region({region={25,3,26,4},type="vault",lit=1,filled=1});
des.stair("up",1,1);des.stair("down",7,5);
des.finalize_level();
'''

def excavation(r):
    # A controlled chest supplements the original-fill survey and gives a stable
    # ordinary-command dig target without exposing hidden state in production.
    r.load(BURIAL_MAP+'''des.object({id="chest",x=3,y=2,buried=true,locked=false,trapped=false,contents=function() des.object({id="diamond"});end});
des.finalize_level();''')
    r.teleport((27,7));g=r.game;target=(28,7);before=g.turn
    assert 'chest' not in g.inspect(*target).lower() and g.turn==before
    assert g.cells[target]['char']=='.'
    tour.settle(g,g.command('l'))
    hints=next(e for e in reversed(g.events) if e['type']=='context')['commands']
    assert not {'loot','pickup','tip'} & {h['name'] for h in hints}
    r.snapshot('Buried chest: ordinary floor before digging',[25,5,16,10]);g=r.game
    start=len(g.events);r.apply_pick('>')
    for _ in range(150):
        if 'pit' in r.messages(start).lower():break
        tour.settle(g,g.command('.'))
    else:raise AssertionError('Pick never completed the pit')
    assert 'you see here a chest' in r.messages(start).lower(),r.messages(start)
    r.checks.append(dict(check='Pick-axe digs up concealed chest',messages=r.messages(start)))
    e=tour.named(g,'loot');menus=[]
    for _ in range(12):
        if e.get('command'):break
        if e['kind']=='menu':menus+=e['items'];g.send('menu cancel')
        elif e['kind']=='yn':g.send('key 121')
        else:g.send('key 27')
        e=g.wait_input()
    assert any('take' in i['text'].lower() for i in menus),menus
    tour.settle(g,e);r.checks.append(dict(check='Unearthed chest opens ordinary container menu'))
    r.aside(target);assert 'chest' in g.inspect(*target).lower()
    r.snapshot('Chest unearthed in a pit',[25,5,16,10]);g=r.game
    r.load(BURIAL_MAP+'''local body=des.object({id="corpse",montype="gnome",x=3,y=2,buried=true});
body:stop_timer("rot-corpse");body:start_timer("zombify-mon",1000);des.finalize_level();''')
    r.teleport((27,7));g=r.game;assert g.cells[target]['char']=='.' and 'corpse' not in g.inspect(*target).lower()
    tour.settle(g,g.command('l'));r.snapshot('Buried zombie corpse: hidden before digging',[25,5,16,10]);g=r.game
    start=len(g.events);r.apply_pick('>')
    for _ in range(150):
        if 'pit' in r.messages(start).lower():break
        tour.settle(g,g.command('.'))
    else:raise AssertionError('Corpse pit never completed')
    # Digging may offer immediate pickup; settle cancels it to leave evidence.
    text=r.messages(start).lower()
    assert 'gnome corpse' in text,text
    r.checks.append(dict(check='Pick-axe unearths zombie-timed corpse',messages=r.messages(start),inspection=text))
    r.aside(target);assert 'corpse' in g.inspect(*target).lower()
    r.snapshot('Corpse unearthed in a pit',[25,5,16,10])
    g=r.game;start=len(g.events)
    for _ in range(1600):
        if 'zombie' in g.inspect(*target).lower():break
        tour.settle(g,g.command('.'))
    else:raise AssertionError('Unearthed corpse did not rise on its retained timer')
    r.checks.append(dict(check='Unearthed corpse retains its zombie timer',messages=r.messages(start)))
    r.snapshot('Unearthed corpse rises as a zombie',[25,5,16,10])

def buried_source(fill):
    code=(tour.DAT/'themerms.lua').read_text()
    code+='''
local original_engraving=des.engraving;
des.engraving=function(t)
 local x,y=nh.abscoord(t.coord.x,t.coord.y);
 nh.pline("CLUE:"..x..":"..y..":"..t.text);
 return original_engraving(t);
end;
des.reset_level();des.level_init({style="solidfill",fg=" "});des.level_flags("noflip","nomongen");
des.map({x=1,y=0,map=[[
----------------
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
|..............|
----------------
]]});
des.region({region={1,1,14,8},type="themed",lit=1,contents=function(rm)
 themeroom_fills[assert(lookup_by_name("Buried treasure",true))].contents(rm);
end});
des.stair("up",1,1);des.stair("down",14,8);
post_level_generate();des.finalize_level();
'''
    return code.replace('lookup_by_name("Buried treasure",true)', 'lookup_by_name('+json.dumps(fill)+',true)')

def source_zombies(r):
    r.load(buried_source('Buried zombies'));g=r.game;before=g.turn
    for y in range(1,9):
        for x in range(2,16):
            assert not any(word in g.inspect(x,y).lower() for word in ('corpse','zombie'))
    assert before==g.turn
    r.snapshot('Original buried-zombie room: concealed corpses',[1,0,16,10]);g=r.game
    start=len(g.events);turn=g.turn
    for _ in range(1500):
        if any(c.get('char')=='Z' for c in g.cells.values()):break
        tour.settle(g,g.command('.'))
    else:raise AssertionError('Original buried-zombie timers never produced visible zombies')
    r.checks.append(dict(check='Original buried corpses stay hidden then rise on original timers',elapsed=g.turn-turn,messages=r.messages(start)))
    r.snapshot('Original buried-zombie room: zombies emerge',[1,0,16,10])

def source_treasure(r):
    r.load(buried_source('Buried treasure'));g=r.game
    marker=next(e['text'] for e in reversed(g.events) if e.get('text','').startswith('CLUE:'))
    _,x,y,clue=marker.split(':',3);position=(int(x),int(y));start=len(g.events)
    walk(g,position)
    # If the hero arrived on the engraving, explicitly read the square.
    tour.settle(g,tour.named(g,'look'))
    assert clue in r.messages(start),r.messages(start)
    target=list(position)
    for n,direction in re.findall(r'(\d+) (east|west|north|south)',clue):
        delta={'east':(1,0),'west':(-1,0),'north':(0,-1),'south':(0,1)}[direction]
        target=[target[i]+int(n)*delta[i] for i in (0,1)]
    target=tuple(target);assert 'chest' not in g.inspect(*target).lower()
    r.snapshot('Original buried treasure: read the Dig clue',[1,0,16,10]);g=r.game
    walk(g,target);start=len(g.events);r.apply_pick('>')
    for _ in range(150):
        if 'you see here a chest' in r.messages(start).lower():break
        tour.settle(g,g.command('.'))
    else:raise AssertionError(('Original clue did not locate treasure',clue,target,r.messages(start)))
    r.checks.append(dict(check='Original treasure engraving leads to buried chest',clue=clue,target=target,messages=r.messages(start)))
    # Stage the screenshot with the object visible beside the hero.
    if target[0]>2:r.aside(target)
    else:
        for _ in range(30):
            if g.cursor!=target:break
            tour.settle(g,g.command('l'))
    assert 'chest' in g.inspect(*target).lower()
    r.snapshot('Original treasure unearthed at the clue destination',[1,0,16,10])


def vault(r):
    r.load(VAULT_MAP)
    r.teleport((30,6));g=r.game
    assert g.cursor==(30,6),g.cursor
    assert 'unexplored' in g.inspect(35,6).lower()
    r.snapshot('Detached vault before discovery',[10,3,28,7]);g=r.game
    start=len(g.events);r.zap('l')
    for _ in range(5):tour.settle(g,g.command('l'))
    assert g.cursor==(35,6),g.cursor
    assert any(c.get('char')=='$' for p,c in g.cells.items() if 35<=p[0]<=36 and 6<=p[1]<=7)
    r.checks.append(dict(check='Digging tunnel discovers real vault and gold',messages=r.messages(start)))
    r.snapshot('Vault discovered through a dug tunnel',[10,3,28,7])
    # Fresh unbreached vault for the independent guard escort check.
    r.load(VAULT_MAP);r.teleport((16,5));r.teleport((36,7));g=r.game
    # No pickup: the no-gold path must allow peaceful escort.
    start=len(g.events)
    for _ in range(80):
        e=g.command('.')
        if e['kind']=='line':break
        tour.settle(g,e)
    else:
        tour.lua(g,r.directory,'local ox,oy=nh.abscoord(0,0); for y=6,7 do for x=35,36 do local m=nh.getmap(x-ox,y-oy);nh.pline("POS:"..x..","..y..":"..m.roomno..":"..m.mapchr);end;end;')
        raise AssertionError(r.messages(start))
    assert 'who are you' in e['prompt'].lower(),e
    g.send('line wizard');tour.settle(g)
    assert 'follow me' in r.messages(start).lower(),r.messages(start)
    r.checks.append(dict(check='Real vault guard asks identity and offers escort',messages=r.messages(start)))
    r.snapshot('Vault guard opens an exit',[10,3,28,7])
    escort(r)
    r.load(VAULT_MAP);r.teleport((16,5));r.teleport((36,7));g=r.game
    e=tour.named(g,'pickup')
    if e['kind']=='menu':
        row=next(i for i in e['items'] if i.get('selectable') and 'gold' in i['text'])
        g.send('menu '+str(row['id']));e=g.wait_input()
    tour.settle(g,e);start=len(g.events)
    for _ in range(100):
        e=g.command('.')
        if e['kind']=='line':break
        tour.settle(g,e)
    else:raise AssertionError('No guard for gold-carrying visitor')
    assert 'who are you' in e['prompt'].lower(),e
    g.send('line wizard');tour.settle(g)
    assert 'drop that gold' in r.messages(start).lower(),r.messages(start)
    e=tour.named(g,'drop');assert e['kind']=='menu',e
    row=next(i for i in e['items'] if i.get('selectable') and 'gold' in i['text'])
    g.send('menu '+str(row['id']));tour.settle(g)
    r.checks.append(dict(check='Guard requests gold; normal drop returns it',messages=r.messages(start)))
    escort(r)

def escort(r):
    g=r.game;start=len(g.events)
    target=None
    keys={(-1,-1):'y',(0,-1):'k',(1,-1):'u',(-1,0):'h',(1,0):'l',(-1,1):'b',(0,1):'j',(1,1):'n'}
    for _ in range(100):
        if g.cursor[0]<=30:break
        guards=[p for p,c in g.cells.items() if p!=g.cursor and c.get('char')=='@' and 'guard' in g.inspect(*p).lower()]
        if guards:target=guards[0]
        if not guards and 'guard disappears' in r.messages(start).lower():
            walk(g,(30,6));break
        assert target and target!=g.cursor,('Lost guard route',g.cursor,r.messages(start))
        dx=target[0]-g.cursor[0];dy=target[1]-g.cursor[1]
        # Follow behind without attacking the peaceful guard.
        key='.' if guards and max(abs(dx),abs(dy))<=1 else keys[(max(-1,min(1,dx)),max(-1,min(1,dy)))]
        tour.settle(g,g.command(key))
    else:raise AssertionError(('Escort stalled',g.cursor,r.messages(start)))
    r.checks.append(dict(check='Follow peaceful vault guard to ordinary corridor',position=g.cursor,messages=r.messages(start)))
    r.snapshot('Vault escort reaches ordinary corridor',[10,3,28,7])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true');parser.add_argument('--catalog',action='store_true');args=parser.parse_args()
    if args.catalog:
        survey_catalog();return
    r=Review()
    try:
        excavation(r);source_treasure(r);source_zombies(r);vault(r)
        index=dict(run=str(r.run),checks=r.checks,snapshots=r.snapshots,
            warnings=[c for c in r.checks if 'Program in disorder' in c.get('messages','')])
        (ROOT/'.artifacts/vault-buried-review.json').write_text(json.dumps(index,indent=2)+'\n')
        print(json.dumps(index,indent=2),flush=True)
    finally:r.close()
    if args.native:
        results=[]
        for scene in index['snapshots']:
            for atlas in ('lantern-modern','soot-and-brass'):
                results.append(shapes.native(scene,atlas));print('CAPTURED',scene['metadata']['case']['label'],atlas,flush=True)
                (ROOT/'.artifacts/vault-buried-native.json').write_text(json.dumps(results,indent=2)+'\n')
        path=shapes.gallery(results,ROOT/'.artifacts/vault-buried-review.html','Vaults and buried rooms')
        path.write_text(path.read_text().replace('Inspection fixtures use the upstream named generators with random contents and lighting.',
            'Original buried-treasure generator plus controlled excavation and real vault fixtures. All interactions run through the bundled NetHack engine.'))
        if index['warnings']:
            path.write_text(path.read_text().replace('<h1>',
                '<p><strong>Open issue:</strong> Vault guard cleanup emits a screen-update warning at (0,0). '
                'The exit and corridor restoration complete. See the item 17 review for disposition.</p><h1>',1))
        print(path)

def survey_catalog():
    results=[]
    for case in tour.catalog():
        if not case.get('buriedFill'):continue
        for mode in ('inspection','exploration'):
            data=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/playtest/prepare.py'),
                'prepare','--case',case['id'],'--mode',mode],text=True))
            run=Path(tempfile.mkdtemp(prefix='buried-catalog-',dir=ROOT/'.artifacts'));directory=run/'game'
            shutil.copytree(Path(data['run'])/'game',directory)
            os.environ.update(HOME=str(directory),NETHACKDIR=str(directory),HACKDIR=str(directory))
            g=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS)
            try:
                tour.settle(g);turn=g.turn;position=g.cursor
                for y in range(1,9):
                    for x in range(2,16):
                        description=g.inspect(x,y).lower()
                        assert not any(word in description for word in ('chest','corpse','zombie')),description
                assert g.turn==turn
                if mode=='inspection':
                    start=len(g.events)
                    tour.lua(g,directory,'''local ox,oy=nh.abscoord(0,0);
    for y=1,8 do for x=2,15 do local m=nh.getmap(x-ox,y-oy);nh.pline("LIGHT:"..tostring(m.lit));end;end;''')
                    lights=[e['text'] for e in g.events[start:] if e.get('text','').startswith('LIGHT:')]
                    assert len(lights)==112 and all(v=='LIGHT:'+str(case['lit']).lower() for v in lights),lights
                g.finish(automatic=True)
                (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in g.events))
                g=tour.load_game_module().Game(directory,name='wizard',options=OPTIONS);tour.settle(g)
                assert (g.turn,g.cursor)==(turn,position)
                results.append(dict(case=case['id'],mode=mode,run=str(run),prepared=data,hiddenInspection=True,lighting=(mode=='inspection'),restoration=True))
                print('PASS',case['id'],mode,flush=True)
            finally:
                if g.process.poll() is None:g.process.kill();g.process.wait()
    assert len(results)==8
    (ROOT/'.artifacts/buried-catalog.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':main()
