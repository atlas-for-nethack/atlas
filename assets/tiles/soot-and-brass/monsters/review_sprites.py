"""Render generated monster source crops for visual inspection using the atlas fitter."""
from pathlib import Path
import json,importlib.util,hashlib
from PIL import Image,ImageDraw
base=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('soot_builder',base/'build.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
reg=json.loads((base/'monster-sources.json').read_text()); art={}; evidence={}
for s in reg['sheets']:
 im=Image.open(base/s['file']).convert('RGBA')
 assert hashlib.sha256((base/s['file']).read_bytes()).hexdigest()==s['sha256']
 for index,(k,b) in enumerate(zip(s['keys'],s['bounds'])):
  if k:
   cell=im.crop(b)
   if index in s.get('keep_largest_component',[]):cell=mod.primary_component(cell)
   art[k]=mod.fit_cell(cell,(im.width/s['columns'],im.height/s['rows']));evidence[k]=(s['file'],b)
keys=sorted(art); assert len(keys)==395,len(keys)
out=base.parents[2]/'.artifacts/soot-and-brass-monsters';out.mkdir(parents=True,exist_ok=True)
contacts=[]
for page in range(7):
 chosen=keys[page*64:(page+1)*64];board=Image.new('RGB',(1024,1200),'#292e31');d=ImageDraw.Draw(board)
 for j,k in enumerate(chosen):
  x=j%8*128;y=j//8*150;board.paste(art[k].resize((128,128),Image.Resampling.NEAREST),(x,y),art[k].resize((128,128),Image.Resampling.NEAREST))
  d.text((x+2,y+129),k.split('/',1)[1][:22],fill='white')
 board.save(out/f'contact-{page}.png')
 for k in chosen:
  a=art[k].getchannel('A');box=a.getbbox()
  if box and (box[0]==0 or box[1]==0 or box[2]==64 or box[3]==64):contacts.append(k)
print('unique keys',len(keys),'outer edge contacts',contacts)
print('output',out)
