#!/usr/bin/env python3
"""Prepare the first small original role/pet sheet, retaining exact source PNG."""
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('foreground_cleanup', ROOT/'prepare_foregrounds.py')
cleanup = importlib.util.module_from_spec(spec); spec.loader.exec_module(cleanup)
KEYS = [
 'monster/338-archeologist', 'monster/339-barbarian', 'monster/340-cave-dweller', 'monster/341-healer',
 'monster/342-knight', 'monster/343-monk', 'monster/344-cleric', 'monster/345-ranger',
 'monster/346-rogue', 'monster/347-samurai', 'monster/348-tourist', 'monster/349-valkyrie',
 'monster/350-wizard', 'monster/034-kitten', 'monster/019-large-dog', 'monster/091-giant-rat',
]


def main():
    path = HERE/'roles-pets-sheet.png'
    source = Image.open(path).convert('RGBA')
    overrides = json.loads((ROOT/'production-overrides.json').read_text())
    rows, tiles = [], []
    for i, key in enumerate(KEYS):
        col, row = i%4, i//4
        box = (round(col*source.width/4), round(row*source.height/4),
               round((col+1)*source.width/4), round((row+1)*source.height/4))
        raw = source.crop(box)
        cleaned, metrics = cleanup.clean_foreground(raw, key)
        bounds = cleaned.getchannel('A').getbbox()
        assert bounds and bounds[0] > 0 and bounds[1] > 0 and bounds[2] < raw.width and bounds[3] < raw.height, (key,bounds)
        trimmed = cleaned.crop(bounds)
        limit = (56,60) if i<13 else [(36,36),(56,54),(44,34)][i-13]
        scale = min(limit[0]/trimmed.width,limit[1]/trimmed.height)
        size = (round(trimmed.width*scale),round(trimmed.height*scale))
        resized = trimmed.resize(size,Image.Resampling.NEAREST)
        tile = Image.new('RGBA',(64,64),(0,0,0,0))
        tile.alpha_composite(resized,((64-size[0])//2,62-size[1]))
        name = key.split('/')[-1]+'.png'
        tile.save(HERE/name); tiles.append(tile)
        details = {'key':key,'sourceCrop':box,'subjectBounds':bounds,'size':size,'cleanup':metrics,
                   'file':'production-sources/'+name,'used':i!=4}
        rows.append(details)
        # The already-approved exact reference knight remains authoritative.
        if i!=4:
            overrides[key]={'file':details['file'],'sha256':hashlib.sha256((HERE/name).read_bytes()).hexdigest(),
                            'origin':'original-ai-generated','source':'production-sources/roles-pets-sheet.png'}
    (ROOT/'production-overrides.json').write_text(json.dumps(overrides,indent=2)+'\n')
    report={'source':'roles-pets-sheet.png','sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'columns':4,'rows':4,'grid':'normalized','prompt':'ROLE-PROMPTS.md',
            'cleanupScriptSha256':hashlib.sha256((ROOT/'prepare_foregrounds.py').read_bytes()).hexdigest(),
            'sprites':rows}
    (HERE/'roles-pets-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    floor = Image.open(HERE/'reference-floor.png').convert('RGBA')
    review = Image.new('RGB',(800,860),'#161c1c');draw=ImageDraw.Draw(review)
    for i,(tile,key) in enumerate(zip(tiles,KEYS)):
        x,y=i%4*200,i//4*215
        composed=floor.copy();composed.alpha_composite(tile)
        review.paste(composed.resize((128,128),Image.Resampling.NEAREST),(x+4,y+4))
        review.paste(composed,(x+132,y+68))
        draw.text((x+4,y+140),key.split('/')[-1],fill='#ddd1b4')
        draw.text((x+4,y+156),'unused comparison' if i==4 else '64px shown at right',fill='#b9ae94')
    review_dir = HERE.parents[3]/'.artifacts/tiles'
    review_dir.mkdir(parents=True, exist_ok=True)
    review.save(review_dir/'roles-pets-review.png')
    print(json.dumps({'totalOverrides':len(overrides),'newRolePetOverrides':15,'sourceSize':source.size}))


if __name__=='__main__':
    main()
