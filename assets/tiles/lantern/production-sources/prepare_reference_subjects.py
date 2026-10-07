#!/usr/bin/env python3
"""Extract the exact nine subject samples from the original Lantern concept.

Only cropping, edge-connected background-alpha removal and nearest-neighbor
resampling are used. The original source image remains unchanged.
"""
from collections import deque
import hashlib
import json
from pathlib import Path
from statistics import median
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'reference-concept.png'
# Source-image pixel coordinates, right/bottom exclusive. Manually inspected
# at 3x to keep the complete outline, weapons, tails, feet and fountain base.
SUBJECTS = {
    'hero': {'box': (70, 148, 171, 269), 'max_size': (56, 60)},
    'dog': {'box': (253, 163, 371, 271), 'max_size': (52, 48)},
    'goblin': {'box': (451, 154, 565, 273), 'max_size': (56, 58)},
    'ant': {'box': (55, 362, 182, 474), 'max_size': (50, 44)},
    'potion': {'box': (281, 362, 347, 454), 'max_size': (28, 36)},
    'scroll': {'box': (462, 363, 561, 454), 'max_size': (38, 38)},
    'chest': {'box': (69, 563, 174, 670), 'max_size': (50, 50)},
    'stairs': {'box': (261, 558, 373, 675), 'max_size': (60, 60)},
    'fountain': {'box': (451, 541, 573, 680), 'max_size': (60, 60)},
}


def extract(crop):
    image = crop.convert('RGBA')
    width, height = image.size
    data = list(image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata())
    edges = [y*width+x for y in range(height) for x in range(width)
             if x < 2 or y < 2 or x >= width-2 or y >= height-2]
    anchor = tuple(round(median(data[i][c] for i in edges)) for c in range(3))
    def background(i):
        r, g, b, _ = data[i]
        # The cards use neutral dark charcoal, not the later atlas studio green.
        # A fixed measured border anchor keeps black subject outlines intact.
        return min(r, g, b) >= 19 and max(abs(data[i][c]-anchor[c]) for c in range(3)) <= 8
    remove = bytearray(len(data)); queue = deque()
    for i in edges:
        if background(i) and not remove[i]:
            remove[i] = 1; queue.append(i)
    while queue:
        i = queue.popleft(); x, y = i%width, i//width
        for j in (i-1 if x else -1, i+1 if x+1<width else -1,
                  i-width if y else -1, i+width if y+1<height else -1):
            if j>=0 and not remove[j] and background(j):
                remove[j] = 1; queue.append(j)
    image.putdata([(r,g,b,0 if remove[i] else a) for i,(r,g,b,a) in enumerate(data)])
    bounds = image.getchannel('A').getbbox()
    if not bounds:
        raise ValueError('The extraction removed the subject')
    return image.crop(bounds), {'borderAnchor': anchor, 'subjectBoundsInCrop': bounds,
                                'removedBackgroundPixels': sum(remove)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=HERE.parents[3]/'.artifacts/reference-extraction')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    record = json.loads((HERE/'reference-extraction-provenance.json').read_text())
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == record['sourceSha256']
    with Image.open(SOURCE) as opened:
        original = opened.convert('RGBA')
    expected = {entry['name']: entry for entry in record['subjects']}
    for name, spec in SUBJECTS.items():
        subject, _ = extract(original.crop(spec['box']))
        limit_w, limit_h = spec['max_size']
        scale = min(limit_w/subject.width, limit_h/subject.height)
        small = subject.resize((round(subject.width*scale), round(subject.height*scale)),
                               Image.Resampling.NEAREST)
        tile = Image.new('RGBA', (64,64), (0,0,0,0))
        tile.alpha_composite(small, ((64-small.width)//2, 62-small.height))
        output = args.output_dir/f'reference-{name}.png'
        tile.save(output)
        assert hashlib.sha256(output.read_bytes()).hexdigest() == expected[name]['sha256'], name
    print(f'Reproduced {len(SUBJECTS)} exact production reference subjects in {args.output_dir}')


if __name__ == '__main__':
    main()
