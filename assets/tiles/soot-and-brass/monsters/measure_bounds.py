"""Measure source sprite bounds without changing generated source pixels."""
import json
from pathlib import Path
from collections import Counter
from PIL import Image
base = Path(__file__).resolve().parent.parent
registry = json.loads((base / 'monster-sources.json').read_text())
for sheet in registry['sheets']:
    image = Image.open(base / sheet['file']).convert('RGBA')
    w,h=image.size; alpha=image.getchannel('A').tobytes(); seen=bytearray(w*h)
    cols,rows=sheet['columns'],sheet['rows']; groups=[]
    for start in range(w*h):
        if seen[start] or alpha[start]<=8: continue
        queue=[start];seen[start]=1;count=0;left=w;top=h;right=bottom=0
        while queue:
            z=queue.pop();x=z%w;y=z//w;count+=1
            left=min(left,x);top=min(top,y);right=max(right,x+1);bottom=max(bottom,y+1)
            for yy in range(max(0,y-1),min(h,y+2)):
                for xx in range(max(0,x-1),min(w,x+2)):
                    q=yy*w+xx
                    if not seen[q] and alpha[q]>8:seen[q]=1;queue.append(q)
        if count>300:
            col=min(cols-1,int((left+right)/2*cols/w));row=min(rows-1,int((top+bottom)/2*rows/h))
            groups.append((row*cols+col,count,(left,top,right,bottom)))
    counts=Counter(g[0] for g in groups)
    missing=[i for i,k in enumerate(sheet['keys']) if k and i not in counts]
    duplicate={i:n for i,n in counts.items() if n>1}
    print(sheet['file'], 'missing',missing,'multiple',duplicate)
    if missing: print(groups)
    bounds=[]
    for i,key in enumerate(sheet['keys']):
        boxes=[g[2] for g in groups if g[0]==i]
        if key and not boxes:raise RuntimeError((sheet['file'],i,key))
        if not key: bounds.append(None);continue
        bounds.append([max(0,min(b[0] for b in boxes)-2),max(0,min(b[1] for b in boxes)-2),min(w,max(b[2] for b in boxes)+2),min(h,max(b[3] for b in boxes)+2)])
    sheet['bounds']=bounds
(registry_path := base/'monster-sources.json').write_text(json.dumps(registry,indent=2)+'\n')
