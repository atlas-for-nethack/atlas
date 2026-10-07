#!/usr/bin/env python3
"""Extract NetHack 5.0 tile metadata without reading or copying tile artwork.

The generated catalog's names/order derive from NetHack (NGPL); this is not an
artwork license. See assets/tiles/sources/NGPL.txt. Regenerate after building the
pinned engine, or use --check to compare the committed catalog with its sources.
"""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / 'assets/tiles/lantern/catalog.json'
EXPECTED_COUNTS = {'monsters': 789, 'objects': 483, 'other': 243}
OFFSETS = {'monsters.txt': 0, 'objects.txt': 789, 'other.txt': 1272, 'generated': 1515}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def slug(label):
    return re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')


def read_headers(path, count):
    # Only identifying headers are retained, never palette or pixel data.
    entries = re.findall(r'^# tile (\d+) \((.*)\)$', path.read_text(), re.M)
    require([int(i) for i, _ in entries] == list(range(count)),
            f'{path}: expected contiguous headers 0..{count - 1}')
    return [label for _, label in entries]


def object_class(index):
    for last, kind in [(0, 'strange'), (17, 'generic'), (88, 'weapon'),
                       (174, 'armor'), (202, 'ring'), (215, 'amulet'),
                       (265, 'tool'), (298, 'food'), (324, 'potion'),
                       (367, 'scroll'), (411, 'spellbook'), (439, 'wand'),
                       (440, 'coin'), (476, 'gem'), (478, 'large-rock'),
                       (479, 'iron-ball'), (480, 'iron-chain'), (482, 'venom')]:
        if index <= last:
            return kind
    raise ValueError(f'Unexpected object entry {index}')


def appearance(index, source_label):
    kind = object_class(index)
    label = source_label.split(' / ', 1)[0]
    if kind in {'ring', 'potion', 'spellbook', 'wand'}:
        label += ' ' + kind
    elif kind == 'amulet' and index <= 213:
        label += ' amulet'
    elif kind == 'scroll':
        label = 'scroll labeled ' + label if index < 366 else label + ' scroll'
    elif kind == 'gem' and index < 476:
        label += ' stone' if index >= 472 else ' gem'
    elif kind == 'generic':
        label = 'unidentified ' + label
    return kind, label


def engine_references(path):
    text = path.read_text()
    expected = {'total_tiles_used': 2303, 'maxmontile': 788,
                'maxobjtile': 1271, 'maxothtile': 1514}
    for name, value in expected.items():
        match = re.search(r'\b' + name + r'\s*=\s*(\d+)', text)
        require(match and int(match[1]) == value, f'{name} changed in generated engine')
    rows = re.findall(r'^\s*\{.*?,\s*(\d+), 0 \},\s*/\* \[(\d+)\] '
                      r'(monsters\.txt|objects\.txt|other\.txt|generated):(\d+) (.*?) \*/',
                      text, re.M)
    require(rows, 'Could not read generated engine glyph map')
    require([int(row[1]) for row in rows] == list(range(len(rows))),
            'Engine glyph map has missing or unparsed entries')
    refs = Counter()
    for tile, glyph, source, entry, label in rows:
        tile, entry = int(tile), int(entry)
        require(0 <= tile < 2303, f'Engine glyph {glyph} tile is outside canonical range')
        # Upstream corpse comments use object number 265, not file entry 267.
        # All body/piletop body glyphs also deliberately use this shared tile.
        if source == 'objects.txt' and entry == 265 and (
                'body of ' in label or re.search(r'\bcorpse \(onum=265\)$', label)):
            expected_tile = 789 + 267
        else:
            expected_tile = OFFSETS[source] + entry
        require(tile == expected_tile,
                f'Engine glyph {glyph}: tile {tile} disagrees with {source}:{entry}')
        refs[tile] += 1
    return refs, len(rows)


