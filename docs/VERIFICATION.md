# Verification guide

Run checks that exercise the behavior being changed. Engine tests use the real
NetHack process; renderer fixtures and event replays support visual review but do
not establish live gameplay. The native tests require a logged-in macOS desktop
and use isolated data under `.artifacts/`. Never substitute player saves or remove
locks owned by a live engine.

## Build and core checks

Build prerequisites and normal player installation are in the [README](../README.md).
For engine changes, rebuild the engine before the app. A release needs Universal 2
engine and recovery binaries; `ENGINE_ARCH=native` is only for local iteration.

```sh
./scripts/build-engine.sh
./scripts/build-app.sh
python3 scripts/test-character-rules.py
python3 scripts/test-engine.py
python3 scripts/test-beginner.py
python3 scripts/test-explore.py
python3 scripts/test-starting-options.py
python3 scripts/test-actions.py
python3 scripts/test-context.py
python3 scripts/test-item-menus.py
python3 scripts/test-prompt-messages.py
python3 scripts/test-targeting.py
python3 scripts/test-experience.py
python3 scripts/test-recovery.py
python3 scripts/test-isolation.py
python3 scripts/test-release-engine.py
node web/input.test.js
node web/app.test.js
```

These cover character restrictions, command/input flow, named menus, perception
boundaries, mode isolation, Save binding independence, UTF-8 serialization,
recovery and frontend callback ordering. The [protocol](protocol.md) describes
the observable contracts. Engine tests check turn and position restoration;
recovery tests stage copies, retain checkpoints and exclude live processes.

## Native application checks

Rebuild the packaged app after engine, native or web changes, then exercise the
affected behavior in it. The core smoke test covers rendering, keyboard and mouse
movement, inventory, action filtering, turn-free inspection, confirmations,
save/restore and safe quit.

```sh
python3 scripts/test-native.py --gender female
python3 scripts/test-native.py --gender male
python3 scripts/test-native.py --mode beginner
python3 scripts/test-native.py --mode explore
python3 scripts/test-native.py --mode pauper
python3 scripts/test-native.py --mode standard --nudist
python3 scripts/test-native.py --mode beginner --nudist
python3 scripts/test-native.py --mode explore --nudist
python3 scripts/test-native.py --mode beginner --blind --deaf
python3 scripts/test-native.py --mode standard --deaf --no-starting-pet
python3 scripts/test-native.py --mode pauper --deaf --no-starting-pet
python3 scripts/test-prompt-messages.py --native
python3 scripts/test-targeting.py --native
```

Use the [environment playtest launcher](ENVIRONMENT-PLAYTESTS.md) for a specific
level, layout or terrain interaction. Report setup alterations, original-world
travel versus reloaded layouts, random sample counts, skips and failed checks.
A screenshot or an Inspection-mode arrival cannot prove ordinary survival or
natural campaign traversal.

## Artwork and imports

Use the [shared tileset preview](../tools/tileset-preview/index.html) with the real
painter and shipped atlases, then verify affected appearances in the native app.
Preserve engine tile ordering, source provenance, family architecture parity and
the shared Modern creature tiers. [TILESETS.md](TILESETS.md) documents rendering
and regional contracts. Focused artwork and regional tests live in `scripts/`;
choose those corresponding to the changed assembler, material or renderer.

```sh
node web/tiles.test.js
node web/frost.test.js
node web/water.test.js
python3 scripts/test-tile-catalog.py
python3 scripts/test-tileset-compiler.py
python3 scripts/test-lantern-modern.py
python3 scripts/test-soot-and-brass.py
python3 scripts/test-tileset-import.py
```

Import geometry cannot certify arbitrary community tile ordering. The
[import policy](TILESET-IMPORT-POLICY.md) specifies resource limits, failure
preservation and the optional native-helper memory benchmark. That benchmark
does not measure full application/WebKit peak memory.

## Packaging and source integrity

```sh
python3 scripts/test-packaging.py
python3 scripts/test-engine-fork.py
python3 scripts/audit-engine-fork.py --report .artifacts/engine-fork-audit.json
python3 scripts/verify-bundle.py
```

The fork audit requires a prepared build tree. It verifies the pinned archive,
expected modified-file bytes, dated upstream notices and classified added source.
Update the [living fork inventory](ENGINE_FORK.md) whenever upstream changes.
Bundle verification checks architectures, deployment targets, dependencies,
resources, notices, source payloads and signature integrity. Packaging regressions
exercise clean staging, archive contamination rejection, source pins, offline
reconstruction and preservation of the previous complete app.

For a local release archive, `python3 scripts/build-release.py --output
/path/to/Atlas-for-NetHack.zip` verifies the app, writes the ZIP, checks its exact
contents and creates a checksum. Build/release outputs belong outside Git.
[Source reconstruction](SOURCE.md) describes rebuilding from a distributed app.

## Evidence and limits

On 2026-10-08, the `electron-port` branch built the engine for two more
platforms. No Electron host, packaged app or Mac build was tested. The macOS
build path is not meant to change, but nobody rebuilt or tested it.

