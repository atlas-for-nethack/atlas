'use strict';
const assert=require('node:assert/strict');
const manifest=require('../assets/tiles/manifest.json');
const renderer=require('../web/tiles.js');
function paint(atlas,cell){
 const calls=[],ctx={globalAlpha:1,drawImage:(...a)=>calls.push(a.slice(1)),save(){},restore(){},beginPath(){},rect(){},clip(){}};
 renderer.paint(ctx,{width:atlas.columns*atlas.tileWidth,height:100000},atlas,cell,0,0,64,64,true,new Map());
 return calls;
}
// Packing changes source origins only. Preserve crop size, destination
// geometry, call ordering and every same-atlas renderer assertion below.
function comparableDraws(calls) {
  return calls.map(call => {
    assert.equal(call.length, 8, 'Expected an explicit source and destination rectangle');
    return [0, 0, ...call.slice(2)];
  });
}
for(const [classic,modern]of [['lantern','lantern-modern'],['soot-and-brass-classic','soot-and-brass']]){
 const a=manifest.tilesets.find(t=>t.id===classic),b=manifest.tilesets.find(t=>t.id===modern);
 for(const atlas of [a,b]){
  assert.deepEqual(Object.keys(atlas.regionalMaterials['quest-earth'].tileMap).sort(),['1291','1292']);
  assert.notDeepEqual(paint(atlas,{tile:1291,material:'quest-earth'}),paint(atlas,{tile:1291}));
  assert.deepEqual(paint(atlas,{tile:1291,material:'quest-earth'}),paint(atlas,{tile:1291,material:'caveman'}));
  for(const tile of [1284,1291,1292,1293,1294,1295,1296])
   assert.deepEqual(paint(atlas,{tile,material:'priest-temple'}),paint(atlas,{tile}));
  assert.notDeepEqual(paint(atlas,{tile:1273,material:'priest-temple'}),paint(atlas,{tile:1273}));
 }
 for(const material of [undefined,'caveman','valley','gehennom','baalz','quest-earth','priest-temple']){
  for(const tile of [1273,1284,1287,1288,1291,1292,1303,1314,1315,1316,1322,1323,1324,1469,1470])
   assert.deepEqual(comparableDraws(paint(a,{tile,material})),comparableDraws(paint(b,{tile,material})),`${material}/${tile}: family architecture must match`);
  for(const atlas of [a,b]){
   for(const tile of [1314,1315,1316,1322,1323,1324,1469,1470])
    assert.deepEqual(paint(atlas,{tile,material}),paint(atlas,{tile}),`${material}: canonical hazard or unknown appearance`);
   const floor=paint(atlas,{tile:1291,material});
   const occupied=paint(atlas,{tile:699,groundTile:1291,material});
   assert.deepEqual(occupied[0],floor[0],'known regional ground survives under an occupant');
   const imported={...atlas,regionalMaterials:undefined};
   assert.deepEqual(paint(imported,{tile:1291,material}),paint(imported,{tile:1291}),'imports without metadata retain canonical fallback');
  }
 }
}
console.log('Quest material reuse, Classic/Modern architecture, canonical hazards, occupied ground and community fallback passed.');
