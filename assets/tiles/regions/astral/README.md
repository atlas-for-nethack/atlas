# Astral light-stone material

Astral is the final gathering of NetHack's three high temples and their courts.
The treatment derives from the shipped Sokoban light masonry, keeping
each family's established construction and directional door silhouettes. Lantern
uses warm pale limestone and its existing timber and gold fittings. Soot & Brass
uses cooler pale stone with its existing brass construction. Bright golden metal
receives a restrained polish; dark timber and metal shadows retain their color.

The deterministic recipe in `material.json` selectively adjusts neutral stone.
It does not apply a single tint to wood, stone and metal. Floor fine grain is
quieted with a three-pixel median sample blended into the source luminance, then
lifted and reduced in contrast. Only source border coordinates receive the darker joint treatment; low-valued
interior grain is quieted normally, including remembered dark floors. Existing
engraving strokes receive extra local contrast from a bounded source-difference
mask against the corresponding ordinary floor. The mask also requires a local
stroke contrast so unrelated background changes do not become engraving. Lit and dark aliases derive independently from their original slots.
No new cracks, alignment emblems, room clues or decorative geometry are invented.

`../../astral_material.py` appends the derived art and aliases ordinary wall IDs
1273 through 1283 to copies of Sokoban sources 1504 through 1514. It copies every
wall mask, door mask and projected alternate. Alpha, offsets, dimensions, depth
and open-door apertures remain exact. Existing atlas pixels, projection records
and materials stay unchanged. Bars, traps, water, stairs, furniture, high altars,
objects, creatures and statues keep their existing artwork.

Classic and Modern share this environment material. Only their existing shared
creature and statue sizing differs. Community tilesets receive no Astral override.

All source artwork and this derivative are original NetHack Atlas assets under
**CC-BY-4.0**, credited to **NetHack Atlas project**. This recipe introduces
no third-party artwork or additional license. Canonical upstream fallback art and
its existing notices remain untouched.

Verify with `python3 scripts/test-astral-materials.py` and add `--shipped` after
regenerating all four original editions. These are artwork/projection checks;
live gameplay, hidden knowledge and original level geometry require the real
engine and native review harnesses separately.
