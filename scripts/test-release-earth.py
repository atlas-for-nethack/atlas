#!/usr/bin/env python3
"""Bounded ordinary pick excavation and random Earth cave effects.

Fresh original Earth source save, separate uncursed/blessed copies, wizard
supplies/protection, ordinary Apply and directional digging. Never changes the
world, actors, traps, discovery or RNG through a diagnostic or setup mutation.
"""
import argparse
from collections import deque
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('earth_air_helpers', ROOT / 'scripts/test-air-plane.py')
air = importlib.util.module_from_spec(spec)
spec.loader.exec_module(air)
inv, tour, checks = air.inv, air.tour, air.checks
FIELDS = ('tile', 'glyph', 'char', 'color', 'pet', 'groundTile', 'material')
FLOORS = set(range(1291, 1297))
MARKER = 'EarthPickProbe'


def write(path, value):
    checks.write(path, value)


def sources():
    archive = tour.RES / 'Source/nethack-500-src.tgz'
    hashes = {}
    with tarfile.open(archive) as upstream:
        for path in ('dat/earth.lua', 'src/dig.c', 'src/apply.c', 'src/vision.c', 'src/display.c'):
            members = [m for m in upstream.getmembers() if m.name.endswith('/' + path)]
            assert len(members) == 1
            assert (tour.DAT.parent / path).read_bytes() == upstream.extractfile(members[0]).read(), path
            hashes[path] = tour.digest(tour.DAT.parent / path)
    return dict(unchangedPinnedSource=True, hashes=hashes, archiveSHA256=tour.digest(archive))


def messages(game, first):
    return [e['text'] for e in game.events[first:] if e['type'] == 'message'
            and not e['text'].startswith(('INV_', 'ATLAS_CONTEXT:', 'ATLAS_PICK:'))]


def current_pick(game, directory):
    first = len(game.events)
    inv.lua(game, directory, '''local o=u.inventory;
while not o:isnull() do local t=o:totable();
 if t.oname=="EarthPickProbe" then
  nh.pline("ATLAS_PICK:"..t.spe.."|"..t.blessed.."|"..t.cursed);
 end; o=o:next(); end;''')
    rows = [e['text'].split(':', 1)[1] for e in game.events[first:]
            if e.get('text', '').startswith('ATLAS_PICK:')]
    assert len(rows) == 1, rows
    spe, blessed, cursed = map(int, rows[0].split('|'))
    return dict(enchantment=spe, blessed=bool(blessed), cursed=bool(cursed))


def witnesses(before, after):
    return [dict(position=list(p), before=old, after=after['terrain'][p])
            for p, old in before['terrain'].items() if old['type'] != after['terrain'][p]['type']]


def trap_positions(memory):
    return {p: t['type'] for p, t in memory['traps'].items()}


def choose_target(game, memory):
    """Use displayed open floor to reach displayed actual rock; no hidden route."""
    queue = deque([game.cursor]); previous = {game.cursor: None}
    while queue:
        position = queue.popleft()
        for dx, dy, key in inv.STEPS:
            target = position[0] + dx, position[1] + dy
            cell = game.cells.get(target, {})
            actual = memory['terrain'].get(target, {})
            if cell.get('tile') == 1272 and actual.get('type') == 'stone' and actual.get('seenv', 0):
                route = []
                point = position
                while previous[point] is not None:
                    parent, move = previous[point]
                    route.append((move, point)); point = parent
                return target, key, list(reversed(route))
        for dx, dy, key in checks.STEPS:
            point = position[0] + dx, position[1] + dy
            cell = game.cells.get(point, {})
            if point in previous or point in memory['traps'] or cell.get('tile') not in FLOORS:
                continue
            previous[point] = (position, key); queue.append(point)
    return None


def dig(game, tool, direction):
    first = len(game.events); position, turn = game.cursor, game.turn
    event = tour.named(game, 'apply')
    assert event['kind'] == 'menu', event
    rows = [i for i in event['items'] if i.get('selectable') and MARKER in i['text']]
    assert len(rows) == 1, (tool, event)
    game.send('menu ' + str(rows[0]['id']))
    event = game.wait_input()
    # Applying an unwielded pick can first spend a wield turn and then queue
    # the ordinary application. Never invent an extra direction or game turn.
    for _ in range(12):
        if event.get('direction'):
            assert 'dig' in event.get('prompt', '').lower(), event
            inv.settle(game, game.command(direction))
            break
        if event.get('command'):
            return dict(completed=False, reason='Apply was interrupted before its direction prompt',
                        messages=messages(game, first), turns=game.turn-turn, start=list(position)), first
        if event['kind'] in ('key', 'text') and not event.get('targeting'):
            game.send('key 32'); event = game.wait_input()
        else:
            raise AssertionError(('Unexpected pick setup prompt', event))
    else:
        raise AssertionError('Pick direction did not arrive')
    text = messages(game, first)
    effect = None
    if any('ceiling collapses around you' in s for s in text):
        effect = 'collapse'
    elif any('mysterious force' in s and 'cave around you' in s for s in text):
        effect = 'expansion'
    elif any('succeed in cutting away some rock' in s for s in text):
        effect = 'excavation'
    return dict(completed=effect is not None, effect=effect, messages=text,
                turns=game.turn-turn, start=list(position), finish=list(game.cursor),
                selectedTool=rows[0]['text'], command='Apply + ordinary pick choice + ' + direction), first


