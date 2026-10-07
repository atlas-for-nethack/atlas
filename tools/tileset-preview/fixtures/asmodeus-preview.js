/* Proposed materials only. The playable atlases and renderer are unchanged. */
"use strict";
const AtlasAsmodeusStudy = (() => {
  function rectangles(atlas) {
    const pieces=new Map(),walls=atlas.lanternWalls;
    const crop=id=>[id%atlas.columns*atlas.tileWidth,Math.floor(id/atlas.columns)*atlas.tileHeight,atlas.tileWidth,atlas.tileHeight];
    function add(target,source,kind) { pieces.set(target.join(','),{target,source,kind}); }
    function frame(f,kind,source=f) {
      if(!f)return;
      add(f.source,source.source,kind);
      (f.alternates||[]).forEach((alternate,i)=>frame(alternate,kind,source.alternates[i]));
    }
    function slot(id,kind,source=kind==='floor'&&atlas.id.startsWith('soot-and-brass')
        ?atlas.regionalMaterials.gehennom.tileMap[id]:id) {
      add(crop(id),crop(source),kind);
      frame(atlas.projectedFrames.frames[id],kind,atlas.projectedFrames.frames[source]);
    }
    function entry(id,rule,kind) {
      slot(Number(id),kind);
      for(const variant of rule?.variants||[])slot(variant,kind);
    }
    // Reuse the shipped Gehennom brick colors, including matching directional
    // poses and connector alternates. Keep the palace's established geometry.
    for(let id=1273;id<=1283;id++) {
      slot(id,'wall',id+209);
      walls.tiles[id].variants.forEach((variant,i)=>slot(variant,'wall',walls.tiles[id+209].variants[i]));
    }
    for(const [id,rule]of Object.entries(walls.doors))entry(id,rule,'door');
    slot(walls.bars.isolated,'door');
    for(const rule of [walls.bars.vertical,walls.bars.horizontal,...Object.values(walls.bars.connections)])entry(walls.bars.tile,rule,'door');
    for(let id=1291;id<=1296;id++)slot(id,'floor');
    if(atlas.id.startsWith('lantern'))slot(1284,'floor');
    return [...pieces.values()];
  }
  function color(family,kind,r,g,b) {
    if(kind==='wall')return [r,g,b];
    if(family==='lantern') {
      const factors=kind==='floor'?[.88,.91,.94]:kind==='door'?[.87,.88,.90]:[.84,.87,.90];
      return [r,g,b].map((v,i)=>Math.round(v*factors[i]));
    }
    if(kind==='floor')return [r,g,b].map(v=>Math.round(v*.94));
    // Retain warm metal detail; pale neutral masonry receives a graphite cast.
    const brass=r>g*1.12&&g>b*1.10;
    return [r,g,b].map((v,i)=>Math.round(brass?v*.90:v*.90*.88+[137,146,151][i]*.12));
  }
  function ornaments(atlas) {
    const marks=new Map();
    function add(frame,x,y,pattern) {
      if(!frame)return;
      marks.set(frame.source.join(','),{x,y,pattern});
    }
    // Corner capstones supply sparse accents without repeating a symbol on
    // every straight wall. Secret walls receive no special treatment.
    for(const id of [1275,1276,1277,1278]) {
      const frame=atlas.projectedFrames.frames[id];
      add(frame,id===1275||id===1277?5:31,5,
        ['##...........##','.##.........##.','.###.......###.','..###.....###..',
         '...###...###...','....#######....','.....#####.....','......###......',
         '......###......','.......#.......']);
    }
    for(const [id,rule]of Object.entries(atlas.lanternWalls.doors)) {
      for(const slot of new Set([Number(id),...rule.variants])) {
        const frame=atlas.projectedFrames.frames[slot];
        if(!frame)continue;
        const front=rule.topology==='horizontal-door';
        add(frame,front?22:20,front?3:2,front?
          ['##.................##','.###.............###.','..###...........###..',
           '...####.......####...','.....####...####.....','.......#######.......',
           '........#####........','.........###.........','..........#..........']:
          ['##.......##','.###...###.','..#######..','....###....','.....#.....']);
      }
    }
    return marks;
  }
  function engrave(pixels,mark,family) {
    if(!mark)return;
    const {data,width,height}=pixels;
    // Carve into existing opaque pixels only. Preserve alpha and the exact
    // collision-independent silhouette, including all doorway openings.
    const original=new Uint8ClampedArray(data);
    function shade(x,y,highlight) {
      if(x<0||y<0||x>=width||y>=height)return;
      const i=(y*width+x)*4;
      if(data[i+3]!==255)return;
      const bevel=family==='lantern'?[144,151,153]:[164,135,84];
      const recess=family==='lantern'?[13,18,23]:[24,20,16];
      // A readable cut needs a lit bevel even in a dark stone face. Blend
      // against the original once so intersecting strokes cannot brighten it
      // repeatedly. These muted material colors are not emissive highlights.
      for(let c=0;c<3;c++)data[i+c]=Math.round(highlight?
        original[i+c]*.35+bevel[c]*.65:original[i+c]*.22+recess[c]*.78);
    }
    mark.pattern.forEach((row,y)=>[...row].forEach((v,x)=>{
      if(v!=='#')return;
      shade(mark.x+x,mark.y+y+1,true);
    }));
    mark.pattern.forEach((row,y)=>[...row].forEach((v,x)=>{
      if(v==='#')shade(mark.x+x,mark.y+y,false);
    }));
  }
  function compose(atlas,image) {
    if(!['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(atlas.id))throw Error('Asmodeus study requires original Atlas art.');
    const output=document.createElement('canvas');output.width=image.width;output.height=image.height;
    const ctx=output.getContext('2d');ctx.drawImage(image,0,0);
    const piece=document.createElement('canvas'),pen=piece.getContext('2d');
    const family=atlas.id.startsWith('lantern')?'lantern':'soot-and-brass';
    const marks=ornaments(atlas);
    for(const {target,source,kind}of rectangles(atlas)) {
      const [x,y,w,h]=target;piece.width=w;piece.height=h;
      // Sample original pixels once, including aliased projected rectangles.
      pen.drawImage(image,...source,0,0,w,h);
      const pixels=pen.getImageData(0,0,w,h),data=pixels.data;
      for(let i=0;i<data.length;i+=4) {
        const rgb=color(family,kind,data[i],data[i+1],data[i+2]);
        data[i]=rgb[0];data[i+1]=rgb[1];data[i+2]=rgb[2];
      }
      engrave(pixels,marks.get(target.join(',')),family);
      pen.putImageData(pixels,0,0);ctx.clearRect(x,y,w,h);ctx.drawImage(piece,x,y);
    }
    return {atlas,image:output};
  }
  function cells(original,proposed) {
    return new Map([...original].map(([key,value])=>{
      const cell={...value};
      delete cell.material;
      // The actual named level currently uses Gehennom wall glyphs without
      // a floor material tag. Keep that exact baseline in the comparison.
      const wall=id=>proposed&&id>=1482&&id<=1492?id-209:
        !proposed&&id>=1273&&id<=1283?id+209:id;
      cell.tile=wall(cell.tile);
      if(Number.isInteger(cell.groundTile))cell.groundTile=wall(cell.groundTile);
      return [key,cell];
    }));
  }
  return {rectangles,color,ornaments,engrave,compose,cells};
})();
if(typeof module!=='undefined')module.exports=AtlasAsmodeusStudy;
