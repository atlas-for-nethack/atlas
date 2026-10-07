#!/usr/bin/env python3
"""Target the original Air-to-Fire portal in an isolated packaged-engine game.

Requires an explicitly selected candidate engine hash. Creates new evidence
paths; never opens existing Air study checkpoints. Wizard Air/Fire/Air travel
stages arrival in Air's original exit partition, then the actual original portal
is entered by ordinary movement. This does not prove full Air traversal.
"""
import argparse
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
spec = importlib.util.spec_from_file_location('release_air', ROOT / 'scripts/test-air-plane.py')
air = importlib.util.module_from_spec(spec)
spec.loader.exec_module(air)
inv, checks, tour = air.inv, air.checks, air.tour


def sources():
    paths = ('dat/air.lua', 'dat/fire.lua', 'dat/dungeon.lua', 'src/do.c',
             'src/dungeon.c', 'src/teleport.c', 'src/trap.c', 'src/mkmaze.c', 'src/sp_lev.c')
    archive = tour.RES / 'Source/nethack-500-src.tgz'
    hashes = {}
    with tarfile.open(archive) as upstream:
        for path in paths:
            members = [m for m in upstream.getmembers() if m.name.endswith('/' + path)]
            assert len(members) == 1, path
            assert (tour.DAT.parent / path).read_bytes() == upstream.extractfile(members[0]).read(), path
            hashes[path] = tour.digest(tour.DAT.parent / path)
    return dict(unchangedPinnedSource=True, hashes=hashes, archiveSHA256=tour.digest(archive))


def cells(game):
    return [copy.deepcopy(c) for _, c in sorted(game.cells.items())]


def approach(game, directory, portal, records, exit_region):
    # Hidden diagnostics choose only this disclosed test placement. They never
    # become renderer data or a player-facing route suggestion.
    terrain = inv.diagnostics(game, directory)['terrain']
    for dx, dy, _ in inv.STEPS:
        point = (portal[0] + dx, portal[1] + dy)
        if not (exit_region[0] <= point[0] <= exit_region[1] and 0 <= point[1] <= 20):
            continue
        if terrain.get(point, {}).get('type') not in ('air', 'cloud'):
            continue
        try:
            air.place(game, point)
        except AssertionError as error:
            records.append(dict(stage='placement', target=list(point), error=str(error)))
            continue
        records.append(dict(stage='placement', target=list(point), reached=True))
        return point
    raise AssertionError('Original occupants/conditions blocked every bounded portal approach; no actor was removed')


