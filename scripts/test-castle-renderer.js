"use strict";
const assert=require('node:assert/strict');
const manifest=require('../assets/tiles/manifest.json');
const renderer=require('../web/tiles.js');
const families=[['lantern','lantern-modern'],['soot-and-brass-classic','soot-and-brass']];
function paint(atlas,cell) {
  const calls=[],ctx={globalAlpha:1,drawImage:(...a)=>calls.push(a.slice(1)),save(){},restore(){},beginPath(){},rect(){},clip(){}};
  renderer.paint(ctx,{width:atlas.columns*atlas.tileWidth,height:100000},atlas,cell,0,0,64,64,true,new Map());
  return calls;
}
for(const [classic,modern]of families) {
  const a=manifest.tilesets.find(t=>t.id===classic),b=manifest.tilesets.find(t=>t.id===modern);
  for(const tile of [1284,1287,1288,1291,1292,1303,1314,1318,1319,1320,1321])
    assert.deepEqual(paint(a,{tile}),paint(b,{tile}),'Castle architecture and features have edition parity');
  for(const atlas of [a,b])for(const groundTile of [1314,1318,1319]) {
    const bare=paint(atlas,{tile:groundTile});
    assert(bare.length,'terrain has a real drawing');
    for(const occupant of [699,632]) {
      const composed=paint(atlas,{tile:occupant,groundTile});
      assert.deepEqual(composed[0],bare[0],'moat or bridge surface is painted beneath occupants');
      assert(composed.length>bare.length,'occupant remains visible above its surface');
    }
  }
}
console.log('Castle architectural parity and known moat/drawbridge ground beneath occupants passed.');
