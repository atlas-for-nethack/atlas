#!/usr/bin/env python3
"""Render the approved unusual-monster study using real, isolated NetHack state.

Reuse the tested movement/door fixture and native harness. Wizard Lua constructs
the room only; visibility, descriptions, movement, save and restore are upstream.
"""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('terrain_gameplay', ROOT / 'scripts/test-lantern-gameplay.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
original_level, original_load = fixture.level, fixture.load


def encounter_level(*args, **kwargs):
    return original_level(*args, **kwargs) + '''
des.monster({id="acid blob",x=1,y=2,peaceful=true,paralyzed=127});
des.monster({id="lichen",x=1,y=4,peaceful=true,paralyzed=127});
des.monster({id="Asmodeus",x=5,y=5,peaceful=true,paralyzed=127});
'''


def load_with_checks(run, *args, **kwargs):
    if not getattr(run, 'soot_see_invisible', False):
        # Demon princes normally begin invisible. Give only this isolated
        # wizard fixture the upstream perception ability, never expose them
        # through the renderer or alter their normal production behavior.
        event = fixture.actions.named(run.game, 'wizintrinsic')
        assert event['kind'] == 'menu', event
        item = next(i for i in event['items'] if i['text'].strip() == 'see invisible')
        run.game.send('menu ' + str(item['id']))
        assert run.game.wait_input().get('command')
        run.soot_see_invisible = True
    original_load(run, *args, **kwargs)
    for x, y, label, slots in [(1, 2, 'acid blob', (12, 13)),
                                (1, 4, 'lichen', (324, 325)),
                                (5, 5, 'Asmodeus', (632, 633))]:
        cell = fixture.at(run.game, x, y)
        assert cell['tile'] in slots, (label, cell)
        assert cell['groundTile'] == 1291, (label, cell)
        before = run.game.turn
        text = run.game.inspect(x + fixture.ORIGIN[0], y + fixture.ORIGIN[1])
        assert label.lower() in text.lower(), (label, text)
        assert run.game.turn == before, (label, 'inspection consumed a turn')


def main():
    fixture.level, fixture.load = encounter_level, load_with_checks
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='soot-encounter-', dir=ROOT / '.artifacts'))
    directory = fixture.prepare(run)
    fixture.native(run, directory, 'soot-and-brass')
    trace = [json.loads(line) for line in (run / 'diagnostics.jsonl.engine.jsonl').read_text().splitlines()]
    visible = {e['tile'] for e in trace if e['type'] == 'cell'}
    for label, slots in [('acid blob', {12, 13}), ('lichen', {324, 325}), ('Asmodeus', {632, 633})]:
        assert visible & slots, f'{label} absent from native engine stream'
    print('PASS actual acid blob, lichen and Asmodeus glyphs, perceived floor, turn-free inspection and native restore/move/save')
    print(f'Evidence and screenshot: {run}')


if __name__ == '__main__':
    main()
