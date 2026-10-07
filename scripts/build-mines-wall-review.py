#!/usr/bin/env python3
"""Capture approved Mines rock walls and dirt floors in real named levels."""
import argparse
import html
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('settlement_review', ROOT/'scripts/build-mixed-big-review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
KIND = 'mines-wall'
GALLERY = ROOT/'.artifacts/mines-wall-review.html'


def rows(fresh=False):
    index = ROOT/'.artifacts/mines-wall-rooms-prepared.json'
    if not fresh:
        return json.loads(index.read_text())
    selected = []
    validations = []
    native_cases = {'minetn-6', 'minend-1', 'minend-2', 'minend-3'}
    for kind, group in [('minetown','Minetown'), ('mines-end','Mines\u2019 End')]:
        # A newly compiled host has a new identity. Prepare fresh disposable
        # worlds instead of relabeling old evidence or weakening hash checks.
        helper_spec = importlib.util.spec_from_file_location(kind+'_preparation',ROOT/f'scripts/prepare-{kind}-review.py')
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        cases = [dict(c) for c in helper.tour.catalog() if c['group'] == group]
        recipes = [(c, 'inspection') for c in cases]
        world = next(c for c in cases if c['id'].endswith('-world'))
        recipes.append((dict(world, id=world['id']+'-exploration'), 'exploration'))
        for case, mode in recipes:
            if case.get('source'):
                case['label'] = (helper.NAMES[int(case['id'].rsplit('-', 1)[1])-1]
                                 if kind == 'minetown' else helper.LAYOUTS[case['id']][0])
            run = Path(tempfile.mkdtemp(prefix='mines-wall-'+case['id']+'-',dir=ROOT/'.artifacts'))
            metadata = helper.tour.prepare(case,mode,run)
            row = helper.finish_metadata(run,metadata)
            validation = helper.validate(row) if kind == 'minetown' else helper.check(row)
            validations.append(dict(run=str(run), result=validation))
            (ROOT/'.artifacts/mines-wall-material-validation.json').write_text(json.dumps(validations,indent=2)+'\n')
            print('VALIDATED',case['id'],mode,flush=True)
            if case['id'] in native_cases:
                selected.append(row)
                index.write_text(json.dumps(selected,indent=2)+'\n')
    return selected


def gallery(prepared, captures):
    review.studio_manifest(KIND, prepared, captures)
    body = ['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Approved Mines rock walls and dirt floors: native review</title>',
        '<style>body{background:#101719;color:#e5e8e1;font:17px system-ui;max-width:1500px;margin:32px auto;padding:0 24px}'
        'a{color:#d6bb84}h1,h2{font-family:Georgia,serif}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:32px}'
        'img{width:100%;border:1px solid #485854}p{line-height:1.5;max-width:1000px}@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>Mines settlements carved into reinforced rock</h1>',
        '<p>Actual rebuilt packaged app. All dedicated Mines walls now use the approved natural rock and excavation supports. '
        'Minetown and every Mines\u2019 End layout now use approved dirt/gravel floors too. '
        'Doors, objects, lighting and NetHack gameplay are unchanged. The existing Mines presentation context covers the whole branch; no per-cell classifier.</p>',
        '<p>Both Modern and Classic families restore isolated copies of the same four saved worlds. '
        'These are native rendering checks, not an additional gameplay playtest. '
        'Studio links fit the complete recorded maps; native wide edges can crop at minimum zoom.</p>',
        '<p><a href="../tools/tileset-preview/index.html?capture=mines-wall-rooms&amp;tileset=lantern-modern">Lantern studio</a> · '
        '<a href="../tools/tileset-preview/index.html?capture=mines-wall-rooms&amp;tileset=soot-and-brass">Soot &amp; Brass studio</a></p>']
    for checkpoint in dict.fromkeys(c['sourceCheckpoint'] for c in captures):
        matched = [c for c in captures if c['sourceCheckpoint']==checkpoint]
        body.append('<h2>'+html.escape(matched[0]['label'])+'</h2>')
        for pair in [('lantern-modern','soot-and-brass'),('lantern','soot-and-brass-classic')]:
            body.append('<div class="pair">')
            for tileset in pair:
                result = next(c for c in matched if c['tileset']==tileset)
                name = review.garden_review.review.NAMES[tileset]
                path = Path(result['screenshot']).relative_to(GALLERY.parent).as_posix()
                body.append(f'<div><h3>{html.escape(name)}</h3><a href="{path}"><img src="{path}" alt="{html.escape(name)}: {html.escape(result["label"])}"></a></div>')
            body.append('</div>')
    GALLERY.write_text('\n'.join(body)+ '\n</html>\n')
    print(GALLERY, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    args = parser.parse_args()
    (ROOT/'.artifacts').mkdir(exist_ok=True)
    prepared = rows(fresh=args.native)
    index = ROOT/f'.artifacts/{KIND}-rooms-native.json'
    if args.native:
        captures = review.garden_review.capture(KIND, classic=True, rows=prepared)
        for result in captures:
            cells = review.garden_review.review.cells(Path(result['run'])/'diagnostics.jsonl.engine.jsonl')
            known = [c for c in cells if c['tile'] not in (1469,1470)]
            assert known and all(c.get('material') == 'mines' for c in known), result['run']
            assert all('groundTile' not in c and 'material' not in c for c in cells if c['tile'] in (1469,1470))
    else:
        captures = json.loads(index.read_text())
    manifest = json.loads((ROOT/'assets/tiles/manifest.json').read_text())
    revisions = {a['id']:a['revision'] for a in manifest['tilesets'] if 'revision' in a}
    for result in captures:
        result['unchangedArtwork'] = False
        if 'artworkRevision' not in result:
            # Do not relabel already versioned historical screenshots.
            result['artworkRevision'] = revisions[result['tileset']]
        result['canonicalMinesWalls'] = list(range(1471,1482))
        result['regionalMaterial'] = 'mines'
    index.write_text(json.dumps(captures,indent=2)+'\n')
    gallery(prepared,captures)


if __name__ == '__main__':
    main()
