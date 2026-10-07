"""Append sacred light-stone derivatives while retaining all shipped geometry.

Only visible architecture and ordinary ground are aliased. Family artwork is the
source, not concept art. Alpha, offsets, wall masks, open apertures and alternates
remain exact; the shared renderer selects them using its existing rules.
"""
import copy
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFilter, ImageChops

HERE = Path(__file__).resolve().parent
RECIPE = HERE / 'regions/astral/material.json'
WALL_ALIASES = tuple(range(1273, 1284))
WALL_SOURCES = tuple(range(1504, 1515))
FLOORS = tuple(range(1291, 1297))


def recolor(image, kind, family, recipe, detail_mask=None):
    """Change RGB selectively; transparent pixels and every alpha value stay exact."""
    pixels = []
    soft = image.filter(ImageFilter.MedianFilter(recipe['floorMedianKernel'])) if kind == 'floor' else image
    settings = recipe['palette'][family]
    details = list(detail_mask.getdata()) if detail_mask is not None else [0] * (image.width*image.height)
    for index, (original, smoothed, detail) in enumerate(zip(image.getdata(), soft.getdata(), details)):
        r, g, b, alpha = original
        if not alpha:
            pixels.append(original)
            continue
        lum = .2126*r + .7152*g + .0722*b
        if kind == 'floor':
            # Quiet fine grain, retaining source joints and visible engraving.
            blurred = .2126*smoothed[0] + .7152*smoothed[1] + .0722*smoothed[2]
            base = lum * .55 + blurred * .45
            value = base * recipe['floorContrast'] + recipe['floorLift']
            x, y = index % image.width, index // image.width
            border = x < recipe['floorJointWidth'] or y < recipe['floorJointWidth'] or x >= image.width-recipe['floorJointWidth'] or y >= image.height-recipe['floorJointWidth']
            if border and lum < recipe['floorJointThreshold']:
                value = lum * .8 + recipe['floorJointLift']
            elif detail:
                # Only source-derived engraving strokes retain extra local
                # contrast. Ordinary dark-floor grain never becomes a joint.
                value += (lum-blurred) * recipe['engravingContrast']
            colors = [value + component for component in settings['stoneBias']]
        elif r > g*1.1 and g > b*1.14:
            # Existing warm wood/metal stays warm. Polish only bright golden
            # fittings; darker timber and deep metal shadows remain unchanged.
            lift = recipe['metalLift'] if r > 110 and g > 80 and g > b*1.28 else 0
            colors = [r + lift, g + lift*.8, b + lift*.35]
        else:
            # Neutral stone only. Keep near-black mortar and spatial shading;
            # the brighter source coping is still brighter than the wall face.
            weight = max(0, min(1, (lum-24)/90))
            lift = recipe['stoneLift'] * weight
            colors = [lum + lift + component*weight for component in settings['stoneBias']]
        pixels.append((*[round(max(0, min(255, value))) for value in colors], alpha))
    result = image.copy()
    result.putdata(pixels)
    return result



def engraving_mask(engraved, plain, recipe):
    """Select existing central scratch strokes, excluding unrelated floor grain.

    Source floors do not always share the same background crop. Require both a
    difference from the corresponding ordinary floor and a local stroke contrast
    within the source engraving bounds; never infer marks outside the source.
    """
    source = engraved.convert('L')
    difference = ImageChops.difference(engraved.convert('RGB'), plain.convert('RGB')).convert('L')
    local = source.filter(ImageFilter.MedianFilter(7))
    x0, y0, x1, y1 = recipe['engravingBounds']
    result = Image.new('L', source.size)
    mask = []
    for index, (value, background, delta) in enumerate(zip(source.getdata(), local.getdata(), difference.getdata())):
        x, y = index % source.width, index // source.width
        mask.append(255 if x0 <= x < x1 and y0 <= y < y1 and delta > 10 and abs(value-background) > 8 else 0)
    result.putdata(mask)
    return result


def append(atlas, projection, family, pack, architecture):
    """Return atlas, projection, count, material, evidence, added frame IDs."""
    recipe = json.loads(RECIPE.read_text())
    if family not in recipe['families']:
        raise ValueError('Astral material requires original Atlas artwork')
    sources = {slot: slot for slot in FLOORS}
    if family == 'lantern':
        sources[1284] = 1284
    sources.update(zip(WALL_ALIASES, WALL_SOURCES))
    wall_tiles = {}
    for alias, source in zip(WALL_ALIASES, WALL_SOURCES):
        rule = copy.deepcopy(architecture['tiles'][str(source)])
        wall_tiles[str(alias)] = rule
        sources.update((slot, slot) for slot in rule['variants'])
    for slot, rule in architecture['doors'].items():
        sources[int(slot)] = int(slot)
        sources.update((variant, variant) for variant in rule['variants'])
    first = atlas.height // 64 * 40
    tile_map = {str(alias): first+i for i, alias in enumerate(sorted(sources))}
    count = first + len(sources)
    output = Image.new('RGBA', (atlas.width, ((count+39)//40)*64))
    output.paste(atlas, (0, 0))
    frames = {}

    def projected(record, kind):
        x, y, width, height = record['source']
        frame = {'image': recolor(atlas.crop((x, y, x+width, y+height)), kind, family, recipe),
                 'offset': list(record['offset']), 'depth': record.get('depth', 64)}
        if record.get('kind'):
            frame['kind'] = record['kind']
        if record.get('alternates'):
            frame['alternates'] = [projected(alternate, kind) for alternate in record['alternates']]
        return frame

    def canonical(slot):
        x, y = slot % 40*64, slot // 40*64
        return atlas.crop((x, y, x+64, y+64))

    for alias, source in sorted(sources.items()):
        target = tile_map[str(alias)]
        kind = 'floor' if alias in FLOORS or alias == 1284 else 'architecture'
        x, y = source % 40 * 64, source // 40 * 64
        pixels = canonical(source)
        detail_mask = engraving_mask(pixels, canonical(1291 if alias == 1293 else 1292), recipe) if alias in (1293, 1296) else None
        output.paste(recolor(pixels, kind, family, recipe, detail_mask),
                     (target % 40*64, target // 40*64))
        if str(source) in projection['frames']:
            frames[target] = projected(projection['frames'][str(source)], kind)
    for rule in wall_tiles.values():
        rule['variants'] = [tile_map[str(variant)] for variant in rule['variants']]
    output, packed = pack(output, frames)
    result_projection = copy.deepcopy(projection)
    result_projection['frames'].update(packed['frames'])
    result_projection['padding'] = [max(a, b) for a, b in zip(projection['padding'], packed['padding'])]
    evidence = {'source': recipe['source'], 'sourcePixelSha256': hashlib.sha256(atlas.tobytes()).hexdigest(),
                'sourceSize': list(atlas.size), 'sourceSlots': sorted(set(sources.values())),
                'wallSourceSlots': list(WALL_SOURCES), 'canonicalWallAliases': list(WALL_ALIASES),
                'floorSlots': sorted(slot for slot in sources if slot in FLOORS or slot == 1284),
                'recipeSha256': hashlib.sha256(RECIPE.read_bytes()).hexdigest(),
                'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'license': recipe['license'], 'credit': recipe['credit'], 'scope': recipe['scope']}
    return output, result_projection, count, {'tileMap': tile_map, 'wallTiles': wall_tiles}, evidence, set(map(str, frames))
