# Lantern terrain and effects generation prompts

Original artwork uses CC BY 4.0. Independently owned drawing and preparation
code uses MIT. See the family license notice for scope and attribution.

Built-in image generation; approved Lantern concept used as style reference. Original generated sheets are retained unchanged. Use the current artwork and connector tests to validate changes.

## terrain-01

Use case: stylized-concept. Asset type: production candidate terrain/effects sprite sheet for the original Lantern roguelike tileset. Reference image role: STYLE ONLY, the approved original Lantern concept, not an edit target. Generate a NEW SQUARE 1024x1024 sprite sheet with an EXACT 8-column by 8-row uniform invisible grid, 64 equally sized square cells touching edge-to-edge. No margins, no gutters, no outlines around cells, no labels, no numerals, no text, no UI, no title. Cells begin at image boundaries; each row occupies exactly one eighth image height. Original Lantern pixel art: 32x32 conceptual base per tile, hard pixel edges, restrained charcoal/slate blue stone, small ivory and brass accents. Orthographic overhead terrain, no isometric cube, no detached floating platforms. Quiet floor textures and distinctly readable objects. The source sheet will be cut at exact eighth fractions, so the specified cell positions are mandatory. Only the 64 subjects listed in row-major order, left to right then top to bottom.

All cells use opaque charcoal #182221 background unless terrain completely fills them. Stone and unexplored/nothing cells are solid very dark charcoal with absolutely no symbols. Floor, corridor, ice, water, pool, lava, walls and wall connectors fill their cells edge-to-edge, no dark framing gaps. Floor masonry scale consistent across cells. Each other dungeon feature centered wholly inside its single cell. Repeated wall connectors join edge midpoints with same wall thickness (12/32 cell) and same height; dark charcoal on unused quadrants. Use top-left illumination without cast shadows beyond cell. Wall topology is exact: vertical joins north+south, horizontal west+east, tlcorn joins south+east, trcorn south+west, blcorn north+east, brcorn north+west, cross joins all four. tuwall (┴) joins north+west+east; tdwall (┬) joins south+west+east; tlwall (┤) joins north+south+west; trwall (├) joins north+south+east. Door orientation matches wall axis. Upstairs light steps rising, downstairs dark descending pit. Stair and ladder branch variants use restrained gold edge accent. Trap tiles show only a recognizable small trap emblem. No creatures, no loot except named fixtures.

Zap effect final direction index 0 means vertical,1 horizontal,2 backslash diagonal descending upper-left to lower-right,3 slash diagonal rising lower-left to upper-right. Thin crisp colored beam hits exactly the proper opposing cell edges. Explosions are SEGMENTS of a single 3x3 burst, never nine individual full bursts: each label names the corresponding ninth. All seven burst types use identical geometric placement; top-left expands toward bottom-right, center filled, right/bottom mirrored, outer edge fades into charcoal; preserve cut edges where segments meet. Swallow tiles similarly form eight border cells of a 3x3 fleshy enclosure. No letters in effects or warning symbols. Warnings use increasingly bold colored danger silhouettes.

CELL ORDER (row,column,subject), coordinates start at 1:
(1,1) stone
(1,2) main walls vertical
(1,3) main walls horizontal
(1,4) main walls tlcorn
(1,5) main walls trcorn
(1,6) main walls blcorn
(1,7) main walls brcorn
(1,8) main walls cross wall
(2,1) main walls tuwall
(2,2) main walls tdwall
(2,3) main walls tlwall
(2,4) main walls trwall
(2,5) no door
(2,6) vertical open door
(2,7) horizontal open door
(2,8) vertical closed door
(3,1) horizontal closed door
(3,2) iron bars
(3,3) tree
(3,4) floor of a room
(3,5) dark part of a room
(3,6) engraving in a room
(3,7) corridor
(3,8) lit corridor
(4,1) engraving in a corridor
(4,2) staircase up
(4,3) staircase down
(4,4) ladder up
(4,5) ladder down
(4,6) branch staircase up
(4,7) branch staircase down
(4,8) branch ladder up
(5,1) branch ladder down
(5,2) unaligned altar
(5,3) chaotic altar
(5,4) neutral altar
(5,5) lawful altar
(5,6) other altar
(5,7) grave
(5,8) throne
(6,1) sink
(6,2) fountain
(6,3) pool
(6,4) ice
(6,5) molten lava
(6,6) wall of lava
(6,7) vertical open drawbridge
(6,8) horizontal open drawbridge
(7,1) vertical closed drawbridge
(7,2) horizontal closed drawbridge
(7,3) air
(7,4) cloud
(7,5) water
(7,6) arrow trap
(7,7) dart trap
(7,8) falling rock trap
(8,1) squeaky board
(8,2) bear trap
(8,3) land mine
(8,4) rolling boulder trap
(8,5) sleeping gas trap
(8,6) rust trap
(8,7) fire trap
(8,8) pit

