# Tilesets and compatibility

Five offline tilesets are available in Display settings. Lantern Classic is the
default. Original artwork uses CC BY 4.0; NetHack Classic and NetHack-derived
catalog metadata retain NGPL. [Component terms](../LICENSES.md) distinguish artwork,
independent tools and engine-derived material.

| Set | Canonical tile size | Rendering |
| --- | --- | --- |
| Lantern Classic (`lantern`) | 64 × 64 | Raised architecture; one-square creatures and statues |
| Lantern Modern (`lantern-modern`) | 64 × 64 | Same architecture; shared stature-based creature and statue sizing |
| Soot & Brass Modern (`soot-and-brass`) | 64 × 64 | Steampunk architecture; shared stature-based creature and statue sizing |
| Soot & Brass Classic (`soot-and-brass-classic`) | 64 × 64 | Same Soot & Brass architecture; one-square creatures and statues |
| NetHack Classic | 16 × 16 | Original NetHack artwork, bounded to each square |

Within each original artwork family, Classic and Modern share identical walls,
doors, floors, objects and regional architecture. Only creature/statue display
sizing differs. Inventory and inspection portraits remain bounded in both
editions. Saved tileset identifiers remain stable; custom imports remain available.

## Ordering, sources and licensing

Every atlas follows NetHack **5.0.0 tile order**, with 40 columns and 2,304 canonical
slots. The engine uses indices 0–2302; slot 2303 is the conventional unused
invisible-monster statue. Supplemental architecture and projected frames are
selected by renderer metadata, never sent as new engine tile indices.
The renderer must use the engine-provided tile index. Glyph numbers are not tile
indices, and shuffled unidentified appearances make name-based guessing incorrect.

Source images, exact prompts, mappings, checksums and assembly records are retained
under [Lantern](../assets/tiles/lantern/README.md),
[Soot & Brass](../assets/tiles/soot-and-brass/README.md) and
`assets/tiles/regions/`. Neither original family uses third-party tileset pixels
as artwork fallback. Monster sex slots may share images; statues derive from the
corresponding creature. Complete slot coverage does not establish that every
appearance has passed live-game review.

Use the family attribution when redistributing original artwork:

> Lantern and Soot & Brass tilesets by the NetHack Atlas project, licensed under CC BY 4.0.

