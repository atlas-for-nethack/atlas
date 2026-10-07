"""Shared packing for declared projected artwork. MIT, see LICENSE.txt."""
import hashlib
from PIL import Image

def occupied_squares(sprite, offset, tile_size=64):
    SIZE = tile_size
    """Grid squares touched by visible art, excluding transparent frame corners."""
    dx, dy = offset
    alpha = sprite.getchannel('A')
    squares = []
    for y in range(dy // SIZE, (dy + sprite.height - 1) // SIZE + 1):
        for x in range(dx // SIZE, (dx + sprite.width - 1) // SIZE + 1):
            box = (max(0, x * SIZE - dx), max(0, y * SIZE - dy),
                   min(sprite.width, (x + 1) * SIZE - dx),
                   min(sprite.height, (y + 1) * SIZE - dy))
            if alpha.crop(box).getbbox():
                squares.append([x, y])
    return squares


def append_projected(atlas, frames, tile_size=64):
    SIZE = tile_size
    """Pack full-resolution projected art below the unchanged canonical grid."""
    x, y, row_height = 0, atlas.height, 0
    entries, packed, seen = {}, [], {}
    padding = [0,0,0,0]
    def pack(frame):
        nonlocal x, y, row_height, padding
        sprite = frame['image']
        if sprite.mode != 'RGBA' or sprite.width > atlas.width:
            raise ValueError('Invalid projected sprite')
        identity = (sprite.size, hashlib.sha256(sprite.tobytes()).hexdigest())
        if identity not in seen:
            if x + sprite.width > atlas.width:
                x, y, row_height = 0, y + row_height, 0
            seen[identity] = [x,y,sprite.width,sprite.height]
            packed.append((sprite,(x,y)))
            x += sprite.width + 2
            row_height = max(row_height,sprite.height+2)
        dx,dy = frame['offset']
        record = {'source': seen[identity], 'offset': [dx,dy], 'depth': frame.get('depth',56)}
        record['occupiedSquares'] = occupied_squares(sprite, (dx, dy), SIZE)
        if frame.get('kind'):
            record['kind'] = frame['kind']
        padding = [max(padding[0],-dx),max(padding[1],-dy),
                   max(padding[2],dx+sprite.width-SIZE),max(padding[3],dy+sprite.height-SIZE)]
        if frame.get('alternates'):
            record['alternates'] = [pack(alternate) for alternate in frame['alternates']]
        return record
    for slot, frame in sorted(frames.items()):
        entries[str(slot)] = pack(frame)
    out = Image.new('RGBA',(atlas.width,((y+row_height+SIZE-1)//SIZE)*SIZE))
    out.paste(atlas,(0,0))
    for sprite,position in packed:
        out.paste(sprite,position)
    return out, {'version':1,'frames':entries,'padding':padding}