## terrain-02

Use case: stylized-concept. Asset type: production candidate terrain/effects sprite sheet for the original Lantern roguelike tileset. Reference image role: STYLE ONLY, the approved original Lantern concept, not an edit target. Generate a NEW SQUARE 1024x1024 sprite sheet with an EXACT 8-column by 8-row uniform invisible grid, 64 equally sized square cells touching edge-to-edge. No margins, no gutters, no outlines around cells, no labels, no numerals, no text, no UI, no title. Cells begin at image boundaries; each row occupies exactly one eighth image height. Original Lantern pixel art: 32x32 conceptual base per tile, hard pixel edges, restrained charcoal/slate blue stone, small ivory and brass accents. Orthographic overhead terrain, no isometric cube, no detached floating platforms. Quiet floor textures and distinctly readable objects. The source sheet will be cut at exact eighth fractions, so the specified cell positions are mandatory. Only the 64 subjects listed in row-major order, left to right then top to bottom.

All cells use opaque charcoal #182221 background unless terrain completely fills them. Stone and unexplored/nothing cells are solid very dark charcoal with absolutely no symbols. Floor, corridor, ice, water, pool, lava, walls and wall connectors fill their cells edge-to-edge, no dark framing gaps. Floor masonry scale consistent across cells. Each other dungeon feature centered wholly inside its single cell. Repeated wall connectors join edge midpoints with same wall thickness (12/32 cell) and same height; dark charcoal on unused quadrants. Use top-left illumination without cast shadows beyond cell. Wall topology is exact: vertical joins north+south, horizontal west+east, tlcorn joins south+east, trcorn south+west, blcorn north+east, brcorn north+west, cross joins all four. tuwall (┴) joins north+west+east; tdwall (┬) joins south+west+east; tlwall (┤) joins north+south+west; trwall (├) joins north+south+east. Door orientation matches wall axis. Upstairs light steps rising, downstairs dark descending pit. Stair and ladder branch variants use restrained gold edge accent. Trap tiles show only a recognizable small trap emblem. No creatures, no loot except named fixtures.

Zap effect final direction index 0 means vertical,1 horizontal,2 backslash diagonal descending upper-left to lower-right,3 slash diagonal rising lower-left to upper-right. Thin crisp colored beam hits exactly the proper opposing cell edges. Explosions are SEGMENTS of a single 3x3 burst, never nine individual full bursts: each label names the corresponding ninth. All seven burst types use identical geometric placement; top-left expands toward bottom-right, center filled, right/bottom mirrored, outer edge fades into charcoal; preserve cut edges where segments meet. Swallow tiles similarly form eight border cells of a 3x3 fleshy enclosure. No letters in effects or warning symbols. Warnings use increasingly bold colored danger silhouettes.

