"use strict";
// Shared by the game and the composed artwork review. The engine supplies ground;
// this renderer neither remembers nor infers map features.
const AtlasTiles = (() => {
  const frostCache = new WeakMap();
  // Cosmetic pixels only: retain the exact architectural source and alpha.
  // Cache artwork, never a cell's remembered terrain or neighbor state.
  function frostedWall(image, source, frost, atlas) {
    if (!frost) return null;
    const key = `${source.join(',')}:${frost.sides}:${frost.variant}`;
    let cache = frostCache.get(image);
    if (!cache) frostCache.set(image, cache = new Map());
    if (cache.has(key)) return cache.get(key);
    const [sx,sy,w,h] = source;
    const canvas = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(w,h)
      : typeof document !== 'undefined' ? document.createElement('canvas') : null;
    if (!canvas) return null;
    canvas.width=w; canvas.height=h;
    const ctx=canvas.getContext('2d');
    ctx.drawImage(image,sx,sy,w,h,0,0,w,h);
    // Outlines come from source alpha analysis during asset preparation.
    // No file-origin canvas readback, hidden terrain query or live image scan.
    const shape=atlas.frostWalls.shapes?.[atlas.frostWalls.sources?.[source.join(',')]];
    ctx.globalCompositeOperation='source-atop';
    function chip(x,y,width,height,bright=true) {
      ctx.fillStyle=bright ? '#d6edf0' : '#7198ad';
      ctx.fillRect(x,y,width,height);
    }
    // Broken crystalline crown, not a white outline or a new wall silhouette.
    for(let x=0;x<w;x++) {
      const top=shape?.top[x] ?? 0;
      if(top===h)continue;
      const n=(x+frost.variant*7)%23;
      if(n<18) {
        chip(x,top,1,n<6?5:3,false);
        chip(x,top,1,n<5?3:2,n<14);
      }
      if(n===7 || n===8) {
        chip(x,top+3,1,8,false); chip(x,top+3,1,6);
      }
    }
    // Small patches along receding caps and occasional frozen mortar joints.
    // Bronze faces and most masonry remain exposed.
    for(let y=9;y<h;y++) {
      const n=(y+frost.variant*5)%19;
      if(n>3)continue;
      const left=shape?.left[y] ?? 0,right=shape?.right[y] ?? w-1;
      if(left>right)continue;
      if(frost.sides & 8)chip(left,y,4,1,n<2);
      if(frost.sides & 2)chip(right-3,y,4,1,n<2);
      if(n===0 && right-left>40) {
        const x=left+12+frost.variant*5;
        chip(x,y,8,1,false); chip(x+2,y,4,1);
      }
    }
    ctx.globalCompositeOperation='source-over';
    if(cache.size>=512)cache.clear();
    cache.set(key,canvas);
    return canvas;
  }
  function tileSource(image, atlas, id) {
    if(!Number.isInteger(id) || id<0 || (Number.isInteger(atlas.count) && id>=atlas.count))return null;
    const tw=atlas.tileWidth || atlas.tileSize || 32,th=atlas.tileHeight || atlas.tileSize || tw;
    const columns=atlas.columns || Math.floor(image.width/tw),sx=id%columns*tw,sy=Math.floor(id/columns)*th;
    return sx+tw<=image.width && sy+th<=image.height ? [sx,sy,tw,th] : null;
  }
  function regionalMaterial(atlas, cell) {
    // Unknown/nothing appearances are never an invitation to decorate a region.
    if (!cell || cell.tile === 1469 || cell.tile === 1470) return null;
    return atlas.regionalMaterials?.[cell.material] || null;
  }
  function materialTile(image, atlas, material, id) {
    const replacement = material?.tileMap?.[id];
    return tileSource(image, atlas, replacement) ? replacement : id;
  }
  function layout(image, atlas, cell, ground, cells) {
    const material = ground ? regionalMaterial(atlas, cell) : null;
    let foreground = materialTile(image, atlas, material, cell.tile), groundBounds = null, frost = null;
    const walls = ground && cells && atlas.lanternWalls;
    const wallForCell = c => c &&
      (regionalMaterial(atlas,c)?.wallTiles?.[c.tile] || walls?.tiles?.[c.tile]);
    let decoration = walls?.version === 1 &&
      (wallForCell(cell) || walls.doors?.[cell.tile]);
    const isBars = walls?.version === 1 && cell.tile === walls.bars?.tile;
    if ((decoration || isBars) && Number.isInteger(cell.x) && Number.isInteger(cell.y)) {
      // These are appearances already sent by the engine, never live terrain.
      // A missing/replaced neighbor is unknown, with no independent map cache.
      const offsets = [[0,-1], [1,0], [0,1], [-1,0],
        [1,-1], [1,1], [-1,1], [-1,-1]];
      function surfaceMask(cx, cy) {
        let mask = 0;
        offsets.forEach(([dx, dy], bit) => {
          const neighbor = cells.get(`${cx + dx},${cy + dy}`);
          if (neighbor && (walls.surfaces.includes(neighbor.groundTile) ||
              walls.surfaces.includes(neighbor.tile))) mask |= 1 << bit;
        });
        return mask;
      }
      const perceivedMask = surfaceMask(cell.x, cell.y);
      if(atlas.frostWalls?.version === 1 && wallForCell(cell)) {
        let sides=0;
        offsets.forEach(([dx,dy],bit)=>{
          // Diagonal ice reaches corner caps, not unrelated straight walls.
          if(bit>=4 && !decoration.topology?.includes('corn'))return;
          const c=cells.get(`${cell.x+dx},${cell.y+dy}`);
          if(c && c.tile!==1469 && c.tile!==1470 &&
              (c.tile===1315 || c.groundTile===1315))sides|=1<<bit;
        });
        if(sides)frost={sides,variant:((cell.x+cell.y)%3+3)%3};
      }
      let mask = perceivedMask;
      if (isBars) {
        // Bars have one engine glyph. Connect only to currently supplied bars
        // or wall/door faces which visibly point toward this cell.
        let connections = 0;
        offsets.slice(0, 4).forEach(([dx, dy], bit) => {
          const neighbor = cells.get(`${cell.x + dx},${cell.y + dy}`);
          if (!neighbor) return;
          const opposite = ["S", "W", "N", "E"][bit];
          const wall = wallForCell(neighbor);
          const door = walls.doors?.[neighbor.tile];
          if (neighbor.tile === walls.bars.tile || wall?.connections?.includes(opposite) ||
              door?.topology === (bit % 2 === 0 ? "vertical-door" : "horizontal-door"))
            connections |= 1 << bit;
        });
        const vertical = connections & 5, horizontal = connections & 10;
        if (vertical && horizontal) decoration = walls.bars.connections?.[connections];
        else if (vertical) decoration = walls.bars.vertical;
        else if (horizontal) decoration = walls.bars.horizontal;
        else {
          // A single known side can establish a room rim, but fully surrounded
          // or unknown ground leaves the freestanding canonical appearance.
          const northSouth = perceivedMask & 5, eastWest = perceivedMask & 10;
          decoration = northSouth && !eastWest ? walls.bars.horizontal
            : eastWest && !northSouth ? walls.bars.vertical : null;
        }
      }
      if (decoration?.groundBounds && decoration.topology !== "bars-junction") {
        // Opening a door may reveal the far floor before the wall beyond it.
        // Keep the door on its already displayed frame, rather than shifting
        // it sideways just because its own surface mask gained a new side.
        const vertical = decoration.topology?.startsWith("vertical-");
        const adjacent = vertical ? [[0,-1], [0,1]] : [[-1,0], [1,0]];
        const frames = adjacent.flatMap(([dx, dy]) => {
          const neighbor = cells.get(`${cell.x + dx},${cell.y + dy}`);
          const kind = wallForCell(neighbor)?.topology;
          return kind === (vertical ? "vertical" : "horizontal")
            ? [surfaceMask(cell.x + dx, cell.y + dy)] : [];
        });
        if (frames.length && frames.every(m =>
          JSON.stringify(decoration.groundBounds[m]) ===
          JSON.stringify(decoration.groundBounds[frames[0]]))) mask = frames[0];
      }
      if (decoration && tileSource(image,atlas,decoration.variants[mask])) {
        // Select topology using engine appearances, then apply its material once.
        foreground = materialTile(image, atlas, material, decoration.variants[mask]);
        groundBounds = decoration.groundBounds?.[mask] || null;
        if (groundBounds && (decoration.open === true || isBars || atlas.projectedFrames?.version === 1)) {
          // The frame stays aligned, but passages and bar gaps meet the
          // adjacent surface. Projected frames also need known floor beside
          // a closed door's narrow jamb. Only direct neighbors extend ground, never the
          // diagonal evidence used to select the decorative wall face.
          let [left, top, bw, bh] = groundBounds;
          let right = left + bw, bottom = top + bh;
          if (decoration.topology?.startsWith("vertical-")) {
            if (perceivedMask & 8) left = 0;
            if (perceivedMask & 2) right = 64;
          } else {
            if (perceivedMask & 1) top = 0;
            if (perceivedMask & 4) bottom = 64;
          }
          groundBounds = [left, top, right - left, bottom - top];
        }
      }
    }
    let frame = ground && atlas.projectedFrames?.version === 1 ? atlas.projectedFrames.frames?.[foreground] : null;
    if(frame?.alternates?.length && Number.isInteger(cell.x)) {
      const variants=frame.alternates;
      frame=variants[((cell.x%variants.length)+variants.length)%variants.length];
    }
    return {foreground, groundBounds, frame, frost,
      groundTile: materialTile(image, atlas, material, cell.groundTile),
      surface: atlas.lanternWalls?.surfaces?.includes(cell.tile) === true};
  }
  function paint(context, image, atlas, cell, x, y, width, height, ground = false, cells = null, phase = "all", prepared = null) {
    if (!image || !atlas) return false;
    function draw(id, bounds = null) {
      const source=tileSource(image,atlas,id);
      if(!source)return false;
      const [sx,sy,tw,th]=source;
      const [bx, by, bw, bh] = bounds || [0, 0, 64, 64];
      context.drawImage(image, sx + bx / 64 * tw, sy + by / 64 * th,
        bw / 64 * tw, bh / 64 * th, x + bx / 64 * width,
        y + by / 64 * height, bw / 64 * width, bh / 64 * height);
      return true;
    }
    const plan = prepared || layout(image, atlas, cell, ground, cells);
    if(phase !== "foreground" && ground && atlas.groundLayers === true && cell.groundTile !== cell.tile)
      draw(plan.groundTile, plan.groundBounds);
    if(phase === "ground")return plan.surface ? draw(plan.foreground) : true;
    if(phase === "foreground" && plan.surface)return true;
    const frame = plan.frame;
    if(frame && Array.isArray(frame.source) && Array.isArray(frame.offset)) {
      const [sx,sy,sw,sh] = frame.source, [dx,dy] = frame.offset;
      if([sx,sy,sw,sh,dx,dy].every(Number.isFinite) && sx>=0 && sy>=0 && sw>0 && sh>0 &&
          sx+sw<=image.width && sy+sh<=image.height) {
        const frosted=frostedWall(image,frame.source,plan.frost,atlas);
        context.drawImage(frosted || image,frosted?0:sx,frosted?0:sy,sw,sh,x+dx/64*width,y+dy/64*height,sw/64*width,sh/64*height);
        return true;
      }
    }
    return draw(plan.foreground);
  }
  function paintWaterPockets(context, atlas, cells, width, height, environment) {
    if (!environment?.waterPlane || atlas.waterPockets?.version !== 1) return;
    // Only current AIR support defines the visible cap. Its inward contour
    // decorates that disclosed clip, never classifies missing neighbors as
    // WATER or reconstructs the complete unseen bubble. Never cache shapes.
    // Gas regions can obscure an old remembered AIR surface. They are not
    // currently visible air, even if the port retains support beneath them.
    const surface = c => c && ![1469,1470,1323,1390].includes(c.tile) ? c.groundTile : null;
    const air = new Map([...cells].filter(([, c]) => surface(c) === 1322));
    const remaining = new Set(air.keys());
    const offsets = [[0,-1],[1,0],[0,1],[-1,0]];
    while (remaining.size) {
      const seed = remaining.values().next().value, pocket = [], queue = [air.get(seed)];
      remaining.delete(seed);
      for (let i=0; i<queue.length; i++) {
        const c=queue[i]; pocket.push(c);
        for (const [dx,dy] of offsets) {
          const key=`${c.x+dx},${c.y+dy}`;
          if (remaining.delete(key)) queue.push(air.get(key));
        }
      }
      const left=Math.min(...pocket.map(c=>c.x))*width;
      const top=Math.min(...pocket.map(c=>c.y))*height;
      const right=(Math.max(...pocket.map(c=>c.x))+1)*width;
      const bottom=(Math.max(...pocket.map(c=>c.y))+1)*height;
      context.save();
      context.beginPath();
      for (const c of pocket) context.rect(c.x*width,c.y*height,width,height);
      context.clip();
      context.fillStyle='#102123';
      context.fillRect(left,top,right-left,bottom-top);
      const tint=context.createLinearGradient(left,top,right,bottom);
      tint.addColorStop(0,'rgba(78,195,216,0.22)');
      tint.addColorStop(0.5,'rgba(62,169,188,0.09)');
      tint.addColorStop(1,'rgba(28,83,100,0.025)');
      context.fillStyle=tint;
      context.fillRect(left,top,right-left,bottom-top);
      // A faint cell lattice remains legible beneath the optical surface.
      context.strokeStyle='#779b9c12'; context.lineWidth=1;
      for (const c of pocket) context.strokeRect(c.x*width+.5,c.y*height+.5,width-1,height-1);
      const inset=Math.min(width,height)*.025, radius=Math.min(width,height)*.16;
      let reflection=null;
      for (const c of pocket) {
        // A glint is optical texture on visible empty air, not an assertion
        // about the unseen edge. Keep it away from occupied logical squares.
        if(c.tile===1322 && (!reflection || c.y<reflection.y || c.y===reflection.y && c.x<reflection.x)) reflection=c;
        const edge=offsets.map(([dx,dy]) => !air.has(`${c.x+dx},${c.y+dy}`));
        if(!edge.some(Boolean))continue;
        const x=c.x*width, y=c.y*height, l=x+inset, r=x+width-inset, t=y+inset, b=y+height-inset;
        context.beginPath();
        if(edge[0]){context.moveTo(edge[3]?l+radius:x,t);context.lineTo(edge[1]?r-radius:x+width,t);}
        if(edge[1]){context.moveTo(r,edge[0]?t+radius:y);context.lineTo(r,edge[2]?b-radius:y+height);}
        if(edge[2]){context.moveTo(edge[1]?r-radius:x+width,b);context.lineTo(edge[3]?l+radius:x,b);}
        if(edge[3]){context.moveTo(l,edge[2]?b-radius:y+height);context.lineTo(l,edge[0]?t+radius:y);}
        if(edge[0]&&edge[3]){context.moveTo(l,t+radius);context.quadraticCurveTo(l,t,l+radius,t);}
        if(edge[0]&&edge[1]){context.moveTo(r-radius,t);context.quadraticCurveTo(r,t,r,t+radius);}
        if(edge[2]&&edge[1]){context.moveTo(r,b-radius);context.quadraticCurveTo(r,b,r-radius,b);}
        if(edge[2]&&edge[3]){context.moveTo(l+radius,b);context.quadraticCurveTo(l,b,l,b-radius);}
        context.strokeStyle='rgba(63,173,193,0.38)';context.lineWidth=Math.min(width,height)*.08;context.stroke();
        context.strokeStyle='rgba(99,205,222,0.48)';context.lineWidth=Math.max(1,Math.min(width,height)*.026);context.stroke();
        // White refraction gathers at curved caps, rather than forming a
        // uniform selection-style rectangle around every straight segment.
        context.beginPath();
        if(edge[0]&&edge[3]){context.moveTo(l,t+radius*1.35);context.lineTo(l,t+radius);context.quadraticCurveTo(l,t,l+radius,t);context.lineTo(l+radius*1.35,t);}
        if(edge[0]&&edge[1]){context.moveTo(r-radius*1.35,t);context.lineTo(r-radius,t);context.quadraticCurveTo(r,t,r,t+radius);context.lineTo(r,t+radius*1.35);}
        if(edge[2]&&edge[1]){context.moveTo(r,b-radius*1.35);context.lineTo(r,b-radius);context.quadraticCurveTo(r,b,r-radius,b);context.lineTo(r-radius*1.35,b);}
        if(edge[2]&&edge[3]){context.moveTo(l+radius*1.35,b);context.lineTo(l+radius,b);context.quadraticCurveTo(l,b,l,b-radius);context.lineTo(l,b-radius*1.35);}
        context.strokeStyle='rgba(182,241,247,0.85)';context.lineWidth=Math.max(1,Math.min(width,height)*.03);context.stroke();
      }
      // One small upper-left glint per currently connected perceived pocket.
      // Clip to its own square, avoiding neighboring or unknown terrain.
      if(reflection) {
        const x=reflection.x*width,y=reflection.y*height;
        context.save();context.beginPath();context.rect(x,y,width,height);context.clip();
        context.strokeStyle='rgba(172,229,237,0.8)';context.lineWidth=Math.max(1,Math.min(width,height)*.022);
        context.beginPath();context.moveTo(x+width*.14,y+height*.42);
        context.quadraticCurveTo(x+width*.24,y+height*.20,x+width*.43,y+height*.16);context.stroke();context.restore();
      }
      context.restore();
    }
  }
  function paintMap(context, image, atlas, cells, width, height = width, focus = null, environment = null) {
    if(!image || atlas?.projectedFrames?.version !== 1)return false;
    const jobs = [...cells.values()].filter(cell=>!(cell.tile===1469 && cell.char===" ")).map(cell=>({cell,plan:layout(image,atlas,cell,true,cells)}));
    // Complete every known ground layer before any art can overhang it. The
    // engine map remains the only source of occupants and remembered surfaces.
    for(const {cell,plan} of jobs)paint(context,image,atlas,cell,cell.x*width,cell.y*height,width,height,true,cells,"ground",plan);
    paintWaterPockets(context,atlas,cells,width,height,environment);
    jobs.sort((a,b)=>(a.cell.y*64+(a.plan.frame?.depth ?? 56))-(b.cell.y*64+(b.plan.frame?.depth ?? 56)) || a.cell.x-b.cell.x);
    // Engine updates include explicit unexplored/nothing placeholders. Presence
    // in the map alone does not make a square eligible for hover cutaways.
    const focusedCell=focus && cells.get(`${focus.x},${focus.y}`);
    const knownFocus=focusedCell && focusedCell.tile!==1469 && focusedCell.tile!==1470;
    const subjectIndex=knownFocus ? jobs.findIndex(({cell,plan})=>cell.x===focus.x &&
      cell.y===focus.y && plan.frame?.kind==='creature') : -1;
    let jobIndex=0;
    for(const {cell,plan} of jobs) {
      const frame=plan.frame;
      const alpha=context.globalAlpha ?? 1;
      // The hovered or targeted square remains legible in a crowd.
      // Any projected foreground (including a door, wall or statue) can cover
      // a different square. Only supplied cells participate; bounded art never
      // intersects another square, and the focused subject itself stays solid.
      if(knownFocus && frame &&
          (focus.x!==cell.x || focus.y!==cell.y)) {
        const left=cell.x*64+frame.offset[0],top=cell.y*64+frame.offset[1];
        const occupied=frame.occupiedSquares;
        const visibleOverlap=Array.isArray(occupied) ?
          occupied.some(([x,y])=>cell.x+x===focus.x && cell.y+y===focus.y) :
          left<(focus.x+1)*64 && left+frame.source[2]>focus.x*64 &&
          top<(focus.y+1)*64 && top+frame.source[3]>focus.y*64;
        // A creature painted behind the focused creature cannot obscure it.
        // Empty-square inspection still fades all artwork covering that floor.
        if(visibleOverlap && (subjectIndex<0 || jobIndex>subjectIndex))
          context.globalAlpha=alpha*0.35;
      }
      paint(context,image,atlas,cell,cell.x*width,cell.y*height,width,height,true,cells,"foreground",plan);
      context.globalAlpha=alpha;
      jobIndex++;
    }
    return true;
  }
  return { paint, paintMap };
})();
if (typeof module !== "undefined") module.exports = AtlasTiles;
