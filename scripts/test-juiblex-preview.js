"use strict";
const assert=require('node:assert/strict');
const manifest=require('../assets/tiles/manifest.json');
const study=require('../tools/tileset-preview/fixtures/juiblex-preview.js');
const renderer=require('../web/tiles.js');
const records=require('../.artifacts/juiblex-review-manifest.json');
const families=[['lantern','lantern-modern'],['soot-and-brass-classic','soot-and-brass']];
assert.throws(()=>study.compose({id:'official'},{}));
function paint(atlas,cell){
  const calls=[],ctx={globalAlpha:1,drawImage:(...a)=>calls.push(a.slice(1)),save(){},restore(){},beginPath(){},rect(){},clip(){}};
  renderer.paint(ctx,{width:atlas.columns*atlas.tileWidth,height:100000},atlas,cell,0,0,64,64,true,new Map());
  return calls;
}
for(const id of families.flat()) {
  const atlas=manifest.tilesets.find(a=>a.id===id),before=JSON.stringify(atlas),token={};
  const result=study.compose(atlas,token);
  assert.equal(result.image,token,'no pixel generation or recoloring');
  assert.equal(JSON.stringify(atlas),before,'shipped metadata immutable');
  const material=result.atlas.regionalMaterials['juiblex-review'];
  assert.deepEqual(atlas.regionalMaterials.juiblex,material,'playable material exactly matches approved preview');
  assert.deepEqual(Object.keys(material.tileMap).sort(),['1291','1292'],'only two dry floor appearances');
  assert(!material.wallTiles,'no manufactured walls');
  for(const tile of [1291,1292]) {
    assert.equal(material.tileMap[tile],atlas.regionalMaterials.gehennom.tileMap[tile]);
    for(const foreground of [tile,632,684,1300]) {
      const cell={tile:foreground,groundTile:tile};
      assert.deepEqual(paint(result.atlas,{...cell,material:'juiblex-review'}),paint(atlas,{...cell,material:'gehennom'}),'known floor under occupants reuses exact Gehennom drawing');
    }
  }
  for(const tile of [1272,1273,1288,1293,1300,1314,1469,1470,632,684])
    assert.deepEqual(paint(result.atlas,{tile,material:'juiblex-review'}),paint(atlas,{tile}),'unrelated water, traps, architecture and actors remain unchanged');
  for(const scene of Object.values(records.scenes)) {
    const original=new Map(scene.cells.map(c=>[`${c.x},${c.y}`,c])),snapshot=JSON.stringify([...original]);
    const proposed=study.cells(original,true),current=study.cells(original,false);
    assert.equal(JSON.stringify([...original]),snapshot);
    assert.deepEqual([...proposed.keys()],[...original.keys()]);
    for(const [key,cell]of proposed) {
      const copy={...cell};delete copy.material;
      assert.deepEqual(copy,current.get(key),'engine tile, lighting, occupants and known ground stay identical');
      if(cell.tile===1469||cell.tile===1470)assert(!cell.material&&!('groundTile'in cell),'unknown remains unknown');
      if(cell.tile===1314)assert.deepEqual(paint(result.atlas,cell),paint(atlas,current.get(key)),'actual pool unchanged');
    }
  }
}
for(const atlas of manifest.tilesets.filter(a=>!families.flat().includes(a.id))) {
  assert(!atlas.regionalMaterials?.juiblex,'other designs are not overridden');
  for(const tile of [1291,1292,1314,699,1469])
    assert.deepEqual(paint(atlas,{tile,material:'juiblex'}),paint(atlas,{tile}),
      'missing optional context falls back to canonical artwork');
}
for(const [classic,modern]of families)assert.deepEqual(
  study.compose(manifest.tilesets.find(a=>a.id===classic),{}).atlas.regionalMaterials['juiblex-review'],
  study.compose(manifest.tilesets.find(a=>a.id===modern),{}).atlas.regionalMaterials['juiblex-review'],
  'Classic and Modern share identical material');
console.log('Juiblex exact Gehennom floor reuse, unrelated art, recorded perception and edition parity passed.');
