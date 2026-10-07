"""Shared Lantern architecture from the retained prototype source, at a 64-pixel floor pitch.

Real directional cap/face pixels replace flattened texture projections. Larger
door/frame silhouettes intentionally extend upward from their logical floor cell.
Only the existing visible-side mask selects direction; topology remains canonical.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

HERE=Path(__file__).resolve().parent
TOPOLOGIES=('vertical','horizontal','tlcorn','trcorn','blcorn','brcorn','cross-wall','tuwall','tdwall','tlwall','trwall')
PORTS={'vertical':'NS','horizontal':'EW','tlcorn':'ES','trcorn':'WS','blcorn':'NE','brcorn':'NW','cross-wall':'NESW','tuwall':'NEW','tdwall':'ESW','tlwall':'NSW','trwall':'NES'}
FAMILIES=('main','mines','gehennom','knox','sokoban')
STARTS=(1273,1471,1482,1493,1504)
SURFACES=[1291,1292,1293,1294,1295,1296,1314,1315,1316,1322,1323,1324]
SOURCE=HERE/'modern-architecture/source.png'
SIZES={'north':(64,71),'north-connector':(64,71),'west':(51,64),'east':(51,64),
       'south':(64,38),'northwest':(51,71),'northeast':(51,71),
       'southwest':(51,38),'southeast':(51,38),'front-door':(64,83),
       'front-open':(64,83),'west-door':(51,81),'open-side-leaf':(14,71)}

def blank(size=(64,64)):return Image.new('RGBA',size)

@lru_cache(None)
def piece(name):
    record=json.loads((HERE/'modern-architecture/extraction.json').read_text())
    path=SOURCE.parent/record['pieces'][name]['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sources'][path.name]:
        raise ValueError('Lantern architecture source changed')
    bounds=record['pieces'][name]['bounds']
    with Image.open(path) as source:
        image=source.convert('RGBA').crop(bounds)
    image.putalpha(image.getchannel('A').point(lambda a: 0 if a<=8 else 255 if a>=240 else a))
    return image.resize(SIZES[name],Image.Resampling.NEAREST)

def sides(mask):
    n,e,s,w=(bool(mask&bit) for bit in (1,2,4,8))
    if not(n or s):n,s=bool(mask&(16|128)),bool(mask&(32|64))
    if not(e or w):e,w=bool(mask&(16|32)),bool(mask&(64|128))
    return n,e,s,w

def frame(image,offset=(0,0),depth=64):return {'image':image,'offset':list(offset),'depth':depth}

def fallback(f):
    out=blank();out.alpha_composite(f['image'],tuple(f['offset']));return out

def portrait(f):
    im=f['image'].copy();im.thumbnail((64,64),Image.Resampling.NEAREST)
    out=blank();out.alpha_composite(im,((64-im.width)//2,64-im.height));return out

def family_image(im,family):
    if family=='main':return im.copy()
    tint={'mines':'#bea780','gehennom':'#bc766c','knox':'#d4cda0','sokoban':'#a7beb0'}[family]
    colored=ImageOps.colorize(ImageOps.grayscale(im),'#080c0e',tint).convert('RGBA')
    if family=='sokoban':
        # Sokoban remains ordinary dungeon masonry, with only a faint sage cast.
        # Preserve the original stone variation instead of replacing its palette.
        colored=Image.blend(im,colored,0.30)
    # Warm material accents retain source color; branch stone keeps source luminance.
    pixels=[]
    for original,recolored in zip(im.getdata(),colored.getdata()):
        r,g,b,a=original
        color=original if r>g*1.1 and g>b*1.14 else (*recolored[:3],a)
        if family=='sokoban':
            # Approved light-stone study: lift midtones, retaining dark mortar
            # and source-colored metal/wood accents. Brightness carries identity.
            cr,cg,cb,ca=color
            if ca and not (cr>cg*1.1 and cg>cb*1.14):
                lum=.2126*cr+.7152*cg+.0722*cb
                t=max(0,min(1,(lum-26)/74))
                lift=round(64*t*t*(3-2*t))
                color=(min(255,cr+lift),min(255,cg+lift),min(255,cb+lift),ca)
        pixels.append(color)
    colored.putdata(pixels);return colored

def straight(vertical,mask,family='main'):
    n,e,s,w=sides(mask)
    if not vertical:
        # A wall keeps its silhouette as exploration reveals either side.
        f=frame(family_image(piece('north'),family),(0,-7),64)
        return f
    if e and not w:return frame(family_image(piece('west'),family),(13,0))
    if w and not e:return frame(family_image(piece('east'),family),(0,0))
    # Shared/unknown wall shows both actual receding faces, with one broad crown.
    # No rotated front texture, and no invented hidden room-facing direction.
    im=blank((77,64))
    im.alpha_composite(piece('east').crop((0,0,26,64)),(0,0))
    im.alpha_composite(piece('west').crop((0,0,23,64)),(26,0))
    im.alpha_composite(piece('west').crop((23,0,51,64)),(49,0))
    return frame(family_image(im,family),(-6,0))

def canvas_frame(f,size=(96,128),origin=(16,64)):
    out=blank(size);out.alpha_composite(f['image'],(origin[0]+f['offset'][0],origin[1]+f['offset'][1]));return out

def trim_frame(im,origin=(16,64),depth=64):
    box=im.getchannel('A').getbbox()
    if not box:return frame(blank())
    return frame(im.crop(box),(box[0]-origin[0],box[1]-origin[1]),depth)

@lru_cache(None)
def wall(topology,mask,family='main'):
    if topology=='vertical':return straight(True,mask,family)
    if topology=='horizontal':return straight(False,mask,family)
    corners={'tlcorn':('northwest',(13,-7),64),'trcorn':('northeast',(0,-7),64),
             'blcorn':('southwest',(13,-7),64),'brcorn':('southeast',(0,-7),64)}
    if topology in corners:
        name,offset,depth=corners[topology]
        im=piece(name)
        if topology in ('blcorn','brcorn'):
            # Close the current room: its southern crown turns back north,
            # rather than repeating a northern column into an unseen room.
            # Keep the approved full-height face and the same floor anchor.
            start=13 if topology=='blcorn' else 0
            full=piece('north').crop((start,0,start+51,71))
            full.paste(im.crop((0,0,51,24)),(0,0))
            im=full
        return frame(family_image(im,family),offset,depth)
    # Join source edge bands at their real crown level, retaining each arm's
    # thickness and shading. Canonical ports alone decide which arms exist.
    h=canvas_frame(straight(False,mask,family));v=canvas_frame(straight(True,mask,family))
    ports=PORTS[topology];out=blank((96,128));cx=48;cy=82
    if 'W' in ports:out.alpha_composite(h.crop((0,0,cx,128)))
    if 'E' in ports:out.alpha_composite(h.crop((cx,0,96,128)),(cx,0))
    if 'N' in ports:out.alpha_composite(v.crop((0,0,96,cy)))
    if 'S' in ports:out.alpha_composite(v.crop((0,cy,96,128)),(0,cy))
    # One original capstone bridges the centre; do not overlay a front texture.
    cap=family_image(piece('south').crop((21,0,43,21)),family)
    out.alpha_composite(cap,(37,64))
    return trim_frame(out,depth=64)

def door_bounds(vertical,mask):
    n,e,s,w=sides(mask)
    if vertical:return [13 if e and not w else 0 if w and not e else 6,0,51,64]
    return [0,0,64,64]

@lru_cache(None)
def side_door(opened):
    im=piece('west-door').copy()
    if opened:
        # Same opening, hinge plane and turned-aside leaf geometry as the
        # approved Soot door. Its original stone jambs remain in both states.
        ImageDraw.Draw(im).polygon([(19,7),(49,10),(49,80),(19,80)],fill=(0,0,0,0))
        leaf=piece('open-side-leaf').transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im.alpha_composite(leaf,(20,10))
    return im

@lru_cache(None)
def front_door(opened):
    return piece('front-open' if opened else 'front-door').copy()

@lru_cache(None)
def door(vertical,opened,mask):
    n,e,s,w=sides(mask)
    if vertical:
        # Anchor the complete stone threshold to the corridor's south edge.
        # Opening the leaf never moves the doorway or changes its height.
        im=side_door(opened).crop((0,0,51,81))
        if w and not e:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return frame(im,(door_bounds(True,mask)[0],-17),64)
    return frame(front_door(opened).copy(),(0,-19),64)

@lru_cache(None)
def metal_rod():
    record=json.loads((HERE/'production-sources/iron-bars-provenance.json').read_text())
    path=HERE/record['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
        raise ValueError('Lantern bar source changed')
    return Image.open(path).convert('RGBA')

@lru_cache(None)
def bars(vertical,mask):
    n,e,s,w=sides(mask)
    if vertical:
        im=side_door(False).copy()
        ImageDraw.Draw(im).polygon([(19,7),(43,10),(43,72),(19,75)],fill=(0,0,0,0))
        for x in (23,31,39):im.alpha_composite(metal_rod().resize((3,61),Image.Resampling.NEAREST),(x,12))
        rail=metal_rod().resize((3,29),Image.Resampling.NEAREST).transpose(Image.Transpose.ROTATE_90)
        im.alpha_composite(rail,(20,19));im.alpha_composite(rail,(20,69))
        if w and not e:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return frame(im,(door_bounds(True,mask)[0],-17),64)
    im=piece('front-door').copy();ImageDraw.Draw(im).rectangle((14,17,50,79),fill=(0,0,0,0))
    for x in (17,27,37,47):im.alpha_composite(metal_rod().resize((3,62),Image.Resampling.NEAREST),(x,17))
    rail=metal_rod().resize((3,44),Image.Resampling.NEAREST).transpose(Image.Transpose.ROTATE_90)
    im.alpha_composite(rail,(10,23));im.alpha_composite(rail,(10,69))
    return frame(im,(0,-19),64)

def bars_join(connections,mask):
    h=canvas_frame(bars(False,mask));v=canvas_frame(bars(True,mask));out=blank((96,128));cx=48;cy=84
    if connections&8:out.alpha_composite(h.crop((0,0,cx,128)))
    if connections&2:out.alpha_composite(h.crop((cx,0,96,128)),(cx,0))
    if connections&1:out.alpha_composite(v.crop((0,0,96,cy)))
    if connections&4:out.alpha_composite(v.crop((0,cy,96,128)),(0,cy))
    return trim_frame(out)

def build(variant_start=2304):
    canonical={};variants=[];projected={};seen={}
    masks=[sum(bit for bit,present in zip((1,2,4,8),sides(m)) if present) for m in range(256)]
    def index(f):
        digest=hashlib.sha256(f['image'].tobytes()+str((f['image'].size,f['offset'],f['depth'])).encode()).hexdigest()
        if digest not in seen:
            tile=variant_start+len(variants);seen[digest]=tile;variants.append(fallback(f));projected[tile]=f
        return seen[digest]
    tiles={}
    for family,start in zip(FAMILIES,STARTS):
        for offset,topology in enumerate(TOPOLOGIES):
            f=wall(topology,0,family);canonical[f'terrain/{family}-walls-{topology}']=portrait(f);projected[start+offset]=f
            tiles[str(start+offset)]={'topology':topology,'connections':PORTS[topology],
              'variants':[index(wall(topology,m,family)) for m in masks]}
    doors={}
    for slot,vertical,opened in ((1285,True,True),(1286,False,True),(1287,True,False),(1288,False,False)):
        name=('vertical' if vertical else 'horizontal')+'-'+('open' if opened else 'closed')+'-door'
        f=door(vertical,opened,0);canonical['terrain/'+name]=portrait(f);projected[slot]=f
        doors[str(slot)]={'topology':('vertical' if vertical else 'horizontal')+'-door','open':opened,
          'variants':[index(door(vertical,opened,m)) for m in masks],'groundBounds':[door_bounds(vertical,m) for m in range(256)]}
    f=bars(False,0);canonical['terrain/iron-bars']=portrait(f);projected[1289]=f
    be={'tile':1289,'isolated':1289,'connections':{}}
    for vertical in (False,True):
        name='vertical' if vertical else 'horizontal'
        be[name]={'topology':name+'-bars','variants':[index(bars(vertical,m)) for m in masks],
          'groundBounds':[door_bounds(vertical,m) for m in range(256)]}
    for connections in (3,6,7,9,11,12,13,14,15):
        be['connections'][str(connections)]={'topology':'bars-junction','connections':connections,
          'variants':[index(bars_join(connections,m)) for m in masks],'groundBounds':[[0,0,64,64] for _ in range(256)]}
    return {'canonical':canonical,'variants':variants,'projected':projected,'metadata':{'version':1,'variantStart':variant_start,
      'neighborOrder':['N','E','S','W','NE','SE','SW','NW'],'surfaces':SURFACES,'tiles':tiles,'doors':doors,'bars':be}}