- Linux x64: `scripts/build-engine.sh` built the engine under WSL 2 Ubuntu
  26.04. The binary links only libc and libm. It needs glibc 2.42 or later, so
  it does not run on older distributions yet. `test-engine.py`,
  `test-actions.py`, `test-context.py`, `test-item-menus.py` and
  `test-engine-fork.py` passed against the real engine. One of five
  `test-actions.py` runs failed its "wait takes one turn" check on a random
  game. Four more runs passed. `test-character-rules.py` needs Node and
  `test-recovery.py` compiles the Swift helper, so neither ran.
- Windows x64: Git Bash and llvm-mingw 20260908 (UCRT) built the engine on an
  AMD64 computer with Windows 11. The binary links only Windows system DLLs,
  including the Universal CRT. The same five suites passed. These suites test a
  new game, movement, save and exact restore. They also test the save after
  stdin closes and checkpoint recovery with `recover.exe`. `--showpaths` and the test runs kept
  every file in the isolated runtime. After the runs, the per-user and
  ProgramData NetHack folders did not exist.
- The fork audit passed with 2 documented modifications on Linux and 4 on
  Windows. `test-engine-fork.py` also checks that the Windows patch is exact,
  safe to apply twice, and applies to both files or neither.

Nobody built Windows ARM64 or Linux ARM64. Nobody tested Electron gameplay,
Windows releases other than Windows 11, or a complete campaign.

On 2026-10-08, the README clarification for issue #2 was checked against the
pinned NetHack 5.0 source: the Deaf property, ambient sounds, monster speech,
chat replies, hearing-dependent item use and hearing-message handling.
Spellcasting and chanting checks were also inspected; deafness does not
prevent chanting. The documentation diff passed `git diff --check`.
No gameplay code changed; no build or gameplay tests were run for this edit.

On 2026-10-08, the v1.1.0 release candidate passed the Universal 2 app build
and bundle/source/license/signature verification. The starting-condition,
Beginner and Explore engine tests, focused JavaScript tests, and all 19 packaging
regressions passed. A fresh isolated native Pauper run with Deaf and No starting
pet passed creation, gameplay, save and restore on Apple Silicon. This candidate
retains the platform limits described below: no Intel gameplay, execution on
macOS 13, or complete campaign was tested.

On 2026-10-08, the same feature branch added Blind, Deaf and No starting pet
to every mode, and Nudist to Explore. `scripts/test-starting-options.py` passed
against the real NetHack 5.0 engine for all four Blind/Deaf and no-pet starts,
their save/restore state, and Explore Nudist. The combined Blind/Deaf runs
checked the engine's condition flags, birth conduct and limited perceived map.
The focused JavaScript tests, existing Beginner, Explore and mode-isolation
checks, and a Universal 2 app build with bundle verification passed. Isolated
native app runs passed for Standard and Pauper Deaf/no-pet,
Beginner Blind/Deaf, and Explore Nudist; they covered creation, relevant engine
state and save/restore. Creation and Blind gameplay screenshots were visually
inspected. No Intel gameplay or complete campaign was tested.

On 2026-10-08, the Pauper and Nudist branch passed `scripts/build-app.sh`
with Universal 2 bundle, source, license and local-signature verification.
`scripts/test-starting-options.py` exercised the real NetHack process for
Pauper's empty inventory, spells, skills, conduct, save/restore and checkpoint
recovery, plus Standard and Beginner Nudist starts and restore. The focused
JavaScript tests and `scripts/test-isolation.py` passed. Isolated native app
smoke runs covered Pauper, Standard Nudist, Beginner Nudist and Explore creation,
inventory, movement, inspection, save and restore; Beginner still exposed its
supply chest. Pauper and Nudist creation and Pauper in-game help screenshots
were visually inspected. These checks ran on Apple Silicon and do not establish
Intel gameplay or complete campaign behavior.

On 2026-10-07, the local publication candidate passed a Universal 2 app build,
bundle/source/license/signature verification, a verified local ZIP and SHA-256,
the focused engine, UI, recovery, tile, and packaging checks, and native
Cocoa/WebKit smoke tests for all five shipped tilesets. The native runs covered
Standard, Beginner, and Explore on Apple Silicon, with isolated save and restore;
native prompt and targeting checks also passed. Regenerated tileset PNG bytes
matched the prior five PNGs exactly. The 1.0.0 candidate also rebuilt offline
from its packaged source archive in a directory without Git; the source
inventory, pinned archives, artwork, and bundle verification passed there.
These checks do not establish Intel gameplay,
execution on macOS 13, notarized distribution, or a complete NetHack campaign.
The local test logs and screenshots are in ignored `.artifacts/`.

The README screenshots were captured from the 1.0.0 packaged app at source
revision `f75ef5b5ae7e52d7fdbe0b48be32535d1fa76663` on Apple Silicon. The
Lantern Modern native fixture passed restore, ordinary arrow movement and
automatic save checks; the Soot & Brass Modern Sokoban fixture passed native
restore and rendering checks. Both use isolated developer saves and capture
only the WebKit game view. See [screenshot provenance](screenshots/README.md)
for the staged scene and wizard-map setup; these captures do not establish
normal campaign progression.

