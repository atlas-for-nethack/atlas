#!/usr/bin/env python3
"""Check exact-source Vlad lighting. Add --shipped to require built materials."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from PIL import Image, ImageEnhance

ROOT=Path(__file__).resolve().parents[1]
TILES=ROOT/'assets/tiles'
SHIPPED='--shipped' in sys.argv
if SHIPPED:sys.argv.remove('--shipped')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

def cell(image,slot):
    x,y=slot%40*64,slot//40*64
    return image.crop((x,y,x+64,y+64))

def frame_pixels(image,frame):
    x,y,w,h=frame['source']
    return image.crop((x,y,x+w,y+h))

class VladMaterials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries={x['id']:x for x in json.loads((TILES/'manifest.json').read_text())['tilesets']}
        cls.regional=module('test_vlad_regional',TILES/'regional_materials.py')
        cls.pack=module('test_vlad_pack',TILES/'packing.py').append_projected
        cls.examples={}
        for ident in ('lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'):
            entry=cls.entries[ident]
            source=Image.open(TILES/entry['file']).convert('RGBA')
            if SHIPPED:
                if 'vlad' not in entry.get('regionalMaterials',{}):
                    raise AssertionError('Missing shipped Vlad material: '+ident)
                cls.examples[ident]=(source,source,entry['projectedFrames'],entry['regionalMaterials']['vlad'])
            else:
                family='lantern' if ident.startswith('lantern') else 'soot-and-brass'
                output,projection,_,material,_,_=cls.regional.append_vlad(
                    source,copy.deepcopy(entry['projectedFrames']),family,cls.pack,entry['lanternWalls'])
                cls.examples[ident]=(source,output,projection,material)

    def check_frame(self,before,after,source_frame,target_frame,factor):
        for key in ('offset','depth','occupiedSquares','kind'):
            self.assertEqual(source_frame.get(key),target_frame.get(key),key)
        source=frame_pixels(before,source_frame)
        target=frame_pixels(after,target_frame)
        self.assertEqual(source.size,target.size)
        self.assertEqual(source.getchannel('A').tobytes(),target.getchannel('A').tobytes())
        self.assertEqual(ImageEnhance.Brightness(source).enhance(factor).tobytes(),target.tobytes())
        originals=source_frame.get('alternates',[]);results=target_frame.get('alternates',[])
        self.assertEqual(len(originals),len(results))
        for original,result in zip(originals,results):self.check_frame(before,after,original,result,factor)

    def test_all_selected_pixels_and_projection(self):
        for ident,(source,output,projection,material) in self.examples.items():
            with self.subTest(edition=ident):
                entry=self.entries[ident]
                for key,target in material['tileMap'].items():
                    slot=int(key);factor=.88 if slot==1284 or 1291<=slot<=1296 else .8
                    original=cell(source,slot);result=cell(output,target)
                    self.assertEqual(ImageEnhance.Brightness(original).enhance(factor).tobytes(),result.tobytes())
                    self.assertEqual(original.getchannel('A').tobytes(),result.getchannel('A').tobytes())
                    if key in entry['projectedFrames']['frames']:
                        self.check_frame(source,output,entry['projectedFrames']['frames'][key],projection['frames'][str(target)],factor)

    def test_directional_coverage_and_exclusions(self):
        for ident,(_,_,_,material) in self.examples.items():
            walls=self.entries[ident]['lanternWalls'];expected=set(range(1273,1290))|set(range(1291,1297))
            if not ident.startswith('lantern'):expected.remove(1284)
            for slot in range(1273,1284):expected.update(walls['tiles'][str(slot)]['variants'])
            for entry in walls['doors'].values():expected.update(entry['variants'])
            bars=walls['bars']
            for entry in (bars['vertical'],bars['horizontal'],*bars['connections'].values()):expected.update(entry['variants'])
            self.assertEqual(expected,set(map(int,material['tileMap'])),ident)

    def test_existing_atlas_and_regional_frames_unchanged(self):
        if SHIPPED:return # Full prefix preservation is checked by in-memory generation.
        for ident,(source,output,projection,_) in self.examples.items():
            self.assertEqual(source.tobytes(),output.crop((0,0,*source.size)).tobytes(),ident)
            for key,frame in self.entries[ident]['projectedFrames']['frames'].items():
                self.assertEqual(frame,projection['frames'][key],(ident,key))

    def test_classic_modern_environment_parity(self):
        for classic,modern in [('lantern','lantern-modern'),('soot-and-brass-classic','soot-and-brass')]:
            _,a,pa,ma=self.examples[classic];_,b,pb,mb=self.examples[modern]
            self.assertEqual(set(ma['tileMap']),set(mb['tileMap']))
            for key,ta in ma['tileMap'].items():
                tb=mb['tileMap'][key]
                self.assertEqual(cell(a,ta).tobytes(),cell(b,tb).tobytes(),(classic,key))
                fa=pa['frames'].get(str(ta));fb=pb['frames'].get(str(tb))
                if fa:
                    self.assertIsNotNone(fb)
                    self.check_frame(a,b,fa,fb,1)

if __name__=='__main__':unittest.main(verbosity=2)
