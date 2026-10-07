#!/usr/bin/env python3
"""Isolated real-engine checks for small hall occupants and gold pickup."""
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
    run = Path(tempfile.mkdtemp(prefix='leprehall-acceptance-', dir=ROOT/'.artifacts'))
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
des.gold(1,4,2); des.gold(250,4,4); des.gold(500,7,3);
des.monster({id="leprechaun",x=7,y=3,peaceful=true,asleep=true,paralyzed=127});
des.finalize_level();
'''
        tour.lua(game, directory, source)
        one, pile, occupied = (14,5), (14,7), (17,6)
        for position in (one, pile):
            assert game.cells[position]['char'] == '$', game.cells[position]
            assert game.cells[position]['groundTile'] == 1291
            assert 'gold' in game.inspect(*position).lower()
        assert game.cells[one]['tile'] == game.cells[pile]['tile'], 'Upstream coin glyph does not encode quantity'
        assert game.cells[occupied]['char'] == 'l'
        description = game.inspect(*occupied).lower()
        assert 'leprechaun' in description and 'gold' not in description, description
        assert game.cells[occupied]['groundTile'] == 1291
        game.finish(automatic=True)
        first_events = game.events.copy()
        shutil.copytree(directory, run/'visual-game')
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        for position, amount in ((one,1), (pile,250)):
            fixture.walk(position)
            event = tour.named(game, 'pickup')
            # Some configurations present a menu even for a single stack.
            if event['kind'] == 'menu':
                row = next(i for i in event['items'] if i.get('selectable') and 'gold' in i['text'])
                assert str(amount) in row['text'], row
                game.send('menu '+str(row['id']))
                event = game.wait_input()
            tour.settle(game, event)
            fixture.step_off()
            assert game.cells[position]['char'] == '.', game.cells[position]
        gold_status = next(e['value'] for e in reversed(game.events)
                           if e['type']=='status' and e.get('name')=='gold')
        assert gold_status.strip().endswith('251'), gold_status
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        second_events = game.events.copy()
        fixture.game = game = terrain.actions.Game(str(directory), name='AtlasContext',
            options=terrain.actions.OPTIONS + ',playmode:debug,pettype:none')
        game.start()
        assert (game.cursor,game.turn) == (position,turn)
        assert game.cells[one]['char'] == game.cells[pile]['char'] == '.'
        game.finish(automatic=True)
        (run/'engine.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in first_events+second_events+game.events))
        print(json.dumps(dict(passed=True,run=str(run),gold=251,
                             checks=['turn-free inspection','occupied gold stays obscured',
                                     'single coin and pile pickup','floor restored','exact save/restore']),indent=2))
    finally:
        fixture.close()


if __name__ == '__main__':
    main()
