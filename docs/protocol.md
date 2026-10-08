# Engine bridge protocol (v1)

NetHack 5.0.0 runs as a child process. stdin is UTF-8 line commands; stdout is UTF-8 JSON Lines. stderr is diagnostics. Host sets cwd and NETHACKDIR to a writable per-player runtime directory populated from engine/runtime. Launch `nethack -u NAME -p ROLE -r RACE -@`; set `NETHACKOPTIONS=gender:GENDER,align:ALIGNMENT,color,hilite_pet,!autopickup,time,!news`. For randomized facets omit that argument/option. `-@` fills unspecified facets randomly. Unix shim does not accept `-d`, `-g`, or `-a`; cwd sets the data directory. Existing saved game for NAME restores automatically. Set NETHACKOPTIONS to the desired options (e.g. `color,hilite_pet,!autopickup`). No external dependencies needed.

## Text encoding

All output JSON strings preserve valid UTF-8 sequences, including ordinary
pet and object names. Quotes, backslashes, ASCII control bytes and DEL are
JSON-escaped. Each malformed UTF-8 byte is emitted as `\ufffd` (U+FFFD),
including isolated continuation bytes, truncated sequences, overlong encodings,
UTF-16 surrogates and values above U+10FFFF. This policy keeps every emitted line
valid UTF-8 JSON without guessing a legacy byte encoding. NUL still terminates
engine C strings. Upstream mixed-glyph escape processing remains responsible
for actual glyph escapes; the JSON serializer does not interpret them. Upstream
name normalization, byte-length limits and native player-name restrictions are
unchanged.

## Interface bridge

The interface sends each action object to its host through one function. If
the host supplies `window.atlasHost`, the interface calls
`window.atlasHost.postMessage(action)`. The Electron preload supplies this
object. Otherwise, the interface calls
`window.webkit.messageHandlers.nethack.postMessage(action)`, the Mac host
handler. Every host delivers events by calling `window.receiveNative(event)`
with one event or an array of events.

With `window.atlasHost`, the interface uses Ctrl+K for the action list and
Ctrl+S for save and exit, and its labels show Ctrl. With the Mac handler,
these shortcuts use Command. A browser preview without a host uses Command on
a Mac and Ctrl elsewhere. NetHack binds neither Ctrl+K nor Ctrl+S. The
interface sends every other Ctrl key to the engine as a control character.

The Electron host in `electron/` loads the interface from the `atlas://app/`
scheme. That scheme serves only `web/` and `assets/`, with a content security
policy that allows only the same origin and `data:` and `blob:` images. The window uses
context isolation and a sandboxed renderer. The host blocks navigation, new
windows and permission requests. The main process accepts only the 13 Mac
actions (`ready`, `diagnostic`, `start`, `load`, `key`, `command`, `input`,
`position`, `menu`, `inspect`, `save`, `importTileset` and `showSaveFolder`)
with the Mac limits, and only from the main frame of that page. It delivers
events in batches through `window.receiveNative`. The data folder is
`NetHack Atlas/5.0` under the per-user application data folder, and
`ATLAS_DATA_DIR` replaces it. With `ATLAS_DATA_DIR`, the browser profile and
the single-instance lock move to a sibling folder that ends in `-electron`.
`--self-test` reads the same `ATLAS_TEST_` variables, `ATLAS_DIAGNOSTICS` and
`ATLAS_SNAPSHOT` as the Mac host and uses non-persistent web storage.

## Host → engine

### Play mode and native UI messages

Character creation sends `{action:"start", name, role, race, gender, alignment, mode, nudist, blind, deaf, noStartingPet}` to the native host. `mode` is `standard` (the default if omitted), `beginner`, `explore` or `pauper`; other values are rejected. The four start choices are optional Booleans. Nudist is available in Standard, Beginner and Explore; Pauper implies it. Blind, Deaf and No starting pet are available in every mode. Continue sends `{action:"load", name, mode}` using the selected save's identity, not the creation selector. A requested missing save is rejected rather than silently loading another adventure.

Native `boot.savedGames` and `exit.savedGames` contain `{name,mode}` entries. The renderer also accepts legacy name strings as Standard. Native `started` includes the resolved `name` and `mode`, which controls the in-game badge and guide. These are native/UI messages, not gameplay commands. A self-test boot additionally supplies `testMode` to exercise each creation path.

Standard launches use the existing runtime root. Beginner uses its `Beginner/` child directory; Explore uses `Explore/`; Pauper uses `Pauper/`. The host explicitly sets `ATLAS_PLAY_MODE` to the selected mode along with `cwd`, `HOME`, `NETHACKDIR`, and `HACKDIR` for that runtime. Startup prepares and recovers all four namespaces independently. Saves, bones, scores, logs and locks never share directories between modes; existing Standard saves are not moved or converted.

Explore launches also pass upstream `-X`, including restores. During runtime preparation, the host authorizes `EXPLORERS=*` only in the Explore sysconf; it preserves other entries and does not modify Standard or Beginner sysconf. The engine owns the starting wand of wishing, optional death refusal, keep-save choice, saved discovery flag and exclusion from the high-score list. `ATLAS_PLAY_MODE=explore` alone does not enable engine discovery mode.

For a new Pauper game, the host adds upstream `pauper` to `NETHACKOPTIONS`. NetHack owns the empty starting inventory, absence of spells and initial skill training, conduct, and normal scoring and death. Pauper implies nudist in the engine. The host does not reapply the option on restore; the saved game retains its starting state. The separate `Pauper/` runtime has no Explore authorization or Beginner chest.

For a new Standard, Beginner or Explore game with `nudist:true`, the host adds upstream `nudist` to `NETHACKOPTIONS`. NetHack omits starting armor and tracks the conduct; wearing armor later ends it. Pauper already implies Nudist. The host adds upstream `blind`, `deaf` and `pettype:none` for the corresponding true start choices in any mode. Blind and Deaf are permanent birth conditions. `pettype:none` suppresses only the initial pet; later taming remains possible. These options are applied only to new games, so restore and recovery retain the saved engine state. Blindness limits map cells and inspection to what the character perceives, including hiding the Beginner chest until discovered through play.