Prior development runs exercised real gameplay on Apple Silicon, all five shipped
tilesets, male/female creation, Standard/Beginner/Explore, keypad modes, rebound
Save, exact restoration, isolated recovery, custom-sheet selection and malformed
import fallback. Universal 2 builds and source/bundle checks passed in those runs.
These are previous test results, not a claim that every command above was rerun
after documentation or repository cleanup. Record new results against the exact
source revision and built artifacts, with logs and hashes in ignored `.artifacts/`.

The shared recipe compiler generated five independently selectable PNGs.
An independent comparison against retained pre-migration assets verified all
2,304 canonical RGBA slots per tileset, every referenced supplemental cell,
projected pixels and draw geometry, regional aliases and directional variants,
frost contours and both original-family architecture pairings. Packing positions
and PNG bytes changed; visible artwork and canonical ordering did not.
Current source and output hashes are in each recipe's provenance receipt.

Seventeen compiler regressions passed, covering a standalone arbitrary name,
rectangular canonical tiles, independently declared large sprites, reproducible
output, resource/geometry rejection, source pins, unique registration, source and
receipt ownership, exclusion of local metadata from receipts, retained
original-art licensing and publication rollback.
Focused Python source/artwork/material checks and JavaScript renderer checks
passed, including cross-edition pixels and geometry, perception fallback,
regional composition and cosmetic frost. Seventeen packaging regressions passed.
Caveman's two optional historical comparisons were skipped without `--oracle`;
current source pixels, corner geometry, edition parity and door exclusions were
checked. Missing explicitly requested historical input still fails.
These results cover source maintenance and packaging, with native and platform
coverage distinguished below.

The packaged Universal 2 app passed bundle/source/license/signature verification.
All five tilesets passed the native Cocoa/WebKit smoke test on Apple Silicon,
using isolated Standard-mode female Wizard games. The checks covered startup,
map rendering, keyboard/mouse input, turn-free inspection, inventory, actions,
save, restore and quit. Lantern Modern and both Soot & Brass editions received
screenshot inspection. The manifest-driven environment launcher passed its
Play, Report and Reset integration check. This run did not exercise Intel
hardware, every supported macOS release, or a complete campaign.

Filename validation regenerated all five shipped PNGs byte for byte and confirmed
that manifest metadata changed only in filenames. Tileset IDs, order, default
selection and saved display choices remain compatible. Recipes and receipts use
consistent edition labels, with version-free PNG names and engine compatibility
in metadata. All receipt hashes match current maintained inputs or the pinned
upstream bitmap; Finder metadata and caches are excluded using the packaging
policy. Four focused Lantern/Soot & Brass source suites passed. After renaming,
all five selections passed the native smoke test on Apple Silicon with isolated
saves, and the rebuilt Universal 2 app passed bundle/source/license verification.
Logs and input/output hashes are retained in ignored `.artifacts/`.

The following limits remain relevant:

- Intel slices have compiled and passed structural checks; Intel gameplay has
  not been exercised. The macOS 13 deployment target does not establish execution
  on every supported macOS release or on the minimum release.
- Local apps are ad-hoc signed. Developer ID signing, Apple notarization and
  downloaded-app Gatekeeper acceptance require separate distribution validation.
- No complete campaign or ascension has been validated. Targeted environment
  checks do not exhaust natural connections, return visits, perception states,
  terrain mutations or random layouts. Ordinary Earth digging and expansion have
  witnesses; ordinary Earth collapse remains unobserved in bounded checks.
- The native WebKit termination notice is implemented, but forced isolated
  WebKit-process termination followed by observable notice and safe Save has not
  been validated. Essential VoiceOver and broader keyboard-only acceptance remain
  incomplete.
- Import helper tests and one largest-shipped-atlas benchmark do not establish
  full WebKit memory bounds, arbitrary artwork compatibility or complete
  interactive file-picker coverage.
- Vault escort checks reproduced `newsym: attempting screen update for <0,0>`
  and `Program in disorder!`; navigation, corridor restoration and save/restore
  completed. No upstream patch or warning suppression has been applied.

The engine pins NetHack 5.0.0 and Lua 5.4.8. Track NetHack reports C500-6
(container-item buffer handling) and C500-12 (recovery while swallowed) against
[the upstream known-bug list](https://www.nethack.org/v500/bugs.html), and review
[Lua 5.4.8 parser, collector and finalization issues](https://www.lua.org/bugs.html#5.4.8)
against the embedded runtime. No backport or dependency substitution addresses
these follow-ups in this snapshot. NetHack's bounded Lua allocator and safe
level-loading libraries narrow exposure, but smoke tests do not establish
absence or remediation. Dependency updates need focused reproduction, updated
source inventory/notices, save compatibility and rebuilt runtime checks.

Documentation-only changes require content, command and link inspection, without
rerunning unrelated gameplay suites.
