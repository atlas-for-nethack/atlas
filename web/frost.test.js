"use strict";
const assert = require("node:assert/strict");

// This mock checks which artwork is drawn and preserves geometry. It does not
// reproduce the frost pattern or pretend to verify raster appearance.
class Canvas {
  constructor(width, height) {
    this.width = width; this.height = height; this.draws = []; this.chips = [];
    this.context = {
      globalCompositeOperation: "source-over",
      drawImage: (...args) => this.draws.push(args),
      getImageData: () => { throw Error('Native file-origin canvas readback is forbidden'); },
      fillRect: (...args) => this.chips.push({args, operation: this.context.globalCompositeOperation})
    };
  }
  getContext() { return this.context; }
}
global.OffscreenCanvas = Canvas;
const tiles = require("./tiles.js");
const image = {width: 2560, height: 4000};
const frames = {};
for (let id=1500; id<1756; id++) {
  frames[id] = {source: [(id%40)*64, Math.floor(id/40)*64, 64, 80],
                offset: [-4,-16], depth: 64, kind: "wall"};
}
const wall = {x:5, y:5, tile:1274};
const atlas = {
  tileWidth:64, tileHeight:64, columns:40, count:2304, groundLayers:true,
  frostWalls:{version:1},
  lanternWalls:{version:1, surfaces:[1291,1314,1315], tiles:{
    1274:{topology:"horizontal", variants:Array.from({length:256},(_,n)=>1500+n)},
    1275:{topology:"top-left-corner", variants:Array.from({length:256},(_,n)=>1500+n)}
  }},
  projectedFrames:{version:1, frames}
};
const ordinary = {...atlas, frostWalls:undefined};

function paint(neighbors, options=atlas, ground=true, subject=wall) {
  const calls=[];
  assert(tiles.paint({drawImage:(...args)=>calls.push(args)}, image, options, subject,
                     100,200,64,64,ground,neighbors));
  return calls;
}
function neighbor(tile, groundTile) {
  return new Map([["5,6", {x:5,y:6,tile,...(groundTile === undefined ? {} : {groundTile})}]]);
}
function assertFrost(neighbors, subject=wall) {
  const actual=paint(neighbors,atlas,true,subject).at(-1);
  const base=paint(neighbors,ordinary,true,subject).at(-1);
  assert(actual[0] instanceof Canvas, "adjacent perceived ice selects a frosted canvas");
  assert.deepEqual(actual[0].draws[0], [image,...base.slice(1,5),0,0,...base.slice(3,5)],
                   "frost starts from exactly the selected architectural crop");
  assert.deepEqual(actual.slice(5),base.slice(5),"frost preserves architectural offset and size");
  assert(actual[0].chips.length>0,"frost adds cosmetic pixels");
  assert(actual[0].chips.every(c=>c.operation==="source-atop"),
         "cosmetic pixels are constrained by existing artwork alpha");
  return actual[0];
}
function assertOrdinary(neighbors, options=atlas, subject=wall) {
  const actual=paint(neighbors,options,true,subject);
  const base=paint(neighbors,{...options,frostWalls:undefined},true,subject);
  assert.deepEqual(actual,base,"non-ice evidence retains ordinary artwork");
}

const map=neighbor(1315);
assertFrost(map);
for(const cell of [{tile:1314},{tile:1291},{tile:1469,groundTile:1315},
                   {tile:1470,groundTile:1315},{tile:32}]) {
  map.set("5,6",{x:5,y:6,...cell});
  assertOrdinary(map);
}
map.delete("5,6"); assertOrdinary(map);
map.clear(); assertOrdinary(map);
assertFrost(neighbor(32,1315));
// The cap follows the prepared source outline rather than a runtime readback
// or an assumed flat bounding-box edge.
const contourImage={...image};
const contourCalls=[];
const source=frames[1504].source;
const contourAtlas={...atlas,frostWalls:{version:1,sources:{[source.join(',')]:0},shapes:[{
  top:Array(64).fill(9),left:Array(80).fill(4),right:Array(80).fill(59)
}]}};
tiles.paint({drawImage:(...args)=>contourCalls.push(args)},contourImage,contourAtlas,wall,
            100,200,64,64,true,neighbor(1315));
const outlined=contourCalls.at(-1)[0];
assert(outlined instanceof Canvas);
assert(outlined.chips.every(c=>c.args[1]>=9),'prepared cap outline keeps frost below transparent upper padding');
assert(outlined.chips.some(c=>c.args[1]===9),'frost reaches the supplied cap edge');
assertOrdinary(neighbor(1323)); // A gas/cloud appearance is not frozen ground.
assertOrdinary(neighbor(1315),ordinary);
assert.deepEqual(paint(neighbor(1315),atlas,false),paint(neighbor(1315),ordinary,false),
                 "inventory and inspection remain canonical without ground rendering");

