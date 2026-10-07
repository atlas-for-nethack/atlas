# Environment playtests

Open **`dist/Atlas Environment Playtests.app`**. This development companion uses
this checkout and Apple's Python 3. It is not part of the player distribution.
Build it after the ordinary app with `./scripts/build-playtest-launcher.sh`.
Rebuild the launcher if the checkout moves.

1. Choose **Environment**, **Layout**, **Tileset**, and **Test mode**.
2. Click **Play**. The actual packaged NetHack app opens a disposable game at
   the chosen destination. Move, explore, fight, open doors, dig, push boulders,
   and try anything the real engine allows.
3. In the game use **Play-test → Report Problem…** (Command-R). Enter what
   happened and what you expected. The report stays on this Mac. It includes a
   screenshot, current display preferences, engine events, build/art fingerprints,
   case setup, and a saved game when available. The game saves and resumes;
   saving unwinds any unfinished prompt, so the screenshot records the state
   before that cancellation. This temporary report save keeps the map open and
   does not announce that the adventure has ended.
4. Use **Play-test → Save and Return to Launcher**, or close the game window.
   **Resume Last Test** continues that run using the currently selected tileset.
5. **Reset Test** saves and closes the current run, then opens a fresh copy of
   its original checkpoint. Old progress and reports remain available. Reset
   refers to the current test, regardless of changes to the selection controls.
   **Play** starts a fresh run of the selected case, using its cached checkpoint.

The menu label identifies disposable playtests. Game files, reports, and test
locks live under `.artifacts/environment-playtests/`, separate from ordinary
saves, bones, recovery, scores, and locks. Native test preferences use a separate
macOS preferences suite outside `.artifacts/`; WebKit test storage is temporary.
The launcher refuses to open a test already running elsewhere. Do not copy or
edit an active game's files yourself.
**Show Reports** opens the current run's reports folder, or its run folder if
there are no reports yet. Each report has a `notes.txt` for your description.

## Modes and limitations

- **Exploration** adds no map reveal, equipment, or protection. Normal role
  supplies, visibility and encounters apply. These remain upstream wizard games
  for direct access, with debug death refusal available. They are not scoring
  standard campaigns.
  Plane arrivals are an upstream exception: wizard Endgame entry supplies a
  real Amulet of Yendor when absent. This prerequisite is recorded in their
  setup metadata; it is not a normal campaign arrival or an Atlas rules patch.
- **Inspection** raises experience to 30, grants long-lived resistances,
  magical breathing and regeneration, reveals the map, and provides a digging
  wand and healing potion. It keeps occupants active. This is not invulnerability
  or proof that ordinary combat and hazards are correct. The precise alterations
  are recorded in each checkpoint's `metadata.json`. The starting map reveal
  can expose isolated corridor squares surrounded by rock. The game labels this
  mode as “starting map revealed”; use Exploration to judge ordinary discovery.
- **Tutorial** enters the actual scripted level live. NetHack deliberately
  forbids tutorial saves. Resume and Reset restart from its pre-entry checkpoint;
  reports capture the screenshot and event trace, not a resumable tutorial save.
  Closing a tutorial ends only that disposable engine process. Original tutorial
  behavior and ordinary save rules have not been modified.
- The launcher uses **current shipped artwork**, including the regional treatments
  described in [TILESETS.md](TILESETS.md).

## Coverage

The catalog in [scripts/playtest/prepare.py](../scripts/playtest/prepare.py)
includes dungeon/Mines/Gehennom samples, named special levels and lairs, Quest
stages, all five planes, tutorials, room shapes, themed fills and buried rooms.
The launcher is the current case inventory; new upstream or recipe changes can
change the available layouts.

Choose **Room shapes** to try an unusual or nested room. Each case invokes its
named upstream generator and retains random dimensions, lighting and contents.
A separate arrival room and ordinary corridors provide a playable starting
point, including for sealed shapes. Inspection reveals the starting map; the
hero can start in either room. The water-surrounded vault deliberately excludes
teleport arrivals, so access and water hazards require their own targeted test.

