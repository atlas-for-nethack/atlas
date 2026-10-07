#!/usr/bin/env python3
"""Assemble original Lantern art with documented foreground alpha cleanup.

Development dependency: Pillow. No player dependency is introduced.
Read catalog.json and sources.json beside this script. sources.json schema 1:
  artwork: {origin: "original-ai-generated", tool: "image_gen",
            prompt_file: "PROMPTS.md", background_rgb: [24, 34, 33]}
  sheets: [{id, file: "sources/name.png", columns, rows, sha256, grid?}]
  art: {art_key: {sheet: id, column, row, extraction?}}
Optional reviewed extraction records specify absolute sourceBounds, local
keepBounds and clearEdgeAlphaMax. They change alpha only inside retained source
pixels, before resizing; sourceBounds can recover a subject crossing a grid cut.
Prompt paths are relative to this directory; source images must be inside its
sources/ directory. All sheets are regular square-cell grids, with no gutters.
The default grid policy "exact" requires integer cell dimensions. Explicit
"normalized" permits a square image and equal row/column count whose cell
edges are round(index * image_dimension / grid_count), when image generation
does not honor the requested output dimensions. Review such geometry visually.
Every catalog slot must have an explicit art assignment. Sharing an art_key is
allowed, but there is no fallback to another key, old artwork or a placeholder.

The optional catalog transform "statue" converts original monster art to a
stone ramp after downsampling: Pillow RGB luminance mapped linearly from
(26, 30, 34) to (191, 196, 190), preserving alpha, exact black, and the exact
declared background_rgb (if supplied). No fuzzy background detection is used;
generated background pixels that differ from the declaration become stone.
No upstream statue image or upstream pixel data is read.
"""

from collections import Counter, deque
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
_cleanup_spec = importlib.util.spec_from_file_location(
    'lantern_foregrounds', HERE / 'prepare_foregrounds.py')
_cleanup = importlib.util.module_from_spec(_cleanup_spec)
_cleanup_spec.loader.exec_module(_cleanup)
COUNT, COLUMNS, SIZE = 2304, 40, 32
# Exact copies of known third-party sheets are rejected even if renamed.
# This is an evidence guard, not an image-similarity or copyright detector.
OLD_ART_HASHES = {
    'f1e9cfebf6c6bdbbdcc1f62df6b530955974f21b96135f28bb5d97c328eb2770',
    '06baa643683fcaaa00c3abc6a93b07b19ad22df1fd884c4cb97bb993d35ff7ea',
    '8be40c664afc81e8f3a40644210a48e434889e821abb1504cd9dad4674d73c3e',
    'f3a9362fc5d315d7bb0261794d658cba6ba0e28ba486160c040c36091f1fceed',
    'b464ce7ea9259164be749858ed9f907527fea3e8c2768a2fa0800adf61574ad7',
    '556ab189b8a3a2e7d94c3496047b7392f34e05e2728ea2e08cea26ba2ca04fea',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum,
            f'{label} must be an integer >= {minimum}')
    return value


def local_file(root, name, label, within=None):
    require(isinstance(name, str) and name.strip(), f'Missing {label}')
    relative = Path(name)
    require(not relative.is_absolute(), f'{label} must be relative')
    path = (root / relative).resolve()
    require(path.is_relative_to((within or root).resolve()),
            f'{label} escapes its allowed directory: {name}')
    require(path.is_file(), f'{label} does not exist: {name}')
    return path


def stone(tile, background_rgb=None):
    gray = ImageOps.grayscale(tile)
    result = ImageOps.colorize(gray, (26, 30, 34), (191, 196, 190)).convert('RGBA')
    result.putalpha(tile.getchannel('A'))
    # Preserve the common black background rather than turning it into stone.
    red, green, blue, _ = tile.split()
    black = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
        lambda level: 255 if level == 0 else 0)
    if background_rgb is not None:
        difference = ImageChops.difference(
            tile.convert('RGB'), Image.new('RGB', tile.size, tuple(background_rgb)))
        red_diff, green_diff, blue_diff = difference.split()
        background = ImageChops.lighter(
            ImageChops.lighter(red_diff, green_diff), blue_diff).point(
                lambda level: 255 if level == 0 else 0)
        black = ImageChops.lighter(black, background)
    result.paste(tile, (0, 0), black)
    return result


