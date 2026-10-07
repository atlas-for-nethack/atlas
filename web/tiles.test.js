"use strict";
const assert = require("node:assert/strict");
const tiles = require("./tiles.js");
const image = { width: 1280, height: 1856 };
const atlas = { tileWidth: 32, tileHeight: 32, columns: 40, count: 2304, groundLayers: true };
const calls = [];
const ctx = { drawImage: (...args) => calls.push(args) };
function paint(cell, options = atlas, ground = true) {
  calls.length = 0;
  tiles.paint(ctx, image, options, cell, 10, 20, 40, 40, ground);
  return calls.map(a => a[2] / 32 * 40 + a[1] / 32);
}
assert.deepEqual(paint({ tile: 32, groundTile: 1291 }), [1291, 32], "floor is painted before the dog");
assert.deepEqual(paint({ tile: 32 }), [32], "unknown ground is not invented");
assert.deepEqual(paint({ tile: 32, groundTile: null }), [32]);
assert.deepEqual(paint({ tile: 32, groundTile: -1 }), [32]);
assert.deepEqual(paint({ tile: 32, groundTile: 2304 }), [32]);
assert.deepEqual(paint({ tile: 32, groundTile: 1291 }, { ...atlas, groundLayers: false }), [32], "legacy sets remain single layer");
assert.deepEqual(paint({ tile: 32, groundTile: 1291 }, atlas, false), [32], "inspector and inventory show only the subject");
assert.deepEqual(paint({ tile: 1291, groundTile: 1291 }), [1291]);
assert.deepEqual(paint({ tile: 32, groundTile: 1314 }), [1314, 32], "a later cell replaces the previous ground without a cache");
console.log("Tile rendering checks passed.");

// A tall northern monster must survive ground and sprites from later map
// updates. Event insertion order must not determine visible depth.
const projectedImage={width:2560,height:5000};
const projectedAtlas={tileWidth:64,tileHeight:64,columns:40,count:2304,groundLayers:true,
  lanternWalls:{version:1,surfaces:[1291]},projectedFrames:{version:1,padding:[24,88,24,0],frames:{
    632:{source:[0,4400,112,134],offset:[-24,-78],depth:56},
    684:{source:[112,4400,64,85],offset:[0,-29],depth:56}
  }}};
const crowd=[{tile:632,groundTile:1291,x:3,y:0},{tile:684,groundTile:1291,x:3,y:1},{tile:1291,x:3,y:2}];
function crowdPaint(items){calls.length=0;const cells=new Map(items.map(c=>[`${c.x},${c.y}`,c]));
  assert(tiles.paintMap(ctx,projectedImage,projectedAtlas,cells,64));return calls.map(c=>c.slice(1));}
const forward=crowdPaint(crowd),backward=crowdPaint([...crowd].reverse());
assert.deepEqual(forward.slice(-2),backward.slice(-2),'foreground depth is independent of engine event order');
assert.deepEqual(forward.slice(-2).map(c=>c.slice(0,4)),[[0,4400,112,134],[112,4400,64,85]],'rear monster precedes front monster');
assert.deepEqual(forward[forward.length-2].slice(4),[168,-78,112,134],'tall art extends above its one-square footprint at the top map edge');
assert.equal(forward.length,5,'all three known floors precede the two creatures');
calls.length=0;tiles.paint(ctx,projectedImage,projectedAtlas,crowd[0],0,0,64,64,false);
assert.equal(calls.length,1);assert.equal(calls[0][3],64,'inspection portrait retains bounded canonical art');
calls.length=0;tiles.paintMap(ctx,projectedImage,projectedAtlas,new Map([['3,0',{tile:632,x:3,y:0}]]),64);
assert.equal(calls.length,1,'unknown ground is never fabricated underneath an overhanging monster');
assert.equal(tiles.paintMap(ctx,image,atlas,new Map(),64),false,'legacy atlases do not opt into projection');
console.log('Projected depth, clipping coordinates, portrait and perception checks passed.');

