#!/usr/bin/env python3
"""Exercise context suggestions using real, isolated NetHack wizard fixtures.

Only the temporary game's sysconf enables upstream wizard commands. No player
saves or production test hooks are used. Fixtures are authored through NetHack's
own special-level Lua interface, then exercised through normal game commands.
"""
import collections
import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('actions_test', ROOT / 'scripts' / 'test-actions.py')
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)

BASE = '''des.level_init({style="solidfill", fg=" "});
des.level_flags("noflip", "nomongen");
des.map({x=10,y=3,lit=true,map=[[
....................
....................
....................
....................
....................
....................
....................
]]});
des.stair("up", 1, 1);
des.stair("down", 18, 5);
'''
DIRECTIONS = [(-1, 0, 'movewest'), (1, 0, 'moveeast'),
              (0, -1, 'movenorth'), (0, 1, 'movesouth')]


class Fixture:
    def __init__(self, directory):
        self.directory = pathlib.Path(directory)
        actions.prepare(directory)
        config = self.directory / 'sysconf'
        config.write_text(config.read_text().replace('WIZARDS=', 'WIZARDS=*'))
        self.game = actions.Game(directory, name='AtlasContext',
                                 options=actions.OPTIONS + ',playmode:debug,pettype:none')
        self.game.start()
        assert 'wizloaddes' in actions.catalog(self.game), 'Isolated wizard setup failed'

    def close(self):
        if self.game.process.poll() is None:
            self.game.process.kill()
            self.game.process.wait(timeout=5)

    def load(self, details=''):
        source = self.directory / 'context.lua'
        source.write_text(BASE + details)
        event = actions.named(self.game, 'wizloaddes')
        assert event['kind'] == 'line', event
        self.game.cells.clear()
        self.game.send('line context.lua')
        event = self.game.wait_input()
        assert event.get('command'), event
        assert not any('Error' in e.get('text', '') or 'impossible' in e.get('text', '').lower()
                       for e in self.game.events[-30:]), self.game.events[-30:]
        self.hints()
        # The upstream level loader chooses a valid arrival square. Step onto
        # plain floor so the hero cannot cover the fixture we need to locate.
        self.step_off()

    def hints(self, expected=(), absent=()):
        event = next(e for e in reversed(self.game.events) if e['type'] == 'context')
        hints = event['commands']
        names = [h['name'] for h in hints]
        assert len(names) == len(set(names)), ('Duplicate hints', hints)
        catalog = actions.catalog(self.game)
        assert all(name in catalog and catalog[name]['selectable'] for name in names), hints
        assert set(expected) <= set(names), ('Missing hints', expected, hints)
        assert not set(absent) & set(names), ('Unexpected hints', absent, hints)
        return {h['name']: h for h in hints}

    def find(self, character):
        positions = [p for p, c in self.game.cells.items() if c['char'] == character]
        assert len(positions) == 1, (character, positions)
        return positions[0]

    def walk(self, target, avoid=()):
        # Walk only ordinary floor and the explicitly selected destination.
        pending = collections.deque([(self.game.cursor, [])])
        visited = {self.game.cursor}
        while pending:
            position, route = pending.popleft()
            if position == target:
                break
            for dx, dy, name in DIRECTIONS:
                next_position = (position[0] + dx, position[1] + dy)
                if next_position in visited or next_position in avoid:
                    continue
                if next_position != target and self.game.cells.get(next_position, {}).get('char') != '.':
                    continue
                visited.add(next_position)
                pending.append((next_position, route + [(name, next_position)]))
        else:
            raise AssertionError(('No known safe route', self.game.cursor, target))
        for name, position in route:
            event = actions.named(self.game, name)
            assert event.get('command'), event
            assert self.game.cursor == position, (name, position, self.game.cursor)
            self.hints()

    def step_off(self):
        x, y = self.game.cursor
        target = next((x + dx, y + dy) for dx, dy, _ in DIRECTIONS
                      if self.game.cells.get((x + dx, y + dy), {}).get('char') == '.')
        self.walk(target)

    def wish(self, description):
        event = actions.named(self.game, 'wizwish')
        assert event['kind'] == 'line', event
        self.game.send('line ' + description)
        assert self.game.wait_input().get('command')

    def cancel(self, name, kind=None, direction=False):
        before = self.game.turn
        event = actions.named(self.game, name)
        if kind:
            assert event['kind'] == kind, event
        if direction:
            assert event.get('direction'), event
        assert not event.get('command'), ('Expected ordinary follow-up prompt', name, event)
        for _ in range(6):
            event = actions.dismiss(self.game, event)
            if event.get('command'):
                break
        assert event.get('command'), event
        assert self.game.turn == before, ('Canceled action spent a turn', name)
        self.hints()


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-context-') as directory:
        fixture = Fixture(directory)
        game = fixture.game
        try:
            # The hero's glyph obscures terrain. Suggestions must survive that
            # overlay and disappear immediately after moving off the feature.
            fixture.load()
            fixture.walk(fixture.find('>'))
            fixture.hints(['down'], ['up'])
            assert game.cells[game.cursor]['char'] == '@'
            before = game.turn
            for _ in range(3):
                game.inspect(*game.cursor)
                assert actions.named(game, 'lookaround').get('command')
                fixture.hints(['down'])
            assert game.turn == before, 'Refreshing context/inspection spent turns'
            fixture.step_off()
            fixture.hints(absent=['up', 'down'])
            fixture.walk(fixture.find('<'))
            fixture.hints(['up'], ['down'])
            print('PASS stairs below hero, moving away, repeated inspection without turns')
            fixture.load('des.object({id="chest",x=18,y=5,locked=false,contents=function() end});')
            fixture.walk(fixture.find('('))
            fixture.hints(['down', 'pickup', 'loot'])
            saved_turn, saved_position = game.turn, game.cursor
            game.finish(automatic=True)
            fixture.game = game = actions.Game(directory, name='AtlasContext',
                options=actions.OPTIONS + ',playmode:debug,pettype:none')
            game.start()
            assert game.turn == saved_turn and game.cursor == saved_position
            fixture.hints(['down', 'pickup', 'loot'])
            print('PASS stair hints survive object overlay and exact save/restore')


            for feature, symbol, script, expected in [
                ('fountain', '{', 'des.terrain(10,3,"{");', ['quaff', 'dip']),
                ('sink', '{', 'des.terrain(10,3,"K");', ['quaff', 'dip']),
                ('throne', '\\', 'des.feature("throne",10,3);', ['sit']),
                ('altar', '_', 'des.altar({x=10,y=3,align="neutral"});', ['offer', 'drop']),
            ]:
                fixture.load(script)
                fixture.walk(fixture.find(symbol))
                fixture.hints(expected)
                if feature == 'fountain':
                    fixture.cancel('quaff', kind='yn')
                    fixture.cancel('dip')
                fixture.step_off()
                fixture.hints(absent=expected)
                if feature == 'sink':
                    fixture.hints(['kick'])
                    fixture.cancel('kick', direction=True)
            print('PASS fountain, sink, throne and altar hints and ordinary prompts')

            fixture.load('des.object({id="chest",x=10,y=3,locked=false,contents=function() end});')
            fixture.walk(fixture.find('('))
            fixture.hints(['pickup', 'look', 'loot', 'tip', 'force'])
            assert game.cells[game.cursor]['char'] == '@'
            before = game.turn
            event = actions.named(game, 'look')
            if not event.get('command'):
                event = actions.dismiss(game, event)
            assert event.get('command') and game.turn == before
            fixture.step_off()
            fixture.hints(['kick'], ['pickup', 'loot', 'tip', 'force'])
            fixture.load('des.object({id="food ration",x=10,y=3});')
            fixture.walk(fixture.find('%'))
            fixture.hints(['pickup', 'look', 'eat'])
            fixture.cancel('eat', kind='yn')
            print('PASS underfoot objects, containers, food and no stale hints')

            # A secret door and buried container exist in the fixture, but have
            # never been shown. Their presence must not produce visible hints.
            fixture.load('des.door({x=10,y=3,state="secret"}); '
                         'des.object({id="chest",x=9,y=3,buried=true,contents=function() end});')
            # Locate the secret door's visible wall, not its private coordinates.
            walls = [p for p,c in game.cells.items() if c['char'] in ('-', '|')]
            assert len(walls) == 1, walls
            sx, sy = walls[0]
            fixture.walk((sx-1,sy))
            fixture.hints(absent=['open', 'close', 'kick', 'loot', 'tip', 'pickup'])
            print('PASS hidden door and buried container do not leak into suggestions')

            for seen in (False, True):
                fixture.load('des.feature("fountain",9,3); '
                             'des.trap({type="bear",x=10,y=3,victim=false,seen=' + str(seen).lower() + '});')
                fountain = fixture.find('{')
                trap = (fountain[0] + 1, fountain[1])
                fixture.walk(fountain, avoid=[trap])
                if seen:
                    fixture.hints(['glance', 'untrap'])
                    fixture.cancel('untrap', direction=True)
                else:
                    assert game.cells[trap]['char'] == '.', game.cells[trap]
                    fixture.hints(absent=['glance', 'untrap'])
            print('PASS discovered trap actions and hidden trap non-disclosure')


            fixture.load('des.monster({id="lichen",x=10,y=3,peaceful=false,paralyzed=127});')
            monster = fixture.find('F')
            fixture.walk((monster[0]-1,monster[1]))
            fixture.hints(['glance', 'chat', 'throw'], ['fire', 'zap', 'cast'])
            fixture.cancel('chat', direction=True)
            print('PASS nearby visible creature, equipment-aware throw and normal chat prompt')
            fixture.load('des.object({id="chest",x=18,y=5,locked=false,contents=function() end});')
            fixture.walk(fixture.find('('))
            fixture.hints(['down', 'loot', 'untrap'], ['apply'])
            fixture.wish('skeleton key')
            fixture.hints(['apply'])
            print('PASS container lock-tool suggestion follows carried equipment')
            # Preserve real protocol events for interface review, including the
            # actual command catalog, cells, status and expanded context labels.
            artifact = ROOT / '.artifacts' / 'expanded-context-events.json'
            artifact.parent.mkdir(exist_ok=True)
            artifact.write_text(json.dumps(game.events, indent=2))

            fixture.load()
            fixture.wish('blessed potion of levitation named AtlasFloat')
            inventory = actions.named(game, 'inventory')
            potion = next(i for i in inventory['items'] if 'AtlasFloat' in i['text'])
            assert actions.dismiss(game, inventory).get('command')
            event = actions.named(game, 'quaff')
            assert event['kind'] == 'yn', event
            game.send('key ' + str(ord(potion['key'])))
            assert game.wait_input().get('command')
            fixture.load('des.feature("fountain",10,3); '
                         'des.object({id="chest",x=10,y=3,locked=false,contents=function() end});')
            fixture.walk(fixture.find('('))
            fixture.hints(['look'], ['quaff', 'dip', 'pickup', 'loot', 'tip', 'force', 'untrap', 'apply'])
            print('PASS levitation suppresses actions that cannot reach the floor')

        finally:
            fixture.close()


    # Pets follow the hero through regenerated levels. Give this check its own
    # game so a moving pet cannot cover an object in a later floor fixture.
    with tempfile.TemporaryDirectory(prefix='atlas-context-pet-') as directory:
        fixture = Fixture(directory)
        game = fixture.game
        try:
            fixture.load()
            event = actions.named(game, 'wizgenesis')
            assert event['kind'] == 'line'
            game.send('line tame sleeping saddled pony')
            assert game.wait_input().get('command')
            fixture.hints(['glance', 'chat', 'name', 'ride'], ['throw', 'fire', 'zap', 'cast'])
            fixture.cancel('ride', direction=True)
            print('PASS nearby pet and visible saddle hints with ordinary direction prompt')
        finally:
            fixture.close()


if __name__ == '__main__':
    main()
