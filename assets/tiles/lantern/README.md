# Lantern artwork

Lantern Classic is the default tileset. Lantern Modern shares its architecture,
floors and objects, with stature-based creature and statue display sizes.
Original artwork uses **CC BY 4.0**. Credit: **Lantern tileset by the NetHack
Atlas project, licensed under CC BY 4.0.** Include the license link and indicate
changes when sharing modified artwork. See [LICENSE.txt](LICENSE.txt) and the
[full license](../sources/CC-BY-4.0.txt). Preparation and drawing code uses MIT;
NetHack-derived catalog and size metadata retains NGPL.

Original generated sources, generation prompts, extraction bounds and hashes
remain beside the deterministic tools. New image generation is not deterministic:
rebuild the shipped artwork from the retained files. No third-party tileset
pixels serve as fallback art.

## Rebuild

Run from the repository root with Python 3 and Pillow:

```sh
python3 scripts/tile-catalog.py --check
python3 scripts/build-tilesets.py assets/tiles/recipes/lantern-classic.json assets/tiles/recipes/lantern-modern.json
python3 scripts/test-lantern.py
python3 scripts/test-lantern-production.py
python3 scripts/test-lantern-modern.py
python3 scripts/test-lantern-crop-repairs.py
python3 scripts/test-transparent-fixtures.py
```

Each recipe produces its own PNG and provenance report. The shared compiler
assembles canonical cells, compacts supplemental architecture, packs selected
projected frames and records frost contours. Neither edition depends on an
already built edition. See [the authoring guide](../../../docs/TILESETS.md)
for the recipe schema and isolated output option.

`build_production.py` prepares the 64-pixel canonical portraits, architectural
frames and regional materials in memory. It imports source loading and cleanup
from `build_atlas.py`. `build_geometry.py` regenerates the procedural
`sources/terrain-geometry.png` source registered in `sources.json`.
`build_modern.py` prepares projected creatures and statues from original sources
and registered overrides. These family modules supply artwork to the shared
compiler; they do not publish selectable tilesets.

Both
original artwork families use [the shared seven-tier creature
catalog](../creature-scale.json) and [size helper](../creature_scale.py).
Aspect ratios are preserved without width caps. Flat trappers and lurkers above
measure their tier along the longest dimension; other creatures use height.

## Maintained inputs

- `catalog.json` records all 2,304 NetHack 5.0 slots, names, appearances and order.
  Unidentified objects use appearance keys rather than hidden identities.
- `sources.json` pins the original source sheets, grids, assignments and reviewed
  extraction masks. `prepare_foregrounds.py` removes edge-connected studio
  backgrounds before nearest-neighbor resizing; see
  [foreground cleanup](FOREGROUND-CLEANUP.md).
- `production-overrides.json` pins the replacement sprites in
  `production-sources/`. `prepare_reference_subjects.py` extracts the nine
  reference subjects from `production-sources/reference-concept.png`.
  `prepare_roles.py`, `prepare_repairs.py`, and the branch-stair and transparent
  fixture preparation scripts reproduce their corresponding overrides.
- `projected_architecture.py` uses retained room and front-door sources from
  `modern-architecture/`. `extraction.json` pins source rectangles and hashes.
  Front and side doors preserve common thresholds across open and closed states.
- [Regional sources and recipes](../regions/) feed `../regional_materials.py`,
  `../samurai_material.py` and `../astral_material.py`. Classic and Modern share
  all walls, doors, floors, objects and architectural rendering.

Recipe, compiler, packer, source and output hashes are in
`classic-provenance.json` and `modern-provenance.json`; `sourceEvidence`
retains the family extraction and assembly records, including Classic
preparation under `sourceEvidence.classicPreparation`. Generation prompts record source lineage; they do not
establish live gameplay coverage or guarantee copyright exclusivity.

## Inspect

Use [the shared tileset preview](../../../tools/tileset-preview/index.html) for
rooms, creature crowding, directional doors, bars and shared walls. Generated
contact sheets belong under `.artifacts/`. Preview fixtures establish rendering
behavior; gameplay needs the rebuilt native app and actual engine:

```sh
./scripts/build-app.sh
python3 scripts/test-native.py --tileset lantern
python3 scripts/test-lantern-gameplay.py --native --tileset lantern
python3 scripts/test-lantern-bars.py --native --tileset lantern
python3 scripts/verify-bundle.py
```

The engine selects terrain materials and owns topology, door state, perception,
movement and turns. Renderer choices use displayed appearances and remembered
ground. Record meaningful results and limits in
[verification notes](../../../docs/VERIFICATION.md).
