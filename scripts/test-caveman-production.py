#!/usr/bin/env python3
"""Verify shipped Caveman materials, provenance and edition parity.

Optional --oracle explicitly enables comparisons to separately retained capture
files. Without an oracle the current production checks run independently of any
private development history; historical comparisons are explicitly skipped.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest
from PIL import Image, ImageEnhance

ROOT=Path(__file__).resolve().parents[1];TILES=ROOT/'assets/tiles'
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--oracle',type=Path)
args,rest=parser.parse_known_args();sys.argv=[sys.argv[0],*rest]
ORACLE=args.oracle
EDITIONS=('lantern','lantern-modern','soot-and-brass','soot-and-brass-classic')


def crop(image,rect):x,y,w,h=rect;return image.crop((x,y,x+w,y+h)).tobytes()
def cell(image,slot):return crop(image,[slot%40*64,slot//40*64,64,64])
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class CavemanProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries={entry['id']:entry for entry in json.loads((TILES/'manifest.json').read_text())['tilesets']}

    def compare_frames(self,a,af,b,bf):
        self.assertEqual(crop(a,af['source']),crop(b,bf['source']))
        for key in ('offset','depth','kind','occupiedSquares'):self.assertEqual(af.get(key),bf.get(key))
        self.assertEqual(len(af.get('alternates',[])),len(bf.get('alternates',[])))
        for aa,bb in zip(af.get('alternates',[]),bf.get('alternates',[])):self.compare_frames(a,aa,b,bb)

    def compare_materials(self,a,aa,am,b,ba,bm):
        self.assertEqual(set(am['tileMap']),set(bm['tileMap']))
        for slot,at in am['tileMap'].items():
            bt=bm['tileMap'][slot]
            self.assertEqual(cell(a,at),cell(b,bt),slot)
            if str(at) in aa['projectedFrames']['frames']:
                self.compare_frames(a,aa['projectedFrames']['frames'][str(at)],b,ba['projectedFrames']['frames'][str(bt)])
        self.assertEqual(set(am['wallTiles']),set(bm['wallTiles']))
        for slot,ar in am['wallTiles'].items():
            br=bm['wallTiles'][slot]
            for key in ('topology','connections'):self.assertEqual(ar.get(key),br.get(key))
            self.assertEqual(len(ar['variants']),len(br['variants']))
            for at,bt in set(zip(ar['variants'],br['variants'])):
                self.assertEqual(cell(a,at),cell(b,bt))
                self.compare_frames(a,aa['projectedFrames']['frames'][str(at)],b,ba['projectedFrames']['frames'][str(bt)])

    def test_exact_approved_review(self):
        if ORACLE is None:self.skipTest('Optional --oracle not supplied')
        path=ORACLE/'caveman-material-manifest.json'
        self.assertTrue(path.is_file(), 'Requested oracle lacks caveman-material-manifest.json')
        approved=json.loads(path.read_text())['tilesets']
        for ident in EDITIONS:
            entry=self.entries[ident];production=Image.open(TILES/entry['file']).convert('RGBA')
            for treatment,region in [('normal','caveman'),('goal','caveman-goal')]:
                expected=approved[ident][treatment]
                image=Image.open(ORACLE/expected['file']).convert('RGBA')
                self.compare_materials(image,expected['atlas'],expected['atlas']['regionalMaterials']['caveman'],
                                       production,entry,entry['regionalMaterials'][region])

    def test_previous_display_pixels_and_regions_unchanged(self):
        if ORACLE is None:self.skipTest('Optional --oracle not supplied')
        folder=ORACLE/'previous-production'
        self.assertTrue((folder/'manifest.json').is_file(), 'Requested oracle lacks previous-production/manifest.json')
        for before in json.loads((folder/'manifest.json').read_text())['tilesets']:
            if before['id'] not in EDITIONS:continue
            after=self.entries[before['id']]
            a=Image.open(folder/before['file']).convert('RGBA');b=Image.open(TILES/after['file']).convert('RGBA')
            # Lantern Modern's existing creature crops move after the expanded
            # Classic base; compare all frames rather than stale coordinates.
            if before['id']!='lantern-modern':self.assertEqual(a.tobytes(),b.crop((0,0,*a.size)).tobytes())
            for slot in range(2304):self.assertEqual(cell(a,slot),cell(b,slot))
            self.assertEqual(before['lanternWalls'],after['lanternWalls'])
            for slot,frame in before['projectedFrames']['frames'].items():
                self.compare_frames(a,frame,b,after['projectedFrames']['frames'][slot])
            for region,material in before['regionalMaterials'].items():
                self.assertEqual(material,after['regionalMaterials'][region])
                for slot in material['tileMap'].values():self.assertEqual(cell(a,slot),cell(b,slot))

    def test_classic_modern_parity(self):
        for classic,modern in [('lantern','lantern-modern'),('soot-and-brass-classic','soot-and-brass')]:
            ca,mo=self.entries[classic],self.entries[modern]
            a=Image.open(TILES/ca['file']).convert('RGBA');b=Image.open(TILES/mo['file']).convert('RGBA')
            for region in ('caveman','caveman-goal'):
                self.compare_materials(a,ca,ca['regionalMaterials'][region],b,mo,mo['regionalMaterials'][region])

    def test_main_mines_aliases_and_door_exclusion(self):
        for ident in EDITIONS:
            entry=self.entries[ident]
            for region in ('caveman','caveman-goal'):
                material=entry['regionalMaterials'][region]
                for i in range(11):
                    self.assertEqual(material['tileMap'][str(1273+i)],material['tileMap'][str(1471+i)])
                    self.assertEqual(material['wallTiles'][str(1273+i)],material['wallTiles'][str(1471+i)])
                expected=set(range(1273,1284))|set(range(1471,1482))|set(range(1291,1297))
                if ident.startswith('lantern'):expected.add(1284)
                self.assertEqual(expected,set(map(int,material['tileMap'])))
                for rule in entry['lanternWalls']['doors'].values():
                    for variant in rule['variants']:self.assertNotIn(str(variant),material['tileMap'])

    def test_source_floor_and_full_height_corners(self):
        folder=TILES/'regions/caveman'
        registry=json.loads((folder/'sources.json').read_text())
        for ident in EDITIONS:
            entry=self.entries[ident]
            family='lantern' if ident.startswith('lantern') else 'soot-and-brass'
            with Image.open(TILES/entry['file']) as opened:
                image=opened.convert('RGBA')
            for treatment,region in [('normal','caveman'),('goal','caveman-goal')]:
                material=entry['regionalMaterials'][region]
                with Image.open(folder/registry['sources'][family+'-'+treatment]['file']) as opened:
                    source=opened.convert('RGBA')
                floor=source.crop((521,397,602,469)).resize((64,64),Image.Resampling.NEAREST)
                dark=ImageEnhance.Brightness(floor).enhance(.66 if family=='lantern' else .47)
                for slot,expected in [(1291,floor),(1292,dark)]:
                    self.assertEqual(cell(image,material['tileMap'][str(slot)]),expected.tobytes(),(ident,treatment,slot))
                for slot in (1473,1474,1475,1476):
                    frame=entry['projectedFrames']['frames'][str(material['tileMap'][str(slot)])]
                    self.assertEqual(frame['source'][2:],[51,71])
                    self.assertEqual(frame['offset'][1],-7)

    def test_source_provenance_and_license(self):
        folder=TILES/'regions/caveman';registry=json.loads((folder/'sources.json').read_text())
        self.assertEqual(registry['license'],'CC-BY-4.0')
        self.assertEqual(registry['floorCrop'],[521,397,602,469])
        self.assertEqual(digest(folder/registry['prompts']['file']),registry['prompts']['sha256'])
        oracle=json.loads((ROOT/'tools/tileset-preview/fixtures/caveman-source-digests.json').read_text())
        self.assertEqual(registry['prompts'],oracle['prompts'])
        self.assertEqual(set(registry['sources']),set(oracle['sources']))
        for key,record in registry['sources'].items():
            self.assertEqual(digest(folder/record['file']),record['sha256'])
            self.assertEqual(digest(ROOT/record['reference']),record['referenceSha256'])
            # Independent frozen digests retain approval evidence without copied PNGs.
            self.assertEqual(record['file'],oracle['sources'][key]['file'])
            self.assertEqual(record['sha256'],oracle['sources'][key]['sha256'])
            self.assertEqual(record['referenceSha256'],oracle['sources'][key]['referenceSha256'])
        for ident in EDITIONS:self.assertEqual(self.entries[ident]['license'],registry['license'])


if __name__=='__main__':unittest.main(verbosity=2)
