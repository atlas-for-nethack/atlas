"""Append approved Samurai plaster/timber architecture without changing a base tile.

Source crops use the existing family wall assembly and gate opening geometry.
Fresh module instances isolate its source callbacks and caches from other regions.
Only walls and directional gates are mapped; floor, bars and creature pixels stay
with the original family. Classic and Modern consume the same material metadata.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
FOLDER = HERE / 'regions/samurai'
WALL_SLOTS = tuple(range(1273, 1284))
DOORS = ((1285, True, True), (1286, False, True),
         (1287, True, False), (1288, False, False))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def private_architecture(family):
    """Fit approved material crops to established pieces, retaining perspective."""
    registry = json.loads((FOLDER / 'sources.json').read_text())
    if family not in registry['sources']:
        raise ValueError('Samurai architecture requires original Atlas artwork')
    record = registry['sources'][family]
    path = FOLDER / record['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('Approved Samurai source changed')
    source = Image.open(path).convert('RGBA')
    if list(source.size) != record['size']:
        raise ValueError('Wrong Samurai source geometry')
    relative = ('lantern/projected_architecture.py' if family == 'lantern'
                else 'soot-and-brass/terrain/projected_architecture.py')
    assembly = load_module('samurai_private_' + family, HERE / relative)
    original_piece = assembly.piece
    pieces = {}
    for name, entry in record['pieces'].items():
        piece = source.crop(entry['bounds']).resize(tuple(entry['size']), Image.Resampling.NEAREST)
        if entry.get('mirror'):
            piece = piece.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        pieces[name] = piece

    def piece(name):
        return pieces[name].copy() if name in pieces else original_piece(name)

    assembly.piece = piece
    assembly.family_image = lambda image, family: image.copy()
    assembly.FAMILIES = ('samurai',)
    assembly.STARTS = (1273,)
    original_straight = assembly.straight

    def straight(vertical, mask, family='samurai'):
        result = original_straight(vertical, mask, family)
        if not vertical:
            plain = {key: value for key, value in result.items() if key != 'alternates'}
            result = dict(plain, alternates=[plain, assembly.frame(piece('north-connector'), (0, -7), 64)])
        return result

    assembly.straight = straight
    side_closed = pieces['west-door']
    side_open = side_closed.copy()
    ImageDraw.Draw(side_open).polygon([(19, 7), (49, 10), (49, 80), (19, 80)], fill=(0, 0, 0, 0))
    # Reuse the approved gate's own wood, retaining the established turned-aside
    # leaf width and hinge plane. The source has no separate open gate drawing.
    side_open.alpha_composite(side_closed.crop((20, 10, 34, 81)), (20, 10))
    assembly.side_door = lambda opened: (side_open if opened else side_closed).copy()

    # The review provides a side gate only. Its wood becomes a frontal leaf;
    # the original front frame fixes the silhouette, coping and hinge geometry.
    front_closed = original_piece('front-door').copy()
    front_closed.alpha_composite(piece('north').crop((0, 0, 64, 15)), (0, 0))
    jamb = piece('west').resize((11, 68), Image.Resampling.NEAREST)
    front_closed.alpha_composite(jamb, (0, 15))
    front_closed.alpha_composite(jamb.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (53, 15))
    leaf = side_closed.crop((20, 15, 45, 75)).resize((42, 60), Image.Resampling.NEAREST)
    front_closed.alpha_composite(leaf, (11, 16))
    front_closed.putalpha(original_piece('front-door').getchannel('A'))
    front_open = front_closed.copy()
    ImageDraw.Draw(front_open).rectangle((10, 15, 53, 76), fill=(0, 0, 0, 0))
    # The same affine projection used by the existing approved Soot front door.
    p0, p1, p3 = (10, 15), (24, 23), (10, 75)
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    bx, by = p3[0] - p0[0], p3[1] - p0[1]
    determinant = ax * by - ay * bx
    a, b = leaf.width * by / determinant, -leaf.width * bx / determinant
    d, e = -leaf.height * ay / determinant, leaf.height * ax / determinant
    opened_leaf = leaf.transform(front_closed.size, Image.Transform.AFFINE,
                                 (a, b, -a*p0[0]-b*p0[1], d, e, -d*p0[0]-e*p0[1]),
                                 Image.Resampling.NEAREST)
    front_open.alpha_composite(opened_leaf)
    assembly.front_door = lambda opened: (front_open if opened else front_closed).copy()
    return assembly, registry, record, path, relative


def append(atlas, projection, family, pack, architecture):
    """Return append_region's six values, with wall rules and gate aliases only."""
    assembly, registry, record, source_path, relative = private_architecture(family)
    first = atlas.height // 64 * 40
    frames, tile_map, wall_tiles, seen = {}, {}, {}, {}
    next_slot = first + len(WALL_SLOTS) + len(DOORS)

    def index(frame):
        nonlocal next_slot
        digest = hashlib.sha256(frame['image'].tobytes() +
                                str((frame['image'].size, frame['offset'], frame['depth'])).encode()).hexdigest()
        if digest not in seen:
            seen[digest] = next_slot
            frames[next_slot] = frame
            next_slot += 1
        return seen[digest]

    masks = [sum(bit for bit, present in zip((1, 2, 4, 8), assembly.sides(mask)) if present)
             for mask in range(256)]
    for offset, topology in enumerate(assembly.TOPOLOGIES):
        slot, target = 1273 + offset, first + offset
        tile_map[str(slot)] = target
        frames[target] = assembly.wall(topology, 0, 'samurai')
        wall_tiles[str(slot)] = {'topology': topology, 'connections': assembly.PORTS[topology],
                                 'variants': [index(assembly.wall(topology, mask, 'samurai')) for mask in masks]}
    for offset, (slot, vertical, opened) in enumerate(DOORS):
        target = first + len(WALL_SLOTS) + offset
        tile_map[str(slot)] = target
        frames[target] = assembly.door(vertical, opened, 0)
        for mask, original_variant in enumerate(architecture['doors'][str(slot)]['variants']):
            generated = index(assembly.door(vertical, opened, masks[mask]))
            key = str(original_variant)
            if key in tile_map and tile_map[key] != generated:
                raise ValueError('Original door alias has incompatible Samurai poses')
            tile_map[key] = generated
    count = next_slot
    output = Image.new('RGBA', (atlas.width, ((count + 39) // 40) * 64))
    output.paste(atlas, (0, 0))
    for slot, frame in frames.items():
        output.paste(assembly.fallback(frame), (slot % 40 * 64, slot // 40 * 64))
    output, packed = pack(output, frames)
    result_projection = copy.deepcopy(projection)
    result_projection['frames'].update(packed['frames'])
    result_projection['padding'] = [max(a, b) for a, b in zip(projection['padding'], packed['padding'])]
    evidence = {'source': str(source_path.relative_to(HERE)), 'sha256': record['sha256'],
                'sourcePixelSha256': hashlib.sha256(atlas.tobytes()).hexdigest(),
                'sourceSize': list(atlas.size), 'wallCrops': record['pieces'],
                'architectureSha256': hashlib.sha256((HERE / relative).read_bytes()).hexdigest(),
                'registrySha256': hashlib.sha256((FOLDER / 'sources.json').read_bytes()).hexdigest(),
                'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'license': registry['license'], 'credit': registry['credit'],
                'scope': 'Approved plaster/timber walls and gates only; all other art unchanged.'}
    return (output, result_projection, count, {'tileMap': tile_map, 'wallTiles': wall_tiles},
            evidence, set(str(slot) for slot in frames))
