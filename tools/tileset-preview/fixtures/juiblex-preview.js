/* Review only: exact shipped Gehennom material on original Juiblex displays. */
"use strict";
const AtlasJuiblexStudy=(()=>{
  function compose(atlas,image) {
    const hell=atlas.regionalMaterials?.gehennom;
    if(!['lantern','lantern-modern','soot-and-brass','soot-and-brass-classic'].includes(atlas.id)||!hell)
      throw Error('Juiblex study requires shipped original Gehennom materials.');
    // The actual swamp has no wall glyphs. Substitute only the two displayed
    // dry-floor appearances, including known ground beneath perceived actors.
    const material={tileMap:{1291:hell.tileMap[1291],1292:hell.tileMap[1292]}};
    return {image,atlas:{...atlas,regionalMaterials:{...atlas.regionalMaterials,
      'juiblex-review':material}}};
  }
  function cells(original,proposed) {
    return new Map([...original].map(([key,value])=>{
      const cell={...value};delete cell.material;
      if(cell.tile===1469||cell.tile===1470)delete cell.groundTile;
      else if(proposed)cell.material='juiblex-review';
      return [key,cell];
    }));
  }
  return {compose,cells};
})();
if(typeof module!=='undefined')module.exports=AtlasJuiblexStudy;