const faded=[];
const fadeContext={globalAlpha:1,drawImage(...args){faded.push({source:args.slice(1,5),alpha:this.globalAlpha});}};
const focusedAtlas={...projectedAtlas,projectedFrames:{...projectedAtlas.projectedFrames,frames:{
  ...projectedAtlas.projectedFrames.frames,684:{...projectedAtlas.projectedFrames.frames[684],kind:'creature'}
}}};
tiles.paintMap(fadeContext,projectedImage,focusedAtlas,new Map(crowd.map(c=>[`${c.x},${c.y}`,c])),64,64,{x:3,y:0});
assert.equal(faded.at(-1).alpha,0.35,'foreground creature fades where it covers a focused known square');
assert.equal(faded.at(-2).alpha,1,'focused subject stays opaque');
assert.equal(fadeContext.globalAlpha,1,'focus fading does not leak into later drawing');
faded.length=0;
tiles.paintMap(fadeContext,projectedImage,focusedAtlas,new Map(crowd.map(c=>[`${c.x},${c.y}`,c])),64,64,{x:70,y:19});
assert(faded.every(c=>c.alpha===1),'unseen focus position does not alter perceived creature art');
faded.length=0;
tiles.paintMap(fadeContext,projectedImage,focusedAtlas,new Map(crowd.map(c=>[`${c.x},${c.y}`,c])),64,64,null);
assert(faded.length>0 && faded.every(c=>c.alpha===1),'clearing hover restores every crowded creature to full opacity');

// Report BFB8875C: explicit engine unknown cells are present in the map,
// unlike the missing-cell case above. They must never trigger cutaways.
for(const tile of [1469,1470]) {
  const cells=new Map(crowd.map(c=>[`${c.x},${c.y}`,c]));
  cells.set('3,0',{x:3,y:0,tile,char:' '});
  faded.length=0;
  tiles.paintMap(fadeContext,projectedImage,focusedAtlas,cells,64,64,{x:3,y:0});
  assert(faded.every(c=>c.alpha===1),'explicit unexplored/nothing focus cannot fade overlapping artwork');
}

// A southern door overhangs the known square to its north, regardless of a
// tileset's name or creature-specific metadata. Its own square stays opaque.
const overhangAtlas={...projectedAtlas,projectedFrames:{version:1,frames:{
  1288:{source:[0,4200,64,83],offset:[0,-45],depth:38}
}}};
const doorwayCells=new Map([
  ['2,2',{x:2,y:2,tile:1288,groundTile:1291}],
  ['2,1',{x:2,y:1,tile:1291}],
  ['3,1',{x:3,y:1,tile:1291}]
]);
for(const [focus,expected] of [[{x:2,y:1},.35],[{x:2,y:2},1],[{x:3,y:1},1],[{x:2,y:0},1],[null,1]]){
  faded.length=0;
  tiles.paintMap(fadeContext,projectedImage,overhangAtlas,doorwayCells,64,64,focus);
  assert.equal(faded.find(c=>c.source[1]===4200).alpha,expected,'only an overlapping known square fades the door');
  assert.equal(fadeContext.globalAlpha,1,'door fading restores draw opacity');
}
overhangAtlas.projectedFrames.frames[1288]={source:[0,4200,64,64],offset:[0,0],depth:64};
faded.length=0;
tiles.paintMap(fadeContext,projectedImage,overhangAtlas,doorwayCells,64,64,{x:2,y:1});
assert(faded.every(c=>c.alpha===1),'a bounded door cannot fade for a neighboring square');

// Report 415D6035: the hill orc southwest of the hero has a transparent
// upper-right corner inside the hero's square. Only visible pixels can occlude.
const orcImage={width:2560,height:5000};
const orcAtlas={...projectedAtlas,projectedFrames:{version:1,frames:{
  150:{source:[172,4204,93,80],offset:[-14,-24],depth:56,kind:'creature',occupiedSquares:[[0,-1],[-1,0],[0,0],[1,0]]}
}}};
const orcCells=new Map([
  ['23,11',{x:23,y:11,tile:150,groundTile:1294}],
  ['24,10',{x:24,y:10,tile:1294}],
  ['24,11',{x:24,y:11,tile:1294}]
]);
for(const [focus,expected] of [[{x:24,y:10},1],[{x:24,y:11},.35],[{x:23,y:11},1]]) {
  faded.length=0;
  tiles.paintMap(fadeContext,orcImage,orcAtlas,orcCells,64,64,focus);
  assert.equal(faded.find(c=>c.source[1]===4204).alpha,expected,'transparent padding cannot trigger fading; visible overhang still does');
}
console.log('Transparent-corner fading regression passed.');