Only `newgame()` reads the exact `beginner` value to create the supply chest. Its contents are 1,000 gold, one identified uncursed magic whistle, two uncursed food rations, and one identified uncursed potion of healing. The chest is uncursed, unlocked and untrapped on nearby reachable room floor away from stairs, named `Beginner supplies`. Normal engine menus handle looting and counts; the frontend does not grant or select items automatically. No save-format change or per-turn grant mechanism is involved, and restore/recovery cannot replenish the chest. Normal permanent death remains enabled. Placement prefers empty reachable floor in the starting room, avoiding traps, boulders, monsters and existing objects. If no empty square is available, ordinary object piles or a tame pet can share the square; reachable room or corridor floor outside the starting room is a final fallback. Stairs and other terrain features are never used. An explicit message reports the exceptional case of no safe floor. The normal engine redraw reveals the chest only when visible. Move onto it to use Loot container; existing saves keep their original chest position.

### Gameplay input

- `key INTEGER`: NetHack byte value (Escape=27, Return=10). Movement controls use the engine-advertised direction bindings. Literal `S` invokes whatever command the player has bound to that key.
- `position X Y`: choose a map location at a `targeting:true` wait. The native `{action:"position", x, y}` message becomes this response. The port accepts in-bounds coordinates only during upstream `getpos`, returns a normal mouse-selection event, and ignores stale/out-of-context or invalid coordinates. This is never a movement command.
- `line TEXT`: response to line prompt. Empty permitted; Escape uses `line ESC` where ESC is the actual escape byte.
- `menu ID[:COUNT],ID[:COUNT]`: selected zero-based row ids; COUNT defaults -1 (all). Empty confirms no selections. `menu cancel` cancels.
- `save`: unwind pending prompts, resolve the engine's named `save` command at the next command boundary through its current binding or the extended-command path, confirm only the engine save prompt, and dismiss save completion. The process exits after successful saving. Rebinding `S` does not change this operation. If neither Save nor extended commands have a binding, the request emits `commandRejected` and the game stays live. A refused or failed save does not auto-confirm a later manual save. Upstream owns cancellation and committed-action semantics; this request does not roll back actions already taken.
- `inspect X Y`: describe an already displayed cell with NetHack's own visible/remembered appearance. Works during any input wait without spending a turn.

## Engine → host

- `{"type":"hello","version":"5.0.0","protocol":1,"width":80,"height":21}`
- `{"type":"cell","x":1,"y":0,"tile":123,"glyph":123,"char":".","color":7,"pet":false}`: incremental cell drawing, x 1..79 and y 0..20; tile indexes use generated official 5.0 ordering.
  Optional `groundTile` supplies a canonical tile index for a safely known ground
  surface beneath the foreground. Each `cell` replaces the entire previous cell:
  omission removes any previous ground layer or material. Optional `material`
  identifies an engine-selected visual region (`"mines"` for the Mines branch,
  `"mines-built"` for remembered finished Minetown interiors,
  `"gehennom"` for ordinary Gehennom filler and the Plane of Fire, `"vlad"` for Vlad's Tower,
  `"asmodeus"` for Asmodeus's lair, `"valley"` for the Valley of the Dead, `"caveman"` / `"caveman-goal"`
  for the Caveman Quest and its goal level, `"juiblex"` for Juiblex’s lair, `"baalz"` for Baalzebub’s lair, `"medusa"` for Medusa's level, `"samurai"` for the Samurai Quest,
  `"earth"` for the Plane of Earth, `"astral"` for the Astral Plane, or `"quest-earth"` / `"priest-temple"`
  for the remembered exterior/interior Quest treatments described below).
  It does not change the canonical `tile` or `groundTile` indexes. The foreground fields retain their
  original meaning, including perceived appearances and pet markers.
- `{"type":"clear","window":"map"}`
- `{"type":"cursor","x":1,"y":0,"playerX":2,"playerY":0}`: map cursor and actual hero coordinates, which differ during location selection.
- `{"type":"message","text":"…"}`
- `{"type":"status","field":0,"name":"title","value":"…","percent":100}`; status values strings; condition is a numeric bit mask encoded as string. statusFlush marks batch completion.
- `{"type":"statusFlush","experience":{"level":2,"points":25,"start":20,"next":40}}`: completes the status batch and provides authoritative hero XP and level thresholds from `newuexp()`. `next:null` means the maximum level. This snapshot is independent of `showexp` and polymorph status-field visibility. The renderer measures progress as `(points-start)/(next-start)`, clamped to 0–100%, and displays total points and the next total threshold.
- `{"type":"input","kind":"key","command":true}`: await ordinary gameplay command. `command:false` denotes More, direction, or targeting input; it is not a gameplay command boundary.
- `{"type":"input","kind":"yn","prompt":"…","choices":"ynq","default":"n"}`: respond with key; choices may be empty (any key).
- `{"type":"input","kind":"line","prompt":"…"}`
- `{"type":"input","kind":"menu","prompt":"…","how":1,"items":[{"id":0,"text":"…","key":"a","group":"…","selectable":true,"selected":false,"tile":123}]}`; how 0=display only, 1=single, 2=multiple. Respond with menu command, including display-only.
- `{"type":"input","kind":"text","prompt":"…","lines":["…"]}`: modal text; any key dismisses.
- `{"type":"inspect","x":1,"y":0,"text":"…"}`. Optional
  `beneath:{"name":"Throne","remembered":false}` supplements an occupant's
  description with an already-known throne. It comes only from upstream
  `lastseentyp`, requires displayed/perceived terrain or valid hero memory, and
  is omitted for unexplored/nothing/swallow glyphs, burial and swallowing.
  Unseen remembered squares set `remembered:true`; the UI labels that distinction.
  An unobscured throne needs no duplicate detail. This field is inspection-only:
  it neither adds a map layer nor changes sitting, targets or turns. Omission
  clears any prior detail; the UI must not retain a separate terrain memory.
