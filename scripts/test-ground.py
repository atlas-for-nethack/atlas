#!/usr/bin/env python3
"""Check perceived ground layers through the actual engine and isolated saves."""
import importlib.util
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_test', ROOT / 'scripts/test-context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
actions = context.actions


def intrinsic(game, name):
    event = actions.named(game, 'wizintrinsic')
    assert event['kind'] == 'menu', event
    item = next(i for i in event['items'] if i['text'].strip() == name)
    game.send('menu ' + str(item['id']))
    assert game.wait_input().get('command')


def lua(fixture, source):
    path = fixture.directory / 'ground-check.lua'
    marker = 'Atlas ground fixture applied.'
    path.write_text(source + '\nnh.pline("' + marker + '");\n')
    start = len(fixture.game.events)
    event = actions.named(fixture.game, 'wizloadlua')
    assert event['kind'] == 'line', event
    fixture.game.send('line ground-check.lua')
    assert fixture.game.wait_input().get('command')
    assert any(e.get('text') == marker for e in fixture.game.events[start:]), fixture.game.events[start:]


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-ground-') as directory:
        fixture = context.Fixture(directory)
        game = fixture.game
        try:
            fixture.load('des.object({id="chest",x=10,y=3,locked=false,contents=function() end});')
            chest = fixture.find('(')
            assert game.cells[chest]['groundTile'] == 1291, game.cells[chest]
            assert game.cells[game.cursor]['groundTile'] == 1291, game.cells[game.cursor]
            fixture.walk(chest)
            assert game.cells[chest]['char'] == '@'
            assert game.cells[chest]['groundTile'] == 1291
            saved_turn, saved_position = game.turn, game.cursor
            game.finish(automatic=True)
            fixture.game = game = actions.Game(directory, name='AtlasContext',
                options=actions.OPTIONS + ',playmode:debug,pettype:none')
            game.start()
            assert (game.turn, game.cursor) == (saved_turn, saved_position)
            assert game.cells[game.cursor]['groundTile'] == 1291
            before = game.turn
            game.inspect(*game.cursor)
            assert actions.named(game, 'lookaround').get('command')
            assert game.turn == before
            assert game.cells[game.cursor]['groundTile'] == 1291
            print('PASS floor beneath chest/hero, exact restore, and turn-free inspection')

            for character, expected in [('I', 1315), ('}', 1314), ('L', 1316)]:
                fixture.load(f'des.terrain(10,3,"{character}"); '
                             'des.monster({id="floating eye",x=10,y=3,peaceful=true,paralyzed=127});')
                eye = fixture.find('e')
                assert game.cells[eye]['groundTile'] == expected, (character, game.cells[eye])
            print('PASS perceived ice, pool and lava beneath a flying monster')

            fixture.load('des.feature("fountain",10,3); '
                         'des.object({id="chest",x=10,y=3,locked=false,contents=function() end});')
            assert game.cells[fixture.find('(')]['groundTile'] == 1291
            fixture.load('des.door({x=10,y=3,state="secret"});')
            # The secret door must look like a wall and gain no doorway floor.
            hidden = (20, 6)  # Lua map-relative (10,3), map origin (10,3).
            assert hidden in game.cells and game.cells[hidden]['char'] in ('|', '-'), game.cells.get(hidden)
            assert 'groundTile' not in game.cells[hidden], game.cells[hidden]
            print('PASS known fixture floor and no secret-door floor disclosure')

            fixture.load()
            lua(fixture, 'nh.parse_config("OPTIONS=dark_room");')
            position = game.cursor
            before_cell = game.cells[position].copy()
            start = len(game.events)
            intrinsic(game, 'blinded')
            after_cell = game.cells[position]
            assert after_cell['tile'] == before_cell['tile'], (before_cell, after_cell)
            assert before_cell['groundTile'] == 1291 and after_cell['groundTile'] == 1292, (before_cell, after_cell)
            assert any(e['type'] == 'cell' and (e['x'], e['y']) == position
                       and e.get('groundTile') == 1292 for e in game.events[start:])
            print('PASS remembered darkness refresh while hero foreground stays unchanged')
            remote = (20, 6)
            assert remote != position and game.cells[remote]['groundTile'] == 1292
            # Test-only Lua changes the actual world, not the hero's memory.
            # The script independently confirms the mutation really happened.
            lua(fixture, 'des.terrain(10,3,"}"); '
                         'assert(nh.getmap(10,3).mapchr == "}");')
            assert game.cells[remote]['groundTile'] == 1292, game.cells[remote]
            assert actions.named(game, 'lookaround').get('command')
            assert game.cells[remote]['groundTile'] == 1292, game.cells[remote]
            print('PASS unseen world mutation to pool retains remembered dark floor')
        finally:
            fixture.close()

    with tempfile.TemporaryDirectory(prefix='atlas-ground-no-memory-') as directory:
        fixture = context.Fixture(directory)
        game = fixture.game
        try:
            # NetHack explicitly disables hero_memory on the Plane of Air.
            event = actions.named(game, 'wizlevelport')
            assert event['kind'] == 'line', event
            game.send('line ?')
            event = game.wait_input()
            assert event['kind'] == 'menu', event
            air = next(i for i in event['items'] if i['text'].strip().startswith('air:'))
            game.send('menu ' + str(air['id']))
            event = game.wait_input()
            for _ in range(12):
                if event.get('command'):
                    break
                event = actions.dismiss(game, event)
            assert event.get('command'), event
            assert any(e['type'] == 'status' and e.get('name') == 'dungeon-level'
                       and 'air' in e.get('value', '').lower() for e in game.events)
            assert game.cells[game.cursor].get('groundTile') in (1322, 1323), game.cells[game.cursor]
            intrinsic(game, 'blinded')
            assert 'groundTile' not in game.cells[game.cursor], game.cells[game.cursor]
            print('PASS memory-disabled Plane of Air omits ground after blindness')
        finally:
            fixture.close()

    with tempfile.TemporaryDirectory(prefix='atlas-ground-sensed-') as directory:
        fixture = context.Fixture(directory)
        game = fixture.game
        try:
            fixture.load('des.map({x=45,y=3,lit=true,map=[[\n.........\n.........\n.........\n.........\n.........\n]]}); '
                         'des.monster({id="lich",x=4,y=2,peaceful=true,paralyzed=127});')
            assert not any(c['char'] == 'L' for c in game.cells.values())
            intrinsic(game, 'monster detection')
            lich = fixture.find('L')
            assert 'groundTile' not in game.cells[lich], game.cells[lich]
            assert game.cells[lich]['tile'] >= 0
            print('PASS sensed creature on unexplored ground has no inferred floor')
        finally:
            fixture.close()


if __name__ == '__main__':
    main()