def run(expected_engine):
    package = air.package()
    assert package['engine'] == expected_engine, ('Candidate engine hash mismatch', package)
    evidence = sources()
    root = Path(tempfile.mkdtemp(prefix='release-world-', dir=ROOT / '.artifacts'))
    result = dict(passed=False, run=str(root), package=package, sourceEvidence=evidence,
                  revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  recipeSHA256=tour.digest(Path(__file__)), records=[],
                  limitations=[
                      'Wizard Endgame entry supplies the real Amulet. Timed protection and flight are setup.',
                      'Wizard Fire-to-Air return stages the upstream exit partition; full ordinary Air traversal is not tested.',
                      'Original actors remain active; bounded inability to reach the portal is a failure, not a pass.',
                      'No native rendering, ordinary survival, complete ascension, Intel or minimum-macOS execution is established.',
                  ])
    checks.write(root / 'results.json', result)
    source = root / 'source'
    case = next(c for c in tour.catalog() if c['id'] == 'air')
    metadata = tour.prepare(case, 'exploration', source)
    assert metadata['case']['source'] is None and metadata['identity']['depth'] == -2, metadata
    pristine = inv.files_hashes(source / 'game')
    checks.write(root / 'source-checkpoint-hashes.json', pristine)
    directory = root / 'working' / 'game'
    shutil.copytree(source / 'game', directory)
    game = checks.open_game(directory)
    previous_events = []
    result.update(sourceCheckpoint=str(source), sourceMetadata=metadata, sourceSHA256=pristine)
    try:
        inv.settle(game)
        origin = tour.identity(game, directory)
        assert origin == metadata['identity']
        initial = inv.diagnostics(game, directory)
        portals = [p for p, t in initial['traps'].items() if t['type'] == 'magic portal']
        assert len(portals) == 1, portals
        portal = portals[0]
        # Upstream may mirror the original special level horizontally. Region
        # coordinates and the portal are flipped together; do not assume the
        # unmirrored Lua drawing is the generated world.
        assert 1 <= portal[0] <= 24 or 56 <= portal[0] <= 79, portal
        exit_region = (1, 24) if portal[0] <= 24 else (56, 79)
        air.protect(game)
        # goto_level(up=false) calls u_on_rndspot(0), which uses dndest. Air's
        # pinned dndest is x56..79. This avoids altering teleport-region rules.
        fire_setup = tour.teleport(game, 'fire')
        fire_identity = tour.identity(game, directory)
        assert fire_identity['depth'] == -3 and fire_identity['level'] == origin['level'] - 1
        air_setup = tour.teleport(game, 'air')
        assert tour.identity(game, directory) == origin
        assert exit_region[0] <= game.cursor[0] <= exit_region[1], ('Expected original down-arrival region', game.cursor, exit_region)
        current = inv.diagnostics(game, directory)
        assert [p for p, t in current['traps'].items() if t['type'] == 'magic portal'] == portals
        result['records'].append(dict(stage='wizard arrival setup', destinations=[fire_setup, air_setup],
                                      arrival=list(game.cursor), originalPortal=list(portal), exitRegion=list(exit_region),
                                      source='goto_level -> u_on_rndspot(0) -> original Air dndest'))
        approach(game, directory, portal, result['records'], exit_region)
        result['before'] = dict(identity=origin, position=list(game.cursor), turn=game.turn, cells=cells(game))
        offset = len(game.events)
        transition = air.move(game, portal, limit=12, portal=True)
        messages = air.messages(game, offset)
        assert any('activated a magic portal' in text.lower() for text in messages), messages
        destination = tour.identity(game, directory)
        assert destination == fire_identity, (origin, destination, fire_identity)
        assert destination['depth'] == -3
        material = checks.material(game.cells.values(), 'gehennom')
        result['records'].append(dict(stage='ordinary original portal activation', movement=transition,
                                      origin=origin, destination=destination, messages=messages, verified=True))
        result['after'] = dict(identity=destination, position=list(game.cursor), turn=game.turn,
                               cells=cells(game), material=material)
        position, turn = game.cursor, game.turn
        game.finish(automatic=True)
        assert any(p.stat().st_size for p in (directory / 'save').iterdir() if p.is_file())
        previous_events.extend(game.events)
        game = checks.open_game(directory)
        inv.settle(game)
        assert (game.cursor, game.turn) == (position, turn)
        assert tour.identity(game, directory) == destination
        restored_material = checks.material(game.cells.values(), 'gehennom')
        result['restore'] = dict(exactPositionAndTurn=True, identity=destination, material=restored_material,
                                 cells=cells(game), limitation='Exact future RNG or all animated cell equality is not asserted')
        game.finish(automatic=True)
        assert inv.files_hashes(source / 'game') == pristine
        assert air.package() == package, 'Candidate changed during test'
        result.update(passed=True, originalSourceCheckpointUnchanged=True,
                      originalSourceSHA256After=inv.files_hashes(source / 'game'))
    except Exception as error:
        result['error'] = repr(error)
        raise
    finally:
        result['originalSourceCheckpointUnchanged'] = inv.files_hashes(source / 'game') == pristine
        checks.write(root / 'results.json', result)
        checks.cleanup(root, game, previous_events)
        print('Evidence:', root, flush=True)
    print('PASS original Air-to-Fire portal activation, Fire material, exact turn/position restore and preserved source checkpoint')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-sha256', required=True,
                        help='Explicit SHA-256 of the integrated packaged Universal candidate to exercise')
    parser.add_argument('--timeout', type=int, default=180,
                        help='Whole-run timeout in seconds (default: 180)')
    args = parser.parse_args()
    assert len(args.engine_sha256) == 64 and all(c in '0123456789abcdef' for c in args.engine_sha256)
    assert 30 <= args.timeout <= 600, 'Use a bounded 30–600 second timeout'
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    def timeout(signum, frame):
        raise TimeoutError('Release world regression exceeded its whole-run time budget')
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(args.timeout)
    try:
        run(args.engine_sha256)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    main()
