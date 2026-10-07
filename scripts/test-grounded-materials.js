'use strict';
// Exercise the shipped renderer with real regional metadata. Engine perception
// and region selection are independently tested by the packaged-engine checks.
const assert = require('node:assert/strict');
const manifest = require('../assets/tiles/manifest.json');
const renderer = require('../web/tiles.js');
const families = [['lantern', 'lantern-modern'], ['soot-and-brass-classic', 'soot-and-brass']];
const floors = [1284, 1291, 1292, 1293, 1294, 1295, 1296];
const hazards = [1272, 1290, 1314, 1315, 1316, 1317, 1322, 1323, 1324,
  ...Array.from({length: 25}, (_, i) => 1325 + i), 1469, 1470];
const ground = [1291, 1292, 1294, 1295, 1314, 1315, 1316, 1318, 1319, 1322, 1323, 1324];
function atlas(id) { return manifest.tilesets.find(t => t.id === id); }
function paint(atlas, cell, phase = 'all', enabled = true, neighbors = new Map()) {
  const calls = [], ctx = {globalAlpha: 1,
    drawImage: (...args) => calls.push(args.slice(1)),
    save() {}, restore() {}, beginPath() {}, rect() {}, clip() {}};
  renderer.paint(ctx, {width: atlas.columns * atlas.tileWidth, height: 100000},
    atlas, cell, 0, 0, 64, 64, enabled, neighbors, phase);
  return calls;
}
function stripFloors(material) {
  const result = JSON.parse(JSON.stringify(material));
  for (const tile of floors) delete result.tileMap[tile];
  return result;
}
// Packing changes source origins only. Preserve crop size, destination
// geometry, call ordering and every same-atlas renderer assertion below.
function comparableDraws(calls) {
  return calls.map(call => {
    assert.equal(call.length, 8, 'Expected an explicit source and destination rectangle');
    return [0, 0, ...call.slice(2)];
  });
}
let regions = 0, layerChecks = 0;
for (const [classic, modern] of families) {
  const a = atlas(classic), b = atlas(modern);
  assert(a && b);
  assert.deepEqual(a.regionalMaterials, b.regionalMaterials,
    `${classic}/${modern}: all regional architectural metadata must match`);
  for (const material of Object.keys(a.regionalMaterials)) {
    regions++;
    for (const tile of [...Array.from({length: 77}, (_, i) => 1273 + i),
      ...Array.from({length: 22}, (_, i) => 1471 + i), 1469, 1470]) {
      assert.deepEqual(comparableDraws(paint(a, {tile, material})), comparableDraws(paint(b, {tile, material})),
        `${material}/${tile}: Classic/Modern architecture and terrain parity`);
    }
    for (const set of [a, b]) {
      const map = set.regionalMaterials[material].tileMap;
      for (const [canonical, replacement] of Object.entries(map)) {
        assert(Number.isInteger(Number(canonical)) && Number(canonical) >= 0);
        assert(Number.isInteger(replacement) && replacement >= 0 && replacement < set.count,
          `${set.id}/${material}: mapping must use an existing atlas slot`);
      }
      for (const tile of hazards) {
        assert.equal(map[tile], undefined, `${material}: no hazard, water or unknown substitution`);
        assert.deepEqual(paint(set, {tile, material}), paint(set, {tile}),
          `${set.id}/${material}/${tile}: canonical hazard, tree or unknown appearance`);
      }
      for (const groundTile of ground) {
        const bare = paint(set, {tile: groundTile, material});
        assert(bare.length, `Known terrain ${groundTile} must draw`);
        for (const occupant of [699, 632, 1297, 1305, 1311]) {
          const occupied = paint(set, {tile: occupant, groundTile, material});
          assert.deepEqual(occupied[0], bare[0],
            `${set.id}/${material}: known ${groundTile} support beneath occupant ${occupant}`);
          assert(occupied.length > bare.length, 'Foreground remains visible above known support');
          layerChecks++;
        }
      }
      const imported = {...set, regionalMaterials: undefined};
      for (const tile of [1273, 1287, 1291, 1292, 1314, 1316, 1469]) {
        const tagged = {tile, groundTile: 1291, material};
        assert.deepEqual(paint(imported, tagged), paint(imported, {...tagged, material: undefined}),
          'Community tiles without regional metadata preserve canonical fallback');
        assert.deepEqual(paint(set, {tile, material}, 'all', false),
          paint(set, {tile}, 'all', false), 'Disabled regional rendering preserves canonical tiles');
      }
    }
  }
  for (const set of [a, b]) {
    const materials = set.regionalMaterials;
    assert.deepEqual(materials['quest-earth'], {tileMap: {
      1291: materials.caveman.tileMap[1291], 1292: materials.caveman.tileMap[1292]}},
      'Outdoor earth reuses only the exact lit/dark Caveman floor slots');
    assert.deepEqual(materials['mines-built'], stripFloors(materials.mines),
      'Built Mines retain exact excavation architecture with canonical interior floors');
    assert.deepEqual(materials['priest-temple'], stripFloors(materials.valley),
      'Priest temple retains exact Valley architecture with canonical interior floors');
    for (const tile of floors) {
      assert.deepEqual(paint(set, {tile, material: 'mines-built'}), paint(set, {tile}),
        'Minetown interior doorway, floor, engraving and corridor remain canonical');
      assert.deepEqual(paint(set, {tile, material: 'priest-temple'}), paint(set, {tile}),
        'Priest temple interior doorway, floor, engraving and corridor remain canonical');
    }
    for (const tile of [1291, 1292]) {
      assert.notDeepEqual(paint(set, {tile, material: 'quest-earth'}), paint(set, {tile}),
        'Outside dry earth actually changes the drawn floor');
      assert.deepEqual(paint(set, {tile, material: 'quest-earth'}),
        paint(set, {tile, material: 'caveman'}), 'Earth uses existing natural-ground art exactly');
    }
    const neighbors = new Map([
      ['3,2', {tile: 1291}], ['4,3', {tile: 1291}],
      ['3,4', {tile: 1292}], ['2,3', {tile: 1292}]]);
    for (const tile of [...Array.from({length: 11}, (_, i) => 1471 + i), 1285, 1286, 1287, 1288]) {
      const cell = {x: 3, y: 3, tile};
      assert.deepEqual(paint(set, {...cell, material: 'mines-built'}, 'foreground', true, neighbors),
        paint(set, {...cell, material: 'mines'}, 'foreground', true, neighbors),
        'Perceived mine wall/support/door shape survives the interior ground correction');
    }
    for (const material of ['medusa', 'samurai']) {
      assert.deepEqual(paint(set, {tile: 1291, material}), paint(set, {tile: 1291}),
        `${material}: existing architectural material retains canonical built floors`);
    }
    const malformed = {...set, regionalMaterials: {broken: {tileMap: {1291: set.count}}}};
    assert.deepEqual(paint(malformed, {tile: 1291, material: 'broken'}), paint(set, {tile: 1291}),
      'Unavailable replacement slots fall back to the canonical appearance');
  }
}
const community = atlas('official');
for (const material of Object.keys(atlas('lantern').regionalMaterials)) {
  for (const tile of [1273, 1287, 1291, 1292, 1314, 1316, 1469]) {
    assert.deepEqual(paint(community, {tile, material}), paint(community, {tile}),
      'NetHack Classic receives no original-family regional override');
  }
}
console.log(`PASS ${regions} regional family mappings, edition parity, canonical hazards and community fallback; ${layerChecks} known-support layer checks.`);
