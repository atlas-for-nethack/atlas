#!/usr/bin/env python3
"""Capture Mines' End and Minetown using the unchanged packaged app.

Prepare with prepare-mines-end-review.py and prepare-minetown-review.py first.
This is visual review, not an additional gameplay playtest.
"""
import argparse
import html
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('room_review', ROOT/'scripts/build-mixed-big-review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
GALLERY = ROOT/'.artifacts/mines-settlement-review.html'
SECTIONS = {
    'mines-end': "32. Mines' End",
    'minetown': '33. Minetown',
}


def gallery():
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Mines\' End and Minetown: native review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;max-width:1500px;margin:32px auto;padding:0 24px}'
        'h1,h2{font-family:Georgia,serif}a{color:#d6bb84}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0 42px}'
        'img{width:100%;display:block;border:1px solid #485854;border-radius:6px}p{line-height:1.5;max-width:1050px}'
        '@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>',
        "<h1>32 and 33: Mines' End and Minetown</h1>",
        '<p>Actual packaged-app screenshots with existing shipped artwork. Left: Lantern Modern. Right: Soot &amp; Brass Modern. '
        'Both editions restore copies of the same disposable world. Click an image for full size. Awaiting owner visual approval.</p>',
        '<p>All three Mines\' End sources and seven Minetown sources are shown, plus an actual world-selected arrival for each. '
        'Named sources are loaded unchanged at their real special-level depth through the wizard loader. '
        'Inspection supplies and map memory are documented test framing; original lighting, occupants and random source choices remain intact.</p>',
        '<p>Current shipped behavior: NetHack selects its Mines branch wall slots on these named levels, with existing floors and features. '
        'The supplemental rough-rock/gravel material used in random caves is not applied here. Buildings, shops, temples, doors, bars and rubble reuse existing assets. '
        'Cave outlines come from NetHack\'s actual layouts, but their walls also use the branch masonry. '
        'No blanket cave reskin, new artwork or gameplay change has been introduced.</p>',
        '<p>Use the studio links for a fitted complete map or larger tile detail. Native views may crop the widest edges at minimum zoom. '
        'The studio replays actual displayed cells, including remembered and unknown areas; it is not a playable simulation. '
        'Additional gameplay playtesting was waived. These captures confirm layout and rendering, not every shop, trap or quest interaction.</p>']
    for kind, title in SECTIONS.items():
        native_path = ROOT/f'.artifacts/{kind}-rooms-native.json'
        prepared_path = ROOT/f'.artifacts/{kind}-rooms-prepared.json'
        if not native_path.exists() or not prepared_path.exists():
            continue
        results = json.loads(native_path.read_text())
        prepared = json.loads(prepared_path.read_text())
        review.studio_manifest(kind, prepared, results)
        body.extend([f'<h2>{html.escape(title)}</h2>',
            f'<p><a href="../tools/tileset-preview/index.html?capture={kind}-rooms&amp;tileset=lantern-modern">Lantern studio</a> · '
            f'<a href="../tools/tileset-preview/index.html?capture={kind}-rooms&amp;tileset=soot-and-brass">Soot &amp; Brass studio</a></p>'])
        for checkpoint in dict.fromkeys(r['sourceCheckpoint'] for r in results):
            matches = [r for r in results if r['sourceCheckpoint']==checkpoint]
            label = html.escape(review.display_label(matches[0]['label'],matches[0]['mode']))
            row = next(r for r in prepared if r['run']==checkpoint)
            note = row['metadata'].get('layoutDescription',row['metadata'].get('sourceGeometry',''))
            body.extend([f'<h3>{label}</h3>',f'<p>{html.escape(note)}</p>','<div class="pair">'])
            for result in matches:
                url = Path(result['screenshot']).relative_to(GALLERY.parent).as_posix()
                name = html.escape(review.garden_review.review.NAMES[result['tileset']])
                body.append(f'<div><h4>{name}</h4><a href="{url}"><img loading="lazy" src="{url}" alt="{name}: {label}"></a></div>')
            body.append('</div>')
    body.append('</html>')
    GALLERY.write_text('\n'.join(body)+'\n')
    print('REVIEW',GALLERY,flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',choices=(*SECTIONS,'all'))
    parser.add_argument('--classic',action='store_true',help='Also capture both Classic editions')
    parser.add_argument('--resume',action='store_true',help='Reuse matching completed captures')
    args = parser.parse_args()
    if args.native:
        for kind in SECTIONS if args.native=='all' else (args.native,):
            rows = json.loads((ROOT/f'.artifacts/{kind}-rooms-prepared.json').read_text())
            rows = [row for row in rows if row['metadata']['mode']=='inspection']
            review.garden_review.capture(kind,args.classic,rows=rows,resume=args.resume)
    gallery()
