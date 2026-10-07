#!/usr/bin/env python3
"""Construct original Lantern terrain at its final 32-pixel resolution.

User-authorized pixel construction and cleanup, September 24, 2026. Textures
come only from this project's original generated terrain-01.png. Original stone
shading and ground detail are preserved within corrected masks and opacity.
No third-party pixel data is read.
Geometry is exact: connected wall ports occupy pixels 10..21 inclusive;
opposite edge profiles are identical; open doors leave a visible passage.
Requires Pillow for development only. Artwork is licensed under CC-BY-4.0.
"""

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SIZE = 32
PORTS = {
    'vertical': 'NS', 'horizontal': 'WE', 'tlcorn': 'SE', 'trcorn': 'SW',
    'blcorn': 'NE', 'brcorn': 'NW', 'cross-wall': 'NSEW', 'tuwall': 'NEW',
    'tdwall': 'SEW', 'tlwall': 'NSW', 'trwall': 'NSE',
}
NAMES = [*PORTS, 'vertical-open-door', 'horizontal-open-door',
         'vertical-closed-door', 'horizontal-closed-door', 'no-door',
         'floor-of-a-room', 'dark-part-of-a-room', 'corridor', 'lit-corridor',
         'pool', 'water', 'stone', 'unexplored', 'nothing',
         'engraving-in-a-room', 'engraving-in-a-corridor']
DONOR = HERE / 'sources/terrain-01.png'
DONOR_SHA256 = '8f105d44b3c2f50c29c2668a84a17a4ee934c16f14a268a9c7c970e4041577a3'


@lru_cache(maxsize=1)
def donor_image():
    if hashlib.sha256(DONOR.read_bytes()).hexdigest() != DONOR_SHA256:
        raise ValueError('Original terrain donor changed; review texture coordinates first')
    return Image.open(DONOR).convert('RGBA')


def donor_cell(column, row):
    image = donor_image()
    return image.crop((round(column * image.width / 8), round(row * image.height / 8),
                       round((column + 1) * image.width / 8), round((row + 1) * image.height / 8)))


@lru_cache(maxsize=1)
def stone_textures():
    # Trim the original straight-wall cell's surrounding transparent margins.
    # The donor's bright cap, bevels and darker masonry face are kept intact.
    horizontal = donor_cell(2, 0).crop((5, 28, 151, 141)).resize(
        (32, 12), Image.Resampling.NEAREST).convert('RGB')
    vertical = horizontal.transpose(Image.Transpose.ROTATE_90)
    profile = [tuple(int(median(horizontal.getpixel((x, y))[channel] for x in range(32)))
                     for channel in range(3)) for y in range(12)]
    return horizontal, vertical, profile


def wall_mask(ports):
    image = Image.new('L', (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 21, 21), fill=255)
    rectangles = {'N': (10, 0, 21, 15), 'S': (10, 16, 21, 31),
                  'W': (0, 10, 15, 21), 'E': (16, 10, 31, 21)}
    for edge in ports:
        draw.rectangle(rectangles[edge], fill=255)
    return image


def wall(ports):
    mask = wall_mask(ports)
    pixels = mask.load()
    image = Image.new('RGBA', (SIZE, SIZE))
    output = image.load()
    horizontal_texture, vertical_texture, profile = stone_textures()

    def inside(x, y):
        # Connected arms continue into adjacent cells, rather than receiving caps.
        if y < 0:
            return 'N' in ports and 10 <= x <= 21
        if y >= SIZE:
            return 'S' in ports and 10 <= x <= 21
        if x < 0:
            return 'W' in ports and 10 <= y <= 21
        if x >= SIZE:
            return 'E' in ports and 10 <= y <= 21
        return pixels[x, y] != 0

    for y in range(SIZE):
        for x in range(SIZE):
            if not inside(x, y):
                continue
            horizontal = 10 <= y <= 21 and ('W' in ports or 'E' in ports)
            color = (horizontal_texture.getpixel((x, y - 10)) if horizontal else
                     vertical_texture.getpixel((x - 10, y)))
            if not inside(x, y + 1) or not inside(x + 1, y):
                color = tuple(int(channel * .66) for channel in color)
            output[x, y] = (*color, 255)

    # Identical profiles at every matching port. Two-pixel depth keeps texture
    # sampling or later nearest-neighbor display scaling from opening cracks.
    for edge in ports:
        for depth in (0, 1):
            for index, color in enumerate(profile):
                point = {'N': (10 + index, depth), 'S': (10 + index, 31 - depth),
                         'W': (depth, 10 + index), 'E': (31 - depth, 10 + index)}[edge]
                output[point] = (*color, 255)
    return image


