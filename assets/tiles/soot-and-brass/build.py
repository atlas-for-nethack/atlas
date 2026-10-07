#!/usr/bin/env python3
"""Assemble original Soot & Brass art, failing on incomplete catalog coverage.

No existing atlas is opened. Cropping, optional declared background removal,
nearest-neighbor sizing and statue derivation are reproducible preparation;
the retained generated source images are never modified.
"""
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SIZE, COLUMNS, COUNT = 64, 40, 2304
CATALOG = HERE.parent / 'lantern/catalog.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key {key} in {path}')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


packing = module('soot_frame_packing', HERE.parent / 'packing.py')
append_projected = packing.append_projected
occupied_squares = packing.occupied_squares


def local(name):
    path = (HERE / name).resolve()
    if not path.is_relative_to(HERE) or not path.is_file():
        raise ValueError(f'Missing or nonlocal source: {name}')
    return path


def remove_background(image, rgb, tolerance=12):
    """Flood only the explicitly declared edge-connected studio background."""
    image = image.convert('RGBA').copy()
    width, height = image.size
    pixels = image.load()
    queue = deque((x, y) for y in range(height) for x in range(width)
                  if x in (0, width - 1) or y in (0, height - 1))
    visited = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or not (0 <= x < width and 0 <= y < height):
            continue
        visited.add((x, y))
        color = pixels[x, y]
        if color[3] == 0 or max(abs(color[i] - rgb[i]) for i in range(3)) <= tolerance:
            pixels[x, y] = (*color[:3], 0)
            queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return image


def fit_cell(image, nominal_size=None):
    # Preserve proportions even when generation returns a nonsquare sheet.
    image = image.copy()
    image.putalpha(image.getchannel('A').point(lambda alpha: 0 if alpha <= 8 else alpha))
    width, height = image.size
    nominal_width, nominal_height = nominal_size or image.size
    scale = min(SIZE / nominal_width, SIZE / nominal_height,
                (52 if nominal_size else SIZE) / width,
                (52 if nominal_size else SIZE) / height)
    scaled = image.resize((max(1, round(width * scale)), max(1, round(height * scale))),
                          Image.Resampling.NEAREST)
    result = Image.new('RGBA', (SIZE, SIZE))
    result.alpha_composite(scaled, ((SIZE - scaled.width) // 2, (SIZE - scaled.height) // 2))
    return result


def primary_component(image):
    """Isolate a reviewed subject when its rectangle contains a neighbor tip.

This is opt-in for named source cells, never a general particle cleanup.
Eight-connected alpha preserves diagonal sprite outlines and original colors.
"""
    pixels = image.load()
    remaining = {(x, y) for y in range(image.height) for x in range(image.width)
                 if pixels[x, y][3] > 8}
    largest = set()
    while remaining:
        seed = min(remaining, key=lambda p: (p[1], p[0]))
        remaining.remove(seed)
        component, queue = {seed}, [seed]
        while queue:
            x, y = queue.pop()
            for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    queue.append(point)
        if len(component) > len(largest):
            largest = component
    result = Image.new('RGBA', image.size)
    target = result.load()
    for point in largest:
        target[point] = pixels[point]
    return result


def sources(known):
    art, evidence, assignments = {}, [], {}
    for category in ('monster', 'object', 'terrain'):
        registry_path = HERE / f'{category}-sources.json'
        registry = read(registry_path)
        evidence.append({'registry': registry_path.name, 'sha256': digest(registry_path)})
        for sheet in registry['sheets']:
            path = local(sheet['file'])
            if digest(path) != sheet['sha256']:
                raise ValueError(f'Source checksum changed: {path}')
            columns, rows = sheet['columns'], sheet['rows']
            if not (type(columns) is int and type(rows) is int and columns > 0 and rows > 0
                    and len(sheet['keys']) == columns * rows):
                raise ValueError(f'Invalid source grid: {path}')
            with Image.open(path) as opened:
                image = opened.convert('RGBA')
            explicit = sheet.get('bounds')
            if explicit is not None and len(explicit) != len(sheet['keys']):
                raise ValueError(f'Crop count does not match key count: {path}')
            evidence.append({'file': sheet['file'], 'sha256': sheet['sha256'],
                             'size': list(image.size), 'columns': columns, 'rows': rows})
            for index, key in enumerate(sheet['keys']):
                if key is None:
                    continue
                if key not in known:
                    raise ValueError(f'Unknown appearance key: {key}')
                x, y = index % columns, index // columns
                bounds = (round(x * image.width / columns), round(y * image.height / rows),
                          round((x + 1) * image.width / columns), round((y + 1) * image.height / rows))
                if explicit is not None:
                    bounds = explicit[index]
                    if (not isinstance(bounds, list) or len(bounds) != 4
                            or not all(type(v) is int for v in bounds)
                            or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]):
                        raise ValueError(f'Invalid source crop: {path}/{index}')
                cell = image.crop(bounds)
                if sheet.get('background_rgb') is not None:
                    cell = remove_background(cell, sheet['background_rgb'], sheet.get('background_tolerance', 12))
                isolated = index in sheet.get('keep_largest_component', [])
                if isolated:
                    cell = primary_component(cell)
                art[key] = fit_cell(cell, (image.width / columns, image.height / rows) if explicit else None)
                history = assignments.setdefault(key, [])
                history.append({'file': sheet['file'], 'cell': index, 'bounds': list(bounds),
                                'primaryComponentOnly': isolated})
    return art, evidence, assignments


def statue(image):
    result = ImageOps.colorize(ImageOps.grayscale(image), '#252c2d', '#c3c9c0').convert('RGBA')
    result.putalpha(image.getchannel('A'))
    return result


def projected_monsters(catalog, assignments):
    policy = read(HERE.parent / 'creature-scale.json')
    spec = importlib.util.spec_from_file_location('original_creature_scale', HERE.parent / 'creature_scale.py')
    sizing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sizing)
    expected = {item['key'] for item in catalog['art_keys'] if item['category'] == 'monster'}
    if set(policy['monsters']) != expected:
        raise ValueError('Monster scale review must explicitly cover every canonical creature')
    images, frames = {}, {}
    for key in sorted(expected):
        record = assignments[key][-1]
        sprite = Image.open(local(record['file'])).convert('RGBA').crop(record['bounds'])
        if record['primaryComponentOnly']:
            sprite = primary_component(sprite)
        sprite.putalpha(sprite.getchannel('A').point(lambda a: a if a > 8 else 0))
        sprite = sprite.crop(sprite.getbbox())
        rule = policy['monsters'][key]
        images[key] = sizing.project_creature(sprite, rule)
    for tile in catalog['tiles']:
        if tile['art_key'] not in images:
            continue
        frame = images[tile['art_key']].copy()
        if tile.get('transform') == 'statue':
            frame['image'] = statue(frame['image'])
        else:
            frame['kind'] = 'creature'
        frames[tile['slot']] = frame
    return frames


