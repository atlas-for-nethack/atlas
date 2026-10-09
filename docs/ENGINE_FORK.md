# NetHack engine fork record

This is the living record of changes to upstream NetHack source used by NetHack
Atlas. Update it whenever an upstream file is changed, replaced or added to the
build. Application UI, Swift hosting, JavaScript overlays and artwork are outside
this inventory. The replacement window port is listed because it occupies an
upstream source path, even though it is not a fork of the gameplay rules.

## Upstream baseline

Inventory maintained October 6, 2026; source audit counts checked October 6, 2026:

- Release: **NetHack 5.0.0**.
- Original archive: [nethack-500-src.tgz](https://www.nethack.org/download/5.0.0/nethack-500-src.tgz).
- SHA-256: `2959b7886aac76185b90aea0c9f80d14343f604de0ae96b3dd2a760f7ab3bde9`.
- Of **1,265 original regular files**, **1,263 remain byte-for-byte unchanged**
  and **2 are modified**. None are missing.
- Windows builds modify **2 more** Windows startup files, so a Windows build tree
  has **1,261 unchanged** and **4 modified** files. macOS and Linux build trees
  do not contain these 2 changes. Updated October 8, 2026.
- One additional maintained build hint is installed. Generated build files and
  executables are not counted as original files or maintained gameplay patches.

The archive remains intact. Maintained changes live in `engine/` and are applied
to the disposable `vendor/NetHack-5.0.0/` tree by the build scripts.

## Modified upstream files

| Upstream path | Change and reason | Maintained implementation | Change dates |
| --- | --- | --- | --- |
| `src/allmain.c` | Add a `SHIM_GRAPHICS`-guarded call to `atlas_beginner_kit()` during new-game initialization, before the first recovery checkpoint. This enables optional Beginner starting supplies. | [`engine/apply-beginner-patch.py`](../engine/apply-beginner-patch.py), implementation in [`engine/winatelier.c`](../engine/winatelier.c) | Hook introduced 2026-09-24; dated notice added 2026-09-29. |
| `win/shim/winshim.c` | Replace the upstream shim with the Atlas JSON window port, connecting the real engine to the local app. This is a window-port replacement, not a replacement of NetHack gameplay. | [`engine/winatelier.c`](../engine/winatelier.c) | Replacement introduced 2026-09-24; regional presentation support added 2026-09-28 and extended 2026-09-29; Earth level presentation context added 2026-09-30; named Mines, Valley of the Dead, Samurai Quest and Medusa presentation contexts extended 2026-10-01; Juiblex dry-ground, Baalzebub Gehennom presentation contexts, perceived lowered-drawbridge ground stage-specific Quest material reuse and remembered exterior-ground classification, Medusa shore reuse, additional Quest stage routing, tree-bordered Garden ground, finished Minetown interiors and exact Valley reuse on Orcus-town added 2026-10-02; Plane of Fire ground reuse added 2026-10-05; Astral sanctuary presentation context added 2026-10-06; upstream notices retained explicitly 2026-09-29. |
| `sys/windows/windmain.c` | Windows builds only. When the shim is the only window port, use the build's `DEFAULT_WINDOW_SYS` for the default window system. Upstream assumes the Windows GUI or console tty port, and the file does not compile without one of them. Also allow Explore mode only when `EXPLORERS=*` is in `sysconf`, as on macOS and Linux. Upstream Windows allows Explore mode in every game. Windows has no user names to match, so a list of names refuses Explore mode. | [`engine/apply-windows-patch.py`](../engine/apply-windows-patch.py) | Introduced 2026-10-08; Explore authorization added 2026-10-08 (ADR 0001). |
| `sys/windows/windsys.c` | Windows builds only. Read the portable `sysconf` by its full path on every startup pass. Upstream adds the earlier `sysconf` folder to the start of the full path on the second pass. The file is then not found, and the game uses the player's own NetHack folders. | [`engine/apply-windows-patch.py`](../engine/apply-windows-patch.py) | Introduced 2026-10-08. |

Both modified files carry prominent dated Atlas change notices and retain the
original upstream copyright and redistribution notices. Port behavior is
documented in [protocol.md](protocol.md), rather than duplicated here as an
inventory of application features.

October 6, 2026: the replacement port resolves host Save using the live named
command table, including extended-command dispatch when Save has no key binding.
It preserves valid UTF-8 when serializing JSON strings and replaces each malformed
byte with U+FFFD. Upstream commands, naming rules, mixed-glyph processing and
save format are unchanged. This extends the existing `win/shim/winshim.c`
replacement and its dated notice; the modified-file inventory remains two files.

October 8, 2026: Windows builds use the upstream Windows startup files with
two small fixes. These fixes are in `sys/windows/windmain.c` and
`sys/windows/windsys.c`, and the table above describes them. Each file has a
dated Atlas notice. `engine/apply-windows-patch.py` applies the fixes only in
Windows builds. It accepts only the pristine or the patched upstream text.
The replacement port also adds two Windows-only items behind `#ifdef _WIN32`.
It sets binary mode on standard input and output. It also supplies empty
versions of three console entry points that the Windows startup code calls.
The save format and the macOS and Linux builds do not change. The
Explore authorization fix changes one gameplay rule on Windows only: it makes
Windows match the macOS rule ([ADR 0001](adr/0001-windows-explore-only-in-explore-mode.md)).

### Deliberate gameplay customization: Beginner supplies

The new-game hook runs after ordinary character initialization. Only
`ATLAS_PLAY_MODE=beginner` enables the gift. It creates an unlocked, untrapped,
uncursed chest on nearby reachable floor, preferably in the starting room,
avoiding stairs and hazardous terrain. The chest contains identified, uncursed
supplies: 1,000 gold pieces, a magic whistle, two food rations and a potion of
healing. Gift gold is included in the initial-funds accounting for the separate
Beginner score record.

NetHack's object creation, containers, pickup, carrying, saving, combat and death
rules handle those supplies normally. The hook does not run on restoration and
does not change role equipment or starting attributes. Standard mode bypasses
the gift. Explore mode uses upstream discovery mode. Beginner saves, bones and
scores are isolated by the host.

There are no other modifications to original core gameplay files in this
inventory. Regional appearances, including Mines, named lairs, the Plane of Earth,
the Samurai Quest, Medusa, Juiblex and Baalzebub, are selected
through the replacement port and Atlas artwork. Astral sanctuary presentation
also uses the replacement port's optional material context. Original level-generation Lua
files and dungeon topology are unchanged. Those appearances do not add new
rooms, alter monster behavior or change level traversal rules.

The port also preserves lowered drawbridge ground beneath perceived occupants.
The surface comes from upstream remembered type and an exact displayed or
remembered bridge glyph. Current orientation is read only for currently visible
lowered terrain. Raised spans use upstream's remembered underlying water, ice,
lava or floor. Missing unseen orientation remains omitted. This presentation
fix does not change drawbridge actions, crushing, drowning or memory rules.

October 2, 2026: the replacement port reuses existing materials by persistent
role and Quest stage, including natural passages, temple compounds, forest
stages and infernal fortifications. Remembered exposed ground around buildings
and Medusa's shores uses existing earth pixels. Ordinary tree-bordered Garden
ground also reuses earth. Named Minetown retains Mines architecture and dirt
streets, with canonical stone floors only in positively remembered rectangular
interiors. Two traversals of valid upstream terrain memory distinguish exposed
dry components from positive enclosures, including indoor pools. Known doors
remain thresholds after opening or breaking. Unknown boundaries cannot prove an
interior; no hidden room-purpose flags or unseen current terrain are consulted.
Command refresh shares a transient classification map, not a persistent cache.
No new artwork, quest Lua, level generation, visibility, save format or gameplay
rule is introduced. Exact stage choices and conservative fallbacks are documented
in the [protocol](protocol.md).


October 2, 2026: the replacement port selects existing Valley presentation on
the persistent named Orcus level (`on_level(&u.uz, &orcus_level)`). This reuses
the already approved material without new glyph indexes, artwork, gameplay,
save format or level generation changes. The pinned `dat/orcus.lua` remains
unchanged. The usual unknown, swallowed and buried appearance exclusions apply.

October 6, 2026: the replacement port selects the approved Astral sanctuary
presentation on the persistent named Astral level (`Is_astralevel(&u.uz)`).
The additional `astral` value uses the existing optional material field and
keeps canonical tile/glyph indexes, perceived supporting terrain and lighting.
The whole level receives the same context; no altar alignment, priest deity,
hidden room purpose or unseen terrain selects it. Unknown, swallowed and buried
appearances still omit material. Original `dat/astral.lua`, temple alignment
shuffling, priests, crowds, terrain memory and ascension rules remain unchanged.
Only the already inventoried replacement `win/shim/winshim.c` is affected;
its prominent dated notice is extended and updated source must be packaged.

## Added integration and generated files

October 5, 2026: the replacement port routes the actual Plane of Fire
(`Is_firelevel(&u.uz)`) to the existing Gehennom presentation material. This
reuses approved dry ground without new artwork, glyph indexes or protocol
fields. The original lava, traps, clouds, portal, occupants and level generation
remain upstream-owned. Unknown, swallowed and buried appearances still omit
material metadata. `dat/fire.lua` and upstream hazard code remain unchanged.
The existing replacement `win/shim/winshim.c` is still the only affected port
path; its prominent dated notice is extended and its updated source is packaged.

`sys/unix/hints/atelier` is added from [`engine/hints`](../engine/hints). It selects
the shim port and generated tile mapping, enables `TILES_IN_GLYPHMAP`, uses static
Lua, disables upstream shell and mail facilities through `NOSHELL` and `NOMAIL`,
and sets relocatable paths and a macOS 13 deployment target. These are build
choices, not edits to the original configuration headers. The packaged private
system configuration comes from [`engine/sysconf`](../engine/sysconf).

Linux builds install the same hint. `scripts/build-engine.sh` gives `make` the
same build choices, without the macOS deployment flags. Windows builds use
the upstream `sys/windows/GNUmakefile` and the maintained fragment
[`engine/windows.mk`](../engine/windows.mk). Upstream makes the generators,
game data, static Lua and `recover.exe`. The fragment links the game with the
Atlas port in place of the console tty port. The Windows runtime `sysconf` is
`engine/sysconf` plus `PORTABLE_DEVICE_PATHS=1`. This setting keeps every
file beside the executable.

Lua 5.4.8 is a separate checksum-pinned dependency under its MIT license, not an
upstream NetHack patch. Native and cross-compilation support is maintained in
[`scripts/build-engine.sh`](../scripts/build-engine.sh) and
[`engine/build-cross.py`](../engine/build-cross.py).

The build generates `src/tile.c`, `include/date.h` and `include/nhlua.h`.
The audit recognizes these as generated source paths; it does not classify their
contents as maintained gameplay modifications. Generated Makefiles, objects,
executables, databases and architecture target directories are build products.
The audit rejects any other added `.c`, `.h` or `.lua` file under the upstream
`src`, `include`, `dat`, `win`, `sys` and `util` directories. This is not a count
of every generated non-source file.

## Repeatable audit

From the repository root:

```sh
./scripts/build-engine.sh
python3 scripts/audit-engine-fork.py --report .artifacts/engine-fork-audit.json
```

The build installs the maintained patch, port and hint, then runs the same audit
before compiling. The application build audits again when packaging source.
The audit verifies the pinned archive checksum, compares every original regular
file with its exact expected content, and rejects missing files, unrecorded
changes, unexpected patch shapes and unclassified added source. It verifies the
maintained build hint and the replacement port's retained upstream notices.

The JSON report records original and current SHA-256 values for every original
file, the two modified paths, counts and recognized generated source paths.
It does not inspect saves or certify binary reproducibility, gameplay coverage
or the licensing of unrelated assets. A matching file count alone is not enough:
the expected bytes must match too.

## Source and NGPL distribution

Each built app includes the NGPL at `Contents/Resources/engine/license`, together
with these files under `Contents/Resources/Source/`:

| Payload | Purpose |
| --- | --- |
| `nethack-500-src.tgz` | Complete unmodified upstream release archive. |
| `engine-upstream-modifications.tar.gz` | Exact updated `src/allmain.c`, replacement `win/shim/winshim.c`, and added `sys/unix/hints/atelier` used by this build. Extract over the original NetHack tree to inspect the updated source directly. |
| `engine-fork-audit.json` | File hashes and classified changes measured when the source payload was packaged. |
| `atlas-source.tar.gz` | Maintained port, patch helper, build scripts, documentation and application source. |
| `lua-5.4.8.tar.gz` | Complete source for the static Lua dependency. |

A Windows distribution must also put the patched `sys/windows/windmain.c` and
`sys/windows/windsys.c` in its modifications archive. It must include
`engine/apply-windows-patch.py` and `engine/windows.mk` too. As of October 8,
2026, the packaging scripts do not make a Windows distribution.

The patch helper, port, hints and system configuration also accompany the
archives as individual files. [SOURCE.md](SOURCE.md) gives reconstruction steps.
The engine fork record is included both in the app's documentation and in the
Atlas source archive. No player saves or generated runtime binaries enter the
source archives.

This implements the following obligations from the bundled
[NetHack General Public License](../assets/tiles/sources/NGPL.txt):

- Paragraph 1: retain upstream copyright, redistribution and warranty notices;
  include the full license with the distribution.
- Paragraph 2(a): identify changes and dates prominently in each modified
  upstream file. This document supplements those file notices.
- Paragraph 2(b): distribute the modified NetHack engine and replacement port
  under the NGPL, without charging for the license.
- Paragraph 3(a): accompany the executable with complete machine-readable
  source, including the original source distribution and the updated files used
  to create the executable, plus required build support.

Artwork licensing is a separate matter, documented in [TILESETS.md](TILESETS.md).
An artwork license does not relicense NetHack-derived code.

## Maintenance rule

For every future upstream modification:

1. Preserve original copyright, license and warranty notices.
2. Add or extend the prominent change notice in the affected file with the
   actual date and a concrete description of the change.
3. Maintain the change in `engine/` or a reproducible patch helper, never solely
   in the disposable `vendor/` tree.
4. Update this inventory, rationale and audit expectations. Review added source
   paths as well as edits to existing paths. Update the packaged modification
   archive if its membership changes.
5. Run the source audit and appropriate engine tests. Rebuild the app and verify
   the bundle so its notices, source archives and executable stay together.
6. Record performed verification and its limits in [VERIFICATION.md](VERIFICATION.md).

The source audit and bundle checks provide concrete evidence for this record;
they do not substitute for reviewing distribution obligations when the engine,
dependencies or release process changes.
