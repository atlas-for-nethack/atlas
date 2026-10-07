#!/usr/bin/env python3
"""Deterministic, edge-connected alpha cleanup of original Lantern sprites.

clean_foreground(image, key) returns (RGBA image, metrics), at input resolution.
RGB values and all non-background alpha values remain unchanged. This helper
must run on an individual source cell before nearest-neighbor resizing.
"""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
VERSION = 1
FIXTURE_NAMES = frozenset("""
vertical-open-door horizontal-open-door vertical-closed-door horizontal-closed-door
iron-bars tree staircase-up staircase-down ladder-up ladder-down
branch-staircase-up branch-staircase-down branch-ladder-up branch-ladder-down
unaligned-altar chaotic-altar neutral-altar lawful-altar other-altar
grave throne sink fountain vertical-open-drawbridge horizontal-open-drawbridge
vertical-closed-drawbridge horizontal-closed-drawbridge arrow-trap dart-trap
falling-rock-trap squeaky-board bear-trap land-mine rolling-boulder-trap
sleeping-gas-trap rust-trap fire-trap pit spiked-pit hole trap-door
teleportation-trap level-teleporter magic-portal web statue-trap magic-trap
anti-magic-field polymorph-trap vibrating-square trapped-door trapped-chest
""".split())


def should_clean(key):
    """Select foreground art only; continuous ground, wall geometry and effects stay intact."""
    return key.startswith(('monster/', 'object/')) or key.removeprefix('terrain/') in FIXTURE_NAMES


def clean_foreground(image, key=''):
    """Remove only edge-connected studio green; preserve opaque black outlines.

The background anchor is inferred from the outer two-pixel border, restricted
    to the known dark green studio palette. Flood fill never follows a rolling
    color average: every removed pixel must match this fixed anchor and hue.
    Ambiguous interior pixels remain opaque and are reported for review.
    """
    result = image.convert('RGBA').copy()
    width, height = result.size
    pixels = list(result.get_flattened_data() if hasattr(result, 'get_flattened_data') else result.getdata())
    total = len(pixels)
    border = [y * width + x for y in range(height) for x in range(width)
              if x < 2 or y < 2 or x >= width - 2 or y >= height - 2]

    def studio(rgb):
        r, g, b = rgb[:3]
        return 14 <= r <= 42 and 23 <= g <= 51 and 19 <= b <= 47 and g-r >= 4 and g+3 >= b

    samples = [pixels[i][:3] for i in border if pixels[i][3] > 2 and studio(pixels[i])]
    anchor = tuple(round(median(p[c] for p in samples)) for c in range(3)) if len(samples) >= 8 else None

    def candidate(index):
        p = pixels[index]
        if p[3] <= 2:
            return True
        return bool(anchor and studio(p) and max(abs(p[c]-anchor[c]) for c in range(3)) <= 9)

    removed = bytearray(total)
    queue = deque()
    for i in border:
        if candidate(i) and not removed[i]:
            removed[i] = 1
            queue.append(i)
    while queue:
        i = queue.popleft()
        x, y = i % width, i // width
        for j in ((i-1 if x else -1), (i+1 if x+1 < width else -1),
                  (i-width if y else -1), (i+width if y+1 < height else -1)):
            if j >= 0 and not removed[j] and candidate(j):
                removed[j] = 1
                queue.append(j)
    # Fully transparent and negligible-alpha pixels do not carry visible detail.
    cleaned = [(p[0], p[1], p[2], 0) if removed[i] or p[3] <= 2 else p
               for i, p in enumerate(pixels)]
    result.putdata(cleaned)
    changed = sum(p[3] > 2 and cleaned[i][3] == 0 for i, p in enumerate(pixels))
    retained_candidates = sum(not removed[i] and p[3] > 2 and candidate(i)
                              for i, p in enumerate(pixels))
    opaque_edge = sum(cleaned[i][3] > 127 for i in border)
    visible = sum(p[3] > 127 for p in cleaned)
    warnings = []
    if anchor is None and sum(pixels[i][3] > 127 for i in border) > len(border)*0.1:
        warnings.append('no-confident-studio-border')
    if opaque_edge > max(8, len(border)*0.05):
        warnings.append('visible-art-near-cell-edge')
    if retained_candidates > max(12, total*0.004):
        warnings.append('enclosed-background-colored-pixels-retained')
    if not visible:
        warnings.append('no-opaque-subject')
    return result, {'key': key, 'version': VERSION, 'width': width, 'height': height,
                    'backgroundAnchor': list(anchor) if anchor else None,
                    'removedOpaquePixels': changed,
                    'transparentPixels': sum(p[3] == 0 for p in cleaned),
                    'visiblePixels': visible, 'opaqueBorderPixels': opaque_edge,
                    'enclosedCandidatePixels': retained_candidates,
                    'warnings': warnings}