def validate_catalog(catalog):
    require(catalog.get('schema') == 1, 'Unsupported catalog schema')
    require(catalog.get('engineVersion') == '5.0.0', 'Catalog engine must be 5.0.0')
    require(catalog.get('requiredTileCount') == COUNT, 'Catalog count must be 2304')
    tiles = catalog.get('tiles')
    require(isinstance(tiles, list) and len(tiles) == COUNT,
            'Catalog must contain exactly 2304 explicit slots')
    slots = set()
    for tile in tiles:
        require(isinstance(tile, dict), 'Tile entry must be an object')
        slot = integer(tile.get('slot'), 'slot')
        require(slot < COUNT and slot not in slots, f'Duplicate or invalid slot: {slot}')
        slots.add(slot)
        for field in ('label', 'category', 'art_key'):
            require(isinstance(tile.get(field), str) and tile[field].strip(),
                    f'Slot {slot} missing {field}')
        require(tile.get('transform') in (None, 'statue'),
                f'Slot {slot} has unsupported transform')
    return sorted(tiles, key=lambda item: item['slot'])


def load_sources(root, manifest, keys, tile_size=SIZE):
    require(manifest.get('schema') == 1, 'Unsupported sources schema')
    metadata = manifest.get('artwork', {})
    require(metadata.get('origin') in ('original-ai-generated', 'original-project-art'),
            'Source artwork must declare original project origin')
    require(metadata.get('tool') in ('image_gen', 'image_gen + build_geometry.py'),
            'Source artwork must identify its generation tools')
    require(metadata.get('foreground_cleanup') in (None, 'edge-connected-v1'),
            'Unsupported foreground cleanup policy')
    background = metadata.get('background_rgb')
    require(background is None or
            (isinstance(background, list) and len(background) == 3 and
             all(type(value) is int and 0 <= value <= 255 for value in background)),
            'background_rgb must contain three integer color channels in 0..255')
    prompt = local_file(root, metadata.get('prompt_file'), 'prompt_file')
    require(prompt.stat().st_size > 0, 'Prompt record is empty')
    assignments = manifest.get('art')
    require(isinstance(assignments, dict), 'Missing art assignments')
    missing = keys - assignments.keys()
    require(not missing, f'Missing art assignments: {sorted(missing)[:10]}')
    require(not assignments.keys() - keys, 'Unused art assignments must be removed')
    sheet_entries = manifest.get('sheets')
    require(isinstance(sheet_entries, list) and sheet_entries, 'Missing source sheets')
    sheets, evidence, source_paths, exact_geometry = {}, [], set(), set()
    for spec in sheet_entries:
        name = spec.get('id')
        require(isinstance(name, str) and name and name not in sheets,
                f'Duplicate or missing sheet id: {name}')
        path = local_file(root, spec.get('file'), 'source sheet', root / 'sources')
        require(path not in source_paths, 'Source file listed more than once')
        source_paths.add(path)
        require(path.suffix.lower() == '.png', 'Source sheets must be lossless PNG')
        sha = digest(path)
        require(sha not in OLD_ART_HASHES, 'Known third-party artwork is forbidden')
        require(isinstance(spec.get('sha256'), str) and
                re.fullmatch('[0-9a-f]{64}', spec['sha256']) and spec['sha256'] == sha,
                f'Source checksum missing or mismatched: {name}')
        columns = integer(spec.get('columns'), 'sheet columns', 1)
        rows = integer(spec.get('rows'), 'sheet rows', 1)
        with Image.open(path) as opened:
            require(opened.format == 'PNG', 'Source file is not a PNG image')
            opened.load()
            image = opened.convert('RGBA')
        width, height = image.size
        grid = spec.get('grid', 'exact')
        require(grid in ('exact', 'normalized'), f'Unknown grid policy: {grid}')
        if grid == 'exact':
            require(width % columns == 0 and height % rows == 0,
                    f'Sheet dimensions are not divisible by grid: {name}')
            require(width // columns == height // rows,
                    f'Sheet cells must be square: {name}')
        else:
            require(width == height and columns == rows,
                    f'Normalized grid needs square image and equal rows/columns: {name}')
        require(min(width // columns, height // rows) >= SIZE,
                f'Sheet cells must be at least 32 pixels: {name}')
        sheets[name] = (image, columns, rows)
        if spec.get('generator') == 'build_geometry.py':
            exact_geometry.add(name)
        evidence.append({'id': name, 'file': spec['file'], 'sha256': sha,
                         'origin': spec.get('origin', 'original-ai-generated'),
                         'generator': spec.get('generator', 'image_gen'),
                         'width': width, 'height': height, 'columns': columns,
                         'rows': rows, 'grid': grid,
                         'cellWidth': width / columns, 'cellHeight': height / rows})
    art, used_sheets = {}, set()
    for key, assignment in assignments.items():
        name = assignment.get('sheet')
        require(name in sheets, f'Unknown sheet for art key {key}: {name}')
        image, columns, rows = sheets[name]
        column = integer(assignment.get('column'), f'{key} column')
        row = integer(assignment.get('row'), f'{key} row')
        require(column < columns and row < rows, f'Art cell out of bounds: {key}')
        used_sheets.add(name)
        extraction = assignment.get('extraction', {})
        require(isinstance(extraction, dict), f'Invalid extraction record: {key}')
        bounds = extraction.get('sourceBounds',
                                [round(column * image.width / columns),
                                 round(row * image.height / rows),
                                 round((column + 1) * image.width / columns),
                                 round((row + 1) * image.height / rows)])
        validate_bounds(bounds, image.size, key)
        sprite = image.crop(bounds)
        if (metadata.get('foreground_cleanup') == 'edge-connected-v1'
                and name not in exact_geometry and _cleanup.should_clean(key)):
            sprite, _ = _cleanup.clean_foreground(sprite, key)
        sprite = reviewed_mask(sprite, extraction, key)
        art[key] = sprite.resize((tile_size, tile_size), Image.Resampling.NEAREST)
    require(used_sheets == sheets.keys(), 'Unused source sheets must be removed')
    return art, evidence, {'file': metadata['prompt_file'], 'sha256': digest(prompt)}


def validate_bounds(bounds, size, key):
    require(isinstance(bounds, list) and len(bounds) == 4
            and all(type(n) is int for n in bounds), f'Invalid crop bounds: {key}')
    x0, y0, x1, y1 = bounds
    require(0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1],
            f'Crop bounds outside source: {key}')