def restore_witness(game, directory, run, label, memory, changed, history):
    position, turn = game.cursor, game.turn
    before_cells = {tuple(w['position']): copy.deepcopy(game.cells.get(tuple(w['position']))) for w in changed}
    game.finish(automatic=True)
    assert any(p.stat().st_size for p in (directory / 'save').iterdir() if p.is_file())
    history.extend(game.events)
    game = checks.open_game(directory); inv.settle(game)
    assert (game.cursor, game.turn) == (position, turn)
    restored = inv.diagnostics(game, directory)
    for p, old in memory['terrain'].items():
        new = restored['terrain'][p]
        assert all(old[k] == new[k] for k in ('type', 'lit', 'horizontal', 'flags')), (p, old, new)
    assert trap_positions(restored) == trap_positions(memory)
    exact = []
    for point, old in before_cells.items():
        new = game.cells.get(point)
        assert old is not None and new is not None, (point, old, new)
        assert all(old.get(f) == new.get(f) for f in FIELDS), (point, old, new)
        exact.append(dict(position=list(point), before=old, after=copy.deepcopy(new)))
    visibility = [dict(position=list(p), before={k: old[k] for k in ('seenv', 'waslit')},
                       after={k: restored['terrain'][p][k] for k in ('seenv', 'waslit')})
                  for p, old in memory['terrain'].items()
                  if any(old[k] != restored['terrain'][p][k] for k in ('seenv', 'waslit'))]
    result = dict(effect=label, exactPositionAndTurn=True, exactStructuralTerrainAndTraps=True,
                  exactChangedDisplayedCells=exact, visibilityRecalculation=visibility,
                  limitation='No assertion of identical future RNG; restore visibility recalculation is recorded separately')
    write(run / (label + '-restore.json'), result)
    return game, result


