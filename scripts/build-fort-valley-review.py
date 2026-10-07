#!/usr/bin/env python3
"""Native Fort Ludios checks and approved Valley material presentation.

Fort preparation/testing is owned by test-fort-ludios.py. Valley captures use
approved shipped artwork; the standard preview retains its approved recipe.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review',ROOT/'scripts/build-mixed-big-review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
tour=review.garden_review.review.shapes.tour


def prepare_valley():
    case=next(c for c in tour.catalog() if c['id']=='valley')
    rows=[]
    for mode in ('inspection','exploration'):
        run=Path(tempfile.mkdtemp(prefix='valley-review-'+mode+'-',dir=ROOT/'.artifacts'))
        metadata=tour.prepare(case,mode,run)
        cells=review.garden_review.review.cells(run/'preparation.jsonl')
        known=[c for c in cells if c['tile'] not in (1469,1470)]
        unknown=[c for c in cells if c['tile'] in (1469,1470)]
        assert known and all(c.get('material')=='valley' for c in known)
        assert all('groundTile' not in c and 'material' not in c for c in unknown)
        assert metadata['identity']['branch']=='Gehennom'
        metadata.update(shapeBounds=[1,0,79,21],displayedCells=cells,
                        testTerrainTiles=sorted({c['tile'] for c in known if c.get('char')=='.'})[:1],
                        valleySourceSHA256=tour.digest(tour.DAT/'valley.lua'),
                        dataSHA256=tour.digest(tour.RES/'engine/nhdat'),
                        designPreviewOnly=False,gameplayPlaytestPerformed=False)
        assert metadata['testTerrainTiles']
        (run/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        rows.append(dict(run=str(run),metadata=metadata))
        (ROOT/'.artifacts/valley-rooms-prepared.json').write_text(json.dumps(rows,indent=2)+'\n')
        print('PREPARED Valley',mode,'unknown cells',len(unknown),flush=True)

    return rows


def add_valley_details():
    path=ROOT/'.artifacts/valley-rooms-review-manifest.json'
    manifest=json.loads(path.read_text())
    scene=manifest['scenes']['valley-inspection']
    # These crops follow actual displayed features, including upstream flips.
    for key,label,tile,w,h in [('temple','Moloch shrine detail',1305,12,13),
                             ('morgue','Graveyard detail',1310,18,13)]:
        feature=next(c for c in scene['cells'] if c['tile']==tile)
        bounds=[max(0,min(scene['width']-w,feature['x']-w//2)),max(0,min(scene['height']-h,feature['y']-h//2)),w,h]
        x,y,w,h=bounds
        cells=[dict(c,x=c['x']-x,y=c['y']-y) for c in scene['cells']
               if x<=c['x']<x+w and y<=c['y']<y+h]
        assert cells
        manifest['scenes'][key]={**scene,'label':label,'width':w,'height':h,
                                  'cells':cells,'cropOf':'valley-inspection','cropBounds':bounds}
    path.write_text(json.dumps(manifest,indent=2)+'\n')


def capture_valley(rows, resume=False):
    framed = copy.deepcopy(rows)
    for row in framed:
        metadata = row['metadata']
        if metadata['mode'] != 'exploration':continue
        # Frame perceived arrival, not the unseen level's full geometry. The
        # standard studio still retains the complete original captured map.
        known = [c for c in metadata['displayedCells'] if c['tile'] not in (1469,1470)]
        assert known
        x = (min(c['x'] for c in known)+max(c['x'] for c in known))//2
        y = (min(c['y'] for c in known)+max(c['y'] for c in known))//2
        metadata['shapeBounds'] = [max(1,min(68,x-6)),max(0,min(9,y-6)),12,12]
    return review.garden_review.capture('valley',classic=True,rows=framed,resume=resume)


def gallery(kind,rows,captures):
    review.studio_manifest(kind,rows,captures)
    if kind=='valley':add_valley_details()
    title='Fort Ludios: native verification' if kind=='fort-ludios' else 'Valley of the Dead: native verification'
    notes=('Original court/barracks family architecture, ordinary floors, moat, throne, treasury and soldiers. '
           'Native captures use copies of isolated real-engine saves; engine gameplay checks are recorded separately.'
           if kind=='fort-ludios' else
           'The screenshots below show the current shipped artwork in real native gameplay. '
           'The approved treatment combines darker familiar masonry, doors and bars with worn Gehennom ground, using existing shipped pixels. '
           'The material is selected by the engine on the actual named level. No terrain, occupants or features are invented.')
    body=['<!doctype html><html lang="en"><meta charset="utf-8">',
          '<meta name="viewport" content="width=device-width,initial-scale=1">',
          '<title>'+title+'</title>',
          '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;max-width:1500px;margin:32px auto;padding:0 24px}'
          'a{color:#d8bd87}h1,h2{font-family:Georgia,serif}p{line-height:1.5;max-width:1050px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:35px}'
          'img{width:100%;border:1px solid #495853}@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>',
          '<h1>'+title+'</h1><p>'+notes+'</p>',
          '<p>Source layouts, lighting and active occupants retain upstream randomness. '
          'Inspection uses documented wizard protection and map reveal; exploration retains unknown space. '
          'Exploration screenshots frame the perceived arrival rather than unseen remote geometry. '
          'Native wide edges can crop at minimum zoom; the frozen studio fits the complete recorded map.</p>']
    for tileset,name in [('lantern-modern','Lantern Modern'),('soot-and-brass','Soot &amp; Brass Modern')]:
        body.append(f'<p><a href="../tools/tileset-preview/index.html?capture={kind}-rooms&amp;tileset={tileset}">{name} studio</a></p>')
    for checkpoint in dict.fromkeys(c['sourceCheckpoint'] for c in captures):
        matched=[c for c in captures if c['sourceCheckpoint']==checkpoint]
        body.append('<h2>'+html.escape(matched[0]['label']+' / '+matched[0]['mode'])+'</h2>')
        for pair in [('lantern-modern','soot-and-brass'),('lantern','soot-and-brass-classic')]:
            if not any(c['tileset'] in pair for c in matched):continue
            body.append('<div class="pair">')
            for tileset in pair:
                result=next((c for c in matched if c['tileset']==tileset),None)
                if result is None:continue
                name=review.garden_review.review.NAMES[tileset]
                path=Path(result['screenshot']).relative_to(ROOT/'.artifacts').as_posix()
                body.append(f'<div><h3>{html.escape(name)}</h3><a href="{path}"><img src="{path}" alt="{html.escape(name)}: {html.escape(result["label"])}"></a></div>')
            body.append('</div>')
    path=ROOT/f'.artifacts/{kind}-review.html'
    path.write_text('\n'.join(body)+'\n</html>\n');print(path,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-valley',action='store_true')
    parser.add_argument('--native',choices=('fort-ludios','valley','all'))
    parser.add_argument('--resume',action='store_true',help='Retain matching completed native captures')
    args=parser.parse_args();(ROOT/'.artifacts').mkdir(exist_ok=True)
    if args.prepare_valley:
        prepare_valley()
        if not args.native:return
    for kind in (('fort-ludios','valley') if args.native=='all' else (args.native,) if args.native else ('fort-ludios','valley')):
        prepared=ROOT/f'.artifacts/{kind}-rooms-prepared.json'
        native=ROOT/f'.artifacts/{kind}-rooms-native.json'
        if not prepared.exists():continue
        rows=json.loads(prepared.read_text())
        if args.native:captures=(capture_valley(rows,args.resume) if kind=='valley' else
                                review.garden_review.capture(kind,classic=True,rows=rows,resume=args.resume))
        elif native.exists():captures=json.loads(native.read_text())
        else:continue
        gallery(kind,rows,captures)


if __name__=='__main__':main()
