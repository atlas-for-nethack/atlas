"use strict";
const assert=require('node:assert/strict');
const tiles=require('./tiles.js');
const manifest=require('../assets/tiles/manifest.json');
const original=manifest.tilesets.filter(t=>['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(t.id));
const image={width:2560,height:30000};
function render(atlas,cells,environment={waterPlane:true},width=64,height=64) {
  const ops=[],stack=[];
  const ctx={globalAlpha:1,
    save(){stack.push(this.globalAlpha);ops.push(['save']);},
    restore(){this.globalAlpha=stack.pop();ops.push(['restore']);},
    drawImage(...args){ops.push(['image',this.globalAlpha,...args.slice(1)]);},
    createLinearGradient(...args){ops.push(['gradient',...args]);return {addColorStop(){}};}
  };
  ctx.stroke=(...args)=>ops.push(['stroke',ctx.strokeStyle,...args]);
  for(const name of ['beginPath','rect','clip','fillRect','strokeRect','moveTo','lineTo','quadraticCurveTo'])
    ctx[name]=(...args)=>ops.push([name,...args]);
  tiles.paintMap(ctx,image,atlas,cells,width,height,null,environment);
  assert.equal(stack.length,0,'all optical clipping restores the canvas state');
  return ops;
}
const cells=new Map([
  ['2,2',{x:2,y:2,tile:1322,groundTile:1322}],
  ['3,2',{x:3,y:2,tile:32,groundTile:1322}],
  ['2,1',{x:2,y:1,tile:1324,groundTile:1324}],
  ['1,2',{x:1,y:2,tile:1324,groundTile:1324}],
  ['2,3',{x:2,y:3,tile:1324}],
  ['3,1',{x:3,y:1,tile:1324}],
]);
const optics=ops=>ops.filter(o=>o[0]!=='image');
const reference=render(original[0],cells);
assert(reference.some(o=>o[0]==='quadraticCurveTo'),'the visible AIR clip has a curved contour');
assert(reference.some(o=>o[0]==='gradient'),'the cap spans a connected visible pocket');
const lastClip=reference.findLastIndex(o=>o[0]==='restore');
const creature=reference.findIndex(o=>o[0]==='image' && o[3]===0 && o[2]===32*64);
// Use the actual canonical dog source: x=32*64, y=0.
assert(creature>lastClip,'optics paint before the occupant, which remains fully opaque');
for(const atlas of original) {
  assert.deepEqual(optics(render(atlas,cells)),optics(reference),'all original editions share the identical environment treatment');
  assert(render(atlas,cells).filter(o=>o[0]==='image').every(o=>o[1]===1),'the cap does not fade sprites');
  assert.equal(optics(render(atlas,cells,{waterPlane:false})).length,0,'Air and ordinary levels stay unchanged');
  assert.equal(optics(render({...atlas,waterPockets:undefined},cells)).length,0,'community sets without explicit capability stay unchanged');
}
const unseen=new Map([...cells].map(([key,c])=>[key,{...c,groundTile:undefined}]));
assert.equal(optics(render(original[0],unseen)).length,0,'blind or engulfed support-free views gain no cap or boundary');
const uncertain=new Map([...cells].map(([key,c])=>[key,c.groundTile===1324?{...c,groundTile:undefined}:c]));
assert.deepEqual(optics(render(original[0],uncertain)),optics(reference),'neighboring WATER support cannot influence a contour of known AIR');
for(const tile of [1469,1470,32,1322,1324]) {
  const neighbors=new Map([...uncertain].map(([key,c])=>[key,c.groundTile===1322?c:{...c,tile}]));
  assert.deepEqual(optics(render(original[0],neighbors)),optics(reference),'unknown or sensed appearances outside the cap cannot influence it');
}
for(const unknown of [1469,1470,1323,1390]) {
  const obscured=new Map([['2,2',{x:2,y:2,tile:unknown,groundTile:1322}]]);
  assert.equal(optics(render(original[0],obscured)).length,0,'unknown or obscuring gas foreground cannot supply visible optical terrain');
}
const drift=new Map(cells);drift.set('2,2',{x:2,y:2,tile:1324,groundTile:1324});
const moved=render(original[0],drift);
assert(!moved.some(o=>o[0]==='rect' && o[1]===128 && o[2]===128),'old AIR square is absent from the next cap clip');
assert.notDeepEqual(optics(moved),optics(reference),'rim and reflection update when an AIR square disappears');
const rectangular=render(original[0],cells,{waterPlane:true},80,48);
assert(rectangular.some(o=>o[0]==='rect' && o[1]===160 && o[2]===96 && o[3]===80 && o[4]===48),'rectangular maps retain logical tile bounds');
console.log('Water cap: perception, moving boundaries, occupant order, edition parity and fallback passed.');
