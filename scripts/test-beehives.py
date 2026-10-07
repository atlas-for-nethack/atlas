#!/usr/bin/env python3
"""Isolated real-engine checks for bees, royal jelly perception, pickup, and save/restore."""
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
    run = Path(tempfile.mkdtemp(prefix='beehive-acceptance-', dir=ROOT/'.artifacts'))
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
des.object({id="lump of royal jelly",x=4,y=2,quantity=1});
des.object({id="lump of royal jelly",x=7,y=3,quantity=1});
des.monster({id="killer bee",x=7,y=3,peaceful=true,asleep=true,paralyzed=127});
des.monster({id="queen bee",x=7,y=4,peaceful=true,asleep=true,paralyzed=127});
des.finalize_level();
'''
        tour.lua(game, directory, source)
        jelly, worker, queen = (14,5), (17,6), (17,7)
        assert game.cells[jelly]['char'] == '%'
        assert game.cells[jelly]['groundTile'] == 1291
        assert 'royal jelly' in game.inspect(*jelly).lower()
        for position, name in ((worker,'killer bee'),(queen,'queen bee')):
            description = game.inspect(*position).lower()
            assert name in description and 'jelly' not in description, description
            assert game.cells[position]['groundTile'] == 1291
        assert game.cells[worker]['tile'] != game.cells[queen]['tile']
        game.finish(automatic=True)
        first_events = game.events.copy()
        shutil.copytree(directory, run/'visual-game')
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        fixture.walk(jelly)
        event = tour.named(game, 'pickup')
        if event['kind'] == 'menu':
            row = next(i for i in event['items'] if i.get('selectable') and 'royal jelly' in i['text'])
            game.send('menu '+str(row['id']))
            event = game.wait_input()
        tour.settle(game, event)
        fixture.step_off()
        assert game.cells[jelly]['char'] == '.'
        event = tour.named(game, 'inventory')
        assert any('royal jelly' in i['text'] for i in event.get('items',[])), event
        tour.settle(game, event)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        second_events = game.events.copy()
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        assert (game.cursor,game.turn) == (position,turn)
        assert game.cells[jelly]['char'] == '.'
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in first_events+second_events+game.events))
        print(json.dumps(dict(passed=True,run=str(run),
                             checks=['turn-free bee and jelly inspection','occupied jelly stays obscured',
                                     'jelly pickup and inventory','floor restored','exact save/restore']),indent=2))
    finally:
        fixture.close()


if __name__ == '__main__':
    main()
