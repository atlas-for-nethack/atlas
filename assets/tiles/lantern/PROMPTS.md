# Lantern generation records

Original artwork uses CC BY 4.0; see [LICENSE.txt](LICENSE.txt). Independently
owned drawing and preparation code uses MIT. The catalog contains NGPL-derived
names and appearances separately from the original artwork.

Initial source generation used the built-in image tool and project-original
`production-sources/reference-concept.png` as its style reference. The reference
was generated without input images; its exact prompt is retained in
[REFERENCE-PROMPTS.md](production-sources/REFERENCE-PROMPTS.md). Generation is
not deterministic. Rebuilds use the retained source images, not new model output.

`build_geometry.py` constructs the registered 32-pixel terrain source from
original Lantern textures. `prepare_foregrounds.py` removes edge-connected
studio backgrounds before assembly, as documented in
[FOREGROUND-CLEANUP.md](FOREGROUND-CLEANUP.md). The production builders then
assemble 64-pixel portraits and full architectural frames.

Exact category prompts and corrective edits:

- [Creature prompts](MONSTER-PROMPTS.md)
- [Object prompts](OBJECT-PROMPTS.md)
- [Terrain and effect prompts](TERRAIN-PROMPTS.md)

Source registries and current provenance pin inputs, extraction bounds and output
hashes. No third-party tileset was used as an image reference. Prompt records
preserve generation lineage; they do not establish live gameplay coverage.
