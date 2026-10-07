#!/usr/bin/env python3
"""Add Lantern Modern with Classic's identical shared architectural pixels.

Reuse the reviewed Soot & Brass size policy and projected-frame packing contract,
but extract only Lantern's own original sources and approved production overrides.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def source_grid(source, columns, rows, cleanup):
    """Follow transparent source-sheet gutters instead of cutting off tall hats.

    Generation did not place every row on its nominal boundary. Search only a
    quarter-cell around each internal cut, so assignments cannot change cells.
    Retain every resolved rectangle in provenance for independent review.
    """
    cleaned, _ = cleanup(source)
    alpha = cleaned.getchannel('A')

    def cuts(length, count, occupied):
        result = [0]
        for i in range(1, count):
            target = round(i*length/count)
            radius = round(length/count/4)
            result.append(min(range(target-radius, target+radius+1),
                              key=lambda p: (occupied(p), abs(p-target))))
        return result + [length]

    def ink(box):
        return sum(alpha.crop(box).histogram()[9:])

    ys = cuts(source.height, rows, lambda y: ink((0,y,source.width,y+1)))
    bounds = {}
    for row in range(rows):
        xs = cuts(source.width, columns, lambda x: ink((x,ys[row],x+1,ys[row+1])))
        for column in range(columns):
            bounds[column,row] = [xs[column],ys[row],xs[column+1],ys[row+1]]
    return cleaned, bounds


def prepare(classic):
    """Add original creature frames to an in-memory Lantern preparation."""
    base = module('lantern_original_sources', HERE / 'build_atlas.py')
    packer_path = HERE.parent / 'packing.py'
    packer = module('projected_frame_packer', packer_path)
    catalog = read(HERE / 'catalog.json')
    registry = read(HERE / 'sources.json')
    overrides = read(HERE / 'production-overrides.json')
    policy_path = HERE.parent / 'creature-scale.json'
    sizing = module('original_creature_scale', HERE.parent / 'creature_scale.py')
    policy = read(policy_path)['monsters']
    keys = {t['art_key'] for t in catalog['tiles'] if t['category'] == 'monster'}
    assert keys == set(policy), 'Size policy must cover the complete Lantern roster'
    metadata = copy.deepcopy(classic['metadata'])
    atlas = classic['image'].copy()
    sheets = {s['id']: s for s in registry['sheets']}
    opened, inputs, subjects, records = {}, {}, {}, {}
    for key in sorted(keys):
        if key in overrides:
            record = overrides[key]
            path = base.local_file(HERE, record['file'], 'approved override')
            assert digest(path) == record['sha256'], key
            sprite = Image.open(path).convert('RGBA')
            bounds = [0, 0, *sprite.size]
            method = 'approved production override'
        else:
            assignment = registry['art'][key]
            sheet = sheets[assignment['sheet']]
            path = base.local_file(HERE, sheet['file'], 'source sheet', HERE / 'sources')
            if path not in opened:
                assert digest(path) == sheet['sha256'], path
                opened[path] = source_grid(Image.open(path).convert('RGBA'), sheet['columns'], sheet['rows'], base._cleanup.clean_foreground)
            source, grid = opened[path]
            x, y = assignment['column'], assignment['row']
            bounds = grid[x,y]
            sprite = source.crop(bounds)
            method = 'original source, existing edge-connected cleanup, gutter-aligned crop'
        inputs[str(path.relative_to(HERE))] = digest(path)
        box = sprite.getchannel('A').getbbox()
        assert box, key
        sprite = sprite.crop(box)
        rule = policy[key]
        subjects[key] = sizing.project_creature(sprite, rule)
        sprite = subjects[key]['image']
        records[key] = {'file': str(path.relative_to(HERE)), 'bounds': bounds, 'alphaBounds': list(box),
                        'method': method, 'size': list(sprite.size)}
    frames = {}
    for tile in catalog['tiles']:
        if tile['art_key'] not in subjects:
            continue
        frame = subjects[tile['art_key']].copy()
        if tile.get('transform') == 'statue':
            frame['image'] = base.stone(frame['image'])
        else:
            frame['kind'] = 'creature'
        frames[tile['slot']] = frame
    atlas, projection = packer.append_projected(atlas, frames)
    architecture = metadata.get('projectedFrames')
    if architecture:
        projection['frames'].update(architecture['frames'])
        projection['padding'] = [max(a,b) for a,b in zip(projection['padding'], architecture['padding'])]
    metadata['projectedFrames'] = projection
    report = {'schema': 1, 'classicPreparation': copy.deepcopy(classic['evidence']),
              'catalogSha256': digest(HERE/'catalog.json'), 'sizePolicy': '../creature-scale.json',
              'scaleHelperSha256': digest(HERE.parent/'creature_scale.py'),
              'sizePolicySha256': digest(policy_path), 'builderSha256': digest(Path(__file__)),
              'packerSha256': digest(packer_path), 'cleanupSha256': digest(HERE/'prepare_foregrounds.py'),
              'inputs': inputs, 'assignments': records,
              'artworkLicense': classic['evidence']['artworkLicense'],
              'artworkCredit': classic['evidence']['artworkCredit']}
    return {'image': atlas, 'metadata': metadata, 'evidence': report}


if __name__ == '__main__':
    raise SystemExit('Build tilesets with: python3 scripts/build-tilesets.py')