const shippedManifest=require('../assets/tiles/manifest.json');
const shippedSoot=shippedManifest.tilesets.find(t=>t.id==='soot-and-brass');
const reportedOrc=shippedSoot.projectedFrames.frames['150'];
assert(Array.isArray(reportedOrc.occupiedSquares),'shipped orc must declare visible coverage');
assert(!reportedOrc.occupiedSquares.some(([x,y])=>x===1 && y===-1),'reported orc has no visible pixels northeast of its square');
assert(reportedOrc.occupiedSquares.some(([x,y])=>x===1 && y===0),'actual club overhang remains eligible for fading');

// Report E48CBAE7: an ettin west of the hero is drawn behind the hero.
// Its arm reaches the hero's tile but cannot hide a subject painted afterward.
const lanternModern=shippedManifest.tilesets.find(t=>t.id==='lantern-modern');
const ettinFrame=lanternModern.projectedFrames.frames['356'];
const heroSlot=Object.keys(lanternModern.projectedFrames.frames).find(slot=>
  Number(slot)>500 && lanternModern.projectedFrames.frames[slot].kind==='creature');
const depthAtlas={...projectedAtlas,projectedFrames:{version:1,frames:{
  356:ettinFrame, [heroSlot]:{source:[0,4000,64,64],offset:[0,-8],depth:56,kind:'creature'}
}}};
const depthImage={width:2560,height:20000};
function ettinOpacity(focus) {
  faded.length=0;
  const cells=new Map([
    ['44,7',{x:44,y:7,tile:356,groundTile:1294}],
    ['45,7',{x:45,y:7,tile:Number(heroSlot),groundTile:1294}],
    ['44,6',{x:44,y:6,tile:1294}]
  ]);
  tiles.paintMap(fadeContext,depthImage,depthAtlas,cells,64,64,focus);
  return faded.find(c=>c.source[0]===ettinFrame.source[0] && c.source[1]===ettinFrame.source[1]).alpha;
}
assert.equal(ettinOpacity({x:45,y:7}),1,'an ettin behind the hero does not fade');
assert.equal(ettinOpacity({x:44,y:6}),.35,'hovering the floor behind its visible upper body still fades it');

const neighbors = new Map();
const wallAtlas = { ...atlas, count: 2560, lanternWalls: {
  version: 1, surfaces: [1291, 1294, 1314],
  tiles: { 1274: { topology: "horizontal", variants: Array.from({ length: 256 }, (_, n) => 2304 + n) } }
} };
image.height = 2048;
function wallPaint(ground = true, options = wallAtlas) {
  calls.length = 0;
  tiles.paint(ctx, image, options, { tile: 1274, x: 5, y: 5 },
    10, 20, 40, 40, ground, neighbors);
  assert(calls.every(a => a[5] === 10 && a[6] === 20 && a[7] === 40 && a[8] === 40),
    "decoration must stay inside its original cell destination");
  return calls.map(a => a[2] / 32 * 40 + a[1] / 32);
}
assert.deepEqual(wallPaint(), [2304], "unknown neighbors use the supplied fallback, not an invented floor");
neighbors.set("5,6", { tile: 32, groundTile: 1291 });
assert.deepEqual(wallPaint(), [2308], "engine-known floor beneath a monster affects only the wall illustration");
neighbors.set("5,6", { tile: 32 });
assert.deepEqual(wallPaint(), [2304], "replacing a remembered surface removes its influence immediately");
neighbors.set("6,4", { tile: 1314 });
assert.deepEqual(wallPaint(), [2320], "diagonal displayed water is safe surface evidence");
assert.deepEqual(wallPaint(false), [1274], "inventory and inspection use canonical art even with neighbors");
assert.deepEqual(wallPaint(true, atlas), [1274], "Classic and imported atlases ignore Lantern decorations");
neighbors.clear();
for (const [i, [dx, dy]] of [[0,-1], [1,0], [0,1], [-1,0],
  [1,-1], [1,1], [-1,1], [-1,-1]].entries()) {
  neighbors.set(`${5 + dx},${5 + dy}`, { tile: 1291 });
  assert.deepEqual(wallPaint(), [2304 + (1 << (i + 1)) - 1], "mask ordering matches artifact metadata");
}
const invalid = { ...wallAtlas, lanternWalls: { ...wallAtlas.lanternWalls,
  tiles: { 1274: { variants: [] } } } };
