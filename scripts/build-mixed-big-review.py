#!/usr/bin/env python3
"""Capture items 30/31 in the packaged app and build their shared review studio.

Prepare/check test-mixed-rooms.py and test-big-rooms.py first. Native sessions
copy isolated checkpoints. The studio replays only displayed engine cells.
"""
import argparse
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('garden_review', ROOT/'scripts/build-garden-swamp-review.py')
garden_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(garden_review)
GALLERY = ROOT/'.artifacts/mixed-big-rooms-review.html'
TITLES = {'mixed': '30. Water-surrounded vaults and mixed themed rooms',
          'big': '31. Big Room'}


def display_label(label, mode):
    return label if label.endswith(' / '+mode) else label+' / '+mode


def studio_manifest(kind, prepared, captures):
    scenes = {}
    for row in prepared:
        metadata = row['metadata']
        case = metadata['case']
        capture = next((r for r in captures if r['sourceCheckpoint'] == row['run']), None)
        if capture is None:
            continue
        cells = garden_review.review.cells(Path(capture['run'])/'diagnostics.jsonl.engine.jsonl')
        x,y,w,h = metadata['shapeBounds']
        shown = [dict(c, x=c['x']-x, y=c['y']-y) for c in cells
                 if x <= c['x'] < x+w and y <= c['y'] < y+h]
        assert shown
        scenes[case['id']+'-'+metadata['mode']] = dict(label=display_label(case['label'],metadata['mode']),
            width=w, height=h, cells=shown, sourceCheckpoint=row['run'],
            engine=metadata['engine'], app=metadata['app'], setup=metadata['setup'],
            originalBounds=metadata['shapeBounds'])
    path = ROOT/f'.artifacts/{kind}-rooms-review-manifest.json'
    path.write_text(json.dumps(dict(scenes=scenes),indent=2)+'\n')


def gallery():
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Mixed rooms and Big Room: real-engine review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;max-width:1500px;margin:32px auto;padding:0 24px}'
        'h1,h2{font-family:Georgia,serif}a{color:#d6bb84}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0 42px}'
        'img{width:100%;display:block;border:1px solid #485854;border-radius:6px}p{line-height:1.5;max-width:1050px}'
        '@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>30 and 31: mixed rooms and Big Room</h1>',
        '<p>Actual packaged-app screenshots with existing shipped artwork. Each pair starts from copies of the same saved world. '
        'Click a screenshot to inspect full size, or use the studio to zoom and hover over the captured map. Awaiting owner approval.</p>',
        '<p>Inspection uses documented wizard setup and map memory. NetHack controls actual terrain, lighting, occupants and rules. '
        'Named-source fixtures preserve original generation but are targeted layouts; world-selected arrivals are shown separately. '
        'The studio is a frozen display, not a playable game. Random terrain and contents make these representative examples, not exhaustive campaign coverage.</p>']
    for kind,title in TITLES.items():
        native_path = ROOT/f'.artifacts/{kind}-rooms-native.json'
        prepared_path = ROOT/f'.artifacts/{kind}-rooms-prepared.json'
        if not native_path.exists() or not prepared_path.exists():
            continue
        results = json.loads(native_path.read_text())
        prepared = json.loads(prepared_path.read_text())
        studio_manifest(kind,prepared,results)
        body.extend([f'<h2>{title}</h2>',
            f'<p><a href="../tools/tileset-preview/index.html?capture={kind}-rooms&amp;tileset=lantern-modern">Lantern studio</a> · '
            f'<a href="../tools/tileset-preview/index.html?capture={kind}-rooms&amp;tileset=soot-and-brass">Soot &amp; Brass studio</a></p>'])
        for checkpoint in dict.fromkeys(r['sourceCheckpoint'] for r in results):
            matches = [r for r in results if r['sourceCheckpoint']==checkpoint]
            label = html.escape(display_label(matches[0]['label'],matches[0]['mode']))
            mode = html.escape(matches[0]['mode'])
            body.extend([f'<h3>{label}</h3>','<div class="pair">'])
            for result in matches:
                url = Path(result['screenshot']).relative_to(GALLERY.parent).as_posix()
                name = html.escape(garden_review.review.NAMES[result['tileset']])
                body.append(f'<div><h4>{name}</h4><a href="{url}"><img loading="lazy" src="{url}" alt="{name}: {label}, {mode}"></a></div>')
            body.append('</div>')
    body.append('</html>')
    GALLERY.write_text('\n'.join(body)+'\n')
    print('REVIEW',GALLERY,flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',choices=('mixed','big','all'))
    parser.add_argument('--classic',action='store_true',help='Also capture both Classic editions')
    parser.add_argument('--resume',action='store_true',help='Reuse matching completed native captures')
    args = parser.parse_args()
    if args.native:
        for kind in (('mixed','big') if args.native=='all' else (args.native,)):
            rows = json.loads((ROOT/f'.artifacts/{kind}-rooms-prepared.json').read_text())
            if kind=='mixed':
                # Unrevealed remote vault/room geometry is not native framing
                # evidence. Its exploration checks remain in the engine index.
                rows = [row for row in rows if row['metadata']['mode']=='inspection']
            garden_review.capture(kind,args.classic,rows=rows,resume=args.resume)
    gallery()