CELL ORDER (row,column,subject), coordinates start at 1:
(1,1) spiked pit
(1,2) hole
(1,3) trap door
(1,4) teleportation trap
(1,5) level teleporter
(1,6) magic portal
(1,7) web
(1,8) statue trap
(2,1) magic trap
(2,2) anti-magic field
(2,3) polymorph trap
(2,4) vibrating square
(2,5) trapped door
(2,6) trapped chest
(2,7) missile zap 1 0
(2,8) missile zap 1 1
(3,1) missile zap 1 2
(3,2) missile zap 1 3
(3,3) fire zap 2 0
(3,4) fire zap 2 1
(3,5) fire zap 2 2
(3,6) fire zap 2 3
(3,7) frost zap 3 0
(3,8) frost zap 3 1
(4,1) frost zap 3 2
(4,2) frost zap 3 3
(4,3) sleep zap 4 0
(4,4) sleep zap 4 1
(4,5) sleep zap 4 2
(4,6) sleep zap 4 3
(4,7) death zap 5 0
(4,8) death zap 5 1
(5,1) death zap 5 2
(5,2) death zap 5 3
(5,3) lightning zap 6 0
(5,4) lightning zap 6 1
(5,5) lightning zap 6 2
(5,6) lightning zap 6 3
(5,7) poison gas zap 7 0
(5,8) poison gas zap 7 1
(6,1) poison gas zap 7 2
(6,2) poison gas zap 7 3
(6,3) acid zap 8 0
(6,4) acid zap 8 1
(6,5) acid zap 8 2
(6,6) acid zap 8 3
(6,7) dig beam
(6,8) flash beam
(7,1) boom left
(7,2) boom right
(7,3) shield1
(7,4) shield2
(7,5) shield3
(7,6) shield4
(7,7) poison cloud
(7,8) valid position
(8,1) swallow top left
(8,2) swallow top center
(8,3) swallow top right
(8,4) swallow middle left
(8,5) swallow middle right
(8,6) swallow bottom left
(8,7) swallow bottom center
(8,8) swallow bottom right

## terrain-03

Use case: stylized-concept. Asset type: production candidate terrain/effects sprite sheet for the original Lantern roguelike tileset. Reference image role: STYLE ONLY, the approved original Lantern concept, not an edit target. Generate a NEW SQUARE 1024x1024 sprite sheet with an EXACT 8-column by 8-row uniform invisible grid, 64 equally sized square cells touching edge-to-edge. No margins, no gutters, no outlines around cells, no labels, no numerals, no text, no UI, no title. Cells begin at image boundaries; each row occupies exactly one eighth image height. Original Lantern pixel art: 32x32 conceptual base per tile, hard pixel edges, restrained charcoal/slate blue stone, small ivory and brass accents. Orthographic overhead terrain, no isometric cube, no detached floating platforms. Quiet floor textures and distinctly readable objects. The source sheet will be cut at exact eighth fractions, so the specified cell positions are mandatory. Only the 64 subjects listed in row-major order, left to right then top to bottom.

All cells use opaque charcoal #182221 background unless terrain completely fills them. Stone and unexplored/nothing cells are solid very dark charcoal with absolutely no symbols. Floor, corridor, ice, water, pool, lava, walls and wall connectors fill their cells edge-to-edge, no dark framing gaps. Floor masonry scale consistent across cells. Each other dungeon feature centered wholly inside its single cell. Repeated wall connectors join edge midpoints with same wall thickness (12/32 cell) and same height; dark charcoal on unused quadrants. Use top-left illumination without cast shadows beyond cell. Wall topology is exact: vertical joins north+south, horizontal west+east, tlcorn joins south+east, trcorn south+west, blcorn north+east, brcorn north+west, cross joins all four. tuwall (┴) joins north+west+east; tdwall (┬) joins south+west+east; tlwall (┤) joins north+south+west; trwall (├) joins north+south+east. Door orientation matches wall axis. Upstairs light steps rising, downstairs dark descending pit. Stair and ladder branch variants use restrained gold edge accent. Trap tiles show only a recognizable small trap emblem. No creatures, no loot except named fixtures.

Zap effect final direction index 0 means vertical,1 horizontal,2 backslash diagonal descending upper-left to lower-right,3 slash diagonal rising lower-left to upper-right. Thin crisp colored beam hits exactly the proper opposing cell edges. Explosions are SEGMENTS of a single 3x3 burst, never nine individual full bursts: each label names the corresponding ninth. All seven burst types use identical geometric placement; top-left expands toward bottom-right, center filled, right/bottom mirrored, outer edge fades into charcoal; preserve cut edges where segments meet. Swallow tiles similarly form eight border cells of a 3x3 fleshy enclosure. No letters in effects or warning symbols. Warnings use increasingly bold colored danger silhouettes.

