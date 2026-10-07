# Mines materials

Original NetHack Atlas artwork, retained from the regional concept boards.
The source boards contain illustrative inhabitants; only declared wall and floor crops are used.

Artwork: CC-BY-4.0. Credit: NetHack Atlas project.
See ../../lantern/LICENSE.txt, ../../soot-and-brass/LICENSE.txt and
../../sources/CC-BY-4.0.txt for the license terms.

`../../regional_materials.py` appends supplemental pixels and mappings. The
engine's Mines-branch material tag selects the complete wall/floor treatment.
All dedicated Mines wall slots (1471 through 1481), including Minetown and
Mines' End, use this treatment. The builder copies the existing wall fallback pixels and shares their directional/projected
frames. Named Mines levels also select the dirt/gravel floors through
the existing regional mapping. Canonical floor pixels, doors, other branches
and imported sheets remain unchanged. Classic and Modern share these environment pixels. The source registry pins SHA-256 hashes; the same CC-BY-4.0 grant applies.