- `{"type":"exit","text":"…"}`

During an explicit development playtest report, the host annotates exit events
with `reason:"playtest-report"`. The successful process-completion event receives
the same reason only when a save exists. The UI keeps the map visible and shows
a report-saving status instead of ending the adventure; native report capture
then restores the saved game. Ordinary exits and failures retain their normal
handling. This host-only annotation changes no engine gameplay or save format.

The host must queue engine events in order and never send gameplay keys while a menu/line prompt is active. Rendering events may occur before hello if upstream initialization emits a message. Unknown event types should be ignored.

## Remembered ground layers

`groundTile` is an optional visual surface, not a second source of game state.
The window port derives it from NetHack's `svl.lastseentyp` (last seen or touched
terrain), remembered `waslit`, and current visibility. NetHack already persists
this memory with each level and restores it from existing saves. The port does
not read live terrain types, door flags, stair directions, altar alignments,
hidden traps, or object stacks to construct this field. It deliberately ignores
the upstream background-glyph argument, which uses current terrain and omits
ordinary room floors.

Supported remembered surfaces are room floor, corridor, ice, pool/moat, water,
lava, lava wall, air and cloud. Known stairs, ladders, doors, fountains, sinks,
altars, graves, thrones and iron bars receive a decorative room floor; this does not infer
their orientation, alignment, contents or current condition. Secret doors,
walls, unknown ground and unsupported topology receive no ground field.
Unseen cells require both level memory and a remembered seen-vector, except
that the hero's known touched location can supply the latter. No ordinary ground
is supplied for unexplored/nothing foregrounds, swallowing or burial. A sensed
creature on unexplored ground therefore does not reveal a floor. Dark remembered
rooms and corridors follow the engine's remembered-lighting options.

Normal glyph events include the current surface. At command input boundaries,
the port also checks already displayed cells and re-emits only those whose
surface changed. These events retain the exact previously emitted foreground;
they do not spend a turn, query undiscovered entities, or create an independent
terrain memory. Clearing the map clears this rendering cache.

The original Plane of Air disables hero terrain memory. Visible supporting air
and clouds use canonical indexes 1322 and 1323, without room-floor substitution
or a regional material. When upstream replaces a previously visible occupant
or portal with a cloud or air fallback, the replacement cell removes its old
foreground and any omitted ground layer. Cloud fallback is an upstream display
behavior, not evidence of a currently seen cloud or retained terrain knowledge.
The interface must not preserve earlier details alongside that replacement.

The original Plane of Water also disables hero terrain memory. Its canonical
water (1324) and air-pocket (1322) appearances use the same supporting-layer
contract. Upstream supplies water as the unseen background for this plane;
that foreground alone does not establish current perception or justify a
`groundTile`. Moving bubbles carry occupants, objects and traps, including the
portal. At stable command boundaries, replacement cells must remove obsolete
air/support and occupant detail. Blind or engulfed views omit outside support.
No regional material, fixed bubble boundary or independently tracked portal
position is supplied by the interface.

Original atlases may opt into `waterPockets:{version:1}`. The renderer enables
it only for the engine's `dungeon-level` status value `Water` (trimmed), never
from a playtest label or an AIR glyph alone. Current `groundTile:1322` support
defines a transient cap clip and its inward optical contour. Missing neighbors
are never classified as WATER; the contour styles only already-disclosed AIR.
It is not a reconstruction of the complete physical bubble perimeter.
Cloud and poison-cloud appearances (1323/1390) are excluded from this visible
clip: upstream regions may obscure a last-known AIR surface without refreshing
it. The renderer does not substitute actual hidden terrain beneath that gas. Quiet cyan
shading and an empty-air glint paint before occupants and preserve their
opacity. Every redraw rebuilds the clip from supplied cells, without a shape
cache, extra terrain lookup, input or turn. The shared frozen preview explicitly
sets Water context only for its Water study. Imported atlases without the
capability, ASCII, portraits, and the Plane of Air retain existing rendering.

Layer-capable tilesets draw this surface before the original foreground tile.
Opaque artwork remains opaque; this protocol does not authorize chroma-keying
imported art. ASCII, inventory icons and inspection icons can retain their
foreground-only presentation. Missing fields remain compatible with older
recorded transcripts and tilesets.

## Regional materials

A cell may contain `"material":"mines"` when the current level is in the
Gnomish Mines (`In_mines(&u.uz)`), including Minetown and all Mines' End
layouts. The Mines check precedes the generic named-special exclusion.
Original artwork families use the approved rock/support walls and dirt/gravel
floors throughout the branch. Dedicated wall slots 1471 through 1481 also
carry the approved rock artwork as a canonical fallback. The engine's tile
indices, terrain, lighting and gameplay remain unchanged; this extends the
existing presentation context without a new field. Named Minetown floors may
use `"material":"mines-built"` when remembered terrain positively establishes
a rectangular enclosed room. That mapping retains Mines walls/supports and
restores canonical stone floors. Streets, caves and uncertain enclosures retain
Mines dirt; no hidden shop, temple or room-purpose flags are read.

`"material":"gehennom"` identifies an ordinary Gehennom filler level
(`In_hell(&u.uz)`, `!Is_special(&u.uz)`, and `!Invocation_lev(&u.uz)`).
The actual Plane of Fire (`Is_firelevel(&u.uz)`) also reuses this existing tag
and artwork for its dry ground. Its canonical lava, fire traps, clouds, portal,
objects and creatures remain unchanged. Selection uses level identity after
the unknown, buried and swallowed guards, never hidden cell or portal data.
Other named special levels, including demon lairs, Wizard's Tower floors and decoys, Sanctum,
and the invocation approach remain excluded. The five Wizard/decoy maps deliberately retain canonical Gehennom wall slots 1482 through 1492 and receive no identity-specific material; their artwork must not distinguish the portal-bearing entrance from the decoy. The test uses only level identity;
it never queries the vibrating square or undiscovered features. Generated cold,
lava, bar-walled and cavernous filler levels share the same regional context.
Their actual terrain indexes remain authoritative; the tag does not turn ice,
water, lava or bars into stone.