def generate(nethack):
    header_sets = {name: read_headers(nethack / 'win/share' / (name + '.txt'), count)
                   for name, count in EXPECTED_COUNTS.items()}
    # Include disabled/conditional monsters: their positions exist in the atlas.
    definitions = re.findall(r'MON\(NAMS?\((.*?)\),\s*(S_\w+)',
                             (nethack / 'include/monsters.h').read_text(), re.S)
    require(len(definitions) == 394, 'Monster definition count changed')
    refs, glyph_count = engine_references(nethack / 'src/tile.c')
    tiles = []
    for index, label in enumerate(header_sets['monsters']):
        name, gender = label.rsplit(',', 1)
        gender = gender.strip()
        require(gender == ('nogender' if index == 788 else ('male' if index % 2 == 0 else 'female')),
                f'Unexpected monster gender at slot {index}')
        pair = index // 2
        monster_class = 'invisible'
        if index < 788:
            definition, monster_class = definitions[pair]
            names = re.findall(r'"([^"]+)"', definition)
            require(names[-1] == name, f'Monster source disagreement at slot {index}')
            monster_class = monster_class.removeprefix('S_').lower()
        visible_label = name
        if name in {'werejackal', 'werewolf', 'wererat'}:
            visible_label += ' (human form)' if monster_class == 'human' else ' (animal form)'
        tiles.append({'slot': index, 'label': visible_label, 'category': 'monster',
                      'art_key': f'monster/{pair:03d}-{slug(visible_label)}',
                      'gender': gender, 'monster_class': monster_class,
                      'source': {'file': 'monsters.txt', 'entry': index}})
    for index, source_label in enumerate(header_sets['objects']):
        kind, label = appearance(index, source_label)
        tiles.append({'slot': 789 + index, 'label': label, 'category': 'object',
                      'object_class': kind, 'art_key': f'object/{kind}/{slug(label)}',
                      'source': {'file': 'objects.txt', 'entry': index}})
    for index, label in enumerate(header_sets['other']):
        category = 'effect' if 78 <= index <= 196 else 'terrain'
        tiles.append({'slot': 1272 + index, 'label': label, 'category': category,
                      'art_key': f'{category}/{slug(label)}',
                      'source': {'file': 'other.txt', 'entry': index}})
    for index, monster in enumerate(tiles[:789]):
        tiles.append({'slot': 1515 + index, 'label': 'statue of ' + monster['label'],
                      'category': 'statue', 'art_key': monster['art_key'],
                      'gender': monster['gender'], 'monster_class': monster['monster_class'],
                      'transform': 'statue', 'derived_from_slot': index,
                      'source': {'file': 'monsters.txt', 'entry': index}})
    require([tile['slot'] for tile in tiles] == list(range(2304)), 'Incomplete canonical catalog')
    art_keys = {}
    for tile in tiles:
        tile['engine_referenced'] = tile['slot'] in refs
        key = tile['art_key']
        if key not in art_keys:
            art_keys[key] = {k: tile[k] for k in ('label', 'category', 'monster_class', 'object_class')
                             if k in tile}
            art_keys[key].update(key=key, slots=[])
        art_keys[key]['slots'].append(tile['slot'])
    source_metadata = []
    for name, headers in header_sets.items():
        payload = '\n'.join(f'{i}: {label}' for i, label in enumerate(headers)) + '\n'
        source_metadata.append({'file': 'win/share/' + name + '.txt',
                                'headers_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                                'entries': len(headers)})
    definition_metadata = '\n'.join(f'{names}: {kind}' for names, kind in definitions) + '\n'
    source_metadata.append({'file': 'include/monsters.h',
                            'names_classes_sha256': hashlib.sha256(definition_metadata.encode()).hexdigest(),
                            'entries': len(definitions)})
    return {
        'schema': 1, 'engineVersion': '5.0.0', 'requiredTileCount': 2304,
        'columns': 40, 'rows': 58,
        'metadata_license': 'NGPL, NetHack DevTeam and contributors; see ../sources/NGPL.txt',
        'metadata_source': 'https://www.nethack.org/v500/download-src.html',
        'metadata_modifications': {'date': '2026-09-24', 'by': 'NetHack Atlas project',
                                   'description': 'Extracted identifying headers, normalized visible appearance names, '
                                                  'grouped reusable art keys and added explicit statue derivations. '
                                                  'No upstream pixels or palettes retained.'},
        'artwork_note': 'This catalog contains identifying metadata only, no upstream artwork. '
                        'Artwork rights are recorded separately. Object labels and shared art keys '
                        'describe appearances, not hidden identities. Statues derive from original '
                        'monster art. Identical male/female keys preserve slots without inventing '
                        'visual differences. engine_referenced=false includes conditional slots; '
                        'only slot 2303 is the conventional unused invisible statue.',
        'sources': source_metadata,
        'engine_validation': {'generated_source': 'src/tile.c', 'glyph_count': glyph_count,
                              'referenced_slots': len(refs),
                              'boundaries': {'maxmontile': 788, 'maxobjtile': 1271,
                                             'maxothtile': 1514, 'total_tiles_used': 2303}},
        'art_keys': list(art_keys.values()), 'tiles': tiles,
    }


def summary(catalog):
    return {'slots': len(catalog['tiles']), 'art_keys': len(catalog['art_keys']),
            'art_by_category': dict(Counter(a['category'] for a in catalog['art_keys'])),
            'engine_glyphs_checked': catalog['engine_validation']['glyph_count'],
            'engine_referenced_slots': catalog['engine_validation']['referenced_slots'],
            'statues_derived_from_monsters': sum(t.get('transform') == 'statue' for t in catalog['tiles'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nethack-root', type=Path, default=ROOT / 'vendor/NetHack-5.0.0')
    parser.add_argument('--output', type=Path, default=DEFAULT_CATALOG)
    parser.add_argument('--check', action='store_true', help='Verify the saved catalog without writing')
    args = parser.parse_args()
    catalog = generate(args.nethack_root)
    if args.check:
        require(json.loads(args.output.read_text()) == catalog,
                f'{args.output}: catalog differs from canonical metadata; regenerate and review')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary(catalog), indent=2))


if __name__ == '__main__':
    main()
