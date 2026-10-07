# Samurai quest architecture

The retained Lantern and Soot & Brass source images are the unchanged,
material edits of actual game-renderer gate scenes. Both depict
aged plaster panels in dark timber framing, a low dressed-stone base and quiet
coping. Lantern retains oak and iron; Soot & Brass uses restrained bronze
fittings. These are project-original source images, not third-party Japanese
architecture assets.

`../../samurai_material.py` fits explicit source crops to the established
semi-isometric family wall pieces. The existing assembly supplies full-height
north and south faces, visible-side choices, corners, shared walls and every
T/cross connection. The side gate supplies its wood and fittings to
the gate variants. Frontal gates use the same coping/jamb pieces and the existing
front-gate silhouette. Open gates retain the established hinge planes and
east/west threshold positions; there is no added roof, doorway or furniture.

The material appends walls and gates without changing any existing atlas pixels.
It leaves family floors, bars, objects and creatures unchanged. Classic and
Modern share all architecture. There are no new size assignments or effects on
community tilesets. Material selection belongs to the engine; this module does
not infer quest identity from map shapes or inhabitants.

`sources.json` records unchanged source and reference hashes, every crop, output
size and license. `prompts.json` retains the exact generation prompts. References
are retained alongside the sources to make their project-original lineage
auditable. The images and derived architecture are available under **CC-BY-4.0**. Credit: **NetHack Atlas project**. Full
terms remain in `../../LICENSES.txt` and the respective family license files.

`scripts/test-samurai-materials.py` checks source records, all 256 neighborhood
masks for each wall topology and gate, opening geometry, family isolation,
unchanged base pixels and floor/object/bar exclusions. Its `--shipped` mode
additionally verifies the regenerated editions and previously captured region
frames.