assert.deepEqual(wallPaint(true, invalid), [1274], "incomplete supplementary artwork falls back to canonical tile");
console.log("Raised wall appearance checks passed.");
const doorAtlas = { ...wallAtlas, lanternWalls: { ...wallAtlas.lanternWalls,
  doors: { 1287: { variants: Array.from({ length: 256 }, (_, n) => 2304 + n) } } } };
neighbors.clear();
neighbors.set("4,5", { tile: 32, groundTile: 1291 });
calls.length = 0;
tiles.paint(ctx, image, doorAtlas, {tile: 1287, x: 5, y: 5, groundTile: 1291},
  10, 20, 40, 40, true, neighbors);
assert.deepEqual(calls.map(a => a[2] / 32 * 40 + a[1] / 32), [1291, 2312],
  "side door uses the same west-surface mask as its neighboring vertical wall, over known floor");
calls.length = 0;
tiles.paint(ctx, image, doorAtlas, {tile: 1287, x: 5, y: 5},
  10, 20, 40, 40, false, neighbors);
assert.deepEqual(calls.map(a => a[2] / 32 * 40 + a[1] / 32), [1287],
  "side door menus retain canonical art");
console.log("Side door appearance checks passed.");
const clipped = { ...doorAtlas, lanternWalls: { ...doorAtlas.lanternWalls,
  doors: { 1287: { variants: Array(256).fill(2304), groundBounds: Array(256).fill([9,0,45,64]) },
           1288: { variants: Array(256).fill(2305), groundBounds: Array(256).fill([0,0,64,24]) } } } };
clipped.lanternWalls.doors[1287].groundBounds[2] = [19,0,45,64];
clipped.lanternWalls.doors[1287].groundBounds[8] = [0,0,45,64];
for (const [neighborKey, expectedX] of [["6,5",19], ["4,5",0], [null,9]]) {
  neighbors.clear();
  if (neighborKey) neighbors.set(neighborKey, {tile:1291});
  calls.length = 0;
  tiles.paint(ctx, image, clipped, {tile:1287, x:5, y:5, groundTile:1291},
    10,20,64,64,true,neighbors);
  assert.deepEqual(calls[0].slice(5), [10+expectedX,20,45,64],
    "ground stays inside the matching west/east/shared door strip");
  assert.deepEqual(calls[0].slice(1,5), [1291%40*32+expectedX/2,Math.floor(1291/40)*32,22.5,32],
    "ground is cropped in place, not stretched into the door footprint");
  assert.deepEqual(calls[1].slice(5), [10,20,64,64], "padded foreground preserves fixed cell coordinates");
}
calls.length=0;
tiles.paint(ctx,image,clipped,{tile:1288,x:5,y:5,groundTile:1291},10,20,64,64,true,neighbors);
assert.deepEqual(calls[0].slice(5), [10,20,64,24], "southern doorway ground stays within the low rim");
calls.length=0;
tiles.paint(ctx,image,clipped,{tile:1288,x:5,y:5},10,20,64,64,true,neighbors);
assert.equal(calls.length,1,"door clipping does not invent missing ground");
console.log("Door ground clipping checks passed.");
const framed = {...clipped, lanternWalls:{...clipped.lanternWalls,
  tiles:{1273:{topology:"vertical",variants:Array(256).fill(2304)}},
  doors:{1287:{...clipped.lanternWalls.doors[1287],topology:"vertical-door",
    groundBounds:Array.from({length:256},(_,m)=>[m&8 && !(m&2)?0:m&2 && !(m&8)?19:9,0,45,64])}}}};
