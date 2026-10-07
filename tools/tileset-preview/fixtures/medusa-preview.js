/* Review-only island weathering over shipped original Atlas architecture. */
"use strict";
const AtlasMedusaStudy = (() => {
  const provenance = Object.freeze({
    status: 'review-only',
    source: 'Shipped Lantern and Soot & Brass original wall and gate sprites',
    author: 'NetHack Atlas project',
    license: 'Reuse under the original artwork CC BY 4.0 license',
    method: 'Neutral limestone midtones, preserved dark joints, deterministic fine and broad weather mottling; subdued existing wood and metal accents',
    geometry: 'Original alpha, projection, directional variants and opening geometry retained',
    unchanged: 'Floors, water, trees, bars, objects, statues and creatures'
  });
  function recipe(atlas) {
    if (!['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(atlas.id))
      throw Error('Medusa material study requires an original Atlas tileset.');
    return {family: atlas.id.startsWith('lantern') ? 'lantern' : 'soot-and-brass',
      stoneLift: 24, desaturation: .82, weather: 8};
  }
  function slotKinds(atlas) {
    const slots = new Map();
    function add(id, rule, kind) {
      slots.set(Number(id), kind);
      for (const variant of rule?.variants || []) slots.set(variant, kind);
    }
    for (let id=1273; id<=1283; id++) add(id, atlas.lanternWalls.tiles[id], 'wall');
    for (const [id, rule] of Object.entries(atlas.lanternWalls.doors)) add(id, rule, 'gate');
    return slots;
  }
  function architectureSlots(atlas) { return new Set(slotKinds(atlas).keys()); }
  function rectangles(atlas) {
    recipe(atlas);
    const rectangles = new Map();
    const add = (source, kind) => rectangles.set(source.join(','), [...source, kind]);
    function frame(f, kind) {
      if (!f) return;
      add(f.source, kind);
      for (const alternate of f.alternates || []) frame(alternate, kind);
    }
    for (const [slot, kind] of slotKinds(atlas)) {
      add([slot%atlas.columns*atlas.tileWidth, Math.floor(slot/atlas.columns)*atlas.tileHeight,
        atlas.tileWidth, atlas.tileHeight], kind);
      frame(atlas.projectedFrames.frames[slot], kind);
    }
    return [...rectangles.values()];
  }
  function noise(x,y) {
    let h = Math.imul(x+211, 374761393) ^ Math.imul(y+89, 668265263);
    h = Math.imul(h ^ h>>>13, 1274126177);
    return ((h ^ h>>>16)>>>0)/4294967295*2-1;
  }
  function color(r,g,b,x,y,kind,style) {
    const gray = .2126*r+.7152*g+.0722*b;
    const warm = r>g*1.1 && g>b*1.14;
    let rgb;
    if (warm) {
      // Existing warm wood/brass receives patina without recoloring iron.
      const fade = kind==='gate' ? .20 : .34;
      rgb = [r,g,b].map(v => (v*(1-fade)+gray*fade)*.87);
      if (style.family==='soot-and-brass') {rgb[0]*=.96; rgb[1]*=1.01;}
    } else {
      const t = Math.max(0,Math.min(1,(gray-30)/65));
      const stone = t*t*(3-2*t);
      const wear = noise(Math.floor(x/4),Math.floor(y/4))*.65+noise(x,y)*.35;
      // Leave the darkest seams deep; lift stone less than clean Sokoban.
      const lift = kind==='wall' ? style.stoneLift*stone : 12*stone;
      const mottling = wear*style.weather*stone;
      rgb = [r,g,b].map(v => v*(1-style.desaturation)+gray*style.desaturation+lift+mottling);
      rgb[0] += stone*2; rgb[2] -= stone*2;
    }
    return rgb.map(v => Math.max(0,Math.min(255,Math.round(v))));
  }
  function transformPixels(data,width,kind,style) {
    for (let p=0; p<data.length; p+=4) {
      if (!data[p+3]) continue;
      const pixel=p/4;
      const rgb=style.treatment==='asmodeus-light'
        ?palaceColor(style.family,kind,data[p],data[p+1],data[p+2])
        :color(data[p],data[p+1],data[p+2],pixel%width,Math.floor(pixel/width),kind,style);
      data[p]=rgb[0]; data[p+1]=rgb[1]; data[p+2]=rgb[2];
    }
    return data;
  }
  // Exact pre-Gehennom Asmodeus palette from commit 5d9f7bb. Reuse only
  // masonry/gate finish; no infernal carvings, floor changes or new geometry.
  function palaceColor(family,kind,r,g,b) {
    if(family==='lantern') {
      const factors=kind==='gate'?[.87,.88,.90]:[.84,.87,.90];
      return [r,g,b].map((v,i)=>Math.round(v*factors[i]));
    }
    const brass=r>g*1.12&&g>b*1.10;
    return [r,g,b].map((v,i)=>Math.round(brass?v*.90:v*.90*.88+[137,146,151][i]*.12));
  }
  function compose(atlas,image,treatment='weathered') {
    if(!['weathered','asmodeus-light'].includes(treatment))throw Error('Unknown Medusa study treatment.');
    const style={...recipe(atlas),treatment};
    const output=document.createElement('canvas'); output.width=image.width; output.height=image.height;
    const ctx=output.getContext('2d'); ctx.drawImage(image,0,0);
    const piece=document.createElement('canvas'), pen=piece.getContext('2d');
    for (const [x,y,w,h,kind] of rectangles(atlas)) {
      piece.width=w; piece.height=h;
      // Always sample the original so canonical/projected aliases never compound.
      pen.drawImage(image,x,y,w,h,0,0,w,h);
      const pixels=pen.getImageData(0,0,w,h);
      transformPixels(pixels.data,w,kind,style);
      pen.putImageData(pixels,0,0);
      ctx.clearRect(x,y,w,h); ctx.drawImage(piece,x,y);
    }
    return {atlas,image:output};
  }
  function reuseSokoban(atlas,image) {
    recipe(atlas);
    const wallTiles={},tileMap={};
    for(let offset=0;offset<11;offset++) {
      const source=1504+offset, target=1273+offset;
      const rule=atlas.lanternWalls.tiles[source];
      if(!rule)throw Error('Shipped Sokoban wall rule missing.');
      wallTiles[target]=rule; tileMap[target]=source;
    }
    // No pixel edits or new artwork. The existing renderer selects the native
    // Sokoban directional rule while engine cells retain canonical appearances.
    const material={wallTiles,tileMap};
    return {image,atlas:{...atlas,regionalMaterials:{...atlas.regionalMaterials,
      'medusa-sokoban-review':material}}};
  }
  function cells(original,treatment,material='medusa-sokoban-review') {
    return new Map([...original].map(([key,cell]) => {
      const copy={...cell}; delete copy.material;
      if(treatment==='sokoban'&&copy.tile!==1469&&copy.tile!==1470)
        copy.material=material;
      return [key,copy];
    }));
  }
  return {compose,reuseSokoban,cells,recipe,provenance,color,palaceColor,transformPixels,architectureSlots,rectangles};
})();
if (typeof module!=='undefined') module.exports=AtlasMedusaStudy;
