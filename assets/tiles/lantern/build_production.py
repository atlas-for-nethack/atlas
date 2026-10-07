#!/usr/bin/env python3
"""Build the 64-pixel Lantern tileset and its wall appearances.

Original source artwork covers every engine slot. Reviewed reference extracts
and subsequent art batches override explicit keys, never engine appearances.
No third-party art is read. Pillow is a development-only dependency.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SIZE, COLUMNS, COUNT = 64, 40, 2304


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


base = module('lantern_assembly', HERE / 'build_atlas.py')


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def base_art(tiles, sources):
    """Cache only reproducible extraction, keyed by every source and helper byte."""
    keys = sorted({tile['art_key'] for tile in tiles})
    paths = [HERE / name for name in ('catalog.json', 'sources.json',
             'build_atlas.py', 'prepare_foregrounds.py')]
    paths += [base.local_file(HERE, s['file'], 'source', HERE / 'sources')
              for s in sources['sheets']]
    fingerprint = hashlib.sha256(''.join(base.digest(p) for p in paths).encode()).hexdigest()
    folder = ROOT / '.artifacts/lantern-production-cache'
    folder.mkdir(parents=True, exist_ok=True)
    image_path, record_path = folder / 'art.png', folder / 'record.json'
    if image_path.is_file() and record_path.is_file():
        record = base.read_json(record_path)
        if (record.get('fingerprint') == fingerprint and record.get('keys') == keys
                and record.get('imageSha256') == base.digest(image_path)):
            with Image.open(image_path) as opened:
                image = opened.convert('RGBA')
            art = {key: image.crop((i % COLUMNS * SIZE, i // COLUMNS * SIZE,
                                   (i % COLUMNS + 1) * SIZE, (i // COLUMNS + 1) * SIZE))
                   for i, key in enumerate(keys)}
            return art, record['inputs']
    art, evidence, _ = base.load_sources(HERE, sources, set(keys), tile_size=SIZE)
    image = Image.new('RGBA', (COLUMNS * SIZE, ((len(keys)+COLUMNS-1)//COLUMNS)*SIZE))
    for i, key in enumerate(keys):
        image.paste(art[key], (i % COLUMNS * SIZE, i // COLUMNS * SIZE))
    image.save(image_path)
    json_write(record_path, {'fingerprint': fingerprint, 'keys': keys,
                            'inputs': evidence, 'imageSha256': base.digest(image_path)})
    return art, evidence


def overrides(art):
    path = HERE / 'production-overrides.json'
    records = base.read_json(path)
    evidence = []
    for key, record in records.items():
        base.require(key in art, f'Override does not name a canonical art key: {key}')
        source = base.local_file(HERE, record['file'], 'production override')
        base.require(base.digest(source) == record['sha256'], f'Override checksum: {key}')
        base.require(record['sha256'] not in base.OLD_ART_HASHES, 'Third-party override forbidden')
        with Image.open(source) as opened:
            base.require(opened.size == (SIZE, SIZE), f'Override must be 64 square: {key}')
            art[key] = opened.convert('RGBA')
        evidence.append({'art_key': key, **record})
    return evidence


def prepare():
    """Prepare original pixels and source evidence without publishing assets."""
    catalog = base.read_json(HERE / 'catalog.json')
    sources = base.read_json(HERE / 'sources.json')
    prompt = base.local_file(HERE, sources['artwork']['prompt_file'], 'prompt_file')
    base.require(prompt.stat().st_size > 0, 'Prompt record is empty')
    tiles = base.validate_catalog(catalog)
    art, source_evidence = base_art(tiles, sources)
    override_evidence = overrides(art)
    walls = module('lantern_projected_architecture', HERE / 'projected_architecture.py').build()
    base.require(not (walls['canonical'].keys() - art.keys()), 'Unknown wall art keys')
    art.update(walls['canonical'])
    # The accepted floor is one visible square per engine step.
    ground_path = HERE / 'production-sources/reference-floor.png'
    with Image.open(ground_path) as opened:
        floor = opened.convert('RGBA')
    base.require(floor.size == (SIZE, SIZE), 'Reference floor must be 64 square')
    for key in ('terrain/floor-of-a-room', 'terrain/no-door', 'terrain/lit-corridor'):
        art[key] = floor.copy()
    from PIL import ImageEnhance
    for key in ('terrain/dark-part-of-a-room', 'terrain/corridor'):
        art[key] = ImageEnhance.Brightness(floor).enhance(.66)
    # A generic visible engraving marker, never the hidden text or its meaning.
    # Keep the same one-step paving seam beneath these shallow chisel marks.
    engraved = floor.copy()
    pen = ImageDraw.Draw(engraved)
    for points in [[(17, 29), (22, 24), (20, 36)], [(25, 27), (29, 32), (25, 37)],
                   [(34, 25), (32, 37)], [(39, 26), (44, 29), (38, 35)]]:
        pen.line([(x, y+1) for x, y in points], fill=(23, 29, 32, 255), width=2)
        pen.line(points, fill=(120, 127, 122, 255), width=1)
    for key in ('terrain/engraving-in-a-room', 'terrain/engraving-in-a-corridor'):
        art[key] = engraved.copy()
    variants = walls['variants']
    total = COUNT + len(variants)
    atlas = Image.new('RGBA', (COLUMNS * SIZE, ((total+COLUMNS-1)//COLUMNS)*SIZE))
    for tile in tiles:
        sprite = art[tile['art_key']]
        base.require(sprite.size == (SIZE, SIZE), f'Wrong sprite size: {tile["art_key"]}')
        if tile.get('transform') == 'statue':
            sprite = base.stone(sprite, sources['artwork'].get('background_rgb'))
        slot = tile['slot']
        atlas.paste(sprite, (slot % COLUMNS * SIZE, slot // COLUMNS * SIZE))
    for offset, sprite in enumerate(variants, COUNT):
        base.require(sprite.size == (SIZE, SIZE), 'Wrong wall variant size')
        atlas.paste(sprite, (offset % COLUMNS * SIZE, offset // COLUMNS * SIZE))
    packer = module('lantern_architecture_packer', HERE.parent / 'packing.py')
    atlas, projection = packer.append_projected(atlas, walls['projected'])
    regional = module('lantern_regional_materials', HERE.parent/'regional_materials.py')
    atlas, projection, total, materials, regional_evidence, _ = regional.append(atlas, projection, 'lantern', packer.append_projected, walls['metadata'])
    metadata = {'tileWidth': SIZE, 'tileHeight': SIZE, 'columns': COLUMNS,
                'count': total, 'canonicalCount': COUNT, 'preferredTileSize': SIZE,
                'groundLayers': True, 'waterPockets': {'version': 1},
                'lanternWalls': walls['metadata'], 'projectedFrames': projection,
                'regionalMaterials': materials}
    report = {'schema': 1, 'engineVersion': '5.0.0', 'canonicalSlots': COUNT,
              'totalImageSlots': total, 'tileWidth': SIZE, 'tileHeight': SIZE,
              'catalogSha256': base.digest(HERE/'catalog.json'),
              'sourceRegistrySha256': base.digest(HERE/'sources.json'),
              'prompts': [{'file': str(p.relative_to(HERE)), 'sha256': base.digest(p)}
                          for p in sorted(HERE.rglob('*PROMPTS.md'))],
              'regionalMaterials': regional_evidence, 'inputs': source_evidence, 'reviewedOverrides': override_evidence,
              'floor': {'file': str(ground_path.relative_to(HERE)), 'sha256': base.digest(ground_path)},
              'wallGeneratorSha256': base.digest(HERE/'projected_architecture.py'),
              'wallSourceRecordSha256': base.digest(HERE/'modern-architecture/extraction.json'),
              'architectureSourceSha256': base.digest(HERE/'modern-architecture/source.png'),
              'packerSha256': base.digest(HERE.parent/'packing.py'),
              'barsSourceRecordSha256': base.digest(HERE/'production-sources/iron-bars-provenance.json'),
              'assemblerSha256': base.digest(Path(__file__)),
              'baseAssemblerSha256': base.digest(HERE/'build_atlas.py'),
              'cleanupSha256': base.digest(HERE/'prepare_foregrounds.py'),
              'artworkLicense': sources['artwork']['publication_license'],
              'artworkCredit': sources['artwork']['credit']}
    return {'image': atlas, 'metadata': metadata, 'evidence': report}


if __name__ == '__main__':
    raise SystemExit('Build tilesets with: python3 scripts/build-tilesets.py')