`"material":"vlad"` identifies the actual Vlad's Tower branch
(`In_V_tower(&u.uz)`), including all three named tower floors. It is checked
before the general special-level exclusion. It does not apply to the Wizard's
Tower, its decoys, or the Gehennom level outside the tower entrance. The tag
only selects the approved darker regional artwork; ladder, stair, door, throne,
wall and floor indexes retain their upstream meanings and gameplay behavior.

`"material":"asmodeus"` identifies the actual named Asmodeus level
(`Is_asmo_level(&u.uz)`), also before the general special-level exclusion.
It applies to the whole level, including the palace, passage and surrounding
maze. It is not inferred from walls, occupants, room bounds or the presence of
Asmodeus. Other demon lairs and ordinary Gehennom filler remain separate.
The original Gehennom wall indexes 1482 through 1492, doors, stairs, lava and
all other terrain retain their upstream meanings. The tag selects the approved
dark palace masonry and restrained ornament without inventing floor surfaces
or changing terrain, lighting, movement or perception.

`"material":"valley"` identifies the actual named Valley of the Dead
(`Is_valley(&u.uz)`) or Orcus-town (`on_level(&u.uz, &orcus_level)`),
before the generic named-special exclusion. Its single
level-wide material uses approved darker family masonry, doors and bars with
existing Gehennom ground. It is not selected from morgue or temple room bounds,
occupants, graves or the altar. Original canonical indexes and engine lighting,
perception, movement, corpses, digging and stair rules remain authoritative.
Unknown/nothing/swallow appearances and swallowed/buried views receive no tag.

`"material":"caveman"` identifies the Caveman role's actual Quest branch
(`Role_if(PM_CAVE_DWELLER)` and `In_quest(&u.uz)`). Home, upper filler,
locate and lower filler share this natural-cave treatment. On that role's
actual nemesis level (`Is_nemesis(&u.uz)`), the tag is `"caveman-goal"`
for the polished, scorched cavern treatment. These checks precede the general
special-level exclusion and use persistent role and level identity, not the
hero's current polymorph form, occupants, quest completion, room shape or
hidden terrain. The goal tag persists after the nemesis dies. Other roles'
Quest levels receive no `caveman-goal` tag; the stage reuse below may select
`caveman`. The Caveman's Dungeons of Doom levels receive neither tag. Lit pockets, darkness, secret doors, shrines, stairs and
traps retain
their canonical indexes and all upstream behavior.

The same shipped materials are also reused by persistent Quest role and stage
identity. Material names identify artwork treatments, not exclusive geography.
These rules precede the generic named-special exclusion:

| Quest role | Home | Upper filler | Locate | Lower filler | Goal |
| --- | --- | --- | --- | --- | --- |
| Monk | exterior `quest-earth`, interior canonical | canonical | `caveman` | canonical | `gehennom` |
| Priest | exterior `quest-earth`, interior canonical | canonical | exterior `quest-earth`, other known cells `priest-temple` | canonical | `gehennom` |
| Healer | exterior `quest-earth`, interior canonical | `caveman` | exterior `quest-earth`, interior canonical | `caveman` | `caveman` |
| Valkyrie | canonical | `caveman` | `caveman` | `gehennom` | `baalz` |
| Wizard | exterior `quest-earth`, interior canonical | canonical | exterior `quest-earth`, interior canonical | canonical | canonical |
| Archeologist | exterior `quest-earth`, interior canonical | canonical | exterior `quest-earth`, interior canonical | canonical | canonical |
| Knight | exterior `quest-earth`, interior canonical | `caveman` | `caveman` | `caveman` | `caveman` |
| Barbarian | exterior `quest-earth`, interior canonical | `caveman` | exterior `quest-earth`, interior canonical | `caveman` | `caveman` |
| Ranger | known dry ground `quest-earth`, other cells canonical | known dry ground `quest-earth`, other cells canonical | `caveman` | `caveman` | `caveman` |
| Tourist | exterior `quest-earth`, interior canonical | `caveman` | canonical | `caveman` | canonical |
| Samurai | exterior `quest-earth`, other known cells `samurai` | `samurai` | exterior `quest-earth`, other known cells `samurai` | `samurai` | `samurai` |

Built sanctuaries retain stone floors. `quest-earth` maps only ordinary floor
and corridor ground to existing natural earth artwork. `priest-temple` retains
Valley architecture around the Priest locate shrine, with canonical stone floors.
Natural passages and islands use unreinforced cave ground; Priest graveyards
use earth ground outside and Valley masonry;
lava fields use Gehennom ground. Valkyrie's fire-giant fortress reuses the
Baalzebub treatment, including ordinary wall aliases to existing Gehennom walls.
Wizard Quest is distinct from the Wizard's Gehennom Tower. Its actual clouds,
water and lighting establish the setting without another material context.
Selection uses `Role_if`, `In_quest`, `Is_qstart`, `Is_qlocate`, `Is_nemesis`
and the persistent locate depth. A four-way traversal of valid upstream terrain
memory (`lastseentyp` with remembered visibility evidence) marks dry ground
connected to known map edges, trees or water as exterior. A second traversal
recognizes positive enclosure, including indoor pools, which takes precedence
over an exterior water seed. Unknown terrain, walls and door thresholds stop
traversal, including open or broken doors. Rectangular Minetown enclosures also
require remembered perimeter corners. Classification is reconstructed after
restoration; no save format or persistent cache changes. With insufficient
remembered evidence, Quest ground retains stone and Minetown retains dirt.
No hidden room flags, current unseen terrain or occupants establish a surface.
Ordinary non-special Dungeons of Doom dry-ground components bordering remembered
trees also reuse `quest-earth` for Garden ground; water alone does not select it.
Unknown/nothing/swallow appearances and swallowed/buried views receive no context.
Canonical tiles, lighting, support ground and gameplay remain unchanged. Imports
without optional mappings retain canonical artwork.

