#!/usr/bin/env python3
"""Capture actual ice/cloud themed fills in the packaged app and build a review.

Run test-ice-rooms.py and test-cloud-rooms.py --prepare --engine first.
Screenshots use copied checkpoints and shipped artwork, never player saves.
"""
import argparse
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shapes', ROOT/'scripts/test-room-shapes.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
GALLERY = ROOT/'.artifacts/ice-cloud-review.html'
NAMES = {'lantern-modern': 'Lantern Modern', 'soot-and-brass': 'Soot & Brass Modern',
         'lantern': 'Lantern Classic', 'soot-and-brass-classic': 'Soot & Brass Classic'}


def cells(path):
    result = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event['type'] == 'clear' and event.get('window') == 'map':
            result.clear()
        elif event['type'] == 'cell':
            result[event['x'],event['y']] = event
    return list(result.values())


def capture(kind, classic=False):
    rows = json.loads((ROOT/f'.artifacts/{kind}-rooms-prepared.json').read_text())
    results = []
    for row in rows:
        metadata = row['metadata']
        assert metadata['engine'] == shapes.tour.digest(shapes.tour.RES/'engine/nethack')
        assert metadata['app'] == shapes.tour.digest(shapes.tour.APP/'Contents/MacOS/NetHackAtlas')
        assert metadata['case']['fill'] == ('Ice room' if kind == 'ice' else 'Cloud room')
        for tileset in NAMES:
            if not classic and tileset in ('lantern','soot-and-brass-classic'):
                continue
            result = shapes.native(row, tileset)
            observed = cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            x,y,w,h = metadata['shapeBounds']
            visible = [c for c in observed if x <= c['x'] < x+w and y <= c['y'] < y+h]
            assert visible and all('material' not in c for c in observed)
            assert all('groundTile' not in c for c in observed if c['tile'] in (1469,1470))
            features = {str(tile): sum(c['tile'] == tile for c in visible)
                        for tile in (1315,1314,1323,1324,216,217)}
            if kind == 'ice':
                assert features['1315'] > 0, (kind,tileset,features)
            else:
                assert features['1323'] + features['1324'] > 0, (kind,tileset,features)
            result.update(kind=kind, mode=metadata['mode'], bounds=metadata['shapeBounds'],
                          displayedFeatures=features, setup=metadata['setup'],
                          sourceCheckpoint=row['run'], engine=metadata['engine'], app=metadata['app'],
                          canonicalArtwork=kind != 'ice', frostedMasonry=kind == 'ice',
                          noHiddenGround=True, nativeVerified=True)
            results.append(result)
            (ROOT/f'.artifacts/{kind}-rooms-native.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS',result['label'],tileset,result['screenshot'],flush=True)
    return results


def gallery():
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            '<title>Ice and cloud rooms: review</title>',
            '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;max-width:1500px;margin:32px auto;padding:0 24px}'
            'h1,h2{font-family:Georgia,serif}a{color:#d6bb84}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0 42px}'
            'img{width:100%;display:block;border:1px solid #485854;border-radius:6px}p{line-height:1.5;max-width:1000px}'
            '@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>',
            '<h1>Ice and cloud rooms</h1><p>Real packaged-app screenshots of the original NetHack themed fills. '
            'Each set uses copies of the same saved world. Ice-adjacent masonry uses the approved frost treatment; gas-room walls retain ordinary artwork. '
            'Click a screenshot to inspect it at full size. Awaiting your approval.</p>',
            '<p>Inspection fixtures reveal the starting map, supply test protection and retain active occupants. '
            'Lighting and perceived contents remain controlled by NetHack. These are targeted generated examples, not campaign encounters.</p>']
    for kind, title, note in (
            ('ice','28. Ice rooms','The original fill turns room terrain into ice and may add melting timers. '
             'Ice can melt into water through upstream timers. Remembered ice can remain outside sight until revisited.'),
            ('cloud','29. Cloud rooms','The original fill creates visible vapor regions and sleeping fog-cloud monsters. '
             'Vapor blocks sight, so a lit room can still hide its far side. This is the actual themed fill, not a room covered in generic cloud terrain.')):
        path = ROOT/f'.artifacts/{kind}-rooms-native.json'
        if not path.exists():
            continue
        results = json.loads(path.read_text())
        body.extend([f'<h2>{title}</h2>',f'<p>{note}</p>'])
        for label in dict.fromkeys(r['label'] for r in results):
            body.extend([f'<h3>{html.escape(label)}</h3>','<div class="pair">'])
            for r in results:
                if r['label'] != label:
                    continue
                url = Path(r['screenshot']).relative_to(GALLERY.parent).as_posix()
                name = html.escape(NAMES[r['tileset']])
                body.append(f'<div><h4>{name}</h4><a href="{url}"><img src="{url}" alt="{name}: {html.escape(label)}"></a></div>')
            body.append('</div>')
    body.append('</html>')
    GALLERY.write_text('\n'.join(body)+'\n')
    print('REVIEW',GALLERY,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',choices=('ice','cloud','all'))
    parser.add_argument('--classic',action='store_true',help='Also capture both Classic editions')
    args = parser.parse_args()
    if args.native:
        for kind in (('ice','cloud') if args.native == 'all' else (args.native,)):
            capture(kind, args.classic)
    gallery()