def previews(catalog, art, terrain):
    folder = ROOT / '.artifacts/soot-and-brass'
    folder.mkdir(parents=True, exist_ok=True)
    for category in ('monster', 'object', 'terrain', 'effect'):
        items = [key for key in catalog['art_keys'] if key['category'] == category]
        # Pages keep individual labels and sprites legible at ordinary zoom.
        for page, start in enumerate(range(0, len(items), 80)):
            subset = items[start:start + 80]
            sheet = Image.new('RGBA', (8 * 160, ((len(subset) + 7) // 8) * 166), '#141b20')
            pen = ImageDraw.Draw(sheet)
            for i, key in enumerate(subset):
                x, y = i % 8 * 160, i // 8 * 166
                sprite = art[key['key']].resize((128, 128), Image.Resampling.NEAREST)
                sheet.alpha_composite(sprite, (x + 16, y + 2))
                label = key['label']
                pen.text((x + 4, y + 132), label[:25], fill='#eadcba')
                pen.text((x + 4, y + 147), label[25:50], fill='#eadcba')
            sheet.convert('RGB').save(folder / f'{category}-{page:02d}.png')
    variants = terrain['variants']
    for page, start in enumerate(range(0, len(variants), 80)):
        subset = variants[start:start + 80]
        sheet = Image.new('RGBA', (8 * 128, ((len(subset) + 7) // 8) * 148), '#171f23')
        pen = ImageDraw.Draw(sheet)
        for i, sprite in enumerate(subset):
            x, y = i % 8 * 128, i // 8 * 148
            sheet.alpha_composite(sprite.resize((128, 128), Image.Resampling.NEAREST), (x, y))
            pen.text((x + 4, y + 130), str(COUNT + start + i), fill='#eadcba')
        sheet.save(folder / f'directional-{page:02d}.png')


def prepare():
    """Prepare original modern art and source evidence without publication."""
    catalog = read(CATALOG)
    tiles = catalog['tiles']
    if (catalog['engineVersion'] != '5.0.0' or len(tiles) != COUNT
            or {t['slot'] for t in tiles} != set(range(COUNT))):
        raise ValueError('Canonical NetHack 5.0 catalog is incomplete')
    known = {item['key'] for item in catalog['art_keys']}
    art, evidence, assignments = sources(known)
    spec = importlib.util.spec_from_file_location('soot_terrain', HERE / 'terrain.py')
    terrain_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(terrain_module)
    terrain = terrain_module.build_wall_art(variant_start=COUNT)
    if set(terrain['canonical']) - known:
        raise ValueError('Terrain generator returned unknown canonical keys')
    art.update(terrain['canonical'])
    missing = known - art.keys()
    if missing:
        raise ValueError(f'Missing {len(missing)} original sprites: {sorted(missing)}')
    for key, sprite in art.items():
        if sprite.size != (SIZE, SIZE) or sprite.mode != 'RGBA':
            raise ValueError(f'Wrong sprite dimensions or mode: {key}')
        # Blank unexplored/dark space is valid; visible actors and items are not.
        if key.startswith(('monster/', 'object/')) and sprite.getchannel('A').getbbox() is None:
            raise ValueError(f'Empty subject: {key}')
    total = COUNT + len(terrain['variants'])
    atlas = Image.new('RGBA', (COLUMNS * SIZE, ((total + COLUMNS - 1) // COLUMNS) * SIZE))
    for tile in tiles:
        sprite = art[tile['art_key']]
        if tile.get('transform') == 'statue':
            sprite = statue(sprite)
        slot = tile['slot']
        atlas.paste(sprite, (slot % COLUMNS * SIZE, slot // COLUMNS * SIZE))
    for slot, sprite in enumerate(terrain['variants'], COUNT):
        if sprite.size != (SIZE, SIZE):
            raise ValueError('Directional sprite escapes its cell')
        atlas.paste(sprite, (slot % COLUMNS * SIZE, slot // COLUMNS * SIZE))
    projected = projected_monsters(catalog, assignments)
    projected.update(terrain.get('projected', {}))
    atlas, projection = append_projected(atlas, projected)
    regional_spec = importlib.util.spec_from_file_location('soot_regional_materials', HERE.parent/'regional_materials.py')
    regional = importlib.util.module_from_spec(regional_spec); regional_spec.loader.exec_module(regional)
    atlas, projection, total, materials, regional_evidence, _ = regional.append(atlas, projection, 'soot-and-brass', append_projected, terrain['metadata'])
    metadata = {'tileWidth': SIZE, 'tileHeight': SIZE, 'columns': COLUMNS,
                'count': total, 'canonicalCount': COUNT, 'preferredTileSize': SIZE,
                'groundLayers': True, 'waterPockets': {'version': 1},
                'lanternWalls': terrain['metadata'], 'projectedFrames': projection,
                'regionalMaterials': materials}
    retained = [p for p in HERE.rglob('*') if p.is_file()
                and p.suffix in ('.png', '.json', '.md', '.py', '.txt')
                and not p.name.endswith('provenance.json') and '__pycache__' not in p.parts]
    report = {'schema': 1, 'engineVersion': '5.0.0', 'canonicalSlots': COUNT,
              'creatureScale': {'file': '../creature-scale.json', 'sha256': digest(HERE.parent/'creature-scale.json'),
                                'helper': '../creature_scale.py', 'helperSha256': digest(HERE.parent/'creature_scale.py')},
              'uniqueArtKeys': len(known), 'directionalVariants': len(terrain['variants']),
              'projectedFrames': len(projection['frames']),
              'catalog': {'file': '../lantern/catalog.json', 'sha256': digest(CATALOG)},
              'regionalMaterials': regional_evidence, 'sources': evidence, 'assignments': assignments,
              'proceduralKeys': sorted(terrain['canonical']),
              'retainedInputs': [{'file': str(p.relative_to(HERE)), 'sha256': digest(p)} for p in sorted(retained)],
              'packerSha256': digest(HERE.parent/'packing.py'),
              'artworkLicense': 'CC-BY-4.0', 'artworkCredit': 'NetHack Atlas project'}
    return {'image': atlas, 'metadata': metadata, 'evidence': report}


if __name__ == '__main__':
    raise SystemExit('Build tilesets with: python3 scripts/build-tilesets.py')