`"material":"samurai"` identifies the Samurai role's actual Quest branch
(`Role_if(PM_SAMURAI)` and `In_quest(&u.uz)`), across home, both fillers,
locate and goal. Selection uses persistent role and branch identity, not the
hero's polymorph form, occupants, room purpose, quest progress or hidden terrain.
The approved atlas substitutes constructed wall and door artwork only. Canonical
pools/moats, stairs, traps, items and actors remain unchanged. Home/locate
exterior floors additionally reuse `quest-earth` as described above. In
particular, the upper filler's actual pool terrain is not classified as mine
walls just because its Lua generator uses the `mines` style. Other roles' Quests
and the Samurai's ordinary dungeon levels receive no Samurai tag. The normal
unknown/nothing/swallow and swallowed/buried protections apply. This adds a value
to the existing optional field; imported tilesets without Samurai metadata use
ordinary fallback artwork.

`"material":"earth"` identifies the actual Plane of Earth
(`Is_earthlevel(&u.uz)`), before the general special-level exclusion. Air,
Fire, Water and Astral do not receive the Earth tag. Selection depends only on
level identity, with the same unknown/nothing/swallow and buried protections
as the other materials. The four original editions alias their existing
ordinary Caveman material maps exactly for this playtest direction. Stone
index 1272 is not remapped: blank rock and dark remembered appearances retain
their canonical presentation. Excavated corridors, cave changes, boulders,
the portal and occupants retain upstream terrain and gameplay meanings.
This adds a value to the existing optional `material` field, not a new field.
Imported or older tilesets without Earth material metadata use ordinary
fallback artwork.

`"material":"astral"` identifies the actual Astral Plane
(`Is_astralevel(&u.uz)`), before the general special-level exclusion. It
selects the approved pale sanctuary architecture and floors in original
artwork families. All three temples receive the same treatment. Selection
uses persistent named level identity, never altar alignment, priest deity,
room purpose, occupants or undiscovered terrain. Foreground tile and glyph
indexes, known supporting ground, lighting and upstream altar descriptions
remain unchanged. The existing unknown/nothing/swallow and swallowed/buried
guards omit the tag. This is an additional value of the optional field;
imported or older tilesets without Astral mappings retain canonical artwork.

These tags are level context, not a query of cell terrain, objects, occupants,
lighting, or connectivity. No tag promises that a wall is diggable. The engine
omits them for unexplored/nothing/swallow appearances and while swallowed or buried.
Sensed occupants can carry the level tag without receiving a `groundTile`.

The port stores material with each displayed cell. Command-boundary refresh
re-emits a cell if its known ground or material changes, retaining the exact
foreground appearance. Clearing the map discards the displayed-cell cache.
Clients must replace the whole cell, including removal of an omitted material;
no material is inferred from neighboring walls or retained across levels.

An atlas can opt in with
`regionalMaterials.mines = {tileMap: {canonical: supplemental}, wallTiles: {canonical: entry}}`.
`regionalMaterials.gehennom`, `regionalMaterials.vlad`,
`regionalMaterials.asmodeus`, `regionalMaterials.valley`, `regionalMaterials.caveman`,
`regionalMaterials["caveman-goal"]`, `regionalMaterials.samurai` and
`regionalMaterials.earth`, `regionalMaterials.juiblex` and
`regionalMaterials.baalz` use the same shape
for their corresponding level tags.
`tileMap` substitutes artwork for safely supplied foreground/ground indexes in
the map. `wallTiles` is optional; Vlad keeps the original wall rules and maps
their selected variants. When present, `wallTiles` entries follow the `lanternWalls.tiles` shape, including
canonical topology and supplementary variant indexes. Their projected frames
remain in the atlas's ordinary `projectedFrames.frames` table. Wall topology,
neighbor surface masks, and ground-pass classification always use the original
engine indexes. Regional wall lookup uses each cell's own material; doors and
bars keep their normal metadata. After selecting a directional wall, door or
bar variant, the renderer applies `tileMap` to that selected index once. Vlad
uses this to retain all original poses and joins with darker supplemental art.
Supplemental indexes are not recursively remapped. Missing material, unknown material, absent atlas metadata, or invalid
supplemental pixels fall back to the ordinary artwork. Inventory and inspection
portraits remain canonical. Classic and Modern members of an original family
share regional architecture; their creature sizing policy is unchanged.

## Feedback before decisions

The renderer accumulates ordered `message` events during an action and shows them inside subsequent modal inputs. It resets this context at the next `input` with `kind:"key", command:true`, not between intermediate choices, text acknowledgments or naming prompts. Text is inserted using `textContent`, without interpreting effects or guessing item identities. Up to 300 recent messages are retained, matching the journal bound. The current prompt is not repeated in the context panel. The existing gameplay event/response contract is unchanged. Effects that the engine emits after an answer remain after that answer; the renderer never advances turns or anticipates outcomes to populate a prompt.

The opt-in native test scenario `prompt-messages` loads an isolated saved fixture and checks live Read/Quaff effects before answering three naming prompts. Its boot `testScenario` value is populated only for `--self-test` launches.

## Runtime and recovery

Set `HOME` to the app's writable data directory to isolate user configuration. Keep `checkpoint` enabled. Bundle immutable `nethack`, `recover`, `nhdat`, `license`, `symbols`, and `sysconf`; create writable `save/`, `perm`, `record`, `logfile`, and `xlogfile` per runtime. The shipped binaries are Universal 2 (arm64 and x86_64), have a macOS 13.0 minimum deployment target, and link only system libSystem; Lua is static.

`sysconf` sets MAXPLAYERS=0, so checkpoints use `<uid><regularized-player-name>.0`. The first four bytes contain the owning PID as a native-endian signed 32-bit integer. Never recover a live process's checkpoint. For a confirmed stale checkpoint, run bundled `recover BASENAME` from its runtime directory (omit `.0`). On success, launch normally to restore the reconstructed save. Closing stdin also invokes NetHack's deferred safe hangup save. Do not forcibly terminate a live process as the normal quit path.

