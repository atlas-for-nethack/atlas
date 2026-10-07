"""Compile tileset recipes into independently selectable PNGs. MIT license.

Source adapters prepare artwork only. This module owns validation, packing,
provenance, export and registration for every source kind.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import tempfile

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COUNT = 2304
MAX_PIXELS = 64_000_000
MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_PNG_BYTES = 64 * 1024 * 1024
REPORTS = {'official/provenance.json', 'lantern/classic-provenance.json',
           'lantern/modern-provenance.json', 'soot-and-brass/modern-provenance.json',
           'soot-and-brass/classic-provenance.json'}
RENDER_KEYS = {'groundLayers', 'waterPockets', 'lanternWalls', 'regionalMaterials',
               'projectedFrames', 'frostWalls'}
GEOMETRY_KEYS = {'tileWidth', 'tileHeight', 'columns', 'count', 'canonicalCount',
                 'preferredTileSize'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def local(root, name, exists=True):
    require(isinstance(name, str) and name and not Path(name).is_absolute(),
            'Paths must be nonempty relative paths')
    parts = Path(name).parts
    require('..' not in parts, f'Parent traversal is forbidden: {name}')
    path = root
    for part in parts:
        path = path / part
        require(not path.is_symlink(), f'Symlinks are forbidden: {name}')
    require(path.resolve().is_relative_to(root.resolve()), f'Nonlocal path: {name}')
    if exists:
        require(path.is_file(), f'Missing source: {name}')
    return path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


packing = module('atlas_shared_packing', HERE / 'packing.py')
frost = module('atlas_shared_frost', HERE / 'frost_walls.py')
payload = module('atlas_payload_policy', ROOT / 'scripts/package.py')


def checked_input(source, field='path', root=ROOT):
    path = local(root, source.get(field))
    require(re.fullmatch(r'[0-9a-f]{64}', str(source.get('sha256', ''))),
            f'Missing SHA-256 for {path}')
    require(path.stat().st_size <= MAX_INPUT_BYTES, f'Input exceeds 128 MiB: {path}')
    require(digest(path) == source['sha256'], f'Source checksum changed: {path}')
    return path


def validate_recipe(recipe):
    allowed = {'schemaVersion', 'id', 'name', 'engineVersion', 'output', 'provenance',
               'license', 'credit', 'licenseFile', 'description', 'version', 'source'}
    require(isinstance(recipe, dict) and not recipe.keys() - allowed, 'Unknown recipe fields')
    require(recipe.get('schemaVersion') == 1, 'Unsupported recipe schema')
    require(recipe.get('engineVersion') == '5.0.0', 'Recipes must target NetHack 5.0.0')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(recipe.get('id', ''))), 'Invalid tileset ID')
    for field in ('name', 'license', 'credit', 'description', 'version'):
        require(isinstance(recipe.get(field), str) and recipe[field].strip(), f'Missing {field}')
    require(Path(recipe.get('output', '')).suffix == '.png'
            and len(Path(recipe['output']).parts) == 1, 'Output must be a PNG filename')
    require(Path(recipe.get('provenance', '')).suffix == '.json', 'Provenance must be JSON')
    local(HERE, recipe['output'], exists=False)
    local(HERE, recipe['provenance'], exists=False)
    local(ROOT, recipe.get('licenseFile'))
    source = recipe.get('source')
    require(isinstance(source, dict), 'Missing source specification')
    if source.get('kind') == 'prepared':
        require(set(source) == {'kind', 'provider', 'creatureSizing'}, 'Unknown preparation fields')
        require(source['provider'] in ('lantern', 'soot-and-brass'), 'Unknown source preparer')
        require(source['creatureSizing'] in ('grid', 'stature'), 'Unknown creature sizing policy')
    else:
        require(source.get('kind') == 'atlas', 'Unknown source kind')
        require(not source.keys() - {'kind', 'path', 'sha256', 'tileWidth', 'tileHeight',
                                    'columns', 'count', 'preferredTileSize', 'rendering'},
                'Unknown atlas source fields')
        for key in ('tileWidth', 'tileHeight', 'columns', 'count'):
            require(type(source.get(key)) is int and source[key] > 0, f'Invalid {key}')
        require(source['count'] >= COUNT, 'The complete 5.0 tile ordering is required')


def atlas_source(source):
    path = checked_input(source)
    with Image.open(path) as opened:
        require(opened.format in ('PNG', 'BMP'), 'Source atlas must be PNG or BMP')
        require(opened.width <= 65536 and opened.height <= 65536
                and opened.width * opened.height <= MAX_PIXELS, 'Source image is too large')
        # Upstream tile2bmp writes nine blank scanlines after its final tile row.
        height = math.ceil(source['count'] / source['columns']) * source['tileHeight']
        require(opened.width == source['columns'] * source['tileWidth']
                and opened.height >= height, 'Source dimensions disagree with the declared grid')
        image = opened.convert('RGBA')
    metadata = {key: source[key] for key in ('tileWidth', 'tileHeight', 'columns', 'count')}
    metadata.update(canonicalCount=COUNT, preferredTileSize=source.get('preferredTileSize', 32))
    integer(metadata['preferredTileSize'], 'preferredTileSize', 1)
    inputs = [path]
    if 'rendering' in source:
        rendering_path = checked_input(source['rendering'])
        rendering = read(rendering_path)
        require(isinstance(rendering, dict) and not rendering.keys() - RENDER_KEYS,
                'Rendering metadata contains unsupported fields')
        metadata.update(rendering)
        inputs.append(rendering_path)
    return {'image': image, 'metadata': metadata, 'evidence': {'sourceKind': 'atlas'},
            'inputPaths': inputs}


def prepare(source, cache):
    if source['kind'] == 'atlas':
        return atlas_source(source)
    provider = source['provider']
    if provider not in cache:
        if provider == 'lantern':
            classic = module('atlas_lantern_source', HERE/'lantern/build_production.py').prepare()
            cache[provider] = module('atlas_lantern_creatures', HERE/'lantern/build_modern.py').prepare(classic)
        else:
            cache[provider] = module('atlas_soot_source', HERE/'soot-and-brass/build.py').prepare()
    return cache[provider]


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, f'Invalid {label}')
    return value


def slot(value, count):
    require((type(value) is int or isinstance(value, str) and value.isdigit())
            and 0 <= int(value) < count, f'Invalid tile reference: {value}')
    return int(value)


def references(metadata):
    """Collect every tile referenced by renderer metadata, never image padding."""
    count = metadata['count']
    result = set(range(COUNT))
    def visit(value, key=None):
        if key in ('variants', 'surfaces'):
            require(isinstance(value, list), f'Invalid {key}')
            result.update(slot(item, count) for item in value)
        elif key in ('tile', 'isolated', 'variantStart'):
            result.add(slot(value, count))
        elif key in ('tiles', 'doors', 'wallTiles', 'tileMap', 'frames'):
            require(isinstance(value, dict), f'Invalid {key}')
            for index, item in value.items():
                result.add(slot(index, count))
                if key == 'tileMap':
                    result.add(slot(item, count))
                else:
                    visit(item)
        elif isinstance(value, dict):
            for field, item in value.items():
                visit(item, field)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for key in ('lanternWalls', 'regionalMaterials', 'projectedFrames'):
        if key in metadata:
            visit(metadata[key])
    return result


def remap(value, mapping, key=None):
    if key in ('variants', 'surfaces'):
        return [mapping[int(item)] for item in value]
    if key in ('tile', 'isolated', 'variantStart'):
        return mapping[int(value)]
    if key in ('tiles', 'doors', 'wallTiles', 'tileMap', 'frames'):
        return {str(mapping[int(index)]): mapping[int(item)] if key == 'tileMap' else remap(item, mapping)
                for index, item in value.items()}
    if isinstance(value, dict):
        return {field: remap(item, mapping, field) for field, item in value.items()}
    if isinstance(value, list):
        return [remap(item, mapping) for item in value]
    return value


def extract_frame(frame, image):
    require(isinstance(frame, dict) and not frame.keys() -
            {'source', 'offset', 'depth', 'occupiedSquares', 'kind', 'alternates'},
            'Invalid projected frame fields')
    rect = frame.get('source')
    require(isinstance(rect, list) and len(rect) == 4, 'Missing projected source rectangle')
    x, y, w, h = [integer(v, 'projected rectangle') for v in rect]
    require(w > 0 and h > 0 and x+w <= image.width and y+h <= image.height,
            'Projected frame escapes its image')
    offset = frame.get('offset')
    require(isinstance(offset, list) and len(offset) == 2 and all(type(v) is int for v in offset),
            'Invalid projected offset')
    depth = integer(frame.get('depth', 56), 'projected depth')
    require(frame.get('kind') in (None, 'creature'), 'Unknown projected kind')
    result = {'image': image.crop((x,y,x+w,y+h)), 'offset': offset, 'depth': depth}
    if frame.get('kind'):
        result['kind'] = frame['kind']
    if 'alternates' in frame:
        require(isinstance(frame['alternates'], list), 'Invalid projected alternates')
        result['alternates'] = [extract_frame(item, image) for item in frame['alternates']]
    return result


def compile_image(prepared, source):
    image = prepared['image']
    metadata = copy.deepcopy(prepared['metadata'])
    require(not metadata.keys() - (GEOMETRY_KEYS | RENDER_KEYS), 'Unsupported prepared metadata')
    tw, th, columns, count = [integer(metadata.get(k), k, 1)
                             for k in ('tileWidth', 'tileHeight', 'columns', 'count')]
    require(count >= COUNT and metadata.get('canonicalCount', COUNT) == COUNT,
            'Incomplete or incompatible canonical tile ordering')
    require(image.width == columns*tw and image.height >= math.ceil(count/columns)*th,
            'Prepared image does not contain its declared grid')
    require(image.width * image.height <= MAX_PIXELS, 'Prepared image exceeds 64 million pixels')
    projection = metadata.pop('projectedFrames', None)
    metadata.pop('frostWalls', None)
    frames = {}
    if projection is not None:
        require(projection.get('version') == 1 and isinstance(projection.get('frames'), dict),
                'Unsupported projected frame metadata')
        selected = projection['frames']
        if source.get('creatureSizing') == 'grid':
            catalog = read(HERE/'lantern/catalog.json')
            creatures = {str(tile['slot']) for tile in catalog['tiles']
                         if tile['category'] == 'monster' or tile.get('transform') == 'statue'}
            selected = {index: frame for index, frame in selected.items() if index not in creatures}
        # Validate all input records, including frames omitted by this recipe.
        for index, frame in projection['frames'].items():
            slot(index, count)
            raw = extract_frame(frame, image)
            if index in selected:
                frames[int(index)] = raw
        metadata['projectedFrames'] = {'frames': selected}
    referenced = sorted(references(metadata))
    mapping = {old: new for new, old in enumerate(referenced)}
    metadata.pop('projectedFrames', None)
    metadata = remap(metadata, mapping)
    metadata['count'] = len(referenced)
    metadata['canonicalCount'] = COUNT
    out = Image.new('RGBA', (columns*tw, math.ceil(len(referenced)/columns)*th))
    for old, new in mapping.items():
        x, y = old % columns*tw, old // columns*th
        out.paste(image.crop((x,y,x+tw,y+th)), (new % columns*tw, new // columns*th))
    if projection is not None:
        # Projected rendering uses a 64-unit dungeon square independently of
        # canonical portrait resolution. Its metadata declares the capability.
        out, metadata['projectedFrames'] = packing.append_projected(
            out, {mapping[index]: raw for index, raw in frames.items()})
        if out.height % th:
            aligned = Image.new('RGBA', (out.width, math.ceil(out.height/th)*th))
            aligned.paste(out, (0,0))
            out = aligned
    if 'lanternWalls' in metadata:
        require(metadata['lanternWalls'].get('version') == 1, 'Unsupported wall metadata')
        require('projectedFrames' in metadata, 'Walls require declared projected frames')
        metadata['frostWalls'] = frost.metadata(out, metadata['projectedFrames'],
                                              metadata['lanternWalls'], metadata.get('regionalMaterials', {}))
    require(out.width <= 65536 and out.height <= 65536 and out.width*out.height <= MAX_PIXELS,
            'Compiled image exceeds supported dimensions')
    return out, metadata


def input_records(prepared, recipe, recipes):
    paths = set(prepared.get('inputPaths', []))
    paths.add(ROOT / 'scripts/package.py')
    source = recipe['source']
    if source['kind'] == 'prepared':
        # Keep every maintained source and helper, excluding generated receipts
        # and output images. This also captures shared regional source artwork.
        registered = [read(path) for path in sorted((HERE/'recipes').glob('*.json'))]
        outputs = {item['output'] for item in registered} | {item['output'] for _, item in recipes}
        reports = REPORTS | {item['provenance'] for item in registered} | {item['provenance'] for _, item in recipes}
        for path in HERE.rglob('*'):
            name = path.relative_to(HERE).as_posix()
            if (path.is_file() and not payload.forbidden(name)
                    and name not in outputs | reports | {'manifest.json'} and 'recipes' not in path.parts):
                paths.add(local(HERE, name))
    paths.add(local(ROOT, recipe['licenseFile']))
    return [{'file': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)} for path in sorted(paths)]


def publish(files):
    """Publish validated bytes and roll back on an ordinary filesystem error."""
    previous = {path: path.read_bytes() if path.exists() else None for path in files}
    installed = []
    try:
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
                staged.write(data)
                temporary = Path(staged.name)
            try:
                temporary.chmod(0o644)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            installed.append(path)
    except BaseException:
        for path in reversed(installed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous[path])
        raise


def build(recipe_paths, output_dir=HERE):
    output_dir = Path(output_dir).resolve()
    recipes = []
    for supplied in recipe_paths:
        path = Path(supplied).absolute()
        require(path.is_relative_to(ROOT), 'Recipes must be inside the repository')
        path = local(ROOT, path.relative_to(ROOT).as_posix())
        recipes.append((path, read(path)))
    require(recipes, 'No tileset recipes selected')
    for _, recipe in recipes:
        validate_recipe(recipe)
    for field in ('id', 'output', 'provenance'):
        require(len({r[field] for _, r in recipes}) == len(recipes), f'Duplicate recipe {field}')
    manifest_path = local(output_dir, 'manifest.json', exists=False)
    manifest = read(manifest_path) if manifest_path.exists() else {
        'engineVersion': '5.0.0', 'requiredTileCount': COUNT, 'default': recipes[0][1]['id'], 'tilesets': []}
    require(manifest.get('engineVersion') == '5.0.0' and manifest.get('requiredTileCount') == COUNT,
            'Incompatible existing manifest')
    selected_ids = {recipe['id'] for _, recipe in recipes}
    occupied = {item['file'] for item in manifest['tilesets'] if item['id'] not in selected_ids}
    require(not occupied & {recipe['output'] for _, recipe in recipes}, 'PNG output already belongs to another tileset')
    owners = {item['id']: item for item in manifest['tilesets']}
    for path, recipe in recipes:
        destination = local(output_dir, recipe['output'], exists=False)
        if destination.exists():
            require(owners.get(recipe['id'], {}).get('file') == recipe['output'],
                    'Existing PNG is not owned by this tileset')
        receipt_path = local(output_dir, recipe['provenance'], exists=False)
        if receipt_path.exists():
            old = read(receipt_path)
            require(isinstance(old, dict)
                    and old.get('recipe', {}).get('file') == path.relative_to(ROOT).as_posix()
                    and old.get('output', {}).get('file') == owners.get(recipe['id'], {}).get('file'),
                    'Existing provenance file is not owned by this recipe')
    cache, files, entries, all_inputs = {}, {}, [], set()
    import io
    for path, recipe in recipes:
        require(path.is_relative_to(ROOT), 'Recipes must be inside the repository')
        prepared = prepare(recipe['source'], cache)
        if recipe['source']['kind'] == 'prepared':
            require(recipe['license'] == prepared['evidence']['artworkLicense']
                    and recipe['credit'] == prepared['evidence']['artworkCredit']
                    and recipe['licenseFile'] == f'assets/tiles/{recipe["source"]["provider"]}/LICENSE.txt',
                    'Prepared artwork must retain its license, credit and notice')
        image, metadata = compile_image(prepared, recipe['source'])
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        data = buffer.getvalue()
        require(len(data) <= MAX_PNG_BYTES, 'Encoded PNG exceeds 64 MiB')
        revision = hashlib.sha256(data).hexdigest()
        entry = {key: recipe[key] for key in ('id', 'name', 'version', 'license', 'credit', 'description')}
        entry.update(file=recipe['output'], revision=revision, **metadata)
        entries.append(entry)
        inputs = input_records(prepared, recipe, recipes)
        all_inputs.update(ROOT/item['file'] for item in inputs)
        all_inputs.add(path)
        require(not {local(output_dir, recipe[field], exists=False) for field in ('output', 'provenance')}
                & {ROOT / item['file'] for item in inputs}, 'An output would overwrite a source input')
        report = {'schema': 1, 'engineVersion': '5.0.0',
                  'recipe': {'file': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)},
                  'compiler': {'file': 'assets/tiles/compiler.py', 'sha256': digest(Path(__file__))},
                  'packer': {'file': 'assets/tiles/packing.py', 'sha256': digest(HERE/'packing.py')},
                  'inputs': inputs,
                  'sourceEvidence': prepared['evidence'],
                  'output': {'file': recipe['output'], 'sha256': revision,
                             'width': image.width, 'height': image.height},
                  'artworkLicense': recipe['license'], 'artworkCredit': recipe['credit']}
        for name, contents in [(recipe['output'], data),
                               (recipe['provenance'], (json.dumps(report, indent=2)+'\n').encode())]:
            destination = local(output_dir, name, exists=False)
            require(destination not in files, 'Output path collision')
            files[destination] = contents
        image.close()
    replacements = {entry['id']: entry for entry in entries}
    manifest['tilesets'] = [replacements.pop(item['id'], item) for item in manifest['tilesets']]
    manifest['tilesets'].extend(replacements.values())
    require(len({entry['id'] for entry in manifest['tilesets']}) == len(manifest['tilesets']), 'Duplicate manifest ID')
    require(len({entry['file'] for entry in manifest['tilesets']}) == len(manifest['tilesets']),
            'Each selectable tileset must own a separate PNG; rebuild all shared entries together')
    require(manifest['default'] in {entry['id'] for entry in manifest['tilesets']}, 'Missing default tileset')
    require(manifest_path not in files, 'Manifest output collision')
    # The manifest is last, after every referenced PNG and receipt is ready.
    files[manifest_path] = (json.dumps(manifest, indent=2)+'\n').encode()
    require(not set(files) & all_inputs, 'An output would overwrite a source input')
    publish(files)
    return entries