neighbors.clear();
for (const y of [4,6]) {
 neighbors.set(`5,${y}`,{tile:1273});
 neighbors.set(`4,${y}`,{tile:1291});
}
neighbors.set("4,5",{tile:1291});neighbors.set("6,5",{tile:1291});
calls.length=0;
tiles.paint(ctx,image,framed,{tile:1287,x:5,y:5,groundTile:1291},10,20,64,64,true,neighbors);
assert.deepEqual(calls[0].slice(5),[10,20,45,64],
 "newly seen floor past a door must not shift it away from agreeing adjacent wall faces");
console.log("Door frame continuity checks passed.");
const passages = {...framed, lanternWalls:{...framed.lanternWalls,
  doors:{1285:{...framed.lanternWalls.doors[1287],open:true},
         1286:{topology:"horizontal-door",open:true,variants:Array(256).fill(2305),
           groundBounds:Array(256).fill([0,0,64,24])}}}};
function passage(tile, groundTile=1291) {
 calls.length=0;
 tiles.paint(ctx,image,passages,{tile,x:5,y:5,groundTile},10,20,64,64,true,neighbors);
 return calls[0].slice(5);
}
assert.deepEqual(passage(1285),[10,20,64,64],
 "open door connects to directly known floor beyond its fixed45px frame");
neighbors.delete("6,5");
assert.deepEqual(passage(1285),[10,20,45,64],
 "unknown far side retains its clipped footprint");
neighbors.set("6,4",{tile:1291});
assert.deepEqual(passage(1285),[10,20,45,64],
 "diagonal floor does not fill unknown space across a door");
neighbors.set("6,5",{tile:32});
assert.deepEqual(passage(1285),[10,20,45,64],
 "sensed creature without a known surface does not extend passage floor");
neighbors.set("6,5",{tile:32,groundTile:1291});
assert.deepEqual(passage(1285),[10,20,64,64],
 "remembered ground under a creature connects the open passage");
const savedBounds=JSON.stringify(passages.lanternWalls.doors[1285].groundBounds);
passage(1285);
assert.equal(JSON.stringify(passages.lanternWalls.doors[1285].groundBounds),savedBounds,
 "per-cell passage extensions do not mutate shared metadata");
neighbors.clear();neighbors.set("5,4",{tile:1291});
assert.deepEqual(passage(1286),[10,20,64,24],"unknown beyond a southern door remains clipped");
neighbors.set("5,6",{tile:1294});
assert.deepEqual(passage(1286),[10,20,64,64],"known southern corridor joins the low open doorway");
passage(1286,null);
assert.equal(calls.length,1,"a passage never supplies ground when the engine omitted it");
console.log("Known open passage continuity checks passed.");
neighbors.clear();
for(const y of [4,6]) {
 neighbors.set(`5,${y}`,{tile:1273});neighbors.set(`6,${y}`,{tile:1291});
}
neighbors.set("6,5",{tile:1291});
assert.deepEqual(passage(1285),[29,20,45,64],"western doorway keeps unknown left margin dark");
neighbors.set("4,5",{tile:1294});
assert.deepEqual(passage(1285),[10,20,64,64],"known western passage joins the fixed right-aligned frame");
console.log("Western open passage continuity checks passed.");

// Bar fixtures describe visible geometry independently of the selection code:
// three floor cells on one side of a wall opening, or adjacent freestanding bars.
const barImage = {width:1280,height:2496};
const barHorizontal = {topology:"horizontal-bars",
 variants:Array.from({length:256},(_,i)=>2304+i),
 groundBounds:Array.from({length:256},()=>[0,0,64,64])};
for(const mask of [1,17,129,145]) barHorizontal.groundBounds[mask]=[0,0,64,24];
const barVertical = {topology:"vertical-bars",
 variants:Array.from({length:256},(_,i)=>2560+i),
 groundBounds:Array.from({length:256},()=>[9,0,45,64])};
