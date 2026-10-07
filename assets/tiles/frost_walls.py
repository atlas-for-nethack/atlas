"""Record wall alpha contours for offline, source-faithful cosmetic frost.

Read-only analysis of artwork, never a terrain cache or image modification.
WKWebView file-origin canvases cannot reliably read image pixels at runtime.
"""
import json
from pathlib import Path


def metadata(image, projection, walls, materials):
    slots = set()
    for tiles in [walls['tiles'], *(m.get('wallTiles', {}) for m in materials.values())]:
        for slot, wall in tiles.items():
            slots.add(int(slot))
            slots.update(wall.get('variants', []))
    # Regional materials may shade a selected ordinary directional wall.
    ordinary_slots = tuple(slots)
    for material in materials.values():
        slots.update(material.get('tileMap', {}).get(str(slot), slot) for slot in ordinary_slots)
    shapes, seen, sources = [], {}, {}
    for slot in sorted(slots):
        record = projection['frames'].get(str(slot))
        if not record:
            continue
        for frame in [record, *record.get('alternates', [])]:
            sx, sy, w, h = frame['source']
            key = ','.join(map(str, frame['source']))
            if key in sources:
                continue
            alpha = image.getchannel('A').crop((sx, sy, sx+w, sy+h))
            top = [next((y for y in range(h) if alpha.getpixel((x,y)) > 128), h) for x in range(w)]
            left = [next((x for x in range(w) if alpha.getpixel((x,y)) > 128), w) for y in range(h)]
            right = [next((x for x in range(w-1,-1,-1) if alpha.getpixel((x,y)) > 128), -1) for y in range(h)]
            shape = dict(top=top, left=left, right=right)
            identity = json.dumps(shape, separators=(',', ':'))
            if identity not in seen:
                seen[identity] = len(shapes)
                shapes.append(shape)
            sources[key] = seen[identity]
    return dict(version=1, sources=sources, shapes=shapes)
