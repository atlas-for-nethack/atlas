#!/usr/bin/env python3
"""Development-only real-engine checkpoint recipes. No player data is used."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
DAT = ROOT / 'vendor/NetHack-5.0.0/dat'
APP = ROOT / 'dist/Atlas.app'
RES = APP / 'Contents/Resources'
BASE = ROOT / '.artifacts/environment-playtests'
ROLES = dict(Arc='Archeologist', Bar='Barbarian', Cav='Caveman', Hea='Healer',
             Kni='Knight', Mon='Monk', Pri='Priest', Ran='Ranger', Rog='Rogue',
             Sam='Samurai', Tou='Tourist', Val='Valkyrie', Wiz='Wizard')
ROOM_SHAPES = ['default', 'Fake Delphi', 'Room in a room',
    'Huge room with another room inside', 'Nesting rooms',
    'Default room with themed fill', 'Unlit room with themed fill',
    'Room with both normal contents and themed fill', 'Pillars', 'Mausoleum',
    'Random dungeon feature in the middle of an odd-sized room',
    'L-shaped', 'L-shaped, rot 1', 'L-shaped, rot 2', 'L-shaped, rot 3',
    'Blocked center', 'Circular, small', 'Circular, medium', 'Circular, big',
    'T-shaped', 'T-shaped, rot 1', 'T-shaped, rot 2', 'T-shaped, rot 3',
    'S-shaped', 'S-shaped, rot 1', 'Z-shaped', 'Z-shaped, rot 1',
    'Cross', 'Four-leaf clover', 'Water-surrounded vault', 'Twin businesses']

DRY_FILLS = ['Spider nest', 'Trap room', 'Massacre', 'Statuary',
             'Light source', 'Ghost of an Adventurer', 'Storeroom']


def catalog():
    cases = []
    def add(id, group, label, target=None, source=None, branch='The Dungeons of Doom', **kw):
        cases.append(dict(id=id, group=group, label=label, target=target,
                          source=source, branch=branch, **kw))
    for i in range(1, 4):
        add(f'dungeon-{i}', 'Dungeon', f'Generated rooms {i}')
        add(f'mines-{i}', 'Mines', f'Generated caves {i}', 'minetn-', branch='The Gnomish Mines', filler=True)
        add(f'gehennom-{i}', 'Gehennom', f'Generated level {i}', 'valley', branch='Gehennom', filler=True)
    add('invocation-approach','Gehennom','Vibrating-square approach','sanctum',branch='Gehennom',filler=True)
    for source, group, label, target, branch in [
        ('rogue', 'Dungeon', 'Rogue level', 'rogue', 'The Dungeons of Doom'),
        ('oracle', 'Dungeon', 'Oracle', 'oracle', 'The Dungeons of Doom'),
        ('castle', 'Dungeon', 'Castle and drawbridge', 'castle', 'The Dungeons of Doom'),
        ('knox', 'Fort Ludios', 'Keep', 'knox', 'Fort Ludios'),
        *[(s, 'Gehennom', label, s, 'Gehennom') for s, label in
          [('valley','Valley of the Dead'),('asmodeus','Asmodeus'),('baalz','Baalzebub'),
           ('orcus','Orcus'),('juiblex','Juiblex'),('sanctum','Sanctum')]],
        *[(s, 'Elemental Planes', s.title(), s, 'The Elemental Planes') for s in ['earth','air','fire','water','astral']],
        *[(f'tower{i}', "Vlad’s Tower", f'Floor {i}', f'tower{i}', "Vlad's Tower") for i in range(1,4)],
        *[(f'wizard{i}', "Wizard’s Tower", f'Floor {i}', f'wizard{i}', 'Gehennom') for i in range(1,4)],
        *[(f'fakewiz{i}', "Wizard’s Tower", f'Decoy {i} (debug identity)', f'fakewiz{i}', 'Gehennom') for i in range(1,3)],
        *[(f'tut-{i}', 'Tutorial', f'Level {i}', f'tut-{i}', 'The Tutorial') for i in range(1,3)],
    ]:
        add(source, group, label, target, branch=branch)
    for prefix, count, group, branch in [('bigrm-',13,'Big Room','The Dungeons of Doom'),
            ('medusa-',4,'Medusa','The Dungeons of Doom'),('minetn-',7,'Minetown','The Gnomish Mines'),
            ('minend-',3,"Mines’ End",'The Gnomish Mines')]:
        add(prefix+'world',group,'World-selected layout',prefix,branch=branch)
        for i in range(1,count+1):
            s=f'{prefix}{i}'
            add(s,group,f'Layout {i}',prefix,s+'.lua',branch)
    for stage in range(1,5):
        for i in (1,2):
            s=f'soko{stage}-{i}'
            add(s,'Sokoban',f'Stage {stage}, layout {i}',f'soko{stage}-',s+'.lua','Sokoban')
    for role,name in ROLES.items():
        for suffix,label in [('strt','Start'),('fila','Upper filler'),('loca','Locate'),('filb','Lower filler'),('goal','Goal')]:
            s=f'{role}-{suffix}'
            add(s,'Quest: '+name,label,f'{role}-'+('loca' if suffix in ('fila','filb') else suffix),
                s+'.lua' if suffix in ('fila','filb') else None,'The Quest',role=name,
                filler=suffix in ('fila','filb'))
    for room in ['throne','barracks','shop','armor shop','scroll shop','potion shop','weapon shop',
                 'food shop','ring shop','wand shop','tool shop','book shop','health food shop',
                 'candle shop','vault','leprehall','zoo','beehive','anthole','morgue','temple','cocknest','swamp']:
        add('room-'+room.replace(' ','-'),'Special rooms',room.title(),room=room)
    for terrain in ['trees','ice','cloud','boulders']:
        add('terrain-'+terrain,'Terrain rooms',terrain.title(),terrain=terrain)
    for shape in ROOM_SHAPES:
        add('shape-'+re.sub(r'[^a-z0-9]+','-',shape.lower()), 'Room shapes', shape, shape=shape)
    for fill in DRY_FILLS:
        variants = [('lit', True, False), ('unlit', False, False), ('mixed', True, True)]
        if fill == 'Light source':
            variants = [('unlit', False, False), ('unlit-mixed', False, True)]
        for variant, lit, mixed in variants:
            add('fill-'+re.sub(r'[^a-z0-9]+','-',fill.lower())+'-'+variant,
                'Dry themed rooms', fill+' / '+variant, fill=fill, lit=lit, mixed=mixed)
    for fill in ['Buried treasure', 'Buried zombies']:
        for lit in (True, False):
            variant = 'lit' if lit else 'unlit'
            add('buried-'+fill.lower().replace('buried ','').replace(' ','-')+'-'+variant,
                'Buried rooms', fill+' / '+variant, buriedFill=fill, lit=lit)
    return cases


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return digest(RES/'engine/nethack')[:12] + '-' + digest(RES/'engine/nhdat')[:12] + '-' + digest(Path(__file__))[:12]


def load_game_module():
    spec=importlib.util.spec_from_file_location('atlas_engine',ROOT/'scripts/test-engine.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUNTIME=RES/'engine'
    return module


def settle(game,event=None):
    event=event or game.wait_input()
    for _ in range(80):
        if event.get('command'): return event
        if event['kind']=='line':
            if 'wish' in event.get('prompt','').lower():
                game.send('line nothing'); event=game.wait_input(); continue
            raise RuntimeError('Unexpected setup question: '+event.get('prompt',''))
        if event['kind']=='menu': game.send('menu cancel')
        elif event['kind']=='yn': game.send('key 110') # Never accept death or destroy a save.
        else: game.send('key 27')
        event=game.wait_input()
    raise RuntimeError('Setup did not reach an ordinary command prompt')


def named(game,name):
    game.send('command '+name)
    return game.wait_input()


def lua(game,directory,source):
    (directory/'setup.lua').write_text(source)
    event=named(game,'wizloadlua')
    assert event['kind']=='line',event
    game.send('line setup.lua')
    before=len(game.events)
    settle(game)
    bad=[e for e in game.events[before:] if any(t in e.get('text','').lower() for t in ['lua error','impossible','error in','stack traceback'])]
    if bad: raise RuntimeError(str(bad))


def identity(game,directory):
    lua(game,directory,'nh.pline("ATLAS_CONTEXT:" .. nh.dnum_name(u.dnum) .. "|" .. u.dlevel .. "|" .. u.depth .. "|" .. u.role);')
    line=next(e['text'] for e in reversed(game.events) if e.get('text','').startswith('ATLAS_CONTEXT:'))
    branch,level,depth,role=line.split(':',1)[1].split('|')
    return dict(branch=branch,level=int(level),depth=int(depth),role=role)


def teleport(game,target):
    event=named(game,'wizlevelport')
    assert event['kind']=='line',event
    game.send('line ?')
    event=game.wait_input()
    assert event['kind']=='menu',event
    matches=[i for i in event['items'] if i.get('selectable',True) and
             re.match(r'^'+re.escape(target.rstrip('-'))+':',i['text'].strip().lstrip('* ').strip())]
    if not matches: raise RuntimeError('World has no destination '+target)
    row=matches[0]
    game.send('menu '+str(row['id']))
    settle(game)
    return row['text'].strip()


def gehennom_filler_depth(game, index=0):
    """Choose an unnamed floor from this world's own wizard branch menu.

    Valley + 1 can be Asmodeus's lair. Never assume the first post-Valley
    floor is filler. Exclude every listed landmark and the invocation floor.
    This is preparation-only diagnostic information, never player UI data.
    """
    event=named(game,'wizlevelport'); assert event['kind']=='line',event
    game.send('line ?'); event=game.wait_input(); assert event['kind']=='menu',event
    bounds=None; excluded={}; inside=False
    for row in event['items']:
        text=row['text'].strip().lstrip('* ').strip()
        heading=re.match(r'^Gehennom: levels (\d+) to (\d+)',text)
        if heading:
            bounds=tuple(map(int,heading.groups())); inside=True; continue
        if inside and not row.get('selectable'):
            break
        if inside:
            match=re.match(r'^(.+?): (\d+)',text)
            if match: excluded[int(match[2])]=match[1]
    game.send('menu cancel'); settle(game)
    assert bounds,'No Gehennom branch in wizard destination menu'
    candidates=[d for d in range(bounds[0]+1,bounds[1]-1) if d not in excluded]
    assert len(candidates)>index,(bounds,excluded,index)
    return candidates[index],dict(branchDepths=bounds,excluded=excluded,
        candidates=candidates,selected=candidates[index],invocationExcluded=bounds[1]-1)


def prepare(case,mode,destination,fixture_environment=None):
    directory=destination/'game'
    directory.mkdir(parents=True)
    for name in ['nhdat','license','symbols','sysconf']:
        shutil.copy2(RES/'engine'/name,directory/name)
    (directory/'sysconf').write_text((directory/'sysconf').read_text().replace('WIZARDS=','WIZARDS=*'))
    (directory/'save').mkdir()
    for name in ['perm','record','logfile','xlogfile']: (directory/name).touch()
    # This helper is a dedicated process; overrides never leak to the owner app.
    for key in ['HOME','NETHACKDIR','HACKDIR']: os.environ[key]=str(directory)
    os.environ['ATLAS_PLAY_MODE']='standard'
    role=case.get('role','Valkyrie')
    align='lawful' if role in ['Knight','Samurai','Archeologist','Monk'] else 'chaotic' if role in ['Barbarian','Ranger','Rogue'] else 'neutral'
    module=load_game_module()
    options=f'gender:female,align:{align},color,hilite_pet,!autopickup,time,!news,checkpoint,playmode:debug,pettype:none,force_invmenu,menustyle:full'
    config = directory/'playtest.nethackrc'
    config.write_text('')
    game=module.Game(directory,role=role,name='AtlasTour',options=options,config=config,
                     fixture_environment=fixture_environment)
    evidence=dict(case=case,mode=mode,engine=digest(RES/'engine/nethack'),
                  app=digest(APP/'Contents/MacOS/NetHackAtlas'),recipe=digest(Path(__file__)),
                  revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  setup=['Isolated upstream wizard game; debug death refusal available.'],sources={})
    try:
        game.start()
        # Supply protection before dangerous arrivals, through upstream commands.
        if mode=='inspection':
            event=named(game,'levelchange'); assert event['kind']=='line'
            game.send('line 30'); settle(game)
            evidence['setup'].append('Experience raised to level 30 for inspection.')
            event=named(game,'wizintrinsic')
            wanted=['fire resistance','cold resistance','sleep resistance','disintegration resistance',
                    'shock resistance','poison resistance','acid resistance','stoning resistance',
                    'magical breathing','HP regeneration']
            rows=[i for i in event['items'] if i['text'].strip().lower() in [w.lower() for w in wanted]]
            game.send('menu '+','.join(str(i['id'])+':1000000' for i in rows))
            settle(game)
            evidence['setup'].append('Timed protection (1,000,000 turns): '+', '.join(i['text'] for i in rows))
        if case['id']=='knox':
            # Ludios is a floating branch until an eligible real vault creates its portal.
            for depth in range(11,25):
                event=named(game,'wizlevelport'); assert event['kind']=='line'
                game.send('line '+str(depth)); settle(game)
        if case['target'] and case['group']!='Tutorial':
            evidence['destination']=teleport(game,case['target'])
            if case['group']=='Elemental Planes':
                evidence['setup'].append('Upstream wizard Endgame entry supplies a real Amulet of Yendor when absent; this is not an ordinary campaign arrival.')
        if case.get('fill'):
            event=named(game,'wizlevelport'); assert event['kind']=='line'
            game.send('line 12'); settle(game)
            evidence['setup'].append('Dungeon depth 12 so level-gated traps and spiders can generate normally.')
        before=identity(game,directory)
        assert before['branch']==('The Dungeons of Doom' if case['group']=='Tutorial' else case['branch']),(case,before)
        if case.get('filler'):
            # Move to an actual filler depth within the same branch, not a renamed main-dungeon map.
            offset=-1 if case['branch']=='The Gnomish Mines' or case['id'].endswith('-fila') or case['id']=='invocation-approach' else 1
            depth=before['level']+offset if case['branch']=='The Quest' else before['depth']+offset
            if case['id'].startswith('gehennom-'):
                depth,selection=gehennom_filler_depth(game,int(case['id'].rsplit('-',1)[1])-1)
                offset=depth-before['depth']
                evidence['fillerSelection']=selection
                evidence['setup'].append('Unnamed Gehennom floor selected from actual world destinations; named lairs, towers, Valley, Sanctum and invocation floor excluded.')
            event=named(game,'wizlevelport'); assert event['kind']=='line'
            game.send('line '+str(depth)); settle(game)
        if case.get('source'):
            path=DAT/case['source']
            evidence['sources'][case['source']]=digest(path)
            lua(game,directory,'des.reset_level();\n'+path.read_text()+'\ndes.finalize_level();\n')
            evidence['setup'].append('Pinned layout loaded into its real branch/level; this is a targeted layout fixture.')
        if case.get('shape'):
            path = DAT/'themerms.lua'
            evidence['sources']['themerms.lua'] = digest(path)
            # Invoke the named upstream generator without rewriting its geometry
            # or contents. A separate arrival room keeps sealed shapes playable.
            code = path.read_text() + '\ndes.reset_level(); des.level_init({style="solidfill",fg=" "});\n'
            code += 'des.level_flags("noflip");\n'
            code += '''local original_map,original_room=des.map,des.room;
local recorded=false;
local function record(t)
 local contents=t.contents;
 t.contents=function(r)
  if not recorded then
   local x,y=nh.abscoord(0,0); recorded=true;
   nh.pline("ATLAS_SHAPE_BOUNDS:"..x..","..y..","..r.width..","..r.height);
  end;
  if contents then contents(r); end;
 end;
end;
des.map=function(t)
 if t.x==nil and t.halign==nil then t.halign="center"; t.valign="center"; end;
 record(t); return original_map(t);
end;
des.room=function(t) record(t); return original_room(t); end;
'''
            code += 'local idx=assert(lookup_by_name('+json.dumps(case['shape'])+',false)); themerooms[idx].contents();\n'
            code += 'des.map=original_map; des.room=original_room;\n'
            code += 'des.room({w=5,h=3,lit=1,contents=function() des.stair("up"); des.stair("down"); end});\n'
            code += 'des.random_corridors(); des.finalize_level();\n'
            lua(game,directory,code)
            marker = next(e['text'] for e in game.events if e.get('text','').startswith('ATLAS_SHAPE_BOUNDS:'))
            evidence['shapeBounds'] = [int(v) for v in marker.split(':')[1].split(',')]
            evidence['setup'].append('Named upstream room generator plus a separate arrival room and ordinary connecting corridors. Implicit themed map placement becomes centered placement for the wizard loader. Random contents and lighting retained; no rotation flipping.')
        if case.get('fill'):
            path = DAT/'themerms.lua'
            evidence['sources']['themerms.lua'] = digest(path)
            lit = '1' if case['lit'] else '0'
            filled = 1 if case['mixed'] else 0
            code = path.read_text() + '\ndes.reset_level(); des.level_init({style="solidfill",fg=" "});\n'
            code += 'des.level_flags("noflip");\n'
            code += 'des.map({x=25,y=5,map=[[\n' + '----------------\n' + '|..............|\n'*8 + '----------------\n]]});\n'
            code += 'des.region({region={1,1,14,8},type="themed",lit='+lit+',filled='+str(filled)+',contents=function(rm)\n'
            code += 'local fill=themeroom_fills[assert(lookup_by_name('+json.dumps(case['fill'])+',true))];\n'
            code += 'assert(fill.eligible==nil or fill.eligible(rm)); fill.contents(rm); end});\n'
            code += 'des.teleport_region({region={2,2,2,2}}); des.stair("up",1,1); des.stair("down",14,8);\n'
            if case['fill'] == 'Garden':
                # The upstream Garden defers its tree boundary until this hook.
                code += 'post_level_generate();\n'
            code += 'des.finalize_level();\n'
            lua(game,directory,code)
            evidence['shapeBounds'] = [25,5,16,10]
            evidence['setup'].append('Named upstream fill in a 14 by 8 themed room, fixed arrival and stairs. '+
                ('Lit' if case['lit'] else 'Unlit')+' room; ordinary contents '+('enabled' if case['mixed'] else 'disabled')+
                '. Source fill randomness retained; light-source eligibility respected.')
        if case.get('buriedFill'):
            path=DAT/'themerms.lua'
            evidence['sources']['themerms.lua']=digest(path)
            code=path.read_text()+'\ndes.reset_level(); des.level_init({style="solidfill",fg=" "}); des.level_flags("noflip");\n'
            # The upstream postprocess engraving handler expects the normal
            # whole-level Lua coordinate origin (1,0).
            code+='des.map({x=1,y=0,map=[[\n'+'----------------\n'+'|..............|\n'*8+'----------------\n]]});\n'
            code+='des.region({region={1,1,14,8},type="themed",lit='+str(int(case['lit']))+',contents=function(rm)\n'
            code+='themeroom_fills[assert(lookup_by_name('+json.dumps(case['buriedFill'])+',true))].contents(rm); end});\n'
            code+='des.teleport_region({region={2,2,2,2}}); des.stair("up",1,1); des.stair("down",14,8);\n'
            code+='post_level_generate(); des.finalize_level();\n'
            lua(game,directory,code)
            evidence['shapeBounds']=[1,0,16,10]
            evidence['setup'].append('Upstream buried fill and its post-generation handler, including engraving or original zombie timers. Rectangular test room with stairs; buried contents remain undisclosed.')
        if case.get('room') or case.get('terrain'):
            room=case.get('room','ordinary')
            content='des.stair("up"); des.stair("down");'
            if room=='temple': content+=' des.altar({align="neutral",type="shrine"});'
            terrain=case.get('terrain')
            if terrain in ['trees','ice','cloud']:
                ch=dict(trees='T',ice='I',cloud='C')[terrain]
                content+=f' for x=2,8,2 do des.terrain(x,3,"{ch}"); end;'
            if terrain=='boulders': content+=' for x=2,8,2 do des.object("boulder",x,3); end;'
            code='des.reset_level(); des.level_init({style="solidfill",fg=" "});\n'
            code+=f'des.room({{type={json.dumps(room)},filled=1,w=14,h=8,lit=1,contents=function() {content} end}});\n'
            code+='des.room({w=8,h=5,lit=1}); des.random_corridors(); des.finalize_level();'
            if room=='vault':
                code='des.reset_level(); des.level_init({style="solidfill",fg=" "}); des.room({type="vault",filled=1,w=2,h=2,lit=1}); des.room({w=12,h=8,lit=1,contents=function() des.stair("up"); des.stair("down"); end}); des.finalize_level();'
            lua(game,directory,code)
            evidence['setup'].append('Targeted engine-generated room, not a natural branch arrival.')
        after=identity(game,directory)
        assert after['branch']==('The Dungeons of Doom' if case['group']=='Tutorial' else case['branch']),(case,after)
        if case.get('filler'): assert after['level']==before['level']+offset,(before,after)
        else: assert before['level']==after['level'],(before,after)
        evidence['identity']=after
        if case['group']=='Tutorial':
            evidence['liveDestination']=case['target']
            evidence['setup'].append('Tutorial entered live after restoring this pre-entry checkpoint. Upstream forbids tutorial saves. Reset restarts; reports contain screenshot and trace, not a resumable tutorial save.')
        if mode=='inspection':
            settle(game,named(game,'wizmap'))
            lua(game,directory,'u.giveobj(obj.new("blessed wand of digging (0:50)")); u.giveobj(obj.new("blessed potion of full healing"));')
            evidence['setup'].append('Wizard map reveal; digging wand and healing potion supplied. Occupants remain active; protection is not invulnerability.')
        evidence['status']=game.status
        if case.get('fill') and mode=='inspection' and not (26 <= game.cursor[0] <= 39 and 6 <= game.cursor[1] <= 13):
            # A branch feature can displace the requested wizard arrival. Frame
            # inspection from already mapped plain floor, preserving exploration.
            target=next(p for p,c in game.cells.items() if 26 <= p[0] <= 39 and 6 <= p[1] <= 13 and c.get('char')=='.')
            event=named(game,'teleport')
            if event['kind']=='menu' and event.get('how')==0:
                game.send('key 32'); event=game.wait_input()
            assert event.get('targeting'),event
            game.send(f'position {target[0]} {target[1]}'); settle(game)
            assert game.cursor==target,(target,game.cursor)
            evidence['setup'].append('Inspection arrival moved by upstream wizard teleport onto mapped plain floor after branch placement displaced it.')
        evidence['arrival']=game.cursor
        evidence['displayedCells']=sum(c.get('char',' ').strip()!='' for c in game.cells.values())
        game.finish(automatic=True)
        if not any((directory/'save').iterdir()): raise RuntimeError('Engine did not produce a checkpoint')
        (destination/'metadata.json').write_text(json.dumps(evidence,indent=2)+'\n')
        (destination/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        return evidence
    finally:
        (destination/'preparation.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        if game.process.poll() is None:
            game.process.kill(); game.process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['catalog','prepare'])
    parser.add_argument('--case'); parser.add_argument('--mode',choices=['inspection','exploration'],default='exploration')
    args=parser.parse_args()
    if args.action=='catalog': print(json.dumps(catalog())); return
    case=next(c for c in catalog() if c['id']==args.case)
    BASE.mkdir(parents=True,exist_ok=True)
    checkpoint=BASE/'checkpoints'/stamp()/case['id']/args.mode
    if not (checkpoint/'metadata.json').exists():
        # Retry optional randomly absent branches/Big Room in new isolated worlds.
        for attempt in range(20):
            staging=BASE/('preparing-'+uuid.uuid4().hex)
            try:
                prepare(case,args.mode,staging)
                checkpoint.parent.mkdir(parents=True,exist_ok=True)
                staging.rename(checkpoint)
                break
            except Exception as error:
                (staging/'failure.txt').write_text(str(error))
                if 'World has no destination' not in str(error): raise
        else: raise RuntimeError('Could not generate a world containing this destination; preparation attempts retained.')
    run=BASE/'runs'/uuid.uuid4().hex
    run.mkdir(parents=True)
    shutil.copytree(checkpoint/'game',run/'game')
    metadata=json.loads((checkpoint/'metadata.json').read_text())
    metadata['checkpoint']=str(checkpoint)
    (run/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(dict(run=str(run),metadata=metadata)))

if __name__=='__main__': main()
