#!/usr/bin/env python3
"""Isolated real-engine checks for undead, corpse perception, pickup, and save/restore."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


terrain = module('terrain', ROOT/'scripts/test-lantern-gameplay.py')
tour = module('tour', ROOT/'scripts/playtest/prepare.py')


def main():
    run = Path(tempfile.mkdtemp(prefix='morgue-acceptance-', dir=ROOT/'.artifacts'))
    directory = run/'game'
    directory.mkdir()
    with patch.dict(os.environ, HOME=str(directory), NETHACKDIR=str(directory),
                    HACKDIR=str(directory), ATLAS_PLAY_MODE='standard'):
        fixture = terrain.context.Fixture(str(directory))
    game = fixture.game
    try:
        source = '''des.reset_level();
des.level_init({style="solidfill",fg=" "});
des.level_flags("noflip","nomongen");
des.map({x=10,y=3,lit=true,map=[[
----------
|........|
|........|
|........|
|........|
|........|
----------
]]});
des.teleport_region({region={2,3,2,3}});
des.stair("up",1,1); des.stair("down",8,5);
des.object({id="corpse",montype="human",x=4,y=2});
des.grave(4,4,"Here rests an Atlas test adventurer.");
des.object({id="corpse",montype="human",x=7,y=3});
des.monster({id="human zombie",x=7,y=3,peaceful=true,asleep=true,paralyzed=127});
des.monster({id="human mummy",x=7,y=4,peaceful=true,asleep=true,paralyzed=127});
des.monster({id="wraith",x=7,y=5,peaceful=true,asleep=true,paralyzed=127});
des.finalize_level();
'''
        tour.lua(game, directory, source)
        corpse, zombie, mummy = (14,5), (17,6), (17,7)
        assert game.cells[corpse]['char'] == '%'
        assert game.cells[corpse]['groundTile'] == 1291
        assert 'corpse' in game.inspect(*corpse).lower()
        for position, name in ((zombie,'human zombie'),(mummy,'human mummy'),((17,8),'wraith')):
            description = game.inspect(*position).lower()
            assert name in description and 'corpse' not in description, description
            assert game.cells[position]['groundTile'] == 1291
        assert len({game.cells[p]['tile'] for p in (corpse,zombie,mummy,(17,8),(14,7))}) == 5
        assert 'grave' in game.inspect(14,7).lower()
        game.finish(automatic=True)
        first_events = game.events.copy()
        shutil.copytree(directory, run/'visual-game')
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        fixture.walk(corpse)
        event = tour.named(game, 'pickup')
        if event['kind'] == 'menu':
            row = next(i for i in event['items'] if i.get('selectable') and 'corpse' in i['text'])
            game.send('menu '+str(row['id']))
            event = game.wait_input()
        tour.settle(game, event)
        fixture.step_off()
        assert game.cells[corpse]['char'] == '.'
        event = tour.named(game, 'inventory')
        assert any('corpse' in i['text'] for i in event.get('items',[])), event
        tour.settle(game, event)
        fixture.walk((14,7))
        before, start = game.turn, len(game.events)
        tour.settle(game, tour.named(game, 'look'))
        assert game.turn == before
        assert any('grave' in e.get('text','').lower()
                   for e in game.events[start:]), game.events[start:]
        fixture.step_off()
        assert 'grave' in game.inspect(14,7).lower()
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        second_events = game.events.copy()
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        assert (game.cursor,game.turn) == (position,turn)
        assert game.cells[corpse]['char'] == '.'
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in first_events+second_events+game.events))
        print(json.dumps(dict(passed=True,run=str(run),
                             checks=['turn-free undead, corpse and grave inspection','occupied corpse stays obscured',
                                     'corpse pickup and inventory','grave underfoot look',
                                     'floor restored','exact save/restore']),indent=2))
    finally:
        fixture.close()


if __name__ == '__main__':
    main()
