#!/usr/bin/env python3
"""Prepare six replacement monsters while preserving all existing overrides."""
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('foreground_cleanup', ROOT/'prepare_foregrounds.py')
cleanup = importlib.util.module_from_spec(spec); spec.loader.exec_module(cleanup)
KEYS = ['monster/105-black-unicorn','monster/114-baby-long-worm','monster/115-baby-purple-worm',
        'monster/116-long-worm','monster/117-purple-worm','monster/119-xan']
LIMITS = [(56,56),(32,24),(32,24),(56,50),(56,58),(44,38)]


def main():
    path=HERE/'monster-repairs-sheet.png';source=Image.open(path).convert('RGBA')
    overrides=json.loads((ROOT/'production-overrides.json').read_text())
    before={k:v for k,v in overrides.items() if k not in KEYS}
    records=[];tiles=[]
    for i,(key,limit) in enumerate(zip(KEYS,LIMITS)):
        c,r=i%3,i//3
        box=(round(c*source.width/3),round(r*source.height/2),round((c+1)*source.width/3),round((r+1)*source.height/2))
        raw=source.crop(box);clean,metrics=cleanup.clean_foreground(raw,key)
        bounds=clean.getchannel('A').getbbox()
        assert bounds and bounds[0]>0 and bounds[1]>0 and bounds[2]<raw.width and bounds[3]<raw.height,(key,bounds)
        subject=clean.crop(bounds);scale=min(limit[0]/subject.width,limit[1]/subject.height)
        size=(round(subject.width*scale),round(subject.height*scale))
        tile=Image.new('RGBA',(64,64),(0,0,0,0));tile.alpha_composite(subject.resize(size,Image.Resampling.NEAREST),((64-size[0])//2,62-size[1]));tiles.append(tile)
        name=key.split('/')[-1]+'.png';tile.save(HERE/name)
        overrides[key]={'file':'production-sources/'+name,'sha256':hashlib.sha256((HERE/name).read_bytes()).hexdigest(),'origin':'original-ai-generated','source':'production-sources/monster-repairs-sheet.png'}
        records.append({'key':key,'sourceCrop':box,'subjectBounds':bounds,'size':size,'cleanup':metrics,'file':name})
    assert all(overrides[k]==v for k,v in before.items())
    (ROOT/'production-overrides.json').write_text(json.dumps(overrides,indent=2)+'\n')
    report={'source':path.name,'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'columns':3,'rows':2,'grid':'normalized','prompt':'REPAIR-PROMPTS.md','cleanupScriptSha256':hashlib.sha256((ROOT/'prepare_foregrounds.py').read_bytes()).hexdigest(),'sprites':records}
    (HERE/'monster-repairs-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    floor=Image.open(HERE/'reference-floor.png').convert('RGBA');review=Image.new('RGB',(660,430),'#161c1c');draw=ImageDraw.Draw(review)
    for i,(key,tile) in enumerate(zip(KEYS,tiles)):
        x,y=i%3*220,i//3*215;composed=floor.copy();composed.alpha_composite(tile)
        review.paste(composed.resize((128,128),Image.Resampling.NEAREST),(x+4,y+4));review.paste(composed,(x+140,y+68));draw.text((x+4,y+145),key.split('/')[-1],fill='#ddd1b4');draw.text((x+4,y+162),'64px shown at right',fill='#b9ae94')
    review_dir = HERE.parents[3]/'.artifacts/tiles'
    review_dir.mkdir(parents=True, exist_ok=True)
    review.save(review_dir/'monster-repairs-review.png')
    print(json.dumps({'replacements':6,'totalOverrides':len(overrides),'preservedOtherOverrides':len(before)}))


if __name__=='__main__':
    main()