def door(opened, horizontal=False):
    image = wall('NS')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 8, 31, 23), fill=(0, 0, 0, 0))
    # Both door states retain the same stone jambs and boundary connections.
    draw.rectangle((10, 6, 21, 7), fill=(176, 181, 167, 255))
    draw.rectangle((10, 24, 21, 25), fill=(70, 83, 86, 255))
    if opened:
        # Hinged panel swings away from the center passage into the upper right.
        draw.polygon([(11, 8), (14, 7), (29, 12), (28, 16), (13, 11)],
                     fill=(56, 36, 23, 255))
        draw.polygon([(14, 8), (27, 12), (27, 14), (14, 10)],
                     fill=(151, 105, 55, 255))
        draw.line((15, 8, 27, 12), fill=(208, 164, 87, 255))
        draw.line((19, 10, 19, 11), fill=(64, 45, 29, 255))
        draw.line((24, 11, 24, 13), fill=(64, 45, 29, 255))
        draw.point((27, 13), fill=(237, 189, 88, 255))
    else:
        draw.rectangle((10, 8, 21, 23), fill=(37, 30, 24, 255))
        # Original closed-door wood retains its small irregular highlights and
        # grooves, inside the precise blocking silhouette.
        wood = donor_cell(7, 1).crop((66, 32, 102, 59)).resize(
            (10, 16), Image.Resampling.NEAREST).convert('RGB').convert('RGBA')
        image.paste(wood, (11, 8))
        draw.rectangle((11, 10, 20, 11), fill=(55, 57, 50, 255))
        draw.rectangle((11, 20, 20, 21), fill=(55, 57, 50, 255))
        for point in ((12, 10), (19, 10), (12, 20), (19, 20)):
            draw.point(point, fill=(145, 143, 104, 255))
        draw.rectangle((16, 14, 19, 18), fill=(224, 180, 89, 255))
        draw.rectangle((17, 15, 18, 17), fill=(41, 35, 28, 255))
    # Rotation preserves identical opaque port profiles and clear traversable gap.
    if horizontal:
        image = image.transpose(Image.Transpose.ROTATE_90)
        # Reapply canonical profiles because rotating a lit edge reverses it.
        reference = wall('WE')
        for x in (0, 1, 30, 31):
            for y in range(SIZE):
                image.putpixel((x, y), reference.getpixel((x, y)))
    return image


def floor(dark=False, corridor=False, engraved=False):
    if engraved:
        column, row = (5, 2)
    else:
        column, row = (4, 2) if dark else (3, 2)
    return opaque_ground(donor_cell(column, row), (42, 51, 59) if dark else (49, 59, 66))


