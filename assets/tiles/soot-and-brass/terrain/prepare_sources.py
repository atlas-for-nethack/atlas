#!/usr/bin/env python3
"""Extract complete original subjects before slicing a generative source grid.

Large silhouettes are associated with their intended row-major cells. Detached
pieces follow the closest primary silhouette, so a portal sparkle above its row
boundary never becomes part of the pit above it. Original RGBA pixels survive
inside a two-pixel-expanded component mask; no subjects are repainted.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageFilter

HERE=Path(__file__).resolve().parent

def extract(name,grid):
    path=HERE/(name+'-source.png')
    im=Image.open(path).convert('RGBA');w,h=im.size
    aa=im.getchannel('A').tobytes();seen=bytearray(w*h);groups=[]
    for pos in range(w*h):
        if seen[pos] or aa[pos]<=32:continue
        pending=[pos];seen[pos]=1;group=[]
        while pending:
            z=pending.pop();group.append(z);x=z%w;y=z//w
            for yy in range(max(0,y-1),min(h,y+2)):
                for xx in range(max(0,x-1),min(w,x+2)):
                    t=yy*w+xx
                    if not seen[t] and aa[t]>32:seen[t]=1;pending.append(t)
        if len(group)<3:continue
        xs=[z%w for z in group];ys=[z//w for z in group]
        box=(min(xs),min(ys),max(xs)+1,max(ys)+1)
        col=min(grid-1,int((box[0]+box[2])/2*grid/w))
        row=min(grid-1,int((box[1]+box[3])/2*grid/h))
        groups.append({'pixels':group,'box':box,'nominal':row*grid+col})
    anchors={}
    for g in groups:
        cell=g['nominal']
        if cell not in anchors or len(g['pixels'])>len(anchors[cell]['pixels']):anchors[cell]=g
    assert set(anchors)==set(range(grid*grid)),set(range(grid*grid))-set(anchors)
    envelopes={i:anchors[i]['box'] for i in anchors}
    # Associate substantial detached pieces first; their complete envelope then
    # owns nearby antialias fragments. This keeps the lowest blue air wisps with
    # the air sprite instead of the crown material in the next row.
    for g in sorted(groups,key=lambda x:len(x['pixels']),reverse=True):
        if len(g['pixels'])<300:continue
        def distance(i):
            a,b=g['box'],envelopes[i]
            dx=max(0,a[0]-b[2],b[0]-a[2]);dy=max(0,a[1]-b[3],b[1]-a[3])
            centers=((a[0]+a[2]-b[0]-b[2])**2+(a[1]+a[3]-b[1]-b[3])**2)/4
            return dx*dx+dy*dy+centers*.0001
        cell=min(anchors,key=distance);a,b=g['box'],envelopes[cell]
        envelopes[cell]=(min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3]))
    masks={i:bytearray(w*h) for i in anchors}
    for g in groups:
        def score(i):
            a,b=g['box'],envelopes[i]
            dx=max(0,a[0]-b[2],b[0]-a[2]);dy=max(0,a[1]-b[3],b[1]-a[3])
            centers=((a[0]+a[2]-b[0]-b[2])**2+(a[1]+a[3]-b[1]-b[3])**2)/4
            return dx*dx+dy*dy+centers*.0001
        cell=min(anchors,key=score)
        # Isolated subvisible debris cannot inflate a sprite to an entire row.
        if score(cell)>(w/grid*.22)**2:continue
        if len(g['pixels'])<12 and score(cell)>36:continue
        for z in g['pixels']:masks[cell][z]=255
    result={}
    output=HERE/'extracted';output.mkdir(exist_ok=True)
    for cell,raw in masks.items():
        selection=Image.frombytes('L',(w,h),bytes(raw)).filter(ImageFilter.MaxFilter(5))
        alpha=ImageChops.multiply(im.getchannel('A'),selection)
        box=alpha.point(lambda x:255 if x>32 else 0).getbbox()
        box=(max(0,box[0]-2),max(0,box[1]-2),min(w,box[2]+2),min(h,box[3]+2))
        image=im.copy();image.putalpha(alpha);image=image.crop(box)
        filename=f'extracted/{name}-{cell:02d}.png';dest=HERE/filename;image.save(dest)
        result[str(cell)]={'file':filename,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
          'sourceBounds':list(box),'primaryBounds':list(anchors[cell]['box'])}
    return {'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cells':result}

if __name__=='__main__':
    result={'method':'Whole-sheet 8-connected alpha>32 components; nearest primary silhouette; original alpha retained within two-pixel component margins.',
      'fixtures':extract('fixtures',6),'traps':extract('traps',5)}
    (HERE/'extraction.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Extracted 61 full terrain subjects, preserving original pixels and source bounds.')
