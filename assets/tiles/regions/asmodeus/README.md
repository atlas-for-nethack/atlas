# Asmodeus palace material

The palace uses the family's original shipped Gehennom brick pixels,
with restrained horn-shaped corner cuts and carved door keystones. It keeps the
existing wall, door and bar silhouettes and directional poses. Lantern retains
its cooler shaded floor; Soot & Brass uses its shaded regional Gehennom floor.

`material.json` retains the carving stencils. `regional_materials.py`
appends production tiles and projected frames without changing any existing
atlas pixels. Both ordinary and Gehennom wall IDs map to the palace material,
including every directional variant and connector alternate. The engine alone
selects the `asmodeus` material context. Classic and Modern share identical
architecture, floors and objects.

`tools/tileset-preview/fixtures/asmodeus-preview.js` is the independent
visual fixture. `scripts/test-asmodeus-materials.py` compares production output
against that reference pixel for pixel, including rounding, carving placement,
alpha, projection geometry and Classic/Modern parity. Node is required only by
that focused test, never by the offline player or tile generator.

These are derivatives of NetHack Atlas project-original artwork, available
under **CC-BY-4.0**. Credit: **NetHack Atlas
project**. Full grants and notices remain in the parent family license files
and `assets/tiles/LICENSES.txt`. No third-party imagery was added. Changes are
regional shading and opaque-pixel carving; source pixels and geometry are
retained in the original family atlases and source artwork. Build provenance
records the recipe, generator and source pixel hashes.
