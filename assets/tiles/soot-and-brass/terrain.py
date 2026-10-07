#!/usr/bin/env python3
"""Original Soot & Brass terrain, with source-faithful raised architecture.

The engine owns topology. Masks only choose which already perceived face is lit.
Original source pixels are retained verbatim; cropping, nearest-neighbor scaling,
branch stone treatments and effect slicing are reproducible. No Lantern pixels.
"""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

HERE = Path(__file__).resolve().parent
TOPOLOGIES = ('vertical', 'horizontal', 'tlcorn', 'trcorn', 'blcorn', 'brcorn',
              'cross-wall', 'tuwall', 'tdwall', 'tlwall', 'trwall')
PORTS = {'vertical': 'NS', 'horizontal': 'EW', 'tlcorn': 'ES', 'trcorn': 'WS',
         'blcorn': 'NE', 'brcorn': 'NW', 'cross-wall': 'NESW', 'tuwall': 'NEW',
         'tdwall': 'ESW', 'tlwall': 'NSW', 'trwall': 'NES'}
FAMILIES = ('main', 'mines', 'gehennom', 'knox', 'sokoban')
STARTS = (1273, 1471, 1482, 1493, 1504)
SURFACES = [1291,1292,1293,1294,1295,1296,1314,1315,1316,1322,1323,1324]

def blank(size=(64,64)):
    return Image.new('RGBA', size)

