#!/usr/bin/env python3
"""Real engine checks for descriptive item selection and legacy-save menus.

Fixtures use upstream wizard commands only inside temporary game directories.
No test hooks, simulated item names, or player saves are involved.
"""
import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('context_test', ROOT / 'scripts' / 'test-context.py')
context_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context_test)
actions = context_test.actions
FULL = ',force_invmenu,menustyle:full'
BASE_OPTIONS = actions.OPTIONS + ',playmode:debug,pettype:none'


class Fixture(context_test.Fixture):
    def __init__(self, directory, menus=FULL):
        self.directory = pathlib.Path(directory)
        actions.prepare(directory)
        config = self.directory / 'sysconf'
        config.write_text(config.read_text().replace('WIZARDS=', 'WIZARDS=*'))
        self.game = actions.Game(directory, name='AtlasItemMenus', options=BASE_OPTIONS + menus)
        self.game.start()
        self.load()


def menu(game, command, fragment):
    event = actions.named(game, command)
    assert event['kind'] == 'menu' and event['how'] == 1, (command, event)
    assert fragment in event['prompt'], (command, event)
    assert not any(token in event['prompt'] for token in ('[', '?*')), event
    assert any(i['selectable'] and len(i['text']) > 3 for i in event['items']), event
    return event


def pick(game, event, predicate, count=None):
    row = next(i for i in event['items'] if i['selectable'] and predicate(i))
    game.send('menu ' + str(row['id']) + (':' + str(count) if count is not None else ''))
    return game.wait_input()


def cancel(game, event, turn):
    assert actions.dismiss(game, event).get('command')
    assert game.turn == turn, 'Browsing/canceling an item menu spent a turn'


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-item-menus-') as directory:
        fixture = Fixture(directory)
        game = fixture.game
        try:
            for item in ['uncursed scroll of blank paper', 'uncursed potion of water',
                         'uncursed oil lamp', 'uncursed leather gloves', '12 uncursed arrows',
                         'uncursed ring of protection']:
                fixture.wish(item)
            before = game.turn
            for command, prompt, item in [
                ('read', 'read', 'unlabeled scroll'),
                ('quaff', 'drink', 'clear potion'),
                ('apply', 'use or apply', 'lamp'),
                ('wear', 'wear', 'leather gloves'),
                ('wield', 'wield', 'bare hands'),
                ('drop', 'drop', '12 arrows'),
                ('dip', 'dip', 'clear potion'),
            ]:
                event = menu(game, command, prompt)
                assert any(item in i['text'] and i['selectable'] for i in event['items']), event
                if command == 'read':
                    candidates = [i for i in event['items'] if i['selectable'] and i['key'] != '*']
                    assert len(candidates) == 1, event
                    assert game.turn == before, 'Single candidate was executed without selection'
                    artifacts = ROOT / '.artifacts'
                    artifacts.mkdir(exist_ok=True)
                    (artifacts / 'item-menu-events.json').write_text(json.dumps(game.events, indent=2))
                cancel(game, event, before)
            print('PASS readable read/drink/apply/wear/wield/drop/dip menus, single candidate and no-turn cancellation')

            event = menu(game, 'read', 'read')
            event = pick(game, event, lambda i: i['key'] == '*')
            assert event['kind'] == 'menu'
            assert any('dagger' in i['text'] for i in event['items']), event
            event = pick(game, event, lambda i: i['key'] == '?')
            assert event['kind'] == 'menu'
            assert not any('dagger' in i['text'] for i in event['items']), event
            cancel(game, event, before)
            print('PASS list-everything and return-to-likely choices preserve engine filtering')

            event = menu(game, 'dip', 'dip')
            event = pick(game, event, lambda i: 'dagger' in i['text'])
            assert event['kind'] == 'menu' and 'into' in event['prompt'], event
            assert any('clear potion' in i['text'] for i in event['items']), event
            cancel(game, event, before)
            print('PASS second-stage dip selection names the target potion and cancels without time')

            event = menu(game, 'puton', 'put on')
            event = pick(game, event, lambda i: 'ring' in i['text'])
            assert event['kind'] == 'yn' and set(event['choices']) == {'l', 'r'}, event
            assert event.get('choiceLabels') == {'r': 'Right hand', 'l': 'Left hand'}, event
            cancel(game, event, before)
            print('PASS ring hand choices carry readable labels and cancel without equipping')

            event = menu(game, 'drop', 'drop')
            assert pick(game, event, lambda i: '12 arrows' in i['text'], count=2).get('command')
            assert game.turn == before + 1, 'Dropping a selected quantity did not take one turn'
            event = actions.named(game, 'inventory')
            assert event['kind'] == 'menu'
            assert any('10 arrows' in i['text'] for i in event['items']), event
            cancel(game, event, before + 1)
            event = menu(game, 'read', 'read')
            assert pick(game, event, lambda i: 'unlabeled scroll' in i['text']).get('command')
            assert game.turn == before + 2, 'Selecting a readable item did not execute the chosen action'
            print('PASS chosen items execute normally and partial stack selection drops exactly two')
        finally:
            fixture.close()

    with tempfile.TemporaryDirectory(prefix='atlas-legacy-menus-') as directory:
        fixture = Fixture(directory, ',!force_invmenu,menustyle:traditional')
        game = fixture.game
        try:
            fixture.wish('uncursed scroll of blank paper')
            event = actions.named(game, 'read')
            assert event['kind'] == 'yn' and '?*' in event['prompt'], event
            cancel(game, event, game.turn)
            fixture.load('des.object({id="chest",x=10,y=3,locked=false,trapped=false,contents=function() '
                         'des.object("food ration"); des.object("dagger"); end});')
            fixture.walk(fixture.find('('))
            saved_turn, saved_position = game.turn, game.cursor
            game.finish(automatic=True)
            fixture.game = game = actions.Game(directory, name='AtlasItemMenus', options=BASE_OPTIONS + FULL)
            game.start()
            assert game.turn == saved_turn and game.cursor == saved_position
            assert any('Restoring save' in e.get('text', '') for e in game.events)
            event = menu(game, 'read', 'read')
            cancel(game, event, saved_turn)
            event = actions.named(game, 'droptype')
            assert event['kind'] == 'menu', ('Legacy save retained traditional category input', event)
            assert any('Weapons' in i['text'] for i in event['items']), event
            cancel(game, event, saved_turn)
            event = actions.named(game, 'loot')
            if event['kind'] == 'yn':
                game.send('key 121')
                event = game.wait_input()
            assert event['kind'] == 'menu', ('Legacy container actions were not a readable menu', event, [e for e in game.events[-80:] if e['type'] == 'message'])
            assert any('take' in i['text'].lower() for i in event['items']), event
            # Looking inside a container can consume time upstream; this check
            # only promises unchanged timing for canceled inventory selection.
            assert actions.dismiss(game, event).get('command')
            print('PASS legacy traditional save restores exact state with full item/category/container menus')
        finally:
            fixture.close()


if __name__ == '__main__':
    main()
