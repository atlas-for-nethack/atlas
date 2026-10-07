#!/usr/bin/env python3
"""Focused real-engine interactions for dry themed-room contents, in disposable games."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value
terrain = module('terrain', ROOT/'scripts/test-lantern-gameplay.py')
tour = module('tour', ROOT/'scripts/playtest/prepare.py')


def main():
    run = Path(tempfile.mkdtemp(prefix='themed-interactions-', dir=ROOT/'.artifacts'))
    directory = run/'game'; directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory), HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = terrain.context.Fixture(str(directory))
    game = fixture.game
    results = []
    def load(contents, lit=1):
        game.cells.clear()
        tour.lua(game, directory, '''des.reset_level();
des.level_init({style="solidfill",fg=" "}); des.level_flags("noflip","nomongen");
des.map({x=25,y=5,map=[[
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
des.region({region={1,1,14,8},lit='''+str(lit)+''',type="ordinary"});
des.teleport_region({region={2,2,2,2}}); des.stair("up",1,1); des.stair("down",14,8);
'''+contents+'\ndes.finalize_level();')
        assert game.cursor == (27,7), game.cursor
    def action(name, match=None):
        event = tour.named(game,name)
        if event['kind']=='menu' and match:
            row = next(i for i in event['items'] if i.get('selectable') and match in i['text'].lower())
            game.send('menu '+str(row['id'])); event=game.wait_input()
        tour.settle(game,event)
    def messages_since(start):
        return ' '.join(e.get('text','') for e in game.events[start:] if e['type']=='message').lower()
    try:
        event=tour.named(game,'wizlevelport');game.send('line 12');tour.settle(game)
        event=tour.named(game,'levelchange');game.send('line 30');tour.settle(game)
        tour.lua(game,directory,'nh.parse_config("OPTIONS=force_invmenu,menustyle:full");')
        for kind in ('web','arrow','dart','falling rock','bear','land mine','sleep gas','rust','anti magic'):
            load('des.trap({type='+json.dumps(kind)+',x=3,y=2,seen=false,victim=false,spider_on_web=false});')
            before = game.turn
            description=game.inspect(28,7).lower()
            assert game.turn==before and 'trap' not in description and 'web' not in description, description
            start=len(game.events)
            tour.settle(game,game.command('l'))
            text=messages_since(start)
            assert game.cursor==(28,7), (kind,game.cursor,text)
            expected = {'web':'web','arrow':'arrow','dart':'dart','falling rock':'rock',
                        'bear':'bear trap','land mine':'land mine','sleep gas':'gas',
                        'rust':'water','anti magic':'magical energy'}
            assert expected[kind] in text, (kind,text)
            results.append(dict(check='hidden trap then step',trap=kind,messages=text))
        load('des.monster({id="small mimic",appear_as="obj:chest",x=3,y=2,asleep=true});')
        before=game.turn;description=game.inspect(28,7).lower()
        assert 'chest' in description and 'mimic' not in description and game.turn==before,description
        start=len(game.events);tour.settle(game,game.command('l'))
        assert 'mimic' in game.inspect(28,7).lower(), messages_since(start)
        results.append(dict(check='mimic stays disguised until contact',messages=messages_since(start)))
        load('des.object({id="chest",x=2,y=2,locked=false,trapped=false,contents=function() des.object("food ration"); end});')
        start=len(game.events);event=tour.named(game,'loot')
        for _ in range(12):
            if event.get('command'):break
            if event['kind']=='yn':game.send('key 121')
            elif event['kind']=='menu':
                assert event.get('items'),event
                results.append(dict(check='real chest opens ordinary loot menu',items=[i['text'] for i in event['items']]))
                game.send('menu cancel')
            else:game.send('key 27')
            event=game.wait_input()
        assert any(r['check']=='real chest opens ordinary loot menu' for r in results)
        tour.settle(game,event)
        for item, extra in [('corpse','montype="newt",'),('statue','montype="newt",')]:
            load('des.object({id="'+item+'",'+extra+'x=3,y=2});')
            assert item in game.inspect(28,7).lower()
            tour.settle(game,game.command('l'));action('pickup',item)
            event=tour.named(game,'inventory')
            assert any(item in i['text'].lower() for i in event.get('items',[])),event
            tour.settle(game,event);tour.settle(game,game.command('h'))
            assert game.cells[(28,7)]['char']=='.',game.cells[(28,7)]
            results.append(dict(check=item+' pickup restores floor'))
        load('des.monster({id="ghost",x=3,y=2,asleep=true,waiting=true}); des.object({id="dagger",x=3,y=2});')
        before=game.turn;description=game.inspect(28,7).lower()
        assert 'ghost' in description and 'dagger' not in description and game.turn==before,description
        results.append(dict(check='ghost inspection respects occupied item'))
        load('des.object({id="oil lamp",x=2,y=2,lit=true,buc="uncursed"});',lit=0)
        action('pickup','lamp')
        for state in ('off','on'):
            start=len(game.events);action('apply','lamp');text=messages_since(start)
            assert 'is now '+state in text,text
            results.append(dict(check='lamp toggles '+state,messages=text))
        position,turn=game.cursor,game.turn;game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        fixture.game=game=tour.load_game_module().Game(directory,name='wizard',options='color,!news,!autopickup,time,force_invmenu,menustyle:full')
        tour.settle(game);assert (game.cursor,game.turn)==(position,turn)
        game.finish(automatic=True)
        results.append(dict(check='interaction save restores exact position and turn'))
        (ROOT/'.artifacts/themed-interactions.json').write_text(json.dumps(dict(run=str(run),results=results),indent=2)+'\n')
        print(json.dumps(dict(run=str(run),results=results),indent=2))
    finally:
        (run/'last-engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in game.events))
        fixture.close()

if __name__=='__main__': main()
