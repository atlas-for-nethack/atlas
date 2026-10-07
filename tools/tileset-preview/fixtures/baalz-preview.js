/* Approved shipped Gehennom pixels on unchanged recorded Baalzebub displays. */
"use strict";
const AtlasBaalzStudy=(()=>{
  function compose(atlas,image) {
    const hell=atlas.regionalMaterials?.gehennom;
    if(!['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(atlas.id)||!hell)
      throw Error('Baalzebub study requires shipped original Gehennom materials.');
    const material=structuredClone(hell);
    // Shared room/door fixtures use ordinary wall IDs. Alias them to existing
    // Gehennom poses, never change the engine terrain or infer secret doors.
    for(let i=0;i<11;i++) {
      material.tileMap[1273+i]=hell.tileMap[1482+i];
      material.wallTiles[1273+i]=structuredClone(hell.wallTiles[1482+i]);
    }
    if(atlas.regionalMaterials.baalz) {
      if(JSON.stringify(material)!==JSON.stringify(atlas.regionalMaterials.baalz))
        throw Error('Playable Baalzebub material differs from approved review.');
    }
    return {image,atlas:{...atlas,regionalMaterials:{...atlas.regionalMaterials,
      'baalz-review':material}}};
  }
  function cells(original,proposed) {
    return new Map([...original].map(([key,value])=>{
      const cell={...value};delete cell.material;
      if(cell.tile===1469||cell.tile===1470)delete cell.groundTile;
      else if(proposed)cell.material='baalz-review';
      return [key,cell];
    }));
  }
  return {compose,cells};
})();
if(typeof module!=='undefined')module.exports=AtlasBaalzStudy;