const diagonal = new Map([["6,4",{x:6,y:4,tile:1315}]]);
assertOrdinary(diagonal);
assertFrost(diagonal,{...wall,tile:1275});
const shared = neighbor(1315);
shared.set("5,4",{x:5,y:4,tile:1291});
assertFrost(shared);

function mapPaint(cells, options=atlas) {
  const calls=[];
  assert(tiles.paintMap({drawImage:(...args)=>calls.push(args)}, image, options,cells,64));
  return calls;
}
const cells = neighbor(1315); cells.set("5,5",wall);
assert(mapPaint(cells).some(c=>c[0] instanceof Canvas),"map renderer uses frost for the known wall");
cells.set("5,6",{x:5,y:6,tile:1314});
assert(mapPaint(cells).every(c=>c[0]===image),"engine water replacement removes frost in map renderer");
cells.clear();
assert.deepEqual(mapPaint(cells),[],"clearing the engine map leaves no cached map decorations");
cells.set("5,5",wall);
assert.deepEqual(mapPaint(cells),mapPaint(cells,ordinary),"redrawing after clear cannot retain prior ice evidence");

const fs=require('node:fs'), path=require('node:path');
const manifest=require("../assets/tiles/manifest.json");
function imageBounds(entry) {
  const png=fs.readFileSync(path.join(__dirname,'../assets/tiles',entry.file));
  assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(png.subarray(12,16).toString(),'IHDR');
  return [png.readUInt32BE(16),png.readUInt32BE(20)];
}
function frostContour(entry, pose, seen, bounds) {
  const [x,y,w,h]=pose.source;
  assert(x>=0 && y>=0 && w>0 && h>0 && x+w<=bounds[0] && y+h<=bounds[1],
         entry.id+': source rectangle remains inside its PNG');
  const key=pose.source.join(',');
  const index=entry.frostWalls.sources[key];
  if(index===undefined)return undefined;
  seen.add(key);
  assert(Number.isInteger(index) && index>=0 && index<entry.frostWalls.shapes.length);
  const contour=entry.frostWalls.shapes[index];
  assert.equal(contour.top.length,w);assert.equal(contour.left.length,h);assert.equal(contour.right.length,h);
  assert(contour.top.every(v=>Number.isInteger(v) && v>=0 && v<=h));
  assert(contour.left.every(v=>Number.isInteger(v) && v>=0 && v<=w));
  assert(contour.right.every(v=>Number.isInteger(v) && v>=-1 && v<w));
  return contour;
}
function compareFrostFrames(classic, first, modern, second, seen, bounds) {
  for(const field of ['offset','depth','kind','occupiedSquares'])
    assert.deepEqual(first[field],second[field],field+': projected geometry matches');
  assert.deepEqual(first.source.slice(2),second.source.slice(2),'matching frame crop dimensions');
  assert.deepEqual(frostContour(classic,first,seen[0],bounds[0]),
                   frostContour(modern,second,seen[1],bounds[1]),
                   'matching frames retain identical prepared alpha contours');
  const aa=first.alternates||[],bb=second.alternates||[];
  assert.equal(aa.length,bb.length,'matching alternate count');
  aa.forEach((pose,index)=>compareFrostFrames(classic,pose,modern,bb[index],seen,bounds));
}
for(const [classicId,modernId] of [["lantern","lantern-modern"],["soot-and-brass-classic","soot-and-brass"]]) {
  const classic=manifest.tilesets.find(t=>t.id===classicId);
  const modern=manifest.tilesets.find(t=>t.id===modernId);
  assert.equal(classic.frostWalls?.version,1,classicId+" opts in explicitly");
  assert.equal(modern.frostWalls?.version,1,modernId+" opts in explicitly");
  const seen=[new Set(),new Set()],bounds=[imageBounds(classic),imageBounds(modern)];
  for(const [slot,frame] of Object.entries(classic.projectedFrames.frames)) {
    const matching=modern.projectedFrames.frames[slot];
    assert(matching,'Modern retains every Classic architectural frame');
    compareFrostFrames(classic,frame,modern,matching,seen,bounds);
  }
  assert.deepEqual([...seen[0]].sort(),Object.keys(classic.frostWalls.sources).sort(),
                   'every Classic frost lookup resolves through an architectural pose');
  assert.deepEqual([...seen[1]].sort(),Object.keys(modern.frostWalls.sources).sort(),
                   'every Modern frost lookup resolves through its matching architectural pose');
}
for(const thirdParty of manifest.tilesets.filter(t=>!['lantern','lantern-modern','soot-and-brass-classic','soot-and-brass'].includes(t.id))) {
  assert.equal(thirdParty.frostWalls,undefined,"other artwork receives no original-family frost policy");
}
console.log("Frost checks passed: perceived ice, replacements, clearing, occupants, corners, geometry, opt-in and edition parity.");