CELL ORDER (row,column,subject), coordinates start at 1:
(1,1) explosion dark top left
(1,2) explosion dark top center
(1,3) explosion dark top right
(1,4) explosion dark middle left
(1,5) explosion dark middle center
(1,6) explosion dark middle right
(1,7) explosion dark bottom left
(1,8) explosion dark bottom center
(2,1) explosion dark bottom right
(2,2) explosion noxious top left
(2,3) explosion noxious top center
(2,4) explosion noxious top right
(2,5) explosion noxious middle left
(2,6) explosion noxious middle center
(2,7) explosion noxious middle right
(2,8) explosion noxious bottom left
(3,1) explosion noxious bottom center
(3,2) explosion noxious bottom right
(3,3) explosion muddy top left
(3,4) explosion muddy top center
(3,5) explosion muddy top right
(3,6) explosion muddy middle left
(3,7) explosion muddy middle center
(3,8) explosion muddy middle right
(4,1) explosion muddy bottom left
(4,2) explosion muddy bottom center
(4,3) explosion muddy bottom right
(4,4) explosion wet top left
(4,5) explosion wet top center
(4,6) explosion wet top right
(4,7) explosion wet middle left
(4,8) explosion wet middle center
(5,1) explosion wet middle right
(5,2) explosion wet bottom left
(5,3) explosion wet bottom center
(5,4) explosion wet bottom right
(5,5) explosion magical top left
(5,6) explosion magical top center
(5,7) explosion magical top right
(5,8) explosion magical middle left
(6,1) explosion magical middle center
(6,2) explosion magical middle right
(6,3) explosion magical bottom left
(6,4) explosion magical bottom center
(6,5) explosion magical bottom right
(6,6) explosion fiery top left
(6,7) explosion fiery top center
(6,8) explosion fiery top right
(7,1) explosion fiery middle left
(7,2) explosion fiery middle center
(7,3) explosion fiery middle right
(7,4) explosion fiery bottom left
(7,5) explosion fiery bottom center
(7,6) explosion fiery bottom right
(7,7) explosion frosty top left
(7,8) explosion frosty top center
(8,1) explosion frosty top right
(8,2) explosion frosty middle left
(8,3) explosion frosty middle center
(8,4) explosion frosty middle right
(8,5) explosion frosty bottom left
(8,6) explosion frosty bottom center
(8,7) explosion frosty bottom right
(8,8) warning 0

## terrain-04

Use case: stylized-concept. Asset type: production candidate terrain/effects sprite sheet for the original Lantern roguelike tileset. Reference image role: STYLE ONLY, the approved original Lantern concept, not an edit target. Generate a NEW SQUARE 1024x1024 sprite sheet with an EXACT 8-column by 8-row uniform invisible grid, 64 equally sized square cells touching edge-to-edge. No margins, no gutters, no outlines around cells, no labels, no numerals, no text, no UI, no title. Cells begin at image boundaries; each row occupies exactly one eighth image height. Original Lantern pixel art: 32x32 conceptual base per tile, hard pixel edges, restrained charcoal/slate blue stone, small ivory and brass accents. Orthographic overhead terrain, no isometric cube, no detached floating platforms. Quiet floor textures and distinctly readable objects. The source sheet will be cut at exact eighth fractions, so the specified cell positions are mandatory. Only the 64 subjects listed in row-major order, left to right then top to bottom.

All cells use opaque charcoal #182221 background unless terrain completely fills them. Stone and unexplored/nothing cells are solid very dark charcoal with absolutely no symbols. Floor, corridor, ice, water, pool, lava, walls and wall connectors fill their cells edge-to-edge, no dark framing gaps. Floor masonry scale consistent across cells. Each other dungeon feature centered wholly inside its single cell. Repeated wall connectors join edge midpoints with same wall thickness (12/32 cell) and same height; dark charcoal on unused quadrants. Use top-left illumination without cast shadows beyond cell. Wall topology is exact: vertical joins north+south, horizontal west+east, tlcorn joins south+east, trcorn south+west, blcorn north+east, brcorn north+west, cross joins all four. tuwall (┴) joins north+west+east; tdwall (┬) joins south+west+east; tlwall (┤) joins north+south+west; trwall (├) joins north+south+east. Door orientation matches wall axis. Upstairs light steps rising, downstairs dark descending pit. Stair and ladder branch variants use restrained gold edge accent. Trap tiles show only a recognizable small trap emblem. No creatures, no loot except named fixtures.