@lru_cache(None)
def source(sheet, index):
    if sheet in ('fixtures','traps'):
        extraction=json.loads((HERE/'terrain/extraction.json').read_text())
        entry=extraction[sheet]['cells'][str(index)]
        path=HERE/'terrain'/entry['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError(f'Extracted terrain subject changed: {path}')
        return Image.open(path).convert('RGBA')
    grid = {'fixtures':6, 'traps':5, 'effects':4}[sheet]
    image = Image.open(HERE / 'terrain' / (sheet + '-source.png')).convert('RGBA')
    x, y = index % grid, index // grid
    cell = image.crop((round(x*image.width/grid),round(y*image.height/grid),
                       round((x+1)*image.width/grid),round((y+1)*image.height/grid)))
    # Tiny subvisible alpha specks around a generated cell must not determine
    # sprite scale. Crop bounds use visible alpha; the retained alpha is unedited.
    box = cell.getchannel('A').point(lambda a:255 if a>32 else 0).getbbox()
    if not box:
        raise ValueError(f'Empty source cell: {sheet}/{index}')
    return cell.crop(box)

def fitted(image, width=58, height=58, bottom=61):
    image=image.copy()
    image.thumbnail((width,height),Image.Resampling.NEAREST)
    out=blank()
    out.alpha_composite(image,((64-image.width)//2,bottom-image.height))
    return out

def tone(image, tint=None, brightness=1):
    alpha=image.getchannel('A')
    if tint:
        image=ImageOps.colorize(ImageOps.grayscale(image),'#080b0d',tint).convert('RGBA')
    else:
        image=ImageEnhance.Brightness(image).enhance(brightness)
    image.putalpha(alpha)
    return image

def texture(index, size=(64,64)):
    if index==0:
        # A complete empty slab from the user's approved Odd Company board.
        # Keep its actual square-cell boundary and original pixel clusters.
        with Image.open(HERE/'terrain/approved-odd-company-source.png') as ref:
            return ref.convert('RGBA').crop((606,291,704,384)).resize(size,Image.Resampling.NEAREST)
    im=source('fixtures',index)
    # Material swatches have an illustrated outer bevel. Remove it before
    # repeating/projecting the actual material to avoid boxed floating floors.
    d=max(3,round(min(im.size)*.09))
    if index==34:
        # One walkable engine cell is one slab, not four decorative subcells.
        box=(d,d,round(im.width*.56),round(im.height*.44))
        im=im.crop(box).resize(size,Image.Resampling.NEAREST)
        ImageDraw.Draw(im).line((0,0,size[0]-1,0),fill='#131b21',width=1)
        ImageDraw.Draw(im).line((0,0,0,size[1]-1),fill='#131b21',width=1)
        return im
    material=im.crop((d,d,im.width-d,im.height-d)).resize(size,Image.Resampling.NEAREST)
    return material

def nonarchitectural():
    out={}
    fixtures={0:'floor-of-a-room',1:'corridor',2:'stone',3:'pool',4:'ice',5:'molten-lava',
      6:'staircase-up',7:'staircase-down',8:'ladder-up',9:'ladder-down',10:'fountain',11:'sink',
      12:'throne',13:'grave',14:'unaligned-altar',15:'chaotic-altar',16:'neutral-altar',17:'lawful-altar',
      18:'other-altar',19:'tree',20:'vertical-open-drawbridge',21:'horizontal-open-drawbridge',
      22:'horizontal-closed-drawbridge',23:'vertical-closed-drawbridge',24:'wall-of-lava',25:'air',
      26:'cloud',27:'water',28:'trapped-chest',29:'trapped-door',34:'engraving-in-a-room'}
    ground={0,1,2,3,4,5,27,34}
    for i,key in fixtures.items():out['terrain/'+key]=texture(i) if i in ground else fitted(source('fixtures',i))
    # Solid rock is blocked mass, not another paved surface. Retain its source
    # texture at a quiet, dark range so narrow corridors read immediately.
    rock = out['terrain/stone']
    subdued = ImageOps.colorize(ImageOps.grayscale(rock), '#101719', '#354047').convert('RGBA')
    subdued.putalpha(rock.getchannel('A'))
    out['terrain/stone'] = subdued
    out['terrain/dark-part-of-a-room']=tone(out['terrain/floor-of-a-room'],brightness=.47)
    out['terrain/lit-corridor']=tone(out['terrain/corridor'],brightness=1.25)
    out['terrain/engraving-in-a-corridor']=tone(out['terrain/engraving-in-a-room'],brightness=.68)
    for name in ('staircase-up','staircase-down','ladder-up','ladder-down'):
        im=out['terrain/'+name].copy()
        # Small brass fork marker gives branch exits independent visible identity.
        p=ImageDraw.Draw(im);p.line([(52,55),(52,44),(47,39)],fill='#eec574',width=3)
        p.line([(52,44),(57,39)],fill='#eec574',width=3)
        out['terrain/branch-'+name]=im
    names=('arrow-trap','dart-trap','falling-rock-trap','squeaky-board','bear-trap','land-mine',
      'rolling-boulder-trap','sleeping-gas-trap','rust-trap','fire-trap','pit','spiked-pit','hole',
      'trap-door','teleportation-trap','level-teleporter','magic-portal','web','statue-trap',
      'magic-trap','anti-magic-field','polymorph-trap','vibrating-square')
    for i,name in enumerate(names):out['terrain/'+name]=fitted(source('traps',i))
    for name in ('unexplored','nothing','no-door'):out['terrain/'+name]=blank()
    beams=('missile','fire','frost','sleep','death','lightning','poison-gas','acid')
    for i,name in enumerate(beams):
        base=fitted(source('effects',i),30,64,64)
        for direction,angle in enumerate((0,90,45,-45)):
            out[f'effect/{name}-zap-{i+1}-{direction}']=base.rotate(angle,Image.Resampling.NEAREST)
    out['effect/dig-beam']=fitted(source('effects',8))
    out['effect/flash-beam']=fitted(source('effects',9))
    boom=fitted(source('effects',10))
    out['effect/boom-left']=boom.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    out['effect/boom-right']=boom
    for i in range(4):
        shield=fitted(source('traps',24),46+i*4,46+i*4,55+i*2)
        out[f'effect/shield{i+1}']=shield
    out['effect/poison-cloud']=fitted(tone(source('fixtures',26),'#9eb447'))
    out['effect/valid-position']=fitted(source('traps',14),38,38,50)
    explosion_sources={'dark':source('effects',12),'noxious':tone(source('effects',12),'#acc140'),
      'muddy':source('effects',13),'wet':source('effects',14),'magical':tone(source('effects',12),'#d893ff'),
      'fiery':source('effects',15),'frosty':tone(source('effects',14),'#e2ffff')}
    for typ,im in explosion_sources.items():
        im=im.resize((192,192),Image.Resampling.NEAREST)
        for row,rname in enumerate(('top','middle','bottom')):
            for col,cname in enumerate(('left','center','right')):
                out[f'effect/explosion-{typ}-{rname}-{cname}']=im.crop((col*64,row*64,(col+1)*64,(row+1)*64))
    swallow=source('effects',11).resize((192,192),Image.Resampling.NEAREST)
    for row,rname in enumerate(('top','middle','bottom')):
        for col,cname in enumerate(('left','center','right')):
            if (row,col)!=(1,1):out[f'effect/swallow-{rname}-{cname}']=swallow.crop((col*64,row*64,(col+1)*64,(row+1)*64))
    colors=('#79b986','#b6c775','#e5d267','#eea856','#eb7847','#ee4949')
    for i,color in enumerate(colors):
        gauge=fitted(source('traps',23));p=ImageDraw.Draw(gauge)
        theta=math.radians(150-i*60)
        p.line((32,34,32+16*math.cos(theta),34-16*math.sin(theta)),fill=color,width=3)
        p.ellipse((29,31,35,37),fill='#f1d6a0')
        for n in range(i+1):p.rectangle((17+n*5,48,19+n*5,51),fill=color)
        out[f'effect/warning-{i}']=gauge
    return out

@lru_cache(None)
def architecture_module():
    import importlib.util
    path=HERE/'terrain/projected_architecture.py'
    spec=importlib.util.spec_from_file_location('soot_projected_architecture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def build_wall_art(variant_start=2304):
    record=json.loads((HERE/'terrain/provenance.json').read_text())
    for entry in record['sources']:
        path=HERE/entry['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError(f'Terrain source changed: {path}')
    result=architecture_module().build(variant_start)
    canonical=nonarchitectural();canonical.update(result['canonical'])
    result['canonical']=canonical
    return result


if __name__=='__main__':
    result=build_wall_art();a=architecture_module()
    output=HERE.parents[2]/'.artifacts/soot-and-brass-terrain';output.mkdir(parents=True,exist_ok=True)
    catalog=json.loads((HERE.parent/'lantern/catalog.json').read_text())
    expected={t['art_key'] for t in catalog['tiles'] if t['category'] in ('terrain','effect')}
    assert expected==set(result['canonical'])
    sheet=Image.new('RGBA',(640,88*((len(expected)+9)//10)),'#172023');pen=ImageDraw.Draw(sheet)
    for i,(key,im) in enumerate(result['canonical'].items()):
        x=i%10*64;y=i//10*88;sheet.alpha_composite(im,(x,y));pen.text((x+2,y+64),key.split('/')[-1][:10],fill='#efdbc0')
    sheet.save(output/'canonical-terrain.png')
    def place(target,f,x,y):
        if f.get('alternates'):f=f['alternates'][(x//64)%len(f['alternates'])]
        target.alpha_composite(f['image'],(x+f['offset'][0],y+f['offset'][1]))
    sheet=Image.new('RGBA',(128*6,160*5),'#0b1013');pen=ImageDraw.Draw(sheet)
    for row,mask in enumerate((4,1,2,8,15)):
        for col,(vertical,opened) in enumerate(((False,False),(False,True),(True,False),(True,True))):
            x=col*128;y=row*160
            for yy in range(2):sheet.alpha_composite(texture(0),(x+32,y+32+yy*64))
            place(sheet,a.door(vertical,opened,mask),x+32,y+80)
        for col,vertical in enumerate((False,True)):
            x=(col+4)*128;y=row*160
            for yy in range(2):sheet.alpha_composite(texture(0),(x+32,y+32+yy*64))
            place(sheet,a.bars(vertical,mask),x+32,y+80)
    sheet.save(output/'doors-and-bars.png')
    room=Image.new('RGBA',(768,448),'#0b1013');records=[];ox,oy=64,48
    for y in range(1,5):
        for x in range(1,9):room.alpha_composite(texture(0),(ox+x*64,oy+y*64))
    for x in range(1,9):records.extend([(a.wall('horizontal',4),x,0),(a.wall('horizontal',1),x,5)])
    for y in range(1,5):records.extend([(a.wall('vertical',2),0,y),(a.wall('vertical',8),9,y)])
    for t,x,y in [('tlcorn',0,0),('trcorn',9,0),('blcorn',0,5),('brcorn',9,5)]:records.append((a.wall(t,0),x,y))
    records=[r for r in records if (r[1],r[2]) not in ((0,3),(9,3))]
    for x,mask,opened in [(0,2,False),(9,8,True)]:
        room.alpha_composite(texture(0),(ox+x*64,oy+3*64));records.append((a.door(True,opened,mask),x,3))
    for f,x,y in sorted(records,key=lambda r:r[2]*64+r[0]['depth']):place(room,f,ox+x*64,oy+y*64)
    room.resize((1536,896),Image.Resampling.NEAREST).save(output/'projected-room.png')
    sheet=Image.new('RGBA',(96*11,160*5),'#0b1013');pen=ImageDraw.Draw(sheet)
    for row,(family,mask) in enumerate(zip(FAMILIES,(4,1,2,8,0))):
        for col,topology in enumerate(TOPOLOGIES):
            x,y=col*96,row*160;place(sheet,a.wall(topology,mask,family),x+16,y+64)
            pen.text((x+2,y+134),topology[:12],fill='#edc58c');pen.text((x+2,y+148),family,fill='#aaadae')
    sheet.save(output/'wall-topologies.png')
    crop_record={'sourceCrops':{name:{'file':f,'sourceBounds':list(box),'outputSize':list(size)} for name,(f,box,size) in a.CROPS.items()},'projection':'Arbitrary-size original directional art anchored to a 64-pixel logical floor cell. All sampling nearest-neighbor.'}
    (HERE/'terrain/architecture-crops.json').write_text(json.dumps(crop_record,indent=2)+'\n')
    print(f'{len(result["canonical"])} canonical keys, {len(result["variants"])} variants, {len(result["projected"])} projected frames')