for(const mask of [2,18,34,50]) barVertical.groundBounds[mask]=[19,0,45,64];
for(const mask of [8,72,136,200]) barVertical.groundBounds[mask]=[0,0,45,64];
const barsAtlas = {...atlas,count:3100,lanternWalls:{version:1,surfaces:[1291,1294],
 tiles:{1273:{topology:"vertical",connections:["N","S"]},
        1274:{topology:"horizontal",connections:["E","W"]},
        1275:{topology:"corner",connections:["N","E"]}},
 doors:{1287:{topology:"vertical-door"},1288:{topology:"horizontal-door"}},
 bars:{tile:1289,horizontal:barHorizontal,vertical:barVertical,
       connections:{3:{topology:"bars-junction",variants:Array(256).fill(2816)}}}}};
function barPaint(cell={tile:1289,x:5,y:5,groundTile:1291},options=barsAtlas,ground=true) {
 calls.length=0;
 tiles.paint(ctx,barImage,options,cell,10,20,64,64,ground,neighbors);
 const foreground=calls.at(-1);
 return foreground[2]/32*40+foreground[1]/32;
}
for(const [name,wallPositions,floorPositions,bank,bounds] of [
 ["north",[[4,5],[6,5]],[[4,6],[5,6],[6,6]],2304,[10,20,64,64]],
 ["south",[[4,5],[6,5]],[[4,4],[5,4],[6,4]],2304,[10,20,64,24]],
 ["west",[[5,4],[5,6]],[[6,4],[6,5],[6,6]],2560,[29,20,45,64]],
 ["east",[[5,4],[5,6]],[[4,4],[4,5],[4,6]],2560,[10,20,45,64]],
]) {
 neighbors.clear();
 const wallTile=["north","south"].includes(name)?1274:1273;
 for(const position of wallPositions) neighbors.set(position.join(","),{tile:wallTile});
 for(const position of floorPositions) neighbors.set(position.join(","),{tile:1291});
 const selected=barPaint();
 assert(selected>=bank && selected<bank+256,`${name} edge connects to visible wall ports`);
 assert.deepEqual(calls[0].slice(5),bounds,`${name} bars keep supplied ground inside their room edge`);
 assert.deepEqual(calls[1].slice(5),[10,20,64,64],"bar foreground stays in its fixed grid cell");
}
neighbors.clear();neighbors.set("4,5",{tile:1289});
assert.equal(barPaint(),2304,"freestanding horizontal run joins the perceived bar");
neighbors.clear();neighbors.set("5,4",{tile:1289});
assert.equal(barPaint(),2560,"freestanding vertical run joins the perceived bar");
neighbors.set("4,5",{tile:1291});neighbors.set("6,5",{tile:1291});
barPaint();
assert.deepEqual(calls[0].slice(5),[10,20,64,64],"floor on both sides continues beneath freestanding vertical bars");
neighbors.delete("4,5");neighbors.delete("6,5");
neighbors.set("6,5",{tile:1289});
assert.equal(barPaint(),2816,"a supplied corner variant joins two visible bar directions");
neighbors.set("4,5",{tile:1289});neighbors.set("5,6",{tile:1289});
assert.equal(barPaint(),1289,"unavailable conflicting junction artwork retains the canonical bar");
neighbors.clear();
assert.equal(barPaint(),1289,"unknown surroundings do not invent a bar orientation");
neighbors.set("5,4",{tile:1274});
assert.equal(barPaint(),1289,"a neighboring wall without a port facing the bar cannot connect");
neighbors.set("6,4",{tile:1291});
assert.equal(barPaint(),1289,"diagonal floor alone cannot establish bar orientation");
neighbors.clear();neighbors.set("5,4",{tile:1287});
assert.equal(barPaint(),2560,"an adjoining visible vertical door can join a vertical bar run");
neighbors.clear();neighbors.set("4,5",{tile:1288});
assert.equal(barPaint(),2304,"an adjoining visible horizontal door can join a horizontal bar run");
neighbors.clear();neighbors.set("5,6",{tile:32,groundTile:1291});
assert.equal(barPaint(),2308,"perceived floor beneath a creature can establish a room rim");
neighbors.set("5,6",{tile:32});
assert.equal(barPaint(),1289,"replacing the neighbor removes old ground evidence immediately");
neighbors.clear();
for(const key of ["5,4","6,5","5,6","4,5"]) neighbors.set(key,{tile:1291});
assert.equal(barPaint(),1289,"floor on every side leaves a single freestanding bar canonical");
neighbors.clear();neighbors.set("4,5",{tile:1289});
barPaint({tile:1289,x:5,y:5});
assert.equal(calls.length,1,"bar selection never supplies ground omitted by the engine");
assert.equal(barPaint(undefined,barsAtlas,false),1289,"bar menus ignore map adjacency");
assert.equal(calls.length,1,"bar menu rendering does not add floor");
assert.equal(barPaint(undefined,atlas),1289,"an imported atlas without Lantern metadata stays canonical");
assert.equal(barPaint(undefined,{...atlas,groundLayers:false}),1289,"legacy atlas remains single layer");
assert.equal(calls.length,1);
const junctionAtlas={...barsAtlas,lanternWalls:{...barsAtlas.lanternWalls,
 tiles:{...barsAtlas.lanternWalls.tiles,1274:{topology:"horizontal",connections:["W"]}},
 bars:{...barsAtlas.lanternWalls.bars,connections:{3:{topology:"bars-junction",
 variants:Array.from({length:256},(_,mask)=>mask===1?2817:2816),
 groundBounds:Array.from({length:256},()=>[0,0,64,64])}}}}};
