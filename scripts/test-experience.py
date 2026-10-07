#!/usr/bin/env python3
"""Check authoritative XP progress using the real engine in an isolated game."""
import importlib.util
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('items', ROOT / 'scripts/test-item-menus.py')
items = importlib.util.module_from_spec(spec)
spec.loader.exec_module(items)


def experience(game):
    return next(e['experience'] for e in reversed(game.events) if e['type'] == 'statusFlush')


with tempfile.TemporaryDirectory(prefix='atlas-experience-') as directory:
    with patch.dict(os.environ, HOME=directory, NETHACKDIR=directory, HACKDIR=directory,
                    ATLAS_PLAY_MODE='standard'):
        fixture = items.Fixture(directory)
        game = fixture.game
        try:
            assert experience(game) == {'level': 1, 'points': 0, 'start': 0, 'next': 20}
            fixture.wish('blessed potion of gain level named ProgressTest')
            event = items.menu(game, 'quaff', 'drink')
            event = items.pick(game, event, lambda i: 'ProgressTest' in i['text'])
            assert event.get('command'), event
            xp = experience(game)
            assert xp['level'] == 2 and xp['start'] == 20 and xp['next'] == 40
            assert 20 <= xp['points'] < 40, xp
            # These independently specified boundaries span both threshold changes
            # and the level cap, then exercise an actual level drain.
            for level, start, next_total in [(9, 2560, 5120), (10, 5120, 10000),
                                             (19, 2560000, 5120000),
                                             (20, 5120000, 10000000),
                                             (30, 100000000, None), (2, 20, 40)]:
                assert items.actions.named(game, 'levelchange')['kind'] == 'line'
                game.send('line ' + str(level))
                assert game.wait_input().get('command')
                xp = experience(game)
                assert (xp['level'], xp['start'], xp['next']) == (level, start, next_total), xp
            saved = experience(game)
            game.finish(automatic=True)
            restored = items.actions.Game(directory, name='wizard', options=items.BASE_OPTIONS + items.FULL)
            fixture.game = restored
            restored.start()
            assert experience(restored) == saved
            restored.finish(automatic=True)
            print('PASS: live XP gain, threshold transitions, level cap, level drain and save/restore')
        finally:
            fixture.close()
