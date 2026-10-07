"use strict";
const assert=require('node:assert/strict');
const manifest=require('../assets/tiles/manifest.json');
const study=require('../tools/tileset-preview/fixtures/medusa-preview.js');
const renderer=require('../web/tiles.js');
const original=new Map([
  ['1,2',{x:1,y:2,tile:1273,groundTile:1291,material:'samurai'}],
  ['2,2',{x:2,y:2,tile:684,groundTile:1314,monsterName:'Medusa'}],
  ['3,2',{x:3,y:2,tile:1469}]
]);
const expected=[...original].map(([key,value])=>{const copy={...value};delete copy.material;return [key,copy];});
assert.deepEqual([...study.cells(original,false)],expected);
assert.deepEqual([...study.cells(original,true)],expected,'both sides retain the identical engine display');
assert.equal(original.get('1,2').material,'samurai','input cells are immutable');
assert.throws(()=>study.recipe({id:'official'}));
function overlaps(a,b) {return a[0]<b[0]+b[2]&&a[0]+a[2]>b[0]&&a[1]<b[1]+b[3]&&a[1]+a[3]>b[1];}
function frames(f) {return [f,...(f.alternates||[]).flatMap(frames)];}
const reports=[];
for (const atlas of manifest.tilesets.filter(a=>['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(a.id))) {
  const slots=study.architectureSlots(atlas), rects=study.rectangles(atlas);
  const token={},snapshot=JSON.stringify(atlas),reused=study.reuseSokoban(atlas,token);
  assert.equal(reused.image,token,'Sokoban reuses the original image without pixel edits');
  assert.equal(JSON.stringify(atlas),snapshot,'review does not mutate shipped metadata');
  const material=reused.atlas.regionalMaterials['medusa-sokoban-review'];
  assert.equal(Object.keys(material.tileMap).length,11,'only walls are replaced');
  for(let i=0;i<11;i++) {
    assert.equal(material.tileMap[1273+i],1504+i);
    assert.equal(material.wallTiles[1273+i],atlas.lanternWalls.tiles[1504+i],
      'all directional variants use the shipped Sokoban rule exactly');
  }
  if(atlas.regionalMaterials?.medusa) {
    assert.deepEqual(atlas.regionalMaterials.medusa,material,'shipped mapping matches approved reuse');
    const image={width:atlas.columns*atlas.tileWidth,height:100000};
    const offsets=[[0,-1],[1,0],[0,1],[-1,0],[1,-1],[1,1],[-1,1],[-1,-1]];
    const paint=(tile,mask,region)=>{
      const calls=[],ctx={drawImage:(...args)=>calls.push(args.slice(1)),
        save(){},restore(){},beginPath(){},rect(){},clip(){}};
      const subject={x:5,y:5,tile,...(region?{material:region}:{})};
      const cells=new Map([['5,5',subject]]);
      offsets.forEach(([dx,dy],i)=>{if(mask&(1<<i))cells.set(`${5+dx},${5+dy}`,{x:5+dx,y:5+dy,tile:1291});});
      renderer.paint(ctx,image,atlas,subject,0,0,64,64,true,cells);
      return calls;
    };
    for(let i=0;i<11;i++)for(let mask=0;mask<256;mask++)
      assert.deepEqual(paint(1273+i,mask,'medusa'),paint(1504+i,mask),
        'every Medusa wall pose renders exactly like native Sokoban');
    for(const tile of [1285,1286,1287,1288,1289,1291,1292,1314,1469,1470,684])
      assert.deepEqual(paint(tile,15,'medusa'),paint(tile,15),
        'doors, ground, actors and unknown appearances remain unchanged');
  }
  for (let id=1273;id<=1283;id++) {
    assert(slots.has(id));
    for (const variant of atlas.lanternWalls.tiles[id].variants) assert(slots.has(variant));
  }
  for (const [id,rule]of Object.entries(atlas.lanternWalls.doors)) {
    assert(slots.has(+id)); for(const variant of rule.variants)assert(slots.has(variant));
  }
  for (const id of [1284,1289,1291,1292,1293,1294,1295,1296,1314,1315,1469,1470,1504])
    assert(!slots.has(id),'floor, bars, water, unknown and Sokoban slots are excluded');
  for (const [id,frame]of Object.entries(atlas.projectedFrames.frames)) {
    if(slots.has(+id)) {
      for (const f of frames(frame))assert(rects.some(r=>r.slice(0,4).join(',')===f.source.join(',')),'all directional frame sources are treated');
    } else {
      for (const f of frames(frame))assert(!rects.some(r=>overlaps(r,f.source)),`unrelated artwork ${id} is never touched`);
    }
  }
  const style=study.recipe(atlas), pixels=new Uint8ClampedArray([75,80,86,255,80,80,80,1,123,86,45,128,17,33,44,0]);
  const originalPixels=pixels.slice();
  study.transformPixels(pixels,2,'wall',style);
  assert.deepEqual([pixels[3],pixels[7],pixels[11],pixels[15]],[255,1,128,0],'alpha remains byte-identical');
  assert.deepEqual(pixels.slice(12),originalPixels.slice(12),'transparent pixel data is preserved');
  const second=study.transformPixels(originalPixels.slice(),2,'wall',style);
  assert.deepEqual(pixels,second,'weathering is reproducible');
  const luminance=rgb=>.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
  const mortar=luminance(study.color(20,20,20,3,3,'wall',style));
  const worn=[];
  for(let y=0;y<64;y++)for(let x=0;x<64;x++)worn.push(luminance(study.color(95,95,95,x,y,'wall',style)));
  const mean=worn.reduce((a,b)=>a+b)/worn.length;
  assert(Math.abs(mortar-20)<.0001,'deep mortar remains dark');
  assert(mean>115&&mean<125,'stone faces have a visible moderate luminance lift');
  assert(Math.max(...worn)-Math.min(...worn)>10,'weather variation supplies a non-color cue');
  reports.push({tileset:atlas.id,slots:slots.size,rectangles:rects.length,stoneMean:Math.round(mean),mortar});
}
for(const [classic,modern]of [['lantern','lantern-modern'],['soot-and-brass-classic','soot-and-brass']]) {
  const a=manifest.tilesets.find(a=>a.id===classic),b=manifest.tilesets.find(a=>a.id===modern);
  assert.deepEqual(study.recipe(a),study.recipe(b),'editions use the identical family material');
  assert.deepEqual(study.reuseSokoban(a,{}).atlas.regionalMaterials['medusa-sokoban-review'],
    study.reuseSokoban(b,{}).atlas.regionalMaterials['medusa-sokoban-review']);
}
const reusedCells=study.cells(original,'sokoban');
assert.equal(reusedCells.get('1,2').tile,1273,'engine glyphs remain unchanged');
assert.equal(reusedCells.get('1,2').material,'medusa-sokoban-review');
assert(!reusedCells.get('3,2').material,'unknown terrain is never decorated');
console.log(JSON.stringify(reports,null,2));
console.log('Medusa source coverage, unrelated-art isolation, alpha, deterministic texture and same-engine-cell checks passed.');