Zap effect final direction index 0 means vertical,1 horizontal,2 backslash diagonal descending upper-left to lower-right,3 slash diagonal rising lower-left to upper-right. Thin crisp colored beam hits exactly the proper opposing cell edges. Explosions are SEGMENTS of a single 3x3 burst, never nine individual full bursts: each label names the corresponding ninth. All seven burst types use identical geometric placement; top-left expands toward bottom-right, center filled, right/bottom mirrored, outer edge fades into charcoal; preserve cut edges where segments meet. Swallow tiles similarly form eight border cells of a 3x3 fleshy enclosure. No letters in effects or warning symbols. Warnings use increasingly bold colored danger silhouettes.

CELL ORDER (row,column,subject), coordinates start at 1:
(1,1) warning 1
(1,2) warning 2
(1,3) warning 3
(1,4) warning 4
(1,5) warning 5
(1,6) unexplored
(1,7) nothing
(1,8) mines walls vertical; rough blue-gray rock masonry
(2,1) mines walls horizontal; rough blue-gray rock masonry
(2,2) mines walls tlcorn; rough blue-gray rock masonry
(2,3) mines walls trcorn; rough blue-gray rock masonry
(2,4) mines walls blcorn; rough blue-gray rock masonry
(2,5) mines walls brcorn; rough blue-gray rock masonry
(2,6) mines walls cross wall; rough blue-gray rock masonry
(2,7) mines walls tuwall; rough blue-gray rock masonry
(2,8) mines walls tdwall; rough blue-gray rock masonry
(3,1) mines walls tlwall; rough blue-gray rock masonry
(3,2) mines walls trwall; rough blue-gray rock masonry
(3,3) gehennom walls vertical; dark charcoal volcanic masonry with muted rust seams
(3,4) gehennom walls horizontal; dark charcoal volcanic masonry with muted rust seams
(3,5) gehennom walls tlcorn; dark charcoal volcanic masonry with muted rust seams
(3,6) gehennom walls trcorn; dark charcoal volcanic masonry with muted rust seams
(3,7) gehennom walls blcorn; dark charcoal volcanic masonry with muted rust seams
(3,8) gehennom walls brcorn; dark charcoal volcanic masonry with muted rust seams
(4,1) gehennom walls cross wall; dark charcoal volcanic masonry with muted rust seams
(4,2) gehennom walls tuwall; dark charcoal volcanic masonry with muted rust seams
(4,3) gehennom walls tdwall; dark charcoal volcanic masonry with muted rust seams
(4,4) gehennom walls tlwall; dark charcoal volcanic masonry with muted rust seams
(4,5) gehennom walls trwall; dark charcoal volcanic masonry with muted rust seams
(4,6) knox walls vertical; precisely cut pale gray fortress masonry
(4,7) knox walls horizontal; precisely cut pale gray fortress masonry
(4,8) knox walls tlcorn; precisely cut pale gray fortress masonry
(5,1) knox walls trcorn; precisely cut pale gray fortress masonry
(5,2) knox walls blcorn; precisely cut pale gray fortress masonry
(5,3) knox walls brcorn; precisely cut pale gray fortress masonry
(5,4) knox walls cross wall; precisely cut pale gray fortress masonry
(5,5) knox walls tuwall; precisely cut pale gray fortress masonry
(5,6) knox walls tdwall; precisely cut pale gray fortress masonry
(5,7) knox walls tlwall; precisely cut pale gray fortress masonry
(5,8) knox walls trwall; precisely cut pale gray fortress masonry
(6,1) sokoban walls vertical; restrained green-gray puzzle chamber stone masonry
(6,2) sokoban walls horizontal; restrained green-gray puzzle chamber stone masonry
(6,3) sokoban walls tlcorn; restrained green-gray puzzle chamber stone masonry
(6,4) sokoban walls trcorn; restrained green-gray puzzle chamber stone masonry
(6,5) sokoban walls blcorn; restrained green-gray puzzle chamber stone masonry
(6,6) sokoban walls brcorn; restrained green-gray puzzle chamber stone masonry
(6,7) sokoban walls cross wall; restrained green-gray puzzle chamber stone masonry
(6,8) sokoban walls tuwall; restrained green-gray puzzle chamber stone masonry
(7,1) sokoban walls tdwall; restrained green-gray puzzle chamber stone masonry
(7,2) sokoban walls tlwall; restrained green-gray puzzle chamber stone masonry
(7,3) sokoban walls trwall; restrained green-gray puzzle chamber stone masonry
(7,4) unused padding: solid charcoal #182221
(7,5) unused padding: solid charcoal #182221
(7,6) unused padding: solid charcoal #182221
(7,7) unused padding: solid charcoal #182221
(7,8) unused padding: solid charcoal #182221
(8,1) unused padding: solid charcoal #182221
(8,2) unused padding: solid charcoal #182221
(8,3) unused padding: solid charcoal #182221
(8,4) unused padding: solid charcoal #182221
(8,5) unused padding: solid charcoal #182221
(8,6) unused padding: solid charcoal #182221
(8,7) unused padding: solid charcoal #182221
(8,8) unused padding: solid charcoal #182221