def opaque_ground(source, base):
    image = Image.new('RGBA', (SIZE, SIZE), (*base, 255))
    image.alpha_composite(source.resize((SIZE, SIZE), Image.Resampling.NEAREST))
    # Repair only the outer pixel ring. Paired mean colors preserve the donor's
    # masonry/water variations while making repeated opposite edges identical.
    for y in range(SIZE):
        left, right = image.getpixel((0, y)), image.getpixel((31, y))
        color = tuple((a + b) // 2 for a, b in zip(left, right))
        image.putpixel((0, y), color)
        image.putpixel((31, y), color)
    for x in range(SIZE):
        top, bottom = image.getpixel((x, 0)), image.getpixel((x, 31))
        color = tuple((a + b) // 2 for a, b in zip(top, bottom))
        image.putpixel((x, 0), color)
        image.putpixel((x, 31), color)
    return image


def water(deep=False):
    # Use the original open-water cell, not the framed pool/basin illustration.
    source = donor_cell(4, 6)
    # Its original image has a transparent inset around the surface. Extend the
    # actual water texture to every edge instead of repeating that inset frame.
    source = source.crop((12, 12, source.width - 12, source.height - 12))
    return opaque_ground(source, (22, 46, 66))


def tiles():
    result = {name: wall(ports) for name, ports in PORTS.items()}
    result.update({
        'vertical-open-door': door(True), 'horizontal-open-door': door(True, True),
        'vertical-closed-door': door(False), 'horizontal-closed-door': door(False, True),
        'no-door': floor(), 'floor-of-a-room': floor(), 'dark-part-of-a-room': floor(dark=True),
        'corridor': floor(dark=True, corridor=True), 'lit-corridor': floor(corridor=True),
        'pool': water(), 'water': water(deep=True),
        'stone': Image.new('RGBA', (SIZE, SIZE), (16, 24, 26, 255)),
        'unexplored': Image.new('RGBA', (SIZE, SIZE), (8, 14, 16, 255)),
        'nothing': Image.new('RGBA', (SIZE, SIZE), (8, 14, 16, 255)),
        'engraving-in-a-room': floor(engraved=True),
        'engraving-in-a-corridor': floor(corridor=True, engraved=True),
    })
    return result


def fixtures(art, directory):
    directory.mkdir(parents=True, exist_ok=True)
    # Rooms have both horizontal and vertical doors and a wall junction.
    rows = [
        'A---O---B A-------B',
        '|.......| |.......|',
        '|.......C.V.~~~...|',
        '|.......| |.~~~...|',
        'D---H---E D---P---E',
    ]
    lookup = {'A': 'tlcorn', 'B': 'trcorn', 'D': 'blcorn', 'E': 'brcorn',
              '|': 'vertical', '-': 'horizontal', '.': 'floor-of-a-room',
              'C': 'vertical-closed-door', 'V': 'vertical-open-door',
              'O': 'horizontal-open-door',
              'H': 'horizontal-closed-door', 'P': 'horizontal-open-door', '~': 'pool'}
    image = Image.new('RGBA', (max(map(len, rows)) * SIZE, len(rows) * SIZE), (8, 14, 16, 255))
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char == ' ':
                continue
            image.alpha_composite(art['floor-of-a-room'], (x * SIZE, y * SIZE))
            image.alpha_composite(art[lookup[char]], (x * SIZE, y * SIZE))
    image.resize((image.width * 3, image.height * 3), Image.Resampling.NEAREST).save(directory / 'rooms.png')
    sheet = Image.new('RGBA', (8 * 128, 4 * 148), (17, 24, 28, 255))
    draw = ImageDraw.Draw(sheet)
    for index, name in enumerate(NAMES):
        x, y = index % 8 * 128, index // 8 * 148
        sample = art['floor-of-a-room'].copy()
        sample.alpha_composite(art[name])
        sheet.alpha_composite(sample.resize((128, 128), Image.Resampling.NEAREST), (x, y))
        draw.text((x + 2, y + 132), name[:21], fill=(223, 216, 192, 255))
    sheet.save(directory / 'individual-tiles.png')


def generate(output, registry=None, preview_dir=None):
    art = tiles()
    sheet = Image.new('RGBA', (8 * SIZE, 4 * SIZE))
    for index, name in enumerate(NAMES):
        sheet.paste(art[name], (index % 8 * SIZE, index // 8 * SIZE))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    if registry is not None:
        metadata = json.loads(registry.read_text())
        metadata['sheets'] = [entry for entry in metadata['sheets'] if entry['id'] != 'terrain-geometry']
        metadata['sheets'].append({
            'id': 'terrain-geometry', 'file': 'sources/terrain-geometry.png',
            'columns': 8, 'rows': 4, 'grid': 'exact', 'sha256': sha,
            'origin': 'original-pixel-construction', 'generator': 'build_geometry.py',
            'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'texture_inputs': [{
                'file': 'sources/terrain-01.png', 'sha256': DONOR_SHA256,
                'columns': 8, 'rows': 8, 'grid': 'normalized',
                'use': 'Original wall masonry, door wood, room/dark/engraved floor and open water; '
                       'bounded crop, nearest-neighbor resize, geometry masks, opaque ground edge repair',
            }],
            'prompt_file': 'TERRAIN-PROMPTS.md',
        })
        for key in metadata['art']:
            name = key.removeprefix('terrain/')
            if '-walls-' in name:
                name = name.split('-walls-', 1)[1]
            if name in NAMES:
                index = NAMES.index(name)
                metadata['art'][key] = {'sheet': 'terrain-geometry', 'column': index % 8, 'row': index // 8}
        used = {entry['sheet'] for entry in metadata['art'].values()}
        metadata['sheets'] = [entry for entry in metadata['sheets'] if entry['id'] in used]
        registry.write_text(json.dumps(metadata, indent=2) + '\n')
    if preview_dir is not None:
        fixtures(art, preview_dir)
    return sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'sources/terrain-geometry.png')
    parser.add_argument('--registry', type=Path,
                        help='Update this source registry after generating the image')
    parser.add_argument('--previews', type=Path, default=ROOT / '.artifacts/lantern-geometry')
    args = parser.parse_args()
    print(generate(args.output, args.registry, args.previews))


if __name__ == '__main__':
    main()