For a paired screenshot survey, run `python3 scripts/test-room-shapes.py --prepare`
then `python3 scripts/test-room-shapes.py --native`. The local gallery is
`.artifacts/room-shapes-review.html`. `--movement` checks reachable plain-floor
diagonals inside the named shape and save/restore; it records skipped movement
when the arrival has no reachable plain-floor 2x2 area. It does not clear traps,
contents or upstream movement restrictions to force a pass.

Choose **Dry themed rooms** for spider nests, trap rooms, massacre scenes,
statuary, light sources, adventurer ghosts and storerooms. These call the upstream
fill functions at depth 12 so level-gated content can appear. Lit, unlit and
ordinary-plus-themed variants are included where eligible. The local paired
survey is `.artifacts/dry-themed-review.html`; regenerate it with
`python3 scripts/test-dry-themed-rooms.py --prepare --engine --native`.
The tests use isolated saves; hidden-state diagnostic queries are not player UI.

Named arrivals use the engine's branch menu. Exact variants are loaded from
pinned upstream Lua into the appropriate real branch and floor, with explicit
reset/finalize and branch/floor checks. Quest roles match their scripts. Ludios
preparation generates eligible main-dungeon floors to establish its actual
portal before entering the branch. Tutorial destinations are entered after
restoring a pre-entry save. Water and Air use the actual planes, not a copied
map in the main dungeon.

Targeted layouts are fixtures. They do not prove every natural stair/portal
transition, random variation, special-room combination, tutorial lesson, or
Castle bridge state has been exercised. World-selected variants are recorded as
world-selected, not assigned a guessed source number. These cases are starting
points for interactive testing. See [VERIFICATION.md](VERIFICATION.md) for evidence
and remaining campaign coverage limits.

Checkpoints are keyed by the engine, game data and recipe hashes; working copies
are retained in unique run directories. No deterministic random seed is promised.
A new engine cannot open an old test through the launcher without regeneration.
Changing only tilesets can reuse the same world for comparison. A report records
the running app and artwork hashes as well as checkpoint provenance.

## Verification

- `python3 scripts/test-environment-playtests.py --all`: creates both modes for
  every case, restores each saved checkpoint with the real bundled engine,
  validates branch/floor/role, checks turn-free inspection, and saves again.
  Tutorial checks here validate the pre-entry checkpoint; native checks validate
  live tutorial arrival.
- `python3 scripts/test-playtest-native.py --tileset lantern-modern`: packaged
  app restore, screenshot/report, save/resume, and reset-copy check. Repeat with
  `--tileset soot-and-brass` or `--case tut-2` for live tutorial reporting.
- The launcher executable accepts `--self-test` to exercise its actual Play and
  Reset buttons, report request, and graceful close, and capture `launcher.png`.
  Results are written under `.artifacts/environment-playtests/`.

The native checks require a logged-in macOS desktop. These checks use disposable
games only. A successful fixture or screenshot does not replace the owner's
interactive playtest or establish Intel gameplay support.

## Buried rooms and vault excavation

Choose **Buried rooms** for Buried treasure or Buried zombies, lit or unlit.
These call the original named fill and post-generation handler. Treasure keeps
its actual “Dig…” engraving; zombies keep their original emergence timers.
Exploration does not reveal buried objects. Inspection maps the room without
revealing buried contents and supplies the existing test equipment. Apply a
pick-axe downward to excavate a pit, or use the inspection wishing wand to
obtain one. Excavation and any subsequent pickup use normal engine commands.

Run `python3 scripts/test-vaults-buried.py --catalog` for the eight mode/case
checks, then `python3 scripts/test-vaults-buried.py --native` for excavation,
original clue/timer checks, real vault guards and paired screenshots. The vault
guard escort can emit `newsym: attempting screen update for <0,0>` and
`Program in disorder!` while navigation, corridor cleanup and save/restore still
complete. This diagnostic is retained as an upstream follow-up; no patch or
suppression has been applied.
