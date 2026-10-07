# Lantern foreground alpha cleanup

`prepare_foregrounds.py` exposes `should_clean(key)` and
`clean_foreground(source_cell, key) -> (RGBA image, metrics)`. Apply cleanup to
the original cropped cell before nearest-neighbor resizing. The helper does not
resize, recenter or redraw the subject.

It selects monsters, objects and an explicit list of terrain fixtures. Continuous
ground, wall geometry and effects are excluded. Statues inherit cleaned creature
alpha before the stone-color transform.

## Method

Original source sheets and hashes stay unchanged. Cleanup modifies alpha only,
preserving RGB. It samples the outer two-pixel border for the dark green studio
palette, calculates a fixed median RGB anchor, and removes matching pixels
connected to the border. Candidates must remain inside the explicit studio-color
envelope and nine channel levels of the fixed anchor. The flood fill never
updates its anchor while traversing the image.

Opaque black outlines and dark gear remain outside the palette. Enclosed
studio-colored pixels remain intact, including ambiguous interior shading.
Existing alpha above two remains unless it matches edge-connected studio green;
alpha zero, one and two become transparent without changing RGB.

## Reproduce and inspect

Run from the repository root with Python and Pillow:

```sh
python3 assets/tiles/lantern/prepare_foregrounds.py
python3 scripts/test-lantern-foregrounds.py
python3 scripts/test-lantern-crop-repairs.py
python3 scripts/test-transparent-fixtures.py
```

Derived sprites, cleanup metrics and review pages go to
`.artifacts/lantern-foregrounds/`. Recreate them after changes to source registries.
Warnings about enclosed studio colors or edge contacts identify review candidates,
not independently proven defects. Inspect complete outlines, weapons and limbs,
then verify the rebuilt production atlas and native renderer separately.

## Limits

Alpha cleanup cannot reconstruct clipped limbs or distinguish colored fragments
from neighboring subjects. Six creatures with source-grid overlap use explicit
replacements in `production-overrides.json`: black unicorn, baby long worm,
baby purple worm, long worm, purple worm and xan. Source sheets remain unchanged.
Other reviewed crop masks are recorded in `sources.json`.

Rings, curled tails and gaps between limbs may enclose colors resembling the
studio background. Automatic removal could erase subject material, so those
pixels remain unless a specific reviewed mask or override handles them. The
transparent trap and bow overrides have their own retained alpha sources and
preparation recipe. Physical stone rims and dark fixture interiors may remain
opaque. This helper does not infer dungeon terrain beneath a sprite.