Most output is JSON, but upstream fatal startup errors may be plain text on stdout; surface such lines as diagnostics. An engine exit before receiving `hello` is a launch failure. `exit` is an engine window-port notification; the child process termination remains authoritative.

### Windows engine launch

The JSON events and input commands are the same on Windows. The launch and the
runtime folder are different:

- Upstream Windows NetHack ignores `HOME`, `NETHACKDIR` and `HACKDIR`. Each
  runtime folder holds its own `nethack.exe` and `recover.exe`. Its `sysconf`
  contains `PORTABLE_DEVICE_PATHS=1`, which keeps every file in that folder.
  Startup also needs `sysconf.template`, `symbols.template`,
  `nethackrc.template`, `Guidebook.txt`, `opthelp` and `nhdat500` there.
- Launch `nethack.exe -u NAME`. Add `-X` for Explore. Upstream Windows does not
  read `-p`, `-r` or `-@`.
- Write the options to `atlas.nethackrc` in the runtime folder as one
  `OPTIONS=` line. Include `role:` and `race:`, and use `random` for a facet
  that the player did not choose. Then set `NETHACKOPTIONS=@atlas.nethackrc`.
  Windows reads the options twice. Option parsing writes into the
  environment value, so a plain `NETHACKOPTIONS` list keeps only its first
  option. The file name must be shorter than 128 characters, so use the
  relative name.
- The checkpoint is `NAME.0` in the runtime folder, with no user ID prefix.
  Its first four bytes hold the Windows process ID. The save is
  `NAME.NetHack-saved-game` in the same folder. Run `recover.exe NAME` from
  the runtime folder.
- Upstream Windows allows debug mode only for a player named `wizard`, and
  ignores `WIZARDS`. The Atlas Windows patch allows Explore mode only when
  `sysconf` contains `EXPLORERS=*` (ADR 0001). With `number_pad` on, the letter direction keys stay bound
  beside the digits. The command catalog reports the bindings that the engine
  really uses.

## Verification

Run `python3 scripts/test-engine.py`. This uses the bundled game engine and data in a temporary runtime, tests new game, actual movement, turn-free hover (including unexplored cells), inventory, manual save, exact turn/position restoration, automatic save from inventory and direction prompts, stdin EOF save, and SIGKILL checkpoint recovery. It writes `.artifacts/game-events.json` containing an actual playable game's rendering events for frontend visual QA. The Intel slice is built and its Mach-O architecture/deployment target checked; executing Intel gameplay still requires an Intel Mac or Rosetta and was not tested on this host.

Quantity prompts advertise `#` among `yn` choices. Accept `#` or a digit to open a line input with `purpose:"count"` and a string `default` containing an initial digit when supplied. Return the full integer using `line N`; zero means no items, positive values use upstream `yn_number`, and Escape cancels back to the original choice prompt. Invalid yes/no responses re-emit the same `input` event. Invalid numeric responses re-emit the numeric line input rather than leaving the frontend waiting.

The native `Recovery.recoverInterruptedGames(in:using:)` helper verifies owner PID, reconstructs saves from checkpoint copies in a private staging directory, publishes only successful results, and retains originals under `Recovered Checkpoints/`. `python3 scripts/test-recovery.py` compiles that helper and verifies live-process exclusion, real interrupted-game restoration, checkpoint retention, and incomplete-file handling.

## Direction and location selection

`input` events from the yes/no window callback and positional-key callback now carry `direction` and `targeting` booleans derived from NetHack's own input context, not English prompt matching:

- `direction:true` means NetHack is asking for an adjacent, vertical, or self direction. It normally accompanies `kind:"yn"`, with empty `choices`. Casting directional spells, zapping wands, throwing, kicking, opening, and closing use this path. Keep the map visible while collecting the response.
- `targeting:true` means keys move the location-selection cursor rather than the hero. It accompanies `kind:"key", command:false`. A map click, Enter or the Select button chooses a location through `position X Y`; period retains its upstream selection binding, and Escape leaves selection. Arrow and diagonal navigation keys use `directionKeys`. The map stays undimmed with a selection bar and a visible white cursor. This context is distinct from the direction prompt, where period usually means self.
- `directionKeys` contains the actual current engine key bindings in this precise order: **west, northwest, north, northeast, east, southeast, south, southwest, down, up**. Defaults are `hykulnjb><`; numeric keypad mode is `47896321><`, and telephone keypad mode is `41236987><`. Map arrows/compass controls through this string instead of assuming alphabetic keys. The field is also present on ordinary positional-key waits.
- `selfKey` contains the current primary self-direction key when `direction:true` (default `.`). The standard alternate is `s`; use the explicit primary binding for a self button.

Direction choices still reach the engine as `key INTEGER`. The engine decides whether a particular action supports self or vertical direction. Escape is forwarded unchanged; it must not be described as undoing an action. In particular, upstream NetHack 5.0 can already have committed spell energy before asking for direction, and escaping that prompt releases the spell using its prior/self direction. The integration preserves this game behavior.

The engine regression suite verifies a real Wizard's directional force-bolt prompt and downward casting, kick prompts, absence of direction flags on ordinary confirmations, distinct farlook cursor selection without a turn, and actual keypad-mode bindings.

`cursor` events carry `x`/`y` for the engine cursor and separate `playerX`/`playerY` for the actual hero. Moving a location-selection cursor must not move the renderer's hero marker or change its movement origin. The UI restores map focus on every targeting wait and preserves action feedback through selection.

`python3 scripts/test-targeting.py` tests real kitten naming with coordinates and keyboard bindings in normal, numeric and telephone keypad modes, cancellation without time or movement, rejected stale/invalid coordinates, farlook, and saving during selection. Its `--native` scenario exercises the Name pet button, monster choice, map click, arrow/diagonal keys, Enter and Escape in the packaged app. `ATLAS_TEST_NUMBER_PAD` selects modes 0, 1 or 3 only on `--self-test` launches; the scenario asserts the actual advertised bindings.