def sample(root, source, tool, original_hashes, completed_limit):
    run = root / tool; directory = run / 'game'
    shutil.copytree(source / 'game', directory)
    game = checks.open_game(directory); history = []
    result = dict(tool=tool, completedDigs=0, attemptedDigs=0, records=[], observed={}, gaps=[],
                  setup=['Original Earth save copied without replacing terrain or actors.',
                         'Wizard level 30 and timed protection/flight from shared Air helper.',
                         f'Wizard-supplied {tool} +99 pick-axe named {MARKER}; upstream SPE_LIM enchantment reduces occupation time through ordinary engine rules.',
                         'Read-only own-tool diagnostics record any blessing/curse changes caused by original actors.',
                         'Ordinary displayed-floor walking and Apply/direction responses only after supply setup.'])
    try:
        inv.settle(game)
        identity = tour.identity(game, directory)
        assert identity['depth'] == -1
        air.protect(game)
        inv.wish(game, f'{tool} +99 pick-axe named {MARKER}')
        supplied = current_pick(game, directory)
        assert supplied == dict(enchantment=99, blessed=tool == 'blessed', cursed=False), supplied
        for attempt in range(completed_limit * 8):
            if result['completedDigs'] >= completed_limit:
                break
            before = inv.diagnostics(game, directory)
            choice = choose_target(game, before)
            if choice is None:
                result['gaps'].append('No reachable currently displayed original rock target remained; no terrain or actors changed to force one')
                break
            target, direction, route = choice
            if route:
                key, expected = route[0]
                start = game.cursor; first = len(game.events)
                event = game.command('m'); assert event.get('command'), event
                inv.settle(game, game.command(key))
                result['records'].append(dict(stage='ordinary walking', start=list(start), expected=list(expected),
                    arrival=list(game.cursor), messages=messages(game, first)))
                continue
            tool_before = current_pick(game, directory)
            record, offset = dig(game, tool, direction)
            result['attemptedDigs'] += 1
            after = inv.diagnostics(game, directory)
            changes = witnesses(before, after)
            record.update(target=list(target), terrainChanges=changes,
                          toolBefore=tool_before, toolAfter=current_pick(game, directory),
                          ordinaryCellEvents=[e for e in game.events[offset:] if e['type'] == 'cell'])
            assert trap_positions(before) == trap_positions(after), 'Pick digging changed an original trap'
            if record['completed']:
                result['completedDigs'] += 1
                effect = record['effect']
                if effect == 'excavation':
                    assert before['terrain'][target]['type'] == 'stone' and after['terrain'][target]['type'] == 'corridor', changes
                    effect_changes = [c for c in changes if tuple(c['position']) == target]
                elif effect == 'expansion':
                    effect_changes = [c for c in changes if c['after']['type'] == 'room']
                else:
                    effect_changes = [c for c in changes if c['before']['type'] != 'stone' and c['after']['type'] == 'stone']
                assert effect_changes, ('Effect message without independent matching terrain change', record)
                changed_positions = {tuple(c['position']) for c in effect_changes}
                emitted = {(e['x'], e['y']) for e in record['ordinaryCellEvents']}
                assert emitted & changed_positions, ('No corresponding actual cell event', record)
                for p in changed_positions:
                    cell = game.cells.get(p, {})
                    if cell.get('tile') in (1469, 1470):
                        assert 'groundTile' not in cell and 'material' not in cell
                    if cell.get('tile') == 1272:
                        assert 'groundTile' not in cell, ('Collapsed displayed rock retained ground', cell)
                if effect not in result['observed']:
                    # Only witnesses with an actual displayed cell are compared;
                    # hidden diagnostic terrain is never turned into a render fixture.
                    visible_changes = [c for c in effect_changes if tuple(c['position']) in emitted]
                    game, restored = restore_witness(game, directory, run, effect, after, visible_changes, history)
                    result['observed'][effect] = restored
            result['records'].append(record)
            write(run / 'results.json', result)
            if 'excavation' in result['observed'] and ('expansion' if tool == 'blessed' else 'collapse') in result['observed']:
                break
        required = {'excavation', 'expansion' if tool == 'blessed' else 'collapse'}
        for effect in sorted(required - result['observed'].keys()):
            result['gaps'].append(f'{effect} not observed in {result["completedDigs"]} completed digs; this is an uncovered effect, not a pass')
        result['passed'] = not result['gaps'] and required <= result['observed'].keys()
        game.finish(automatic=True)
        assert inv.files_hashes(source / 'game') == original_hashes
        return result
    except Exception as error:
        result['error'] = repr(error); result['passed'] = False
        raise
    finally:
        write(run / 'results.json', result)
        checks.cleanup(run, game, history)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-sha256', required=True)
    parser.add_argument('--completed-limit', type=int, default=24)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    assert 1 <= args.completed_limit <= 24 and 30 <= args.timeout <= 600
    package = air.package()
    assert package['engine'] == args.engine_sha256, ('Candidate engine hash mismatch', package)
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='release-earth-', dir=ROOT / '.artifacts'))
    result = dict(passed=False, package=package, sourceEvidence=sources(),
                  recipeSHA256=tour.digest(Path(__file__)),
                  revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  samples=[], limitations=['Protected wizard arrival/supplies; no ordinary campaign or native-renderer acceptance.',
                                          'Random effect absence is a gap. No RNG assignment, forced cave call or actor removal.'])
    source = root / 'source'; original = None
    def timeout(signum, frame):
        raise TimeoutError('Bounded Earth test exceeded its whole-run time budget')
    previous = signal.signal(signal.SIGALRM, timeout); signal.alarm(args.timeout)
    try:
        case = next(c for c in tour.catalog() if c['id'] == 'earth')
        metadata = tour.prepare(case, 'exploration', source)
        assert metadata['case']['source'] is None and metadata['identity']['depth'] == -1
        original = inv.files_hashes(source / 'game')
        result.update(sourceMetadata=metadata, sourceSHA256=original)
        write(root / 'results.json', result)
        for tool in ('uncursed', 'blessed'):
            result['samples'].append(sample(root, source, tool, original, args.completed_limit))
            write(root / 'results.json', result)
        assert air.package() == package, 'Candidate changed during test'
        result['passed'] = all(s['passed'] for s in result['samples'])
        print('PASS' if result['passed'] else 'GAPS', 'ordinary Earth pick evidence:', root)
    except Exception as error:
        result['error'] = repr(error)
        raise
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, previous)
        if original is not None:
            result['originalSourceCheckpointUnchanged'] = inv.files_hashes(source / 'game') == original
            assert result['originalSourceCheckpointUnchanged']
        write(root / 'results.json', result)
        print('Evidence:', root, flush=True)
    if not result['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
