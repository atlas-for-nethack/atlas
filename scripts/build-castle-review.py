#!/usr/bin/env python3
"""Capture tested Castle saves in the packaged app, never player saves."""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('castle_native_review', ROOT/'scripts/build-ice-cloud-review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

def capture():
    rows = json.loads((ART/'castle-prepared.json').read_text())
    engine = review.shapes.tour.digest(review.shapes.tour.RES/'engine/nethack')
    host = review.shapes.tour.digest(review.shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
    results = []
    for row in rows:
        row = copy.deepcopy(row)
        meta = row['metadata']
        assert meta['engine'] == engine, 'Reverify checkpoints after an engine rebuild'
        # Frame perceived bridge appearances or the actual arrival hero.
        # This changes renderer zoom/scroll only, never gameplay placement.
        bridge = [c for c in meta['displayedCells']
                  if c['tile'] in (1318,1319,1320,1321)
                  or c.get('groundTile') in (1318,1319)]
        if meta['mode']=='inspection' and bridge:
            x,y=bridge[0]['x'],bridge[0]['y']
        else:
            x,y=meta['arrival']
        left,top=max(1,min(70,x-5)),max(0,min(11,y-5))
        meta['shapeBounds']=[left,top,10,10]
        visible=[c for c in meta['displayedCells'] if left<=c['x']<left+10 and top<=c['y']<top+10]
        # The shared native readiness harness checks foreground appearances.
        # Occupied deck/moat ground is independently asserted after restore.
        available={c['tile'] for c in visible}
        meta['testTerrainTiles']=sorted(available&{1314,1318,1319,1320,1321})
        if not meta['testTerrainTiles']:
            meta['testTerrainTiles']=[next(t for t in (1291,1292,1293,1294) if t in available)]
        meta['setup'].append('Native camera frames already perceived bridge terrain or the original arrival hero; no hero or terrain change.')
        for tileset in review.NAMES:
            result = review.shapes.native(copy.deepcopy(row), tileset)
            result['label']='Castle / '+meta.get('bridgeState',meta['mode'])
            cells = review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            assert cells and all('material' not in c for c in cells), 'Castle must keep its ordinary dungeon artwork'
            assert all('groundTile' not in c for c in cells if c['tile'] in (1469,1470)), 'Hidden ground leaked'
            x,y,w,h = meta['shapeBounds']
            visible = [c for c in cells if x <= c['x'] < x+w and y <= c['y'] < y+h]
            assert visible
            terrain = {tile for c in visible for tile in (c['tile'],c.get('groundTile')) if tile is not None}
            assert set(meta.get('testTerrainTiles',[])) <= terrain, (meta['case']['label'],tileset,terrain)
            if meta.get('bridgeState') in ('lowered-hero','destroyed-moat-hero'):
                hero=next(c for c in cells if (c['x'],c['y'])==tuple(meta['arrival']))
                expected=1319 if meta['bridgeState']=='lowered-hero' else 1314
                assert hero.get('groundTile')==expected, ('Supporting deck/moat lost in native restore',tileset,hero)
                assert hero['char']=='@' and hero['tile']!=expected, ('Hero must be self-visible above supporting ground',tileset,hero)
            result.update(mode=meta['mode'], sourceCheckpoint=row['run'], bounds=meta['shapeBounds'],
                engine=engine,app=host,checkpointApp=meta['app'],displayedTerrain=sorted(terrain),setup=meta['setup'],
                nativeVerified=True,canonicalArtwork=True,noHiddenGround=True)
            results.append(result)
            (ART/'castle-native.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS',result['label'],tileset,result['screenshot'],flush=True)
    return results

def gallery():
    results = json.loads((ART/'castle-native.json').read_text())
    manifest = json.loads((ART/'castle-review-manifest.json').read_text())
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Castle: engine and native review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;max-width:1550px;margin:28px auto;padding:0 24px}h1,h2{font-family:Georgia,serif}p{line-height:1.5;max-width:1100px}a{color:#d8bd87}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}img{width:100%;border:1px solid #495853}figure{margin:0 0 24px}figcaption{padding:10px 0}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>46. Castle: real drawbridge and moat tests</h1>',
        '<p>Existing dungeon masonry fits this fortified stronghold and its throne room, barracks and storerooms. '
        'The original moat, towers, gate and drawbridge give it its identity. Classic and Modern share the same architecture.</p>',
        '<p>These are actual packaged-app screenshots of saved Castle test states. The bridge transitions were produced through real engine actions, '
        'with disclosed wizard preparation in isolated disposable games. Original arrival retains unexplored space. '
        'NetHack owns terrain, visibility, hazards and turn progression.</p>',
        '<p>Frozen engine captures using the current shipped artwork.</p>']
    body.append('<h2>Whole Castle layout</h2><p>Overview through the standard game renderer using the original revealed engine records. Native screenshots below verify the playable bridge states.</p>')
    for stem,name in [('lantern','Lantern Modern'),('soot','Soot & Brass Modern')]:
        body.append('<figure><figcaption>'+html.escape(name)+'</figcaption><a href="castle-'+stem+'-overview.png"><img src="castle-'+stem+'-overview.png" alt="'+html.escape(name+' full Castle')+'"></a></figure>')
    for ident,name in [('lantern-modern','Lantern Modern'),('soot-and-brass','Soot & Brass Modern')]:
        links=[]
        for key,scene in manifest['scenes'].items():
            url='../tools/tileset-preview/index.html?capture=castle&tileset='+ident+'&scene='+key
            links.append('<a href="'+html.escape(url,quote=True)+'">'+html.escape(scene['label'])+'</a>')
        body.append('<p>'+html.escape(name)+': '+' · '.join(links)+'</p>')
    for label in dict.fromkeys(r['label'] for r in results):
        body.append('<h2>'+html.escape(label)+'</h2><div class="pair">')
        for r in results:
            if r['label']!=label:continue
            url=Path(r['screenshot']).relative_to(ART).as_posix()
            name=review.NAMES[r['tileset']]
            body.append('<figure><figcaption>'+html.escape(name)+'</figcaption><a href="'+url+'"><img src="'+url+'" alt="'+html.escape(label+' / '+name)+'"></a></figure>')
        body.append('</div>')
    body.append('</html>')
    path=ART/'castle-review.html'
    path.write_text('\n'.join(body)+'\n')
    print('REVIEW',path,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    if args.native:capture()
    gallery()
