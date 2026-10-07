#!/usr/bin/env python3
"""Capture preserved real-engine environments using the packaged renderer.

Run the preparation/engine verification recipe after packaging first. Native
sessions are serial and use copied checkpoints, never a player's saves.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'.artifacts'
spec=importlib.util.spec_from_file_location('ground_native',ROOT/'scripts/build-ice-cloud-review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
MODERN=['lantern-modern','soot-and-brass']
CLASSIC=['lantern','soot-and-brass-classic']


def camera(meta):
    """Frame known floor transitions and architecture without moving the hero."""
    cells=meta['displayedCells'];width,height=26,17
    if meta['mode']=='exploration':
        x,y=meta['arrival'];width,height=12,12
        left,top=max(1,min(68,x-6)),max(0,min(9,y-6))
    else:
        def score(x,y):
            shown=[c for c in cells if x<=c['x']<x+width and y<=c['y']<y+height]
            ground=[c for c in shown if c['tile'] in (1291,1292)]
            natural=sum(c.get('material') in ('quest-earth','mines') for c in ground)
            built=len(ground)-natural
            walls=sum(1273<=c['tile']<=1283 or 1471<=c['tile']<=1481 for c in shown)
            return min(natural,built)*4+walls+min(natural,60),-x,-y
        left,top=max(((x,y) for x in range(1,81-width) for y in range(22-height)),key=lambda p:score(*p))
    meta['shapeBounds']=[left,top,width,height]
    tiles={c['tile'] for c in cells if left<=c['x']<left+width and top<=c['y']<top+height}
    meta['testTerrainTiles']=sorted(tiles & {1291,1292,1293,1294,1314,1315,1316,1323,1324})
    assert meta['testTerrainTiles'],meta['case']


def selected(row):
    m=row['metadata'];identifier=m['case']['id']
    if m['mode']=='exploration':
        return identifier in ('medusa-world','minetown-world','Kni-strt') or (identifier.startswith('minetn-') and m.get('worldSelected'))
    if identifier.startswith(('medusa-','minetn-')) or m['case'].get('fill')=='Garden':return True
    if identifier.startswith(('Arc-','Kni-','Bar-','Ran-','Tou-','Sam-','Wiz-')):
        return identifier.endswith(('-strt','-loca')) or identifier in ('Kni-goal','Bar-goal','Ran-goal','Ran-fila')
    return False


def capture():
    rows=json.loads((ART/'grounded-environments-review-prepared.json').read_text())
    engine=review.shapes.tour.digest(review.shapes.tour.RES/'engine/nethack')
    host=review.shapes.tour.digest(review.shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
    results=[];classic_groups=set()
    for original in rows:
        if not selected(original):continue
        row=copy.deepcopy(original);m=row['metadata'];assert m['engine']==engine
        camera(m);identifier=m['case']['id']
        group='Medusa' if identifier.startswith('medusa-') else 'Minetown' if identifier.startswith('minetn-') or identifier=='minetown-world' else 'Gardens' if m['case'].get('fill')=='Garden' else m['identity']['role']+' Quest'
        editions=list(MODERN)
        if group in ('Medusa','Minetown') and group not in classic_groups and m['mode']=='inspection':
            editions+=CLASSIC;classic_groups.add(group)
        for tileset in editions:
            result=review.shapes.native(copy.deepcopy(row),tileset)
            cells=review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            assert cells
            assert all('material' not in c and 'groundTile' not in c for c in cells if c['tile'] in (1469,1470))
            expected={(c['x'],c['y']):c.get('material') for c in m['displayedCells']}
            assert all(c.get('material')==expected.get((c['x'],c['y'])) for c in cells),'Native material differs from independently restored engine'
            result.update(group=group,case=identifier,mode=m['mode'],bounds=m['shapeBounds'],
                label=m['case'].get('label',identifier)+' / '+m['mode'],engine=engine,app=host,
                sourceCheckpoint=original['run'],setup=m['setup'],nativeVerified=True,noHiddenGround=True)
            results.append(result);(ART/'grounded-environments-native.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS',identifier,m['mode'],tileset,result['screenshot'],flush=True)
    assert results and classic_groups=={'Medusa','Minetown'}
    return results


def gallery():
    rows=json.loads((ART/'grounded-environments-native.json').read_text())
    manifest=json.loads((ART/'grounded-environments-review-manifest.json').read_text())
    body=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Natural grounds and finished interiors</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;max-width:1550px;margin:28px auto;padding:0 24px}h1,h2{font-family:Georgia,serif}p{line-height:1.5;max-width:1100px}a{color:#d8bd87}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}img{width:100%;border:1px solid #495853}figure{margin:0 0 24px}figcaption{padding:10px 0}summary{cursor:pointer;padding:12px 0}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>Natural grounds and finished interiors</h1>',
        '<p>Real packaged-app captures of original NetHack levels: earth around island buildings and settlements, stone inside intact buildings, '
        'and mine streets with rock walls and supports. Existing family artwork and licensing are retained. Tourist locate/goal town streets stay paved. '
        'Classic and Modern share architecture; creature and statue sizing is their only intended difference.</p>',
        '<p>Each capture restores a copy of a preserved source save. Inspection examples disclose map reveal and test protection; '
        'unrevealed arrivals retain unknown space. Cameras do not move the hero or replace terrain. These are environment checks, not completed quests.</p>',
        '<p>Full captured maps in the <a href="../tools/tileset-preview/index.html?capture=grounded-environments&tileset=lantern-modern">standard renderer: Lantern Modern</a> or '
        '<a href="../tools/tileset-preview/index.html?capture=grounded-environments&tileset=soot-and-brass">Soot &amp; Brass Modern</a>.</p>']
    for group in dict.fromkeys(r['group'] for r in rows):
        body.append('<h2>'+html.escape(group)+'</h2>')
        for identifier,mode in dict.fromkeys((r['case'],r['mode']) for r in rows if r['group']==group):
            note = ' (named Big Room boundary: original ground retained)' if identifier == 'fill-garden-lit' else ''
            body.append('<details'+(' open' if mode=='inspection' else '')+'><summary>'+html.escape(identifier+' / '+mode+note)+'</summary><div class="pair">')
            for r in rows:
                if (r['case'],r['mode'])!=(identifier,mode):continue
                url=Path(r['screenshot']).relative_to(ART).as_posix();name=review.NAMES[r['tileset']]
                body.append('<figure><figcaption>'+html.escape(name)+'</figcaption><a href="'+url+'"><img loading="lazy" src="'+url+'" alt="'+html.escape(identifier+' / '+name)+'"></a></figure>')
            body.append('</div></details>')
    body.append('<details><summary>All engine-reviewed stage maps</summary>')
    for key,scene in manifest['scenes'].items():
        url='../tools/tileset-preview/index.html?capture=grounded-environments&tileset=lantern-modern&scene='+key
        body.append('<p><a href="'+html.escape(url,quote=True)+'">'+html.escape(scene['label'])+'</a></p>')
    body.append('</details></html>');p=ART/'grounded-environments-review.html';p.write_text('\n'.join(body)+'\n');print('REVIEW',p)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native',action='store_true');args=parser.parse_args()
    if args.native:capture()
    gallery()