## terrain-04-v2 targeted blank-cell correction

Use case: precise-object-edit. Edit target: terrain-04.png, an exact8by8tile sprite sheet. Make ONLYthese changes: row1,column6 and row1,column7 must each be a perfectly flat opaque verydark charcoal #0c1416rectangle, extending exactly to the entire cell boundaries including all edges. Remove every pixel of visual detail, alpha/transparency, glow, speckle, halo and neighboring sprite bleed inside those two cells. They are unexplored and nothing, not symbols. Preserve all other cells, wall connectors, silhouettes, colors, dimensions and exact8by8grid layout unchanged. Do not add outlines, text, borders or margins. Preserve the original resolution1254square. The two edited cells cover xfrom5/8to7/8ofwidth and yfrom0to1/8ofheight. No other change.


## terrain-explosions-v2

Use case: stylized-concept. Asset type: original Lantern game effects source sheet. Reference image role: approved Lantern pixel-art STYLE ONLY. NEW square sprite sheet. Exactly THREE columns by THREE rows of equally sized LARGE square blocks, touching, no gaps, no margins, no borders, no text. Each large block is one single explosion that will be subdivided by engine into a 3 by 3 tile burst. Thus the final sheet has an implicit 9 by 9 fine grid. Do not draw gridlines. Requested 1024 square, preserve square output.
There are seven complete large explosions with clean pixel-art edges, not photographs, no wispy lighting, controlled palette matching Lantern. Each explosion centered precisely within its own large block and fills that block symmetrically, extending close to all four edges. Within each large block the center must occupy exactly the middle third in both axes, corners flare diagonally, edge middles flare perpendicular. All seven bursts use identical placement and scale so subdivisions connect. Dark transparent background around bursts, no floor, no environment. No tiny detached sparks outside block boundaries.
Exact LARGE block order:
Row 1,col 1: dark explosion, charcoal-violet jagged smoke energy, visible dark outline.
Row 1,col 2: noxious explosion, muted toxic yellow-green smoke energy.
Row 1,col 3: muddy explosion, warm brown mud and dust energy.
Row 2,col 1: wet explosion, slate-blue and ivory water splash.
Row 2,col 2: magical explosion, violet and pale lilac magical energy.
Row 2,col 3: fiery explosion, rust-red orange gold fire.
Row 3,col 1: frosty explosion, pale cyan and ivory ice burst.
Row 3,col 2: only a SMALL low-level danger icon, muted yellow angular warning diamond, centered precisely in the central third of the block. No letters, numerals or punctuation. Remainder of block transparent.
Row 3,col 3: completely empty transparent black, no artwork.
No nine separate little bursts within a block: one coherent large burst per block. Keep all art within its large block. Crisp restrained 32-pixel-per-fine-cell style and matching silhouettes.

## terrain-corrections-01

