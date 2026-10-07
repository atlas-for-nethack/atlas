/* Approved review recipe using shipped assets. No pixel edits or game state. */
"use strict";
const AtlasValleyStudy = (() => {
  function compose(atlas, image) {
    const vlad=atlas.regionalMaterials?.vlad, hell=atlas.regionalMaterials?.gehennom;
    if(!vlad||!hell)throw Error('Valley proposal requires original Atlas materials.');
    const tileMap={...vlad.tileMap}, wallTiles={};
    for(let i=0;i<11;i++){
      const ordinary=1273+i, infernal=1482+i;
      wallTiles[ordinary]=structuredClone(atlas.lanternWalls.tiles[ordinary]);
      wallTiles[infernal]=structuredClone(atlas.lanternWalls.tiles[ordinary]);
      tileMap[infernal]=vlad.tileMap[ordinary];
    }
    for(const id of [1284,1291,1292,1293,1294,1295,1296])
      if(hell.tileMap[id]!==undefined)tileMap[id]=hell.tileMap[id];
    return {image,atlas:{...atlas,regionalMaterials:{...atlas.regionalMaterials,
      'valley-review':{tileMap,wallTiles}}}};
  }
  function cells(cells, proposed) {
    return new Map([...cells].map(([key,cell])=>{
      const next={...cell};
      if(proposed&&next.tile!==1469&&next.tile!==1470)next.material='valley-review';
      return [key,next];
    }));
  }
  function reuse(atlas,image) {
    if(!atlas.regionalMaterials?.valley)throw Error('This review requires shipped Valley materials.');
    return {image,atlas:{...atlas,regionalMaterials:{...atlas.regionalMaterials,
      'valley-review':structuredClone(atlas.regionalMaterials.valley)}}};
  }
  return {compose,cells,reuse};
})();
if(typeof module!=='undefined')module.exports=AtlasValleyStudy;
