"""Append approved materials and install the shared canonical Mines walls.

Engine cell.material selects these on the specified environment only.
Mines branch wall slots reuse approved excavation art without regional tags.
Canonical ordering, floors and every other environment remain unchanged.
"""
import hashlib
import copy
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageStat

HERE = Path(__file__).resolve().parent
CROPS = {
    'north': ((570,105,666,211),(64,71)),
    'north-connector': ((666,105,762,211),(64,71)),
    'west': ((255,211,331,307),(51,64)),
    'east': ((1211,211,1287,307),(51,64)),
    'south': ((431,578,527,635),(64,38)),
    'northwest': ((255,105,331,211),(51,71)),
    'northeast': ((1211,105,1287,211),(51,71)),
    'southwest': ((255,578,331,635),(51,38)),
    'southeast': ((1211,578,1287,635),(51,38)),
}
FLOOR_CROP = (521,217,606,288)

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

def append(atlas, projection, family, pack, architecture):
    materials, evidence, frames = {}, {}, set()
    for region, wall_start in [('mines', 1471), ('gehennom', 1482)]:
        atlas, projection, count, material, record, added = append_region(
            atlas, projection, family, pack, region, wall_start)
        materials[region] = material
        evidence[region] = record
        frames.update(added)
    atlas, projection, count, material, record, added = append_vlad(
        atlas, projection, family, pack, architecture)
    materials['vlad'] = material
    evidence['vlad'] = record
    frames.update(added)
    atlas, projection, count, material, record, added = append_asmodeus(
        atlas, projection, family, pack, architecture, materials)
    materials['asmodeus'] = material
    evidence['asmodeus'] = record
    frames.update(added)
    for treatment, region in [('normal', 'caveman'), ('goal', 'caveman-goal')]:
        atlas, projection, count, material, record, added = append_caveman(
            atlas, projection, family, pack, treatment)
        materials[region] = material
        evidence[region] = record
        frames.update(added)
    # Plane of Earth reuses the approved ordinary cave pixels and geometry.
    # Copy metadata only: solid stone and unknown space retain canonical art.
    materials['earth'] = copy.deepcopy(materials['caveman'])
    # Valley reuses the approved Vlad architecture and Gehennom ground.
    # Only metadata is composed; every source pixel and projection is retained.
    materials['valley'] = compose_valley(materials, architecture)
    evidence['valley'] = {
        'sourceMaterials': ['vlad', 'gehennom'],
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
        'canonicalWallAliases': list(range(1482, 1493)),
        'groundSlots': [slot for slot in (1284, *range(1291, 1297))
                        if str(slot) in materials['gehennom']['tileMap']],
        'license': evidence['vlad']['license'],
        'credit': evidence['vlad']['credit'],
    }
    # Outdoor Quest ground reuses only the approved lit/dark natural floor.
    # Priest temple architecture keeps Valley walls/doors with canonical floors.
    materials['quest-earth'] = compose_quest_earth(materials)
    materials['priest-temple'] = compose_priest_temple(materials)
    evidence.update(quest_reuse_evidence(evidence))
    # Built rooms in Minetown keep mine supports around canonical stone floors.
    materials['mines-built'] = compose_mines_built(materials)
    evidence['mines-built'] = mines_built_evidence(evidence)
    # Append the approved Samurai walls and gates after every existing region.
    # The module maps architecture only; ordinary floors and terrain stay exact.
    samurai = module('production_samurai_material', HERE/'samurai_material.py')
    atlas, projection, count, material, record, added = samurai.append(
        atlas, projection, family, pack, architecture)
    materials['samurai'] = material
    evidence['samurai'] = record
    frames.update(added)
    # Medusa reuses the shipped Sokoban wall family exactly. Its ordinary
    # doors, floors, water and inhabitants retain their canonical artwork.
    materials['medusa'] = compose_medusa(architecture)
    evidence['medusa'] = {
        'sourceFamily': 'sokoban', 'sourceWallSlots': list(range(1504, 1515)),
        'canonicalWallAliases': list(range(1273, 1284)),
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
        'unchanged': 'Doors, floors, water, trees, objects, creatures and statues.',
        'license': evidence['vlad']['license'],
        'credit': evidence['vlad']['credit'],
    }
    # Juiblex is an unlit swamp, with no walls in the reviewed upstream map.
    # Reuse only approved Gehennom dry ground, never water or blank stone.
    materials['juiblex'] = compose_juiblex(materials)
    evidence['juiblex'] = {
        'sourceMaterials': ['gehennom'], 'groundSlots': [1291, 1292],
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
        'unchanged': 'Water, blank stone, architecture, stairs, traps, fountains, objects and creatures.',
        'license': evidence['gehennom']['license'],
        'credit': evidence['gehennom']['credit'],
    }
    # Baalzebub's original fly fortress reuses approved Gehennom architecture.
    # Copy metadata only, including ordinary wall aliases for shared fixtures.
    materials['baalz'] = compose_baalz(materials)
    evidence['baalz'] = {
        'sourceMaterials': ['gehennom'],
        'canonicalWallSlots': list(range(1482, 1493)),
        'canonicalWallAliases': list(range(1273, 1284)),
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
        'unchanged': 'Doors, bars, blank stone, water, lava, traps, stairs, objects and creatures.',
        'license': evidence['gehennom']['license'],
        'credit': evidence['gehennom']['credit'],
    }
    # All Mines architecture is excavated rock, including named settlements.
    # Change only the dedicated wall slots. Floors still require the existing
    # engine regional tag, including named Mines levels.
    mines = materials['mines']
    for slot in range(1471, 1482):
        key = str(slot)
        source = mines['tileMap'][key]
        sx, sy = source % 40 * 64, source // 40 * 64
        atlas.paste(atlas.crop((sx, sy, sx + 64, sy + 64)),
                    (slot % 40 * 64, slot // 40 * 64))
        architecture['tiles'][key] = copy.deepcopy(mines['wallTiles'][key])
        projection['frames'][key] = copy.deepcopy(projection['frames'][str(source)])
        frames.add(key)
    evidence['mines']['canonicalWallSlots'] = list(range(1471, 1482))
    evidence['mines']['canonicalWallPolicy'] = 'All Mines walls use approved excavated rock/supports; canonical floors unchanged.'
    # Astral appends the approved pale sanctuary derivative last. Every older
    # material keeps its allocation, source pixels and directional geometry.
    astral = module('production_astral_material', HERE/'astral_material.py')
    atlas, projection, count, material, record, added = astral.append(
        atlas, projection, family, pack, architecture)
    materials['astral'] = material
    evidence['astral'] = record
    frames.update(added)
    return atlas, projection, count, materials, evidence, frames


def compose_medusa(architecture):
    """Use native Sokoban canonical and directional wall sources unchanged."""
    return {
        'tileMap': {str(1273+i): 1504+i for i in range(11)},
        'wallTiles': {str(1273+i): copy.deepcopy(architecture['tiles'][str(1504+i)])
                      for i in range(11)},
    }


def compose_quest_earth(materials):
    """Reuse only Caveman lit/dark floor, without architecture or hazards."""
    return {'tileMap': {str(slot): materials['caveman']['tileMap'][str(slot)]
                        for slot in (1291, 1292)}}


def compose_priest_temple(materials):
    """Retain Valley architectural aliases without its infernal ground."""
    result = copy.deepcopy(materials['valley'])
    for slot in (1284, *range(1291, 1297)):
        result['tileMap'].pop(str(slot), None)
    return result


def compose_mines_built(materials):
    """Retain approved mine architecture, with canonical interior ground."""
    result = copy.deepcopy(materials['mines'])
    for slot in (1284, *range(1291, 1297)):
        result['tileMap'].pop(str(slot), None)
    return result


def mines_built_evidence(evidence):
    """Record existing mine-pixel reuse without new atlas content."""
    return {
        'sourceMaterials': ['mines'],
        'removedGroundSlots': [1284, *range(1291, 1297)],
        'generator': 'assets/tiles/regional_materials.py',
        'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
        'unchanged': 'Mine walls, supports, doors, canonical interior floors, hazards, fixtures, objects and creatures.',
        'license': evidence['mines']['license'],
        'credit': evidence['mines']['credit'],
    }


def quest_reuse_evidence(evidence):
    """Describe metadata composition under the existing artwork permissions."""
    common = {
        'generator': 'assets/tiles/regional_materials.py',
        'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'pixelPolicy': 'Metadata-only reuse; no appended or modified pixels.',
    }
    return {
        'quest-earth': dict(common, sourceMaterials=['caveman'], groundSlots=[1291, 1292],
            unchanged='Walls, doors, corridors, hazards, blank stone, water, lava, fixtures, objects and creatures.',
            license=evidence['caveman']['license'], credit=evidence['caveman']['credit']),
        'priest-temple': dict(common, sourceMaterials=['valley'],
            removedGroundSlots=[1284, *range(1291, 1297)],
            unchanged='Canonical interior floors, corridors, water, lava, altars, stairs, objects and creatures.',
            license=evidence['valley']['license'], credit=evidence['valley']['credit']),
    }


def compose_juiblex(materials):
    """Use the exact approved Gehennom lit and remembered dry-ground sources."""
    return {'tileMap': {str(slot): materials['gehennom']['tileMap'][str(slot)]
                        for slot in (1291, 1292)}}


def compose_baalz(materials):
    """Reuse the approved Gehennom material and every directional wall pose."""
    result = copy.deepcopy(materials['gehennom'])
    for offset in range(11):
        ordinary, infernal = str(1273 + offset), str(1482 + offset)
        result['tileMap'][ordinary] = result['tileMap'][infernal]
        result['wallTiles'][ordinary] = copy.deepcopy(result['wallTiles'][infernal])
    return result


def compose_valley(materials, architecture):
    """Compose the approved Valley preview from existing environmental metadata.

    Gehennom canonical walls use ordinary dungeon poses before the Vlad map
    selects their darker frames. Doors, bars and all directional aliases retain
    the existing Vlad mappings. No supplementary slots or pixels are created.
    """
    vlad = materials['vlad']['tileMap']
    gehennom = materials['gehennom']['tileMap']
    tile_map = copy.deepcopy(vlad)
    wall_tiles = {}
    for offset in range(11):
        ordinary, infernal = str(1273 + offset), str(1482 + offset)
        wall_tiles[ordinary] = copy.deepcopy(architecture['tiles'][ordinary])
        wall_tiles[infernal] = copy.deepcopy(architecture['tiles'][ordinary])
        tile_map[infernal] = vlad[ordinary]
    for slot in (1284, *range(1291, 1297)):
        key = str(slot)
        if key in gehennom:
            tile_map[key] = gehennom[key]
    return {'tileMap': tile_map, 'wallTiles': wall_tiles}


def append_caveman(atlas, projection, family, pack, treatment):
    """Crop the approved natural cave sources without redrawing source pixels.

    Keep the established doors and bars. Full-height walls, southern closures,
    and all connector poses use the same production architecture assembly as
    the approved review. Separate normal/goal material tags are engine-owned.
    """
    if family not in ('lantern','soot-and-brass') or treatment not in ('normal','goal'):
        raise ValueError('Unsupported Caveman material')
    folder=HERE/'regions/caveman'
    registry=json.loads((folder/'sources.json').read_text())
    record=registry['sources'][f'{family}-{treatment}']
    source_path=folder/record['file']
    if hashlib.sha256(source_path.read_bytes()).hexdigest()!=record['sha256']:
        raise ValueError('Caveman approved source changed')
    source=Image.open(source_path).convert('RGBA')
    if source.size!=(1536,1024):raise ValueError('Wrong Caveman source geometry')
    relative=('lantern/projected_architecture.py' if family=='lantern'
              else 'soot-and-brass/terrain/projected_architecture.py')
    architecture=module('production_caveman_'+family+'_'+treatment,HERE/relative)
    original_piece=architecture.piece
    def piece(name):
        if name not in CROPS:return original_piece(name)
        bounds,size=CROPS[name]
        return source.crop(bounds).resize(size,Image.Resampling.NEAREST)
    architecture.piece=piece
    architecture.family_image=lambda image,family:image.copy()
    original_straight=architecture.straight
    def straight(vertical,mask,family='main'):
        frame=original_straight(vertical,mask,family)
        if not vertical:
            plain={key:value for key,value in frame.items() if key!='alternates'}
            frame=dict(plain,alternates=[plain,plain,architecture.frame(piece('north-connector'),(0,-7),64)])
        return frame
    architecture.straight=straight
    architecture.FAMILIES=('caveman',);architecture.STARTS=(1471,)
    floor=source.crop(tuple(registry['floorCrop'])).resize((64,64),Image.Resampling.NEAREST)
    dim=.66 if family=='lantern' else .47
    dark=ImageEnhance.Brightness(floor).enhance(dim)
    floors={1291:floor,1292:dark,1293:floor,1294:dark,1295:floor,1296:dark}
    if family=='lantern':floors[1284]=floor
    first=atlas.height//64*40
    tile_map={str(slot):first+i for i,slot in enumerate(floors)}
    canonical_first=first+len(floors)
    for i in range(11):
        tile_map[str(1471+i)]=canonical_first+i
        tile_map[str(1273+i)]=canonical_first+i
    variant_start=canonical_first+11
    walls=architecture.build(variant_start=variant_start)
    wall_tiles=copy.deepcopy(walls['metadata']['tiles'])
    for i in range(11):wall_tiles[str(1273+i)]=copy.deepcopy(wall_tiles[str(1471+i)])
    used={int(slot) for slot in walls['metadata']['tiles']}
    used.update(slot for rule in walls['metadata']['tiles'].values() for slot in rule['variants'])
    count=variant_start+len(walls['variants'])
    output=Image.new('RGBA',(atlas.width,((count+39)//40)*64));output.paste(atlas,(0,0))
    def paste(slot,image):output.paste(image,(slot%40*64,slot//40*64))
    for slot,image in floors.items():paste(tile_map[str(slot)],image)
    frames={}
    for slot in used:
        target=tile_map.get(str(slot),slot)
        frames[target]=walls['projected'][slot]
        paste(target,architecture.fallback(frames[target]))
    output,extra=pack(output,frames)
    projection['frames'].update(extra['frames'])
    projection['padding']=[max(a,b) for a,b in zip(projection['padding'],extra['padding'])]
    evidence={'source':str(source_path.relative_to(HERE)),'sha256':record['sha256'],
              'sourcePixelSha256':hashlib.sha256(atlas.tobytes()).hexdigest(),'sourceSize':list(atlas.size),
              'wallCrops':CROPS,'floorCrop':registry['floorCrop'],'darkBrightness':dim,
              'architectureSha256':hashlib.sha256((HERE/relative).read_bytes()).hexdigest(),
              'generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'registrySha256':hashlib.sha256((folder/'sources.json').read_bytes()).hexdigest(),
              'license':registry['license'],'credit':registry['credit'],
              'doors':'Existing approved family doors and bars, unchanged'}
    return output,projection,count,{'tileMap':tile_map,'wallTiles':wall_tiles},evidence,set(str(k) for k in frames)


def append_asmodeus(atlas, projection, family, pack, architecture, materials):
    """Append the approved palace without changing any existing source pixels.

    Both main-dungeon and Gehennom wall IDs resolve to the same palace frames.
    Read original Gehennom art directly, not its later regional replacement.
    The independent test compares this implementation to the approved JS study.
    """
    recipe_path=HERE/'regions/asmodeus/material.json'
    recipe=json.loads(recipe_path.read_text())
    if family not in recipe['families']:raise ValueError('Unsupported palace artwork')
    selected={};aliases={}
    def select(slot,source,kind):selected[int(slot)]=(int(source),kind)
    for slot in range(1273,1284):
        select(slot,slot+209,'wall');aliases[slot+209]=slot
        for target,source in zip(architecture['tiles'][str(slot)]['variants'],
                                 architecture['tiles'][str(slot+209)]['variants']):
            select(target,source,'wall');aliases[source]=target
    for slot,rule in architecture['doors'].items():
        for variant in {int(slot),*rule['variants']}:select(variant,variant,'door')
    bars=architecture['bars'];select(bars['isolated'],bars['isolated'],'door')
    for rule in (bars['vertical'],bars['horizontal'],*bars['connections'].values()):
        for variant in {bars['tile'],*rule['variants']}:select(variant,variant,'door')
    floors=set(range(1291,1297))
    if family=='lantern':floors.add(1284)
    for slot in floors:
        select(slot,slot if family=='lantern' else materials['gehennom']['tileMap'][str(slot)],'floor')
    marks={}
    for slot in (1275,1276,1277,1278):
        marks[tuple(projection['frames'][str(slot)]['source'])]=(5 if slot in (1275,1277) else 31,5,recipe['cornerPattern'])
    for slot,rule in architecture['doors'].items():
        front=rule['topology']=='horizontal-door'
        for variant in {int(slot),*rule['variants']}:
            marks[tuple(projection['frames'][str(variant)]['source'])]=(22 if front else 20,3 if front else 2,
                            recipe['frontPattern'] if front else recipe['sidePattern'])
    def rounded(value):return int(value+.5) # Match JavaScript Math.round for RGB.
    def treated(image,kind,mark=None):
        values=[]
        for r,g,b,a in image.getdata():
            rgb=(r,g,b)
            if kind!='wall':
                if family=='lantern':
                    factors=(.88,.91,.94) if kind=='floor' else (.87,.88,.90)
                    rgb=tuple(rounded(v*f) for v,f in zip(rgb,factors))
                elif kind=='floor':rgb=tuple(rounded(v*.94) for v in rgb)
                else:
                    brass=r>g*1.12 and g>b*1.10
                    rgb=tuple(rounded(v*.90 if brass else v*.90*.88+t*.12)
                              for v,t in zip(rgb,(137,146,151)))
            values.append((*rgb,a))
        result=Image.new('RGBA',image.size);result.putdata(values)
        if mark:
            original=result.copy();pixels=result.load();originals=original.load()
            mx,my,pattern=mark
            bevel=(144,151,153) if family=='lantern' else (164,135,84)
            recess=(13,18,23) if family=='lantern' else (24,20,16)
            for highlight in (True,False):
                for dy,row in enumerate(pattern):
                    for dx,token in enumerate(row):
                        x,y=mx+dx,my+dy+int(highlight)
                        if token!='#' or not (0<=x<image.width and 0<=y<image.height):continue
                        pixel=originals[x,y]
                        if pixel[3]!=255:continue
                        factor=.35 if highlight else .22
                        tone=bevel if highlight else recess
                        pixels[x,y]=tuple(rounded(v*factor+t*(.65 if highlight else .78))
                                          for v,t in zip(pixel[:3],tone))+(255,)
        return result
    def crop(frame):
        x,y,w,h=frame['source'];return atlas.crop((x,y,x+w,y+h))
    def projected(source,geometry,kind,mark=None):
        if source['source'][2:]!=geometry['source'][2:]:raise ValueError('Palace geometry mismatch')
        result={'image':treated(crop(source),kind,mark),'offset':list(geometry['offset']),
                'depth':geometry.get('depth',64)}
        if 'kind' in geometry:result['kind']=geometry['kind']
        if geometry.get('alternates'):
            result['alternates']=[projected(s,g,kind) for s,g in zip(source['alternates'],geometry['alternates'])]
        return result
    first=atlas.height//64*40
    tile_map={str(slot):first+i for i,slot in enumerate(sorted(selected))}
    count=first+len(selected)
    out=Image.new('RGBA',(atlas.width,((count+39)//40)*64));out.paste(atlas,(0,0))
    frames={}
    for slot,(source,kind) in sorted(selected.items()):
        target=tile_map[str(slot)];x,y=source%40*64,source//40*64
        out.paste(treated(atlas.crop((x,y,x+64,y+64)),kind),(target%40*64,target//40*64))
        geometry=projection['frames'].get(str(slot))
        if geometry:frames[target]=projected(projection['frames'][str(source)],geometry,kind,marks.get(tuple(geometry['source'])))
    for alias,slot in aliases.items():tile_map[str(alias)]=tile_map[str(slot)]
    source_hash=hashlib.sha256(atlas.tobytes()).hexdigest()
    out,extra=pack(out,frames)
    projection['frames'].update(extra['frames'])
    projection['padding']=[max(a,b) for a,b in zip(projection['padding'],extra['padding'])]
    evidence={'source':recipe['source'],'sourcePixelSha256':source_hash,'sourceSize':list(atlas.size),
              'sourceSlots':{str(k):{'source':s,'kind':kind} for k,(s,kind) in selected.items()},
              'recipe':'regions/asmodeus/material.json','recipeSha256':hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
              'generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'license':recipe['license'],'credit':recipe['credit']}
    return out,projection,count,{'tileMap':tile_map},evidence,set(str(k) for k in frames)


def append_vlad(atlas, projection, family, pack, architecture):
    """Shade exact existing art, never reconstruct or replace its geometry.

    tileMap includes directional variant IDs. The renderer applies it after
    selecting a wall, door or bar variant from the ordinary architecture rules.
    """
    registry=json.loads((HERE/'regions/vlad/material.json').read_text())
    if family not in registry['families']:
        raise ValueError('Vlad material requires original Atlas artwork')
    floors=set(range(1291,1297))
    if family=='lantern':floors.add(1284)
    selected=set(floors)
    def select(slot, entry):
        selected.add(int(slot))
        selected.update(entry.get('variants',[]))
    for slot in range(1273,1284):select(slot,architecture['tiles'][str(slot)])
    for slot,entry in architecture['doors'].items():select(slot,entry)
    bars=architecture['bars']
    selected.add(bars['isolated'])
    for entry in (bars['horizontal'],bars['vertical'],*bars['connections'].values()):
        select(bars['tile'],entry)
    first=atlas.height//64*40
    tile_map={str(slot):first+i for i,slot in enumerate(sorted(selected))}
    count=first+len(selected)
    out=Image.new('RGBA',(atlas.width,((count+39)//40)*64))
    out.paste(atlas,(0,0))
    def shaded(pixels,factor):
        # Brightness changes RGB only; alpha and every source pixel position stay.
        return ImageEnhance.Brightness(pixels).enhance(factor)
    def projected(frame,factor):
        x,y,w,h=frame['source']
        result={'image':shaded(atlas.crop((x,y,x+w,y+h)),factor),
                'offset':list(frame['offset']),'depth':frame.get('depth',64)}
        if 'kind' in frame:result['kind']=frame['kind']
        if frame.get('alternates'):
            result['alternates']=[projected(a,factor) for a in frame['alternates']]
        return result
    frames={}
    for source_slot in sorted(selected):
        factor=registry['floorBrightness'] if source_slot in floors else registry['architectureBrightness']
        target=tile_map[str(source_slot)]
        x,y=source_slot%40*64,source_slot//40*64
        out.paste(shaded(atlas.crop((x,y,x+64,y+64)),factor),(target%40*64,target//40*64))
        source_frame=projection['frames'].get(str(source_slot))
        if source_frame:frames[target]=projected(source_frame,factor)
    source_hash=hashlib.sha256(atlas.tobytes()).hexdigest()
    out,extra=pack(out,frames)
    projection['frames'].update(extra['frames'])
    projection['padding']=[max(a,b) for a,b in zip(projection['padding'],extra['padding'])]
    evidence={'source':'existing family atlas before Vlad append',
              'sourcePixelSha256':source_hash,'sourceSize':list(atlas.size),
              'sourceSlots':sorted(selected),'floorSlots':sorted(floors),
              'architectureBrightness':registry['architectureBrightness'],
              'floorBrightness':registry['floorBrightness'],
              'generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'license':registry['license'],'credit':registry['credit']}
    return out,projection,count,{'tileMap':tile_map},evidence,set(str(k) for k in frames)


def append_region(atlas, projection, family, pack, region, wall_start):
    registry=json.loads((HERE/'regions'/region/'sources.json').read_text())
    record=registry['sources'][family]
    path=HERE/'regions'/region/record['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    source=Image.open(path).convert('RGBA')
    assert source.size==(1536,1024)
    relative=('lantern/projected_architecture.py' if family=='lantern'
              else 'soot-and-brass/terrain/projected_architecture.py')
    architecture=module('production_'+region+'_'+family,HERE/relative)
    crops=dict(CROPS)
    if region=='gehennom':
        crops['north']=(((425,105,515,211) if family=='lantern' else (728,105,824,211)),(64,71))
        crops['north-connector']=(((518,105,614,211) if family=='lantern' else (666,105,762,211)),(64,71))
    original_piece=architecture.piece
    def piece(name):
        if name not in crops:return original_piece(name)
        bounds,size=crops[name]
        return source.crop(bounds).resize(size,Image.Resampling.NEAREST)
    architecture.piece=piece
    architecture.family_image=lambda image,family:image.copy()
    original_straight=architecture.straight
    def straight(vertical,mask,family='main'):
        f=original_straight(vertical,mask,family)
        if not vertical:
            plain={k:v for k,v in f.items() if k!='alternates'}
            f=dict(plain,alternates=[plain,plain,architecture.frame(piece('north-connector'),(0,-7),64)])
        return f
    architecture.straight=straight
    architecture.FAMILIES=(region,);architecture.STARTS=(wall_start,)
    first=atlas.height//64*40
    floor=source.crop(FLOOR_CROP).resize((64,64),Image.Resampling.NEAREST)
    shade=tuple(int(c*.45) for c in ImageStat.Stat(floor.convert('RGB')).mean)+(255,)
    ImageDraw.Draw(floor).rectangle((0,0,63,63),outline=shade,width=1)
    dim=.66 if family=='lantern' else .47
    dark=ImageEnhance.Brightness(floor).enhance(dim)
    engraved=floor.copy();pen=ImageDraw.Draw(engraved)
    # Generic visible engraving, never hidden text or a hint about meaning.
    for points in [[(17,29),(22,24),(20,36)],[(25,27),(29,32),(25,37)],[(34,25),(32,37)],[(39,26),(44,29),(38,35)]]:
        pen.line([(x,y+1) for x,y in points],fill=(23,29,32,255),width=2)
        pen.line(points,fill=(120,127,122,255),width=1)
    floors={1291:floor,1292:dark,1294:dark,1295:floor,
            1293:engraved,1296:ImageEnhance.Brightness(engraved).enhance(dim)}
    if family=='lantern':floors[1284]=floor
    tile_map={str(slot):first+i for i,slot in enumerate(floors)}
    canonical_first=first+len(floors)
    tile_map.update({str(slot):canonical_first+slot-wall_start for slot in range(wall_start,wall_start+11)})
    variant_start=canonical_first+11
    walls=architecture.build(variant_start=variant_start)
    entries=walls['metadata']['tiles']
    used={int(s) for s in entries}
    used.update(s for entry in entries.values() for s in entry['variants'])
    count=variant_start+len(walls['variants'])
    out=Image.new('RGBA',(atlas.width,((count+39)//40)*64));out.paste(atlas,(0,0))
    def paste(slot,pixels):out.paste(pixels,(slot%40*64,slot//40*64))
    for canonical,pixels in floors.items():paste(tile_map[str(canonical)],pixels)
    frames={}
    for slot in used:
        target=tile_map.get(str(slot),slot);frame=walls['projected'][slot]
        frames[target]=frame;paste(target,architecture.fallback(frame))
    out,extra=pack(out,frames)
    projection['frames'].update(extra['frames'])
    projection['padding']=[max(a,b) for a,b in zip(projection['padding'],extra['padding'])]
    evidence={'source':str(path.relative_to(HERE)),'sha256':record['sha256'],
              'generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'architectureSha256':hashlib.sha256((HERE/relative).read_bytes()).hexdigest(),
              'floorCrop':list(FLOOR_CROP),'darkBrightness':dim,'wallCrops':crops,
              'license':registry['license'],'credit':registry['credit']}
    material={'tileMap':tile_map,'wallTiles':entries}
    return out,projection,count,material,evidence,set(str(k) for k in frames)