Include the [license link](https://creativecommons.org/licenses/by/4.0/) and indicate
changes. [Lantern's notice](../assets/tiles/lantern/LICENSE.txt) and
[Soot & Brass's notice](../assets/tiles/soot-and-brass/LICENSE.txt) define scope,
including original regional derivatives and procedural frost/Water pixels.
Independent preparation/drawing code uses MIT; NetHack Classic pixels and the
NetHack-derived appearance and creature-size catalogs retain NGPL.
[Permissions and source evidence](../assets/tiles/sources/PERMISSIONS.md),
[CC BY 4.0](../assets/tiles/sources/CC-BY-4.0.txt) and
[NGPL](../assets/tiles/sources/NGPL.txt) accompany the repository and bundle.

## Rendering contract

Original atlases opt into known ground layers and versioned architectural
metadata. The engine supplies `groundTile` from its own terrain memory; the
browser does not infer it from objects or retain a second terrain cache.
Unknown or unsupported ground has no layer. Inventory and inspection show the
subject alone. Unknown declaration versions and ordinary community imports
retain the bounded painter.

The `lanternWalls.version: 1` field is shared by both original
families, but each selected atlas supplies its own lookup tables. Door faces,
bars, corners and junctions follow displayed topology and known supporting
ground. Opening a door keeps its frame footprint; floor continues only toward
known surfaces. Full-height walls preserve their horizontal silhouette and
floor anchor as either side becomes explored. Lantern's iron bars have transparent
gaps with neutral orientation where connectivity is unknown. These appearances
never change passability, collision, item identity, visibility or turns.

`projectedFrames.version: 1` supplies explicit source rectangles, destination
offsets and depth anchors in 64-unit floor coordinates. Artwork is packed below canonical
atlas rows in the same offline PNG. The map paints known ground first, then
foreground by anchor position. Logical-square indicators stay above the artwork.
Frame overhang determines canvas padding, camera centering and inverse mouse
coordinates. Movement, targeting and inspection always use logical engine squares.

Foreground fades to 35% opacity when it obscures the hovered/targeted square, or
the hero's square when neither is active. This includes doors, walls, bars and
statues as well as creatures; the focused subject remains opaque. Optional
`occupiedSquares` records relative `[x,y]` squares with nontransparent source
pixels, preventing transparent corners from fading a neighbor. Frames without
it use rectangle overlap for compatibility. A focused projected `kind:"creature"`
only fades art painted in front of it. Cosmetic `alternates` may repeat by map
column without consulting hidden neighbors. No overlap handling invents occupants
or changes hitboxes.

## Modern creature tiers

[creature-scale.json](../assets/tiles/creature-scale.json) assigns every creature
one display tier across all original Modern artwork.
[creature_scale.py](../assets/tiles/creature_scale.py) applies its exact height,
preserving aspect ratio without width caps reducing that height. Artwork style
cannot change the assigned tier. Classic creatures remain within one square;
this policy does not apply to third-party atlases.

| Tier | Size at 64px floor pitch | Example |
| --- | ---: | --- |
| Tiny | 32px | Newt |
| Small | 48px | Goblin |
| Standard | 80px | Human |
| Large | 104px | Bone devil |
| Very Large | 128px | Balrog |
| Huge | 160px | Titan |
| Massive | 192px | Adult dragon |

The catalog records explicit assignments derived from upstream sizes, with roster
exceptions such as bulky large creatures, baby dragons and dwarves. The invisible
marker is Standard and worm-tail segments are Small. These are display tiers,
not measurements in feet. Statues use their subject's tier and scale axis.
Flat trappers and lurkers above use `scaleAxis:"longest"`, measuring the longest
image dimension instead of height; a Huge trapper is 160px wide. Tier size does
not change occupied squares or reach, and long-worm segments remain engine-owned.

## Regional materials

Optional cell `material` values come from engine level/branch identity and valid
player terrain memory. They do not change canonical `tile`/`groundTile` indices,
level generation, lighting, gameplay or saved terrain. Unknown/nothing,
swallowed and buried appearances omit regional decoration. Third-party atlases
and NetHack Classic use their canonical artwork when they lack a mapping.
The [protocol](protocol.md) is the exact routing and perception reference,
including Quest-stage tables and conservative exterior/interior classification.

| Environment | Current treatment and boundary |
| --- | --- |
| Gnomish Mines, including Minetown and Mines' End | `mines` selects reinforced rock and dirt/gravel ground. Dedicated wall slots 1471–1481 match. Minetown's `mines-built` keeps that architecture but exposes canonical stone floor only in positively remembered enclosed interiors; unknown/breached enclosures retain dirt. |
| Ordinary Gehennom | `gehennom` selects darker walls and ground for ordinary fillers. Special levels retain canonical appearance unless separately routed below. |
| Vlad's Tower | `vlad` uses darker ordinary architecture on all three floors: walls/doors/bars at 80% brightness, floors/engravings at 88%. Geometry, alpha and illumination remain unchanged. |
| Asmodeus's palace | `asmodeus` uses darker Gehennom brickwork with restrained horn-shaped corner/lintel cuts. Named-level identity selects it across the palace, passage and surroundings. |
| Valley of the Dead and Orcus-town | `valley` reuses darker Vlad masonry/doors/bars and Gehennom ground. Orcus uses the exact Valley mapping, preserving original ruined gaps, boulders, graves and shrine. |
| Caveman Quest | `caveman` uses unreinforced natural rock and quiet earth/worn-stone floors; `caveman-goal` uses smoother rock with restrained scorch marks. Existing features and occupants remain canonical. |
| Samurai Quest | `samurai` selects pale plaster, dark timber, stone bases and directional wooden gates in that role's actual Quest. Floors, water, bars and other features retain their original art. |
| Medusa | `medusa` reuses Sokoban wall slots 1504–1514 and existing earth on remembered exposed shores; positively enclosed buildings retain stone floors. All four layouts use named-level identity. |
| Juiblex | `juiblex` reuses Gehennom dry-floor slots 1291/1292 only, including safely known ground beneath occupants. Water and other features remain unchanged. |
| Baalzebub | `baalz` reuses Gehennom walls and ground with canonical doors/bars. The original fly-fortress geometry supplies identity. |
| Astral Plane | `astral` uses a pale Sokoban-derived sanctuary variant, quieter stone floors and family fittings. All three altars retain the same canonical appearance; artwork never identifies unseen alignment. |
| Plane of Earth | `earth` uses natural stone/ground within the existing engine presentation context. Digging, cave expansion/collapse and hazards remain upstream-owned. |
| Plane of Fire | `gehennom` reuses dry ground; lava, fire traps, clouds, portal and occupants remain canonical. |

Recipes, source images and hashes for original regional artwork live under
`assets/tiles/regions/`; family preparation supplies cells and metadata-only
reuse, retained in each compiled report’s `sourceEvidence`. Reused pixels retain the family artwork grant. No regional
mapping supplies a hidden room purpose, trap, portal or creature identity.

Quest compounds and natural grounds use stage-specific existing materials.
Monk sanctuaries, Priest temples/graveyards, Healer islands/compounds, Valkyrie
ice/lava stages and Wizard compounds retain their original terrain distinctions.
Archeologist, Knight, Barbarian, Ranger and Tourist also have explicit stage
routing; Tourist locate/goal streets remain paved. Samurai and Wizard compounds
use earth outside while retaining their architectural family. Rogue guilds keep
ordinary dungeon masonry and floors. `quest-earth` maps floor/corridor slots
1291/1292 to existing Caveman earth; `priest-temple` copies Valley architecture
without doorway/floor substitutions. Remembered tree-bordered Gardens also use
existing natural ground.

Exterior classification consults valid remembered terrain, with doors retained
as thresholds after opening/breaking. Unknown boundaries cannot establish an
interior; ground without a remembered exterior seed conservatively keeps stone.
The command refresh shares a transient classification map rather than persistent
frontend knowledge. Details and exact role/stage choices remain in the protocol.

The Castle retains ordinary dungeon fortifications, moat and drawbridge art.
Known lowered-drawbridge ground beneath occupants requires visible terrain or an
exact remembered bridge glyph; missing unseen orientation omits that layer.
Raised-span memory resolves underlying surfaces through upstream rules.
The Wizard's Gehennom Tower and both look-alike towers use canonical infernal
architecture, with no decoration revealing the portal-bearing entrance.
The vibrating square, invocation level and Moloch's Sanctum retain canonical
infernal terrain and special-level exclusions. Art never marks undiscovered
ritual locations, hidden entrances or remote altar information.

## Frost and moving Water pockets

All four original editions opt into version 1 of `frostWalls`. The renderer
adds restrained crown frost, icicles and edge/joint patches over the selected
wall frame, clipped by its source alpha. Geometry, depth, fittings and existing
ice-floor pixels remain unchanged. [frost_walls.py](../assets/tiles/frost_walls.py)
records alpha contours during preparation, avoiding native file-origin canvas
pixel readback. The procedural drawing definition is in `web/tiles.js`.

Only engine-supplied ice tile 1315 or known ice beneath an occupant selects frost.
Straight walls require direct ice neighbors; diagonals can reach corner caps.
Unknown cells provide no evidence. Current appearance changes remove frost;
unseen remembered ice follows NetHack memory until updated. Cached canvases hold
artwork only. Cloud rooms keep ordinary masonry and engine-controlled vapor.

The Plane of Air retains canonical open air/clouds (1322/1323), without invented
floors or platforms. Upstream disables terrain memory there, so replacement cells
and omitted ground layers must clear older detail. Unseen cells may revert to
cloud appearances rather than unexplored black.

The Plane of Water retains family water (1324). Perceived moving air pockets use
quiet blue-green interiors, a faint cyan cap and a small reflection in visible
empty air. `waterPockets` requires explicit original-atlas opt-in and Water
status. Its inward rim follows current supported AIR, not unseen bubble geometry.
Partial perception can truncate the cap. Unseen water fallback does not reveal
creatures, current bubble shape or the moving portal. The procedural artwork uses
the family CC BY 4.0 grant; drawing code retains its separate component license.
No asset sheet, regional material or engine rule changes for this treatment.

## Custom imports

The importer accepts lossless row-major PNG/BMP sheets in **5.0 order**. Width
and height must divide by the declared tile dimensions, with at least 2,304 slots.
[The import policy](TILESET-IMPORT-POLICY.md) documents file/raster/output limits,
bounded reads, startup reload, atomic persistence and failure preservation.
Geometry establishes capacity, not artwork ordering, and does not convert older
sheets. Imports omit original-family projections and regional metadata, preserve
background/alpha pixels, and retain rectangular aspect ratio. Use an artist's
original lossless file rather than a browser preview. Import presets are
convenience dimensions, not permission to redistribute unbundled artwork.

## Authoring and rebuilding

The normal app build uses checked-in PNGs. Optional tile regeneration requires
Python 3 and Pillow; players need neither. One recipe defines one selectable
entry, one complete offline PNG and one provenance report. The shared entrypoint
builds every recipe in `assets/tiles/recipes/` by default, or only the recipes
named on the command line:

The default includes NetHack Classic, whose recipe reads the checksum-pinned
`vendor/NetHack-5.0.0/dat/nhtiles.bmp`. Run `./scripts/build-engine.sh` or the
normal `./scripts/build-app.sh` once to prepare that upstream source. The tile
compiler itself does not download sources. A selected original-family or
contributor recipe needs only its retained local inputs.

```sh
python3 scripts/build-tilesets.py
python3 scripts/build-tilesets.py assets/tiles/recipes/lantern-classic.json
python3 scripts/build-tilesets.py assets/tiles/recipes/lantern-classic.json --output-dir .artifacts/tileset-review
```

An isolated output directory receives its own manifest, PNGs and provenance;
use it for contributor review before changing shipped files. IDs and file paths
must be unique. Recipe and source paths resolve from the repository root.
A recipe declares `schemaVersion: 1`, `id`, `name`, `engineVersion: "5.0.0"`,
`output` (PNG path), `provenance` (JSON path), `license`, `credit`, `licenseFile`,
`description`, `version` and `source`. Output and provenance paths are relative
to `assets/tiles/`, and `licenseFile` is a repository-root-relative path to the
retained license notice.

Use lowercase filenames with hyphens. Original paired editions follow
`<family>-<edition>.png` and `<family>-<edition>.json`, with
receipts at `<family>/<edition>-provenance.json`. For example, Lantern Classic
uses `lantern-classic.png`, `lantern-classic.json` and
`lantern/classic-provenance.json`. A standalone tileset may omit the edition and
use `<family>.png`, `<family>.json` and `<family>/provenance.json`; no matching
edition is required. Engine compatibility belongs in recipe and manifest
metadata. Check the tile catalog and ordering before an engine update; remapping,
new artwork or regeneration is needed only when relevant inputs change. Keep
registered IDs stable for saved display choices. See [AGENTS.md](../AGENTS.md) for the
recommended convention.

For an already drawn sheet, use `source.kind: "atlas"` with `path`, `sha256`, `tileWidth`,
`tileHeight`, `columns` and `count`. It needs no Python module or family adapter. An ordinary bounded
sheet can provide only canonical cells; supplemental cells and optional renderer
metadata are supported when needed. Use your own stable ID and descriptive name:
Classic/Modern names or pairs are not required. Declare `count: 2304` for a canonical-only sheet, or its full cell count when
metadata references supplemental cells. Unreferenced extra cells are removed.
The retained sheet must follow NetHack 5.0 tile order. Rectangular bounded tiles
are supported; use 64-pixel cells for projected architecture. For example:

```json
{
  "schemaVersion": 1,
  "id": "example-art",
  "name": "Example Art",
  "engineVersion": "5.0.0",
  "output": "example-art.png",
  "provenance": "example-art/provenance.json",
  "license": "CC-BY-4.0",
  "credit": "Example Artist",
  "licenseFile": "assets/tiles/example-art/LICENSE.txt",
  "description": "Original artwork in NetHack 5.0 tile order.",
  "version": "1 / NetHack 5.0.0",
  "source": {
    "kind": "atlas",
    "path": "assets/tiles/example-art/source.png",
    "sha256": "REPLACE_WITH_SOURCE_SHA256",
    "tileWidth": 64,
    "tileHeight": 64,
    "columns": 40,
    "count": 2304,
    "preferredTileSize": 64
  }
}
```

Optional `source.rendering: {"path": "assets/tiles/example-art/rendering.json",
"sha256": "REPLACE_WITH_METADATA_SHA256"}` pins a separate JSON metadata source.
Its fields use the rendering contracts above: `groundLayers`, `lanternWalls`,
`projectedFrames`, `regionalMaterials`, `frostWalls` and `waterPockets` as
applicable. Projected rectangles refer to pixels in the retained source PNG;
lookup tables refer to its row-major cell indices. `projectedFrames` has
`version: 1` and a `frames` object keyed by tile index. Each frame declares
`source: [x, y, width, height]` in source pixels, `offset: [x, y]` in 64-unit
floor coordinates, and a `depth` anchor in the same coordinates. Optional
`kind: "creature"` enables creature overlap behavior; `alternates` contains
additional frame records. The packer calculates `occupiedSquares` from alpha
and derives `padding: [left, top, right, bottom]` from the selected poses.
Include only declarations supported by the artwork. Ground, regional and overlap behavior must respect
engine perception and logical squares. The compiler preserves referenced pixels
and geometry while remapping supplemental IDs and packed source coordinates,
then recomputes frost contours for the completed PNG.

The original families use `source.kind: "prepared"`, `provider: "lantern"` or
`"soot-and-brass"`, and `creatureSizing: "grid"` or `"stature"`. Family preparation
modules retain their reviewed extraction and drawing rules. The common compiler
handles final cells, projections, metadata, PNG publication and provenance.
Each Classic and Modern entry has an independent PNG; their environmental pixels
remain identical, and only creature/statue projection sizing differs.

Every report has schema version 1 and hashed `recipe`, `compiler`, `packer` and
`inputs` records, plus `sourceEvidence`, `output`, `artworkLicense` and
`artworkCredit`. Each file record contains `file` and `sha256`; `output` also
records `width` and `height`. Source evidence retains family assignments,
extraction bounds, prompt/source hashes and regional recipes. Preparation counts
describe the source template; the manifest describes each final profile. Hashes establish
which inputs produced the output, not artwork permission or live-game coverage.
Retain an explicit redistributable license and attribution notice for new art.

NetHack Classic uses the retained upstream bitmap as its recipe source. It trims
upstream `tile2bmp`’s empty trailing scanlines while preserving the 2,304 slots.
The pinned engine mapping has `maxmontile=788`, `maxobjtile=1271`,
`maxothtile=1514` and `total_tiles_used=2303`.

Use [the shared preview](../tools/tileset-preview/index.html) for every new tileset.
Its selector reads the compiled manifest automatically. Reuse the actual game renderer, room, crowding,
three-largest-creature, four-sided-door, bar, shared-wall and ice scenes, zoom
controls and catalog. Keep Classic/Modern comparisons. The largest-creature
scene uses shared tier heights and stable catalog order for ties; the seven-tier
scene uses one representative per tier. Base fixtures require no generated test
artifacts. Optional `?capture=<name>` views load a local
`.artifacts/<name>-review-manifest.json` produced by a maintained capture builder.

These are illustrative fixtures or recorded captures. Follow visual review with
real-engine and packaged-native checks for gameplay changes. Record results and
limits in [VERIFICATION.md](VERIFICATION.md), and use
[environment playtests](ENVIRONMENT-PLAYTESTS.md) for targeted disposable games.
