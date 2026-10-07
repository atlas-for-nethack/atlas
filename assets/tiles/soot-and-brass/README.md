# Soot & Brass artwork

Original grimdark steampunk artwork for NetHack Atlas. Classic and Modern have
independent atlas PNGs with identical architecture, floors and objects. Modern displays
creatures and statues at their assigned stature; Classic uses one-square
portraits. Lantern Classic remains the application default.

Original artwork uses **CC BY 4.0**. Credit: **Soot & Brass tileset by the NetHack
Atlas project, licensed under CC BY 4.0.** Include the license link and indicate
changes when sharing modified artwork. See [LICENSE.txt](LICENSE.txt) and the
[full license](../sources/CC-BY-4.0.txt). Independent preparation and drawing code
uses MIT; NetHack-derived metadata retains NGPL.

## Rebuild

Run from the repository root with Python 3 and Pillow:

```sh
python3 scripts/build-tilesets.py assets/tiles/recipes/soot-and-brass-modern.json assets/tiles/recipes/soot-and-brass-classic.json
python3 scripts/test-soot-and-brass.py
node web/tiles.test.js
```

The shared compiler produces each edition independently and updates
`../manifest.json`. Modern uses `../soot-and-brass-modern.png` and `modern-provenance.json`;
Classic uses `../soot-and-brass-classic.png` and `classic-provenance.json`.
The reports record recipe, compiler, packer, source and output hashes, with
family extraction records under `sourceEvidence`. See
[the authoring guide](../../../docs/TILESETS.md) for recipes and isolated outputs.

`build.py` prepares artwork and rendering metadata in memory for the compiler.
It requires artwork for all 2,304 canonical slots instead of falling back to other
tilesets. The shared [catalog](../lantern/catalog.json)
contains upstream names and appearances, not upstream image pixels. Unknown
objects retain their displayed appearance rather than hidden magical identity.

`monster-sources.json` and `object-sources.json` pin the source sheets, explicit
whole-subject extraction bounds, and appearance assignments. Negligible alpha
at or below eight is removed during assembly; originals remain unchanged.
Two monster cells use `keep_largest_component` to exclude detached neighboring
sprite tips. Object portraits preserve their source scale with a 52-pixel limit
and clear tile margins. Creature map frames use the full-resolution original
sources, [shared seven-tier catalog](../creature-scale.json) and
[size helper](../creature_scale.py). Aspect ratios are preserved without width
caps. Flat trappers and lurkers above use their longest dimension; other
creatures use height. Upstream size evidence and its regeneration helper live
in [metadata](../metadata/).

`terrain.py` assembles fixtures, traps, effects and directional architecture.
`terrain/prepare_sources.py` reproduces whole-subject extracts pinned by
`terrain/extraction.json`. `terrain/projected_architecture.py` samples the
retained original references:
[initial concept](terrain/approved-first-concept-source.png) and
[room concept](terrain/approved-odd-company-source.png). Their exact generation
prompts remain under `references/`; crop bounds and source hashes are in
`terrain/architecture-crops.json` and `terrain/provenance.json`.
Regional sources and recipes live in [regions](../regions/). Both editions share
all environmental pixels. No third-party artwork is supplied as fallback.

The atlas contains 64-pixel canonical squares, supplemental directional cells
and projected frames described by `projectedFrames`. The `lanternWalls` version
1 field is the shared renderer contract. Decorative faces use displayed
appearances and engine-maintained ground memory. NetHack owns terrain material
selection, collision, door state, perception and turns.

## Inspect

Use [the shared tileset preview](../../../tools/tileset-preview/index.html) for
room, crowding, directional-door, bar and shared-wall comparisons. Generated
contact sheets belong under `.artifacts/`. Exact source hashes and mechanical
coverage do not establish visual quality or live gameplay coverage. Exercise
the rebuilt native application with isolated data:

```sh
./scripts/build-app.sh
python3 scripts/test-native.py --tileset soot-and-brass
python3 scripts/test-lantern-gameplay.py --native --tileset soot-and-brass
python3 scripts/test-lantern-bars.py --native --tileset soot-and-brass
python3 scripts/test-soot-and-brass-gameplay.py
python3 scripts/test-soot-and-brass-crowding.py --native
python3 scripts/verify-bundle.py
```

The terrain tests accept the selected tileset despite their Lantern filenames.
Record meaningful results and limits in
[verification notes](../../../docs/VERIFICATION.md). Python, Pillow and Node are
development tools, not player dependencies.