Use case: stylized-concept. Asset type: three corrective original Lantern roguelike sprites in one square source sheet. Reference image is STYLE ONLY, the approved Lantern concept. Generate NEW crisp restrained pixel art at a conceptual 32x32 pixels per sprite, enlarged with hard edges. Exactly TWO equal columns by TWO equal rows, invisible uniform grid, touching cells, no gutters, no outer margins, no frames, no labels, no text. Source image square 1024x1024. Every sprite centered inside its own quarter, occupying about 70 percent of that cell. Opaque flat very dark charcoal #182221 cell backgrounds. No glow, no fire, no explosions, no fountain, no water, no scene.
Top-left quarter: flying wooden boomerang LEFT effect. A single light-brown bent wooden throwing stick shaped like a slim right parenthesis ), convex on the right and open on the left, pale worn wood highlight, pointed upper and lower ends. Only the wooden boomerang, no trail, no flame.
Top-right quarter: flying wooden boomerang RIGHT effect. Exact horizontal mirror of the top-left wooden boomerang, shaped like a slim left parenthesis (, convex on the left and open on the right. Same scale, material and detail, only wood.
Bottom-left quarter: LEVEL TELEPORTER trap, a small violet angular spiral surrounding a tiny pair of descending slate steps, rendered as an overhead magical floor symbol. Clear purple geometric teleport rune plus tiny steps distinguishes it from a simple teleportation spiral. Low-profile flat symbol, never an upright portal, never a fountain. Use muted lavender, ivory and slate, no letters or numbers.
Bottom-right quarter: completely flat charcoal #182221, no subject and no variation.
Maintain original Lantern style and exact 2x2 quadrant geometry. These are independent game tiles, not a poster or composition.

## Precise terrain geometry with original Lantern textures

`build_geometry.py` uses this
project's original generated `sources/terrain-01.png` as its only texture donor,
preserving the bright stone caps, darker masonry faces and original floor/water
detail. No third-party art is loaded. Original Lantern artwork uses
CC BY 4.0; see [LICENSE.txt](LICENSE.txt).

The generator verifies the donor SHA-256 before reading it. The source registry
records both the generator and donor hashes. Donor cells use the original
normalized 8 × 8 grid, with zero-based coordinates:

- Wall masonry: cell (2, 0), crop (5, 28, 151, 141), resized to 32 × 12.
  Vertical texture rotates that strip. Exact silhouette masks constrain the
  texture; matching edge profiles come from the donor's median stone colors.
- Closed-door wood: cell (7, 1), crop (66, 32, 102, 59), excluding the original
  latch. It textures the corrected blocking panel; a single brass latch remains.
- Room floor: cell (3, 2); dark floor: (4, 2); room/corridor engraving: (5, 2).
  Corridors use room/dark-room textures rather than the former rail-like borders.
- Pool and water: cell (4, 6), cropped inward 12 source pixels to remove the
  original transparent inset, then extended across the complete 32-pixel tile.

Ground textures are composited over a matching opaque dark slate or water base;
only the outer pixel ring is averaged with its opposite edge for repeatable
joins. Interior texture is not replaced with procedural noise. Pool uses the
original open-water texture, not the framed basin illustration.

`sources/terrain-geometry.png` is an exact 8-column, 4-row atlas (256 × 128).
The generator's `NAMES` list gives its row-major cell order. It supplies the
11 wall connector shapes shared by five wall families, both orientations of
open/closed doors, the empty doorway, room/corridor/engraved ground, pool/water
and featureless solid-rock/unknown cells. Padding is never assigned a game tile.

Wall ports are 12 opaque pixels wide, coordinates 10 through 21 inclusive,
with identical profiles at matching edges. Open doors swing away from a clear
floor passage; closed doors block it with a wood panel. Wall/door margins remain
transparent for the renderer's remembered-ground layer. Ground and water fill
the complete tile without transparent seams.

Rebuild and register this source, using a development Python with Pillow:

```sh
python3 assets/tiles/lantern/build_geometry.py --registry assets/tiles/lantern/sources.json
python3 scripts/test-lantern-geometry.py
```

The complete source registry and atlas are assembled separately. QA previews
are `.artifacts/lantern-geometry/individual-tiles.png` and `rooms.png`, including
both door orientations/states and joined water.
Independent final-pixel checks cover edge topology, 12-pixel stroke widths,
matching profiles, connected walls, clear open doors, blocked closed doors,
opaque ground, unframed water, and retained stone-cap contrast/detail. They do
not substitute for native-gameplay or user visual acceptance.