def source_cells(root):
    manifest = json.loads((root/'sources.json').read_text())
    sheets = {}
    for spec in manifest['sheets']:
        path = root/spec['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec['sha256']:
            raise ValueError(f"Source checksum mismatch: {spec['id']}")
        sheets[spec['id']] = (Image.open(path).convert('RGBA'), spec)
    cells = {}
    for key, assignment in manifest['art'].items():
        image, spec = sheets[assignment['sheet']]
        x, y, cols, rows = assignment['column'], assignment['row'], spec['columns'], spec['rows']
        cells[key] = image.crop((round(x*image.width/cols), round(y*image.height/rows),
                                round((x+1)*image.width/cols), round((y+1)*image.height/rows)))
    return cells


def review_page(entries, sprites, ground, destination, heading):
    cell, cols, header = 160, 7, 36
    page = Image.new('RGB', (cols*cell, header+((len(entries)+cols-1)//cols)*cell), '#e0dfd8')
    draw = ImageDraw.Draw(page)
    draw.text((12, 12), heading, fill='#17221f')
    for index, (slot, label, key) in enumerate(entries):
        x, y = index%cols*cell, header+index//cols*cell
        # Each sprite is shown over both actual room-floor and water tiles.
        for i, background in enumerate(ground):
            tile = background.copy()
            tile.alpha_composite(sprites[key])
            page.paste(tile.resize((64, 64), Image.Resampling.NEAREST), (x+8+i*72, y+8))
        draw.text((x+8, y+80), str(slot)+' '+label[:20], fill='#17221f')
        draw.text((x+8, y+96), 'floor       water', fill='#40534a')
        # Actual 1:1 rendering is retained below the enlarged pair.
        for i, background in enumerate(ground):
            tile = background.copy(); tile.alpha_composite(sprites[key]);page.paste(tile, (x+16+i*64, y+114))
    page.save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=HERE)
    parser.add_argument('--output', type=Path, default=HERE.parents[2]/'.artifacts'/'lantern-foregrounds')
    parser.add_argument('--pilot', action='store_true', help='Only build seven representative sprites')
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((root/'catalog.json').read_text())
    tiles = {item['slot']: item for item in catalog['tiles']}
    cells = source_cells(root)
    pilot = [700, 32, 144, 0, 1088, 1114, 1006]
    keys = {tiles[n]['art_key'] for n in pilot} if args.pilot else {
        item['art_key'] for item in catalog['tiles'] if should_clean(item['art_key'])}
    sprites, metrics = {}, []
    for key in sorted(keys):
        image, report = clean_foreground(cells[key], key)
        sprite = image.resize((32, 32), Image.Resampling.NEAREST)
        report['file'] = key.replace('/', '__')+'.png'
        sprite.save(out/report['file'])
        report['outputSha256'] = hashlib.sha256((out/report['file']).read_bytes()).hexdigest()
        sprites[key] = sprite
        metrics.append(report)
    grounds = [cells[tiles[n]['art_key']].resize((32, 32), Image.Resampling.NEAREST) for n in (1291, 1324)]
    entries = [(n, tiles[n]['label'], tiles[n]['art_key']) for n in pilot]
    review_page(entries, sprites, grounds, out/'pilot-floor-water.png', 'Lantern foreground cleanup: 2x and actual 32px views')
    if not args.pilot:
        representatives = {}
        for slot, tile in tiles.items():
            if tile['art_key'] in keys:
                representatives.setdefault(tile['art_key'], (slot, tile['label'], tile['art_key']))
        ordered = [representatives[k] for k in sorted(keys)]
        for page, start in enumerate(range(0, len(ordered), 70)):
            review_page(ordered[start:start+70], sprites, grounds, out/f'review-{page:02d}.png', 'All foregrounds: original floor and water, 2x and actual size')
    report = {'schema': 1, 'cleanupVersion': VERSION, 'artKeys': len(metrics),
              'sourcesSha256': hashlib.sha256((root/'sources.json').read_bytes()).hexdigest(),
              'warnings': dict(Counter(w for m in metrics for w in m['warnings'])),
              'sprites': metrics}
    (out/'cleanup-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'artKeys': len(metrics), 'warnings': report['warnings'], 'pilot': str(out/'pilot-floor-water.png')}))


if __name__ == '__main__':
    main()
