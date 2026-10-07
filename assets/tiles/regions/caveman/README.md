# Caveman quest cave materials

These four project-original sourceboards are the unchanged Caveman
quest artwork sources. The ordinary cave and Chromatic Dragon chamber use separate
source art for Lantern and Soot & Brass, with identical architecture in their
Classic and Modern editions. The goal treatment depicts smoother, worn natural
stone with restrained scorch marks. Neither treatment creates lava or changes
terrain gameplay.

`regional_materials.py` appends `caveman` and `caveman-goal` materials. It crops
and assembles source pixels using the existing full-height architecture builder,
including south-wall closure. The quiet interior floor crop is `(521,397,602,469)`;
lit/unlit brightness retains each family's existing presentation. Ordinary and
mines wall glyphs share the same material through aliases. Existing
doors and bars remain unchanged. No generated source redraw is used at runtime.

`sources.json` records image hashes, reference lineage, crop and license.
`prompts.json` retains the exact image-edit prompts. The family license notices
define the current artwork grant.
Sources are available under
**CC-BY-4.0**. Credit: **NetHack Atlas project**.
Normal sources derive from original Mines source art; goal sources derive from
the corresponding normal Caveman source. No third-party imagery was added.
Full license terms and family grants remain in `assets/tiles/LICENSES.txt`,
`lantern/LICENSE.txt` and `soot-and-brass/LICENSE.txt`.

`scripts/test-caveman-production.py` verifies source hashes, aliases and edition
parity. When the retained `.artifacts/caveman-approved-oracle` capture is present,
it additionally checks exact captured pixels, projection geometry, and
preservation of every prior shipped region and display asset.
