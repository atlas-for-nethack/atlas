"use strict";
const assert=require('node:assert/strict');
const manifest=require('../assets/tiles/manifest.json');
const study=require('../tools/tileset-preview/fixtures/baalz-preview.js');
const renderer=require('../web/tiles.js');
const records=require('../.artifacts/baalz-review-manifest.json');
const families=[['lantern','lantern-modern'],['soot-and-brass-classic','soot-and-brass']];
assert.throws(()=>study.compose({id:'official'},{}));
function paint(atlas,tile,material,mask=0,groundTile) {
  const calls=[],ctx={globalAlpha:1,drawImage:(...a)=>calls.push(a.slice(1)),save(){},restore(){},beginPath(){},rect(){},clip(){}};
  const cell={x:5,y:5,tile,...(material?{material}:{}),...(groundTile?{groundTile}:{})};
  const cells=new Map([['5,5',cell]]);
  [[0,-1],[1,0],[0,1],[-1,0],[1,-1],[1,1],[-1,1],[-1,-1]].forEach(([dx,dy],i)=>{
    if(mask&(1<<i))cells.set(`${5+dx},${5+dy}`,{x:5+dx,y:5+dy,tile:1291});
  });
  renderer.paint(ctx,{width:atlas.columns*atlas.tileWidth,height:100000},atlas,cell,0,0,64,64,true,cells);
  return calls;
}
for(const id of families.flat()) {
  const atlas=manifest.tilesets.find(a=>a.id===id),before=JSON.stringify(atlas),token={};
  const result=study.compose(atlas,token),material=result.atlas.regionalMaterials['baalz-review'];
  assert.deepEqual(atlas.regionalMaterials.baalz,material,'playable mapping matches approved review');
  assert.equal(result.image,token,'reuse original image bytes');
  assert.equal(JSON.stringify(atlas),before,'metadata immutable');
  for(let i=0;i<11;i++)for(let mask=0;mask<256;mask++) {
    assert.deepEqual(paint(result.atlas,1482+i,'baalz-review',mask),paint(atlas,1482+i,'gehennom',mask),'actual fortress directional walls exactly reuse Gehennom');
    assert.deepEqual(paint(result.atlas,1273+i,'baalz-review',mask),paint(atlas,1482+i,'gehennom',mask),'shared fixture wall aliases match existing directional artwork');
  }
  for(const tile of [1291,1292])for(const actor of [tile,699,632,1300])
    assert.deepEqual(paint(result.atlas,actor,'baalz-review',15,tile),paint(atlas,actor,'gehennom',15,tile),'known ground under occupants reuses Gehennom');
  for(const tile of [1272,1285,1286,1287,1288,1289,1300,1314,1315,1469,1470,632,684])
    assert.deepEqual(paint(result.atlas,tile,'baalz-review',15),paint(atlas,tile,null,15),'unrelated doors, bars, traps, water, lava and actors unchanged');
  for(const scene of Object.values(records.scenes)) {
    const original=new Map(scene.cells.map(c=>[`${c.x},${c.y}`,c])),snapshot=JSON.stringify([...original]);
    const proposed=study.cells(original,true),current=study.cells(original,false);
    assert.equal(JSON.stringify([...original]),snapshot,'engine records immutable');
    assert.deepEqual([...proposed.keys()],[...original.keys()]);
    for(const [key,cell]of proposed) {
      const copy={...cell};delete copy.material;
      assert.deepEqual(copy,current.get(key),'canonical terrain, lighting and perceived occupants identical');
      if(cell.tile===1469||cell.tile===1470)assert(!cell.material&&!('groundTile'in cell),'unknown stays unknown');
    }
  }
  for(const [tile,value]of Object.entries(atlas.regionalMaterials.gehennom.tileMap))assert.equal(material.tileMap[tile],value);
}
for(const [classic,modern]of families)assert.deepEqual(
  study.compose(manifest.tilesets.find(a=>a.id===classic),{}).atlas.regionalMaterials['baalz-review'],
  study.compose(manifest.tilesets.find(a=>a.id===modern),{}).atlas.regionalMaterials['baalz-review'],
  'edition architecture parity');
console.log('Baalzebub exact Gehennom reuse, all directional poses, unrelated art, perception and edition parity passed.');