def reviewed_mask(sprite, extraction, key):
    """Apply only explicitly reviewed masks, preserving retained RGBA pixels.

    keepBounds excludes adjacent source-cell fragments and grid lines. Optional
    edge-alpha flood removes faint rectangular backing from shield effects,
    retaining their original translucent cores and any enclosed detail.
    """
    if not extraction:
        return sprite
    require(bool(extraction.get('reason')), f'Missing extraction rationale: {key}')
    keep = extraction.get('keepBounds', [0, 0, *sprite.size])
    validate_bounds(keep, sprite.size, key)
    result = sprite.copy()
    alpha = result.getchannel('A')
    retained = Image.new('L', result.size)
    retained.paste(alpha.crop(keep), keep[:2])
    threshold = extraction.get('clearEdgeAlphaMax')
    if threshold is not None:
        require(type(threshold) is int and 0 <= threshold < 128,
                f'Invalid edge alpha threshold: {key}')
        width, height = result.size
        pixels = bytearray(retained.tobytes())
        queue = deque(i for i, a in enumerate(pixels) if a <= threshold
                      and (i % width in (0, width-1) or i // width in (0, height-1)))
        seen = set(queue)
        while queue:
            i = queue.popleft()
            pixels[i] = 0
            x, y = i % width, i // width
            for j in (i-1 if x else -1, i+1 if x+1 < width else -1,
                      i-width if y else -1, i+width if y+1 < height else -1):
                if j >= 0 and j not in seen and pixels[j] <= threshold:
                    seen.add(j)
                    queue.append(j)
        retained = Image.frombytes('L', result.size, bytes(pixels))
    result.putalpha(retained)
    require(result.getchannel('A').getbbox(), f'Reviewed mask erased subject: {key}')
    return result


def previews(tiles, sprites, directory):
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    # Fixed-size pages keep all slot labels legible at 1:1 viewing.
    for page, start in enumerate(range(0, COUNT, 240)):
        entries = tiles[start:start + 240]
        preview = Image.new('RGB', (960, 100 * ((len(entries) + 11) // 12)), '#101316')
        draw = ImageDraw.Draw(preview)
        for index, tile in enumerate(entries):
            x, y = index % 12 * 80, index // 12 * 100
            sprite = sprites[tile['slot']].resize((64, 64), Image.Resampling.NEAREST)
            preview.paste(sprite, (x + 8, y), sprite)
            draw.text((x + 4, y + 66), str(tile['slot']), fill='#ded6b8')
            label = tile['label'].encode('ascii', 'replace').decode()
            draw.text((x + 4, y + 80), label[:12], fill='#ded6b8')
        path = directory / f'lantern-slots-{page:02d}.png'
        preview.save(path)
        paths.append(str(path))
    return paths


def prepare(root=HERE):
    """Prepare canonical source portraits in memory for extraction verification."""
    root = Path(root).resolve()
    catalog_path, sources_path = root / 'catalog.json', root / 'sources.json'
    catalog, manifest = read_json(catalog_path), read_json(sources_path)
    tiles = validate_catalog(catalog)
    keys = {tile['art_key'] for tile in tiles}
    art, evidence, prompt = load_sources(root, manifest, keys)
    atlas = Image.new('RGBA', (COLUMNS * SIZE, ((COUNT + COLUMNS - 1) // COLUMNS) * SIZE))
    for tile in tiles:
        sprite = art[tile['art_key']]
        if tile.get('transform') == 'statue':
            sprite = stone(sprite, manifest['artwork'].get('background_rgb'))
        slot = tile['slot']
        atlas.paste(sprite, (slot % COLUMNS * SIZE, slot // COLUMNS * SIZE))
    report = {
        'schema': 1, 'engineVersion': '5.0.0', 'tileCount': COUNT,
        'columns': COLUMNS, 'tileWidth': SIZE, 'tileHeight': SIZE,
        'assignedSlots': len(tiles), 'uniqueArtKeys': len(keys),
        'sharedArtSlots': COUNT - len(keys),
        'statueSlots': sum(tile.get('transform') == 'statue' for tile in tiles),
        'categories': dict(sorted(Counter(tile['category'] for tile in tiles).items())),
        'catalogSha256': digest(catalog_path), 'sourcesSha256': digest(sources_path),
        'prompt': prompt, 'inputs': evidence,
        'assemblerSha256': digest(HERE / 'build_atlas.py'),
        'geometryGeneratorSha256': digest(HERE / 'build_geometry.py')
            if any(item['generator'] == 'build_geometry.py' for item in evidence) else None,
        'transforms': {'resize': 'nearest-neighbor to 32x32',
                       'foregroundCleanup': manifest['artwork'].get('foreground_cleanup'),
                       'foregroundCleanupScriptSha256': digest(HERE / 'prepare_foregrounds.py'),
                       'statue': 'RGB luminance; stone ramp #1a1e22 to #bfc4be; '
                                 'preserve alpha, exact black and declared background; '
                                 'no fuzzy background detection',
                       'background_rgb': manifest['artwork'].get('background_rgb')},
    }
    metadata = {'tileWidth': SIZE, 'tileHeight': SIZE, 'columns': COLUMNS,
                'count': COUNT, 'canonicalCount': COUNT}
    return {'image': atlas, 'metadata': metadata, 'evidence': report}


if __name__ == '__main__':
    raise SystemExit('Build tilesets with: python3 scripts/build-tilesets.py')