neighbors.clear();
neighbors.set("5,4",{tile:1289});neighbors.set("6,5",{tile:1289});
neighbors.set("4,5",{tile:1274});neighbors.set("4,4",{tile:1291});
assert.equal(barPaint(undefined,junctionAtlas),2816,
 "bar junctions keep their own perceived neighborhood instead of inheriting a straight wall frame");
console.log("Iron-bar perception, room-edge clipping and isolation checks passed.");

// A level material changes artwork only. Canonical appearances still decide
// topology and floor passes, and every incoming cell replaces its material.
const regionalAtlas = {...wallAtlas, regionalMaterials:{mines:{
  tileMap:{1291:2200,1294:2201,1471:2202,1469:2200,1470:2200},
  wallTiles:{1471:{topology:'vertical',variants:Array.from({length:256},(_,mask)=>2304+mask)}}
}}};
assert.deepEqual(paint({tile:1291,groundTile:1291,material:'mines'},regionalAtlas),[2200],
  'regional floor is drawn once while retaining canonical floor identity');
assert.deepEqual(paint({tile:32,groundTile:1291,material:'mines'},regionalAtlas),[2200,32],
  'engine-known regional ground is drawn under the unchanged creature');
assert.deepEqual(paint({tile:32,material:'mines'},regionalAtlas),[32],
  'material alone does not invent ground beneath a sensed creature');
assert.deepEqual(paint({tile:1291,material:'mines'},regionalAtlas,false),[1291],
  'inspection icons keep canonical artwork');
assert.deepEqual(paint({tile:1291},regionalAtlas),[1291],
  'omitting material immediately restores the ordinary floor');
assert.deepEqual(paint({tile:1291,material:'unrecognized'},regionalAtlas),[1291]);
assert.deepEqual(paint({tile:1291,material:'mines'},atlas),[1291],
  'imported and older atlases without regional metadata remain unchanged');
assert.deepEqual(paint({tile:1291,material:'mines'},
  {...regionalAtlas,regionalMaterials:{mines:{tileMap:{1291:999999}}}}),[1291],
  'missing supplemental pixels fall back to canonical artwork');
assert.deepEqual(paint({tile:1469,material:'mines'},regionalAtlas),[1469],
  'unexplored appearances cannot acquire regional decoration');