## Action catalog and named commands

At the first gameplay command wait, and after a keybinding/movement-mode or
wizard-mode change, the engine emits:

```json
{"type":"commands","commands":[{"name":"kick","description":"kick something","keys":["Ctrl+D"],"prefix":false,"movement":false,"selectable":true}]}
```

The catalog comes from this engine's actual extended-command table and active
key bindings. It includes movement, prefixes and unbound commands; excludes
internal, compile-time unavailable and (outside wizard mode) wizard-only
commands. `keys` are display labels, not bytes to send. Empty keys mean no key
is currently bound. A `selectable:false` row is reference-only, notably `toggle`,
which requires a parameter supplied by a particular key binding. Descriptions
explain actions, not whether the current character has the equipment or ability
to succeed. The engine still decides availability in the current situation.

Send `command NAME` with an exact catalog name only at an advertised
`input` with `kind:"key", command:true`. The port returns the current bound key
through NetHack's ordinary command parser, or supplies the named extended
command through the currently bound extended-command key. It never calls game
command functions directly. Prefix actions continue to request the next command;
normal confirmations and direction prompts are preserved.

An unknown, unavailable or out-of-context request emits
`{"type":"commandRejected","name":"...","text":"..."}` and leaves the
existing input wait intact, without spending a turn or adding a queued action.
The host should restore its last active prompt if it disabled that prompt while
sending the request. Named actions are not accepted as menu choices, directions,
location-selection keys, text acknowledgments or line responses.

Before each gameplay command wait the engine emits contextual hints:

```json
{"type":"context","commands":[{"name":"up","label":"Ascend","reason":"Stairs underfoot"}]}
```

An empty array clears prior hints. `name` is an exact catalog command;
`label` is an optional readable label (fall back to the catalog name), and
`reason` describes the situation. Entries are deduplicated by command name in
priority order: underfoot features and items, adjacent features and creatures,
then ranged actions. Choosing a hint uses ordinary named-command dispatch.
Item, direction, targeting and confirmation prompts remain owned by NetHack;
a hint does not automatically select the object or creature that suggested it.

Current hints cover:

- Underfoot stairs/ladders: the matching ascend or descend command.
- Underfoot fountains/sinks: drink and, with carried items, dip. Thrones: sit.
  Altars: sacrifice and, with carried items, drop.
- Remembered items underfoot: pick up and look here. A displayed container adds
  loot/tip; a chest or large box adds check for traps, apply when carrying a
  lock tool, and force when the hero wields an appropriate weapon. A displayed food item or corpse adds eat.
- Adjacent closed doors: open, kick, check for traps, and apply when carrying a
  key, lock pick or credit card. Open doors: close/kick. Sinks and displayed
  chests/large boxes: kick.
- Revealed nearby traps: examine; disarm for arrow/dart, bear, web, landmine or
  squeaky-board traps. Pits remain examine-only; the core cannot disarm them.
- Perceived adjacent creatures: inspect/chat. Pets: name and, with a physically
  visible saddle, ride. A recognized shopkeeper: pay. A mounted hero: dismount.
- Other creature glyphs in sight: throw with carried weapons/gems, fire with a
  quivered item, zap with a carried wand, cast with a remembered, non-forgotten
  spell. Pets, ridden creatures and shopkeepers alone do not trigger these
  choices. This does not classify the remaining creatures as hostile. Ordinary
  map movement retains NetHack's attack and pet-swapping behavior.

The input sources deliberately differ from raw world state. Adjacent hints use
cached foreground glyphs already sent to the renderer. Under the hero, NetHack's
remembered `levl[x][y].glyph` supplies objects/traps and `svl.lastseentyp` supplies
seen or touched terrain, because the foreground hero covers these features.
After remembered terrain identifies stairs/ladders beneath the hero, the engine
consults stair metadata for direction. This preserves the hint when an item or
trap overlays the stairs and after a saved game restores. It never discovers a
staircase by querying that metadata without the remembered-terrain gate.

Own inventory, wielded/quivered items and spell memory gate equipment-dependent
hints without assuming charges, usability or success. `can_reach_floor(FALSE)`
gates fountain/sink interaction, throne sitting, and floor pickup, eating or
container manipulation so levitation does not offer misleading terrain actions.
Looking at a remembered item remains available even when it cannot be reached. The only creature
equipment query requires a displayed pet, physical sight via `canseemon`, and
no blindness or hallucination, before checking the externally visible saddle.
No suggestions query undiscovered traps, actual adjacent terrain, locks,
container contents, hidden object stacks or monster hostility. Memory can be
stale and appearances can be disguises. Only the displayed/remembered top object
contributes object-specific hints; an obscured item is not discovered by the
panel. Hallucination suppresses object- and creature-specific hints; swallowing
or burial clears the panel. Blindness suppresses ranged and saddle hints, but
remembered terrain/object and other perceived creature hints may remain.

A suggestion is a way to find an applicable command, not a guarantee that it is
safe, possible or turn-free. The core still evaluates reach, conditions,
equipment, target selection and action consequences. Grave digging, boulder
pushing, tree interactions, applying a carried saddle and pool dipping are not
part of this expansion.

`python3 scripts/test-actions.py` exercises catalog contents and live bindings,
normal and unbound named actions, direction/target/menu rejection, no-turn
inspection actions, a one-turn wait, prefix handling, keypad bindings and nearby
door hints against the real bundled engine in isolated temporary games.

## Readable selection defaults

The native launcher sets `force_invmenu,menustyle:full`. `getobj` then emits
normal `menu` events with complete player-known item descriptions, appropriate
choices, single-candidate menus and list-all alternatives. No inventory-letter
parsing or extra item-discovery logic is needed. Counts and hands/self choices
use upstream menu identifiers and the existing selection protocol.

`force_invmenu` is a session option, but menu style is saved. At the first
command wait, the port reapplies `MENU_FULL` when `force_invmenu` is enabled so
old saves also receive readable category and container-action menus. This is
once per engine launch; later deliberate in-game option changes are respected.

