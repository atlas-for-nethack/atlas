# Branch staircase study

Original artwork uses CC BY 4.0. Independently owned drawing and preparation
code uses MIT. See the family license notice for scope and attribution.

Generated with the built-in image tool using only original Lantern references.
Artwork uses [CC BY 4.0](../../LICENSE.txt), credited to the NetHack Atlas project.
`branch-up-source-v2.png` is the retained source used by `prepare.py`.

## First candidate

Edit target: the existing regular up-stair tile (slot 1297), extracted losslessly
from `assets/tiles/lantern-classic.png`. Supporting style reference:
`assets/tiles/lantern/production-sources/reference-stairs.png`, the accepted down
stairs. The latter was not edited. The first generation produced an intermediate image, used for the refinement
below; that intermediate is not needed for deterministic preparation.
The exact up-stair reference is preserved as `regular-up-reference.png`.

Exact prompt:

Use case: precise-object-edit. Create ONE production candidate sprite for branch stairs UP in the Lantern roguelike tileset. Image 1 is the edit target: regular upward stairs. Image 2 is an UNCHANGED style reference for dark charcoal masonry and hand-crafted pixel texture, it depicts stairs DOWN and must NOT be copied as the new geometry. Keep Image 1's single straight flight of bright stone treads rising toward the TOP of the image, the slight top-down frontal roguelike viewpoint, crisp pixel shading, restrained gray stone palette, and readable upward progression. Replace the narrow plain side frame with a slightly heavier SQUARED masonry gateway frame, two solid straight stone side posts and a modest squared top lintel. Put a tiny muted brass fork-shaped/Y-shaped inlay centered in the TOP lintel to indicate a known passage to another dungeon branch. Frame distinction must also be readable in silhouette, not just color. NO side alcove, NO side space, NO secondary flight, NO branching stairs, NO dark descending hole, NO door leaf, NO rounded arch, NO glowing magic, NO text labels, NO background floor, NO room scene. It must still immediately read as ascending stairs, not a doorway. One centered complete sprite only on a genuinely transparent background. Design at a logical 64x64 pixel tile resolution, crisp pixel clusters, suitable for nearest-neighbor reduction to exactly64x64. Within that logical tile leave at least2 transparent pixels on every side, total stone structure about48pixels wide and60pixels tall. Preserve all step and frame detail and avoid smooth illustration or blurry resampling. Deliver a square PNG sprite, not a presentation board.

## Refined candidate

Edit target: the first generated intermediate. Supporting reference: the existing regular
up-stair tile. Output: `branch-up-source-v2.png`. The first candidate's dark gaps
looked like ladder rungs, so the second pass makes the steps a continuous flight.

Exact prompt:

Precise edit of Image1, a proposed branch staircase UP sprite. Image2 shows the correct existing continuous upward stone stair flight and pixel style. Keep Image1's symmetrical rectangular stone frame and small muted brass fork/Y inlay at its TOP. Replace ONLY the ladder-like central interior with a continuous solid stone staircase like Image2: 8 or9 closely touching shallow treads and risers, NO black empty gaps between treads, NO separated rungs. Treads have bright upper edges and darker adjoining solid vertical risers. The staircase rises away from the viewer toward the top, shallow top-down oblique roguelike view, slightly receding upper treads. The uppermost step terminates just below the lintel. Thin the side posts slightly so the steps remain the dominant readable shape. Keep a compact squared cap, no tall empty doorway, no side alcove or side flight. Preserve textured charcoal/slate pixels, no smooth gradients, no blurry detail, no glowing magic, no text. ONE centered sprite on genuinely transparent background, square canvas, intended for nearest-neighbor reduction to a64x64 game cell. Complete compact structure must occupy about48x60 of those logical pixels with2pixel transparent margin minimum. Match Image2's fine crisp pixel density. This is a solid ascending stair, NOT a ladder and NOT a downward dark hole.

## Review

`prepare.py` retains the generated source unchanged, discards alpha-one/two
specks and fits the full subject into a transparent 64-pixel cell by nearest
neighbor sampling. It does not repaint RGB values. See `provenance.json`.
The branch-up sprite is assigned only to the existing branch staircase
up art key. Regular stairs, both downward variants and engine behavior are unchanged.