assert.deepEqual(paint({tile:1470,material:'mines'},regionalAtlas),[1470]);
const regionalCells=new Map([
  ['5,5',{tile:1471,x:5,y:5,material:'mines'}],
  ['6,5',{tile:32,groundTile:1291,x:6,y:5,material:'mines'}]
]);
function regionalWall() {
  calls.length=0;
  tiles.paint(ctx,image,regionalAtlas,regionalCells.get('5,5'),10,20,40,40,true,regionalCells);
  return calls.map(a=>a[2]/32*40+a[1]/32);
}
assert.deepEqual(regionalWall(),[2306],
  'regional wall variants use original east-neighbor ground, not remapped floor IDs');
regionalCells.set('6,5',{tile:32,x:6,y:5,material:'mines'});
assert.deepEqual(regionalWall(),[2304],'replaced unknown ground removes its topology influence');
regionalCells.set('5,5',{tile:1471,x:5,y:5});
assert.deepEqual(regionalWall(),[1471],'replacing material removes regional wall art without a cache');
regionalCells.clear();regionalCells.set('5,5',{tile:1471,x:5,y:5});
assert.deepEqual(regionalWall(),[1471],'map clear does not retain regional artwork');
const projectedRegional={...projectedAtlas,count:2560,regionalMaterials:regionalAtlas.regionalMaterials,
  lanternWalls:{...projectedAtlas.lanternWalls,tiles:{}},
  projectedFrames:{version:1,frames:{
    2202:{source:[256,4300,64,88],offset:[0,-24],depth:56},
    2308:{source:[320,4300,64,96],offset:[0,-32],depth:56}
  }}};
calls.length=0;
tiles.paintMap(ctx,projectedImage,projectedRegional,new Map([
  ['5,5',{tile:1471,x:5,y:5,material:'mines'}],
  ['5,6',{tile:1291,x:5,y:6,material:'mines'}]
]),64);
assert.equal(calls.length,2);
assert.deepEqual(calls[1].slice(1,5),[320,4300,64,96],
  'regional topology variant selects its own supplemental projected frame');
// Without regional wall variants, the remapped canonical wall has its own frame.
const fallbackRegional={...projectedRegional,regionalMaterials:{mines:{tileMap:{1471:2202,1291:2200}}}};
calls.length=0;
tiles.paintMap(ctx,projectedImage,fallbackRegional,new Map([
  ['5,5',{tile:1471,x:5,y:5,material:'mines'}],
  ['5,6',{tile:1291,x:5,y:6,material:'mines'}]
]),64);
assert.equal(calls.length,2);
assert.deepEqual(calls[0].slice(1,5),[0,3520,64,64],
  'canonical floor identity keeps regional floor in the ground pass');
assert.deepEqual(calls[1].slice(1,5),[256,4300,64,88],
  'regional fallback resolves its supplemental projected frame');
console.log('Regional material selection, topology, layering and replacement checks passed.');

// Vlad preserves door/bar geometry while shading the selected directional art.
const vladVariants={...barsAtlas,regionalMaterials:{vlad:{tileMap:{1291:2200,2304:2201,2560:2202,2202:2203}}}};
neighbors.clear();neighbors.set('5,4',{tile:1289});neighbors.set('5,6',{tile:1289});
assert.equal(barPaint({tile:1289,x:5,y:5,material:'vlad'},vladVariants),2202,
 'regional material applies to the selected vertical bar, without recursive remapping');
assert.equal(barPaint({tile:1289,x:5,y:5},vladVariants),2560,
 'leaving the tower restores ordinary directional bars');
const vladDoor={...passages,regionalMaterials:{vlad:{tileMap:{2304:2201,2305:2202,1291:2200}}}};
calls.length=0;
tiles.paint(ctx,image,vladDoor,{tile:1286,x:5,y:5,groundTile:1291,material:'vlad'},10,20,64,64,true,neighbors);
assert.deepEqual(calls.map(a=>a[2]/32*40+a[1]/32),[2200,2202],
 'directional door and its engine-known floor both receive the tower treatment');
console.log('Tower directional material checks passed.');

assert.equal(barPaint({tile:1289,x:5,y:5,material:'vlad'},
 {...barsAtlas,regionalMaterials:{vlad:{tileMap:{2560:999999}}}}),2560,
 'invalid regional directional art falls back to the ordinary selected pose');
