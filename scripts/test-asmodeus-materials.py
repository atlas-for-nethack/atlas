#!/usr/bin/env python3
"""Compare production palace pixels to the independently approved JS preview.

Use --shipped after rebuilding. Without it, also verify append-only preservation.
Node is a test dependency only; production tile generation needs just Pillow.
"""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
TILES=ROOT/'assets/tiles'
SHIPPED='--shipped' in sys.argv
if SHIPPED:sys.argv.remove('--shipped')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

def crop(image,rect):
    x,y,w,h=rect;return image.crop((x,y,x+w,y+h))

def rect(slot):return [slot%40*64,slot//40*64,64,64]

def digest(image):return hashlib.sha256(image.tobytes()).hexdigest()

class AsmodeusMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries={a['id']:a for a in json.loads((TILES/'manifest.json').read_text())['tilesets']}
        cls.regional=module('asmodeus_regional',TILES/'regional_materials.py')
        cls.pack=module('asmodeus_pack',TILES/'packing.py').append_projected
        cls.examples={}
        for ident in ('lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'):
            entry=cls.entries[ident];source=Image.open(TILES/entry['file']).convert('RGBA')
            family='lantern' if ident.startswith('lantern') else 'soot-and-brass'
            if SHIPPED:
                cls.examples[ident]=(source,source,entry['projectedFrames'],entry['regionalMaterials']['asmodeus'])
            else:
                output,projection,_,material,_,_=cls.regional.append_asmodeus(
                    source,copy.deepcopy(entry['projectedFrames']),family,cls.pack,
                    entry['lanternWalls'],entry['regionalMaterials'])
                cls.examples[ident]=(source,output,projection,material)

    def test_exact_approved_preview_pixels_and_geometry(self):
        # JS supplies its rectangle plan and processes original raw pixels. It
        # does not call production Python, so rounding or stencil drift fails.
        for ident,(source,output,projection,material) in self.examples.items():
            entry=self.entries[ident]
            js="""const fs=require('fs'),s=require('./tools/tileset-preview/fixtures/asmodeus-preview.js');
const a=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify({pieces:s.rectangles(a),marks:[...s.ornaments(a)]}));"""
            plan=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(entry).encode(),cwd=ROOT))
            marks=dict(plan['marks']);cases=[];results=[]
            mapping={}
            def pair(original,target):
                for key in ('offset','depth','occupiedSquares','kind'):
                    self.assertEqual(original.get(key),target.get(key),(ident,key))
                mapping[','.join(map(str,original['source']))]=target['source']
                self.assertEqual(len(original.get('alternates',[])),len(target.get('alternates',[])))
                for a,b in zip(original.get('alternates',[]),target.get('alternates',[])):pair(a,b)
            for key,target in material['tileMap'].items():
                mapping[','.join(map(str,rect(int(key))))]=rect(target)
                if key in entry['projectedFrames']['frames']:
                    pair(entry['projectedFrames']['frames'][key],projection['frames'][str(target)])
            for piece in plan['pieces']:
                key=','.join(map(str,piece['target']));original=crop(source,piece['source'])
                result=crop(output,mapping[key])
                self.assertEqual(original.size,result.size)
                self.assertEqual(original.getchannel('A').tobytes(),result.getchannel('A').tobytes())
                cases.append({'kind':piece['kind'],'width':original.width,'height':original.height,
                              'mark':marks.get(key),'data':base64.b64encode(original.tobytes()).decode()})
                results.append(digest(result))
            js="""const fs=require('fs'),crypto=require('crypto'),s=require('./tools/tileset-preview/fixtures/asmodeus-preview.js');
const {family,cases}=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cases.map(c=>{const data=new Uint8ClampedArray(Buffer.from(c.data,'base64'));
for(let i=0;i<data.length;i+=4){const rgb=s.color(family,c.kind,...data.slice(i,i+3));data.set(rgb,i);}
s.engrave({data,width:c.width,height:c.height},c.mark,family);
return crypto.createHash('sha256').update(data).digest('hex');})));"""
            expected=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps({
                'family':'lantern' if ident.startswith('lantern') else 'soot-and-brass','cases':cases}).encode(),cwd=ROOT))
            self.assertEqual(expected,results,ident)

    def test_wall_aliases_and_directional_coverage(self):
        for ident,(_,_,_,material) in self.examples.items():
            wall=self.entries[ident]['lanternWalls'];mapping=material['tileMap']
            for slot in range(1273,1284):
                self.assertEqual(mapping[str(slot)],mapping[str(slot+209)])
                for a,b in zip(wall['tiles'][str(slot)]['variants'],wall['tiles'][str(slot+209)]['variants']):
                    self.assertEqual(mapping[str(a)],mapping[str(b)])
            for slot,rule in wall['doors'].items():
                for key in {int(slot),*rule['variants']}:self.assertIn(str(key),mapping)
            bars=wall['bars']
            for rule in (bars['horizontal'],bars['vertical'],*bars['connections'].values()):
                for key in {bars['tile'],bars['isolated'],*rule['variants']}:self.assertIn(str(key),mapping)
            self.assertTrue(set(range(1291,1297))<=set(map(int,mapping)))
            self.assertFalse(set(range(0,1273))&set(map(int,mapping)))

    def test_existing_atlas_and_frames_unchanged(self):
        if SHIPPED:return
        for ident,(source,output,projection,_) in self.examples.items():
            self.assertEqual(source.tobytes(),crop(output,[0,0,*source.size]).tobytes(),ident)
            for key,frame in self.entries[ident]['projectedFrames']['frames'].items():
                self.assertEqual(frame,projection['frames'][key])

    def test_classic_modern_parity(self):
        for classic,modern in [('lantern','lantern-modern'),('soot-and-brass-classic','soot-and-brass')]:
            _,a,pa,ma=self.examples[classic];_,b,pb,mb=self.examples[modern]
            self.assertEqual(set(ma['tileMap']),set(mb['tileMap']))
            def equal_frames(fa,fb):
                self.assertEqual(crop(a,fa['source']).tobytes(),crop(b,fb['source']).tobytes())
                for key in ('offset','depth','kind','occupiedSquares'):self.assertEqual(fa.get(key),fb.get(key))
                self.assertEqual(len(fa.get('alternates',[])), len(fb.get('alternates',[])))
                self.assertEqual(fa['source'][2:], fb['source'][2:])
                for aa,bb in zip(fa.get('alternates',[]),fb.get('alternates',[])):equal_frames(aa,bb)
            for key,ta in ma['tileMap'].items():
                tb=mb['tileMap'][key]
                self.assertEqual(crop(a,rect(ta)).tobytes(),crop(b,rect(tb)).tobytes())
                if str(ta) in pa['frames']:equal_frames(pa['frames'][str(ta)],pb['frames'][str(tb)])

if __name__=='__main__':unittest.main(verbosity=2)
