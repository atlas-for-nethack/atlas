# Ordinary Gehennom materials

Original NetHack Atlas artwork from the retained regional concept boards.
Only declared architectural and floor crops are used, not the illustrative
inhabitants on the boards.

Artwork: CC-BY-4.0. Credit: NetHack Atlas project.
See ../../lantern/LICENSE.txt, ../../soot-and-brass/LICENSE.txt and
../../sources/CC-BY-4.0.txt for license terms.

`../../regional_materials.py` appends supplemental pixels and mappings using
current full-height geometry. Lantern's plain wall avoids repeated bones;
Soot & Brass avoids repeated furnace vents. The source registry pins hashes.

Only the engine's ordinary Gehennom material tag selects this art. Named locations select their own engine-supplied material contexts; their
recipes may reuse these same source pixels. Lava, water, ice and iron bars retain their own terrain
artwork and gameplay. Classic and Modern share these environment pixels.
