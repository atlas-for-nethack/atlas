#!/usr/bin/env python3
"""Capture original Quest checkpoints in isolated packaged-app sessions.

Prepare and verify each role against the packaged engine first. Every Modern
stage is captured, plus Classic home and goal for architecture parity. Source
checkpoints and player saves are never changed. Native launches are serial.
"""
import argparse
import copy
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / '.artifacts'
spec = importlib.util.spec_from_file_location('quest_native', ROOT/'scripts/build-ice-cloud-review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
ROLES = ['monk', 'priest', 'healer', 'valkyrie', 'wizard']
MODERN = ['lantern-modern', 'soot-and-brass']
CLASSIC = ['lantern', 'soot-and-brass-classic']
outdoor_spec = importlib.util.spec_from_file_location('quest_ground_checks', ROOT/'scripts/test-quest-outdoors.py')
outdoors = importlib.util.module_from_spec(outdoor_spec)
outdoor_spec.loader.exec_module(outdoors)


def frame(meta):
    """Center the camera on the actual saved arrival, without moving the hero."""
    x,y = meta['arrival']
    left,top = max(1,min(68,x-6)),max(0,min(9,y-6))
    meta['shapeBounds'] = [left,top,12,12]
    foreground = {c['tile'] for c in meta['displayedCells']
                  if left<=c['x']<left+12 and top<=c['y']<top+12}
    meta['testTerrainTiles'] = sorted(foreground & {1291,1292,1293,1294,1314,1315,1316,1322,1323,1324})
    assert meta['testTerrainTiles'], ('No visible readiness terrain',meta['case'],foreground)


def capture():
    engine = review.shapes.tour.digest(review.shapes.tour.RES/'engine/nethack')
    host = review.shapes.tour.digest(review.shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
    results = []
    for role in ROLES:
        rows = json.loads((ART/f'{role}-review-prepared.json').read_text())
        assert len(rows)==6, (role,len(rows))
        for original in rows:
            row = copy.deepcopy(original)
            meta = row['metadata']
            assert meta['engine']==engine, 'Refresh and reverify original checkpoints after rebuilding'
            frame(meta)
            suffix = meta['case']['id'].split('-')[-1]
            editions = MODERN + (CLASSIC if meta['mode']=='inspection' and suffix in ('strt','goal') else [])
            for tileset in editions:
                result = review.shapes.native(copy.deepcopy(row),tileset)
                cells = review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
                assert cells and all('groundTile' not in c and 'material' not in c
                                     for c in cells if c['tile'] in (1469,1470))
                material = meta['expectedMaterial']
                known = [c for c in cells if c['tile'] not in (1469,1470)]
                outdoors.material(cells,material,meta['mode'])
                result.update(role=role,stage=suffix,mode=meta['mode'],material=material,
                    label=role.title()+' / '+suffix+' / '+meta['mode'],
                    sourceCheckpoint=original['run'],bounds=meta['shapeBounds'],
                    engine=engine,app=host,checkpointApp=meta['app'],nativeVerified=True,
                    noHiddenGround=True,setup=meta['setup'])
                results.append(result)
                (ART/'quests-native.json').write_text(json.dumps(results,indent=2)+'\n')
                print('PASS',result['label'],tileset,result['screenshot'],flush=True)
    assert len(results)==80, len(results)
    return results


def grounds():
    """Review the five corrected outdoor stages and original unrevealed arrivals."""
    engine=review.shapes.tour.digest(review.shapes.tour.RES/'engine/nethack')
    host=review.shapes.tour.digest(review.shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
    scenes={'Mon-strt':'home-detail','Pri-strt':'home-shrine',
            'Pri-loca':'locate-shrine','Hea-strt':'home-detail','Hea-loca':'shrine'}
    results=[]
    for role in ('monk','priest','healer'):
        rows=json.loads((ART/f'{role}-review-prepared.json').read_text())
        manifest=json.loads((ART/f'{role}-baseline-review-manifest.json').read_text())
        for original in rows:
            row=copy.deepcopy(original);meta=row['metadata'];identifier=meta['case']['id']
            if identifier not in scenes:continue
            assert meta['engine']==engine,'Refresh preserved saves first'
            if meta['mode']=='inspection':
                scene=manifest['scenes'][scenes[identifier]]
                x,y,w,h=scene['cropBounds'];meta['shapeBounds']=[x+1,y,w,h]
                foreground={c['tile'] for c in meta['displayedCells'] if x+1<=c['x']<x+1+w and y<=c['y']<y+h}
                meta['testTerrainTiles']=sorted(foreground & {1291,1292,1314})
                assert meta['testTerrainTiles']
                editions=MODERN+CLASSIC
            else:
                frame(meta);editions=MODERN
            for tileset in editions:
                result=review.shapes.native(copy.deepcopy(row),tileset)
                cells=review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
                checks=outdoors.material(cells,meta['expectedMaterial'],meta['mode'])
                result.update(role=role,stage=identifier,mode=meta['mode'],
                    label=role.title()+' / '+identifier+' / '+meta['mode'],
                    sourceCheckpoint=original['run'],bounds=meta['shapeBounds'],
                    engine=engine,app=host,nativeVerified=True,perception=checks,setup=meta['setup'])
                results.append(result)
                (ART/'quest-grounds-native.json').write_text(json.dumps(results,indent=2)+'\n')
                print('PASS grounds',result['label'],tileset,result['screenshot'],flush=True)
    assert len(results)==26,len(results)
    return results


def details():
    """Frame already displayed goal architecture, without relocating the hero."""
    engine=review.shapes.tour.digest(review.shapes.tour.RES/'engine/nethack')
    host=review.shapes.tour.digest(review.shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
    results=[]
    for role,key in [('valkyrie','goal-detail'),('wizard','barred-hall')]:
        rows=json.loads((ART/f'{role}-review-prepared.json').read_text())
        row=copy.deepcopy(next(r for r in rows if r['metadata']['case']['id'].endswith('-goal')))
        meta=row['metadata'];assert meta['engine']==engine
        scene=json.loads((ART/f'{role}-baseline-review-manifest.json').read_text())['scenes'][key]
        x,y,w,h=scene['cropBounds'];meta['shapeBounds']=[x+1,y,w,h]
        foreground={c['tile'] for c in meta['displayedCells'] if x+1<=c['x']<x+1+w and y<=c['y']<y+h}
        meta['testTerrainTiles']=sorted(foreground&{1291,1292,1314,1315,1316,1318,1319,1320,1321})
        assert meta['testTerrainTiles']
        for tileset in MODERN:
            result=review.shapes.native(copy.deepcopy(row),tileset)
            cells=review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            outdoors.material(cells,meta['expectedMaterial'],meta['mode'])
            assert all('groundTile' not in c and 'material' not in c for c in cells if c['tile'] in (1469,1470))
            result.update(role=role,stage='goal-detail',mode='inspection',material=meta['expectedMaterial'],
                label=role.title()+' / '+scene['label'],sourceCheckpoint=row['run'],bounds=meta['shapeBounds'],
                engine=engine,app=host,nativeVerified=True,noHiddenGround=True,
                setup=meta['setup']+['Camera frames already displayed goal architecture; hero and terrain unchanged.'])
            results.append(result);(ART/'quests-details-native.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS',result['label'],tileset,result['screenshot'],flush=True)
    return results


def gallery():
    results = json.loads((ART/'quests-native.json').read_text())
    if (ART/'quests-details-native.json').exists():
        results += json.loads((ART/'quests-details-native.json').read_text())
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Quests 47–51: packaged-app review</title>',
        '<style>body{background:#101719;color:#e6e8df;font:17px system-ui;max-width:1550px;margin:28px auto;padding:0 24px}h1,h2{font-family:Georgia,serif}p{line-height:1.5;max-width:1100px}a{color:#d8bd87}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}img{width:100%;border:1px solid #495853}figure{margin:0 0 24px}figcaption{padding:10px 0}summary{cursor:pointer;padding:12px 0}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>47–51. Monk, Priest, Healer, Valkyrie and Wizard Quests</h1>',
        '<p>Original NetHack Quest stages rendered in the playable packaged app with existing approved artwork. '
        'Constructed sanctuaries use dungeon architecture, natural passages and islands use cave ground, '
        'graveyards use the Valley treatment, and infernal stages use Gehennom. Wizard retains canonical architecture.</p>',
        '<p>Each capture restores a copy of a preserved original saved world. Revealed inspection examples supply test protection; '
        'unrevealed arrival examples retain unknown space. Engine tests separately exercise movement, inspection, hazards and restoration. '
        'These targeted examples do not demonstrate a complete campaign or quest dialogue progression.</p>']
    if (ART/'quest-grounds-native.json').exists():
        updated=json.loads((ART/'quest-grounds-native.json').read_text())
        body.extend(['<h2>Updated outdoor grounds</h2>',
            '<p>The five corrected stages below use earth outside and stone inside. Priest locate retains Valley masonry around its stone-floored temple. '
            'These are newer packaged-app captures of the same preserved worlds. Trees, water, hazards, layouts and gameplay remain upstream. '
            'The original captures farther below are retained as comparison evidence.</p>'])
        for label in dict.fromkeys(r['label'] for r in updated):
            body.append('<details open><summary>'+html.escape(label)+'</summary><div class="pair">')
            for r in updated:
                if r['label']!=label:continue
                url=Path(r['screenshot']).relative_to(ART).as_posix()
                name=review.NAMES[r['tileset']]
                body.append('<figure><figcaption>'+html.escape(name)+'</figcaption><a href="'+url+'"><img loading="lazy" src="'+url+'" alt="'+html.escape(label+' / '+name)+'"></a></figure>')
            body.append('</div></details>')
        body.append('<h2>Previous stage and goal checks</h2>')
    for role in ROLES:
        body.append('<h2>'+role.title()+'</h2>')
        body.append('<p>Frozen engine captures using the current shipped artwork.</p>')
        manifest=json.loads((ART/f'{role}-baseline-review-manifest.json').read_text())
        for tileset in MODERN:
            links=[]
            for key,scene in manifest['scenes'].items():
                url='../tools/tileset-preview/index.html?capture='+role+'-baseline&tileset='+tileset+'&scene='+key
                links.append('<a href="'+html.escape(url,quote=True)+'">'+html.escape(scene['label'])+'</a>')
            body.append('<p>'+html.escape(review.NAMES[tileset])+': '+' · '.join(links)+'</p>')
        for label in dict.fromkeys(r['label'] for r in results if r['role']==role):
            body.append('<details'+(' open' if 'strt / inspection' in label or 'goal / inspection' in label else '')+'><summary>'+html.escape(label)+'</summary><div class="pair">')
            for r in results:
                if r['label']!=label:continue
                url=Path(r['screenshot']).relative_to(ART).as_posix()
                name=review.NAMES[r['tileset']]
                body.append('<figure><figcaption>'+html.escape(name)+'</figcaption><a href="'+url+'"><img loading="lazy" src="'+url+'" alt="'+html.escape(label+' / '+name)+'"></a></figure>')
            body.append('</div></details>')
    body.append('</html>')
    path=ART/'quests-review.html';path.write_text('\n'.join(body)+'\n');print('REVIEW',path,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--details',action='store_true')
    parser.add_argument('--grounds',action='store_true')
    args=parser.parse_args()
    if args.native:capture()
    if args.details:details()
    if args.grounds:grounds()
    gallery()