Some finite `yn` selectors add an optional `choiceLabels` object mapping response
characters to readable labels. The port recognizes upstream response identities:
`rightleftchars`, `hidespinchars`, `ynaqchars` and `ynNaqchars`. These provide
Right hand/Left hand, Hide/Spin a web, and All/Choose quantity. The frontend still
sends the original response character. Arbitrary inventory letters never acquire
guessed semantic labels, and responses after the ESC hidden-choice marker remain
hidden. Ordinary confirmations retain the existing default and Escape handling;
we do not globally enable upstream `query_menu`, whose cancellation returns the
default response rather than the port's existing cancellation result.

Run `python3 scripts/test-item-menus.py` for real-engine coverage of item menus,
list-all navigation, cancellation, partial-stack counts, ring-hand labels and
traditional-menu saved-game upgrades.

## Development environment launcher

`Atlas Environment Playtests.app` is a separate, workspace-only companion.
It starts the packaged app with `--playtest` and `ATLAS_PLAYTEST_RUN` naming a
validated disposable `environment-playtests/runs/<id>` directory. The host uses
its `game/` child, a nonpersistent WebKit store and test preferences, acquires an
exclusive run lock, verifies the engine fingerprint, and restores automatically.
`ATLAS_TEST_TILESET` also selects the initial atlas in this explicit mode.
Ordinary launches do not watch playtest controls or automatically answer prompts.

At a playtest restore only, the host answers the exact upstream debug question
`Do you want to keep the save file?` with No. This consumes the working save;
the pristine source checkpoint remains separate. Other game prompts remain
under player control.

The companion writes an atomic `request.json` under that run for `close` or
`report` (with optional `notes`). The host polls only during an explicit playtest.
Report captures the WebKit view and current display settings, invokes the existing
`save` protocol, then copies files only after engine exit and restores the game.
Local reports include metadata and the engine event trace. No HTTP service,
external communication, or new engine command is introduced.

Tutorial cases restore a pre-entry checkpoint, then use ordinary wizard
level-port prompts to enter the real tutorial branch. Upstream cannot save a
tutorial; reports are screenshot/trace only, and close terminates that isolated
live tutorial process. Relaunch/reset starts a new entrance copy. The launcher
does not change the engine's tutorial, save format, or gameplay rules.

In a playtest, `boot.playtest` contains the explicitly selected test label and
inspection/exploration mode. The UI shows these as a playtest badge and **Test
start** label, not as inferred current branch identity. Ordinary boot sends null.

## Room-shape capture harness

For `--self-test` only, `ATLAS_TEST_SCENARIO=room-shape` selects a native
screenshot survey. Boot `testRoomBounds` contains the JSON `[x,y,width,height]`
from `ATLAS_TEST_ROOM_BOUNDS`. It frames the already displayed engine map after
the requested tileset image loads, emits a `room-shape` diagnostic/snapshot,
and completes the disposable test. It neither supplies terrain to the renderer
nor changes gameplay commands. Ordinary launches receive an empty value and do
not activate the harness.

Native self-test boot may include `testTerrainTiles`, a JSON array string of
expected canonical terrain IDs for room captures without masonry walls. It is
passed only from the isolated test harness; ordinary gameplay does not use it.
Existing room tests still require wall appearances when the array is empty.


`"material":"medusa"` identifies the actual named Medusa level
(`Is_medusa_level(&u.uz)`), before the generic special-level exclusion.
All four upstream layouts share this context. Original artwork families reuse
only their existing Sokoban walls, canonical slots 1504 through 1514 and their
directional rules. Remembered exposed dry shore ground may select `quest-earth`;
positively enclosed buildings retain stone floors and the light masonry. Doors,
water, trees, statues, objects and creatures retain their ordinary appearances.
Classification uses the terrain-memory rules above, not hidden room purpose,
occupants or secret-door detection. Unknown/nothing/swallow appearances
and swallowed/buried views receive no context. Canonical glyphs and ground,
lighting, traversal, encounters and save formats are unchanged. Tilesets without
this optional material continue to render the engine's canonical dungeon tiles.


`"material":"juiblex"` identifies the actual named Juiblex level
(`Is_juiblex_level(&u.uz)`), before the generic special-level exclusion.
Original artwork families map only dry-floor slots 1291 and 1292 to their
existing Gehennom ground, including safely known floor beneath occupants.
Water, blank stone, traps, stairs, fountains, objects and creatures retain
their canonical appearances. The reviewed upstream swamp has no wall glyphs;
no additional boundaries are drawn. Unknown/nothing/swallow appearances and
swallowed/buried views receive no context. The tag selects presentation only,
without changing glyphs, ground knowledge, lighting, terrain, encounters or
save formats. Tilesets lacking this optional mapping retain canonical art.


`"material":"baalz"` identifies the actual named Baalzebub level
(`Is_baal_level(&u.uz)`), before the generic special-level exclusion.
Original families reuse their exact approved Gehennom walls, directional poses
and ground, including known ground beneath occupants. Doors, bars, blank stone,
water, lava, traps, stairs, objects and creatures retain canonical artwork.
The material includes ordinary wall aliases for shared renderer fixtures and
the Valkyrie Quest fortress described above. No
room classification, hidden occupants or secret doors select it. Unknown,
nothing and swallow appearances and swallowed/buried views receive no context.
Canonical glyphs, ground knowledge, lighting, terrain, encounters and save
formats are unchanged. Community sets without this mapping use canonical art.


Known lowered drawbridge ground may use canonical tiles 1318 or 1319 beneath
an occupant. The port uses upstream `lastseentyp` plus an exact foreground or
remembered bridge glyph; currently visible lowered terrain can supply its
orientation through `back_to_glyph`. It never reads unseen current orientation.
When an unseen object has overwritten the remembered bridge glyph, orientation
is unavailable and the ground is omitted. Raised spans already resolve to
known underlying terrain through upstream `update_lastseentyp`. Blocking
portcullis appearances receive no decorative floor. These layers do not change
bridge mechanics or disclose remote bridge transitions.
