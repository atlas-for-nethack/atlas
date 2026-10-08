# Working on Atlas for NetHack

## Product and architecture

Build a self-contained, offline macOS application around the real NetHack 5.0 engine. Preserve upstream gameplay rules and make the interface comfortable for keyboard and mouse play. The default distribution targets macOS 13 or later and contains both Apple Silicon and Intel binaries.

- `native/`: Swift AppKit host, local WKWebView, process bridge, save recovery and tile import.
- `web/`: dependency-free HTML/CSS/JavaScript interface and canvas renderer.
- `engine/`: maintained C window port, build configuration and cross-compilation support. `winatelier.c` replaces the upstream shim only inside the generated build tree.
- `assets/tiles/`: shipped artwork, tile mappings, conversion script, provenance and licenses.
- `scripts/`: builds, engine tests, native application tests and bundle verification.
- `docs/`: architecture, protocol, UI, source/licensing and verification evidence.

Read `README.md` and the relevant documents before changing an integration boundary. Keep `docs/protocol.md` synchronized with changes to the C, Swift or JavaScript bridge.

## Working approach

- Make the smallest complete change for the requested behavior. Avoid incidental refactors and unnecessary dependencies.
- Work collaboratively on design choices. Before implementing a major change to the app's architecture, gameplay interaction, or visual direction, present the proposed design, meaningful alternatives, and tradeoffs to the user, then wait for their explicit sign-off. Approval of one design does not authorize a materially different design. Routine fixes and small changes within an approved design can proceed without another sign-off.
- For substantial design work, use bounded sub-agent tasks when authorized, with clear ownership of files. Integrate and verify the combined result yourself. Do not have multiple agents edit or build the same outputs concurrently.
- Inspect existing changes before editing or committing. Preserve unrelated work.
- Verify a reported bug against the actual engine when possible. Preview fixtures and recorded events are useful for layout checks, but do not prove live gameplay works.
- Keep user-facing explanations concise and nontechnical unless technical details help. Do not claim unperformed testing or platform support beyond the evidence.

## Gameplay and data invariants

- NetHack owns game state and turn progression. Do not simulate gameplay or infer hidden monster or object information in the interface. Hover inspection must respect what the adventurer can perceive and must not consume turns.
- Respect the engine's input kind and command/direction/targeting flags. Direction requests use the bar below the map, without obscuring or dimming the dungeon. Use the engine's direction bindings for arrow and compass controls, including keypad modes.
- Pass Escape through using the appropriate protocol response. Do not promise it reverses a committed spell or action; upstream NetHack determines the outcome.
- Selection prompts should list named choices using the engine's menus, including single-item selections and restored games. Preserve safe cancellation, quantity selection, keyboard accelerators and unknown-item descriptions. Never infer item names from prompt letters.
- Character creation must expose sex and alignment, including explicit random choices, and honor role/race/sex/alignment restrictions. Preserve saved characters when changing creation defaults.
- Populate action lists and shortcuts from the engine catalog. Dispatch named actions through ordinary engine command handling. Context suggestions must use displayed appearances, engine-maintained player memory and known inventory or abilities, never undiscovered world state. Account for features under the hero sprite. Browsing and filtering commands must not advance turns.
- Saves, bones and scores belong in the app's Application Support directory. Never use a player's real save directory for automated testing or remove locks belonging to a live engine.
- Recovery must preserve original checkpoints until recovery succeeds. Stage recovery in isolation and publish a successful save safely.
- Keep the renderer offline. Do not introduce remote scripts, fonts, telemetry or runtime package-manager dependencies.

## Builds

From the repository root on macOS with Xcode Command Line Tools and Python 3:

```sh
./scripts/build-app.sh
```

The first build downloads checksum-pinned NetHack and Lua sources. The full app build packages the engine, data, source archives, artwork and license notices. It stages a complete signed bundle before replacing `dist/Atlas.app`; preserve this behavior so rebuilding cannot overwrite binaries inside a running game.

For engine changes, run `./scripts/build-engine.sh` before rebuilding the app. `ENGINE_ARCH=native` can speed local engine iteration, but release verification requires a Universal 2 engine and recovery helper. Use `REBUILD_ENGINE=1 ./scripts/build-app.sh` when a full engine rebuild is needed.

Changes to downloaded or generated files under `vendor/` are disposable. Maintain engine changes in `engine/` and update build scripts when necessary. Preserve archive checksums and source/license distribution requirements.

Keep `docs/ENGINE_FORK.md` as the living inventory of actual upstream NetHack source changes. Preserve upstream notices and add prominent dated change notices in every modified upstream file, as required by NGPL paragraph 2(a). Update the source audit and packaged updated-file archive when the inventory changes. Run `python3 scripts/audit-engine-fork.py` against the prepared build tree and verify the rebuilt source payload. GUI and overlay changes belong in their own documentation.

Tile regeneration additionally requires Pillow:

```sh
python3 scripts/build-tilesets.py
```

Maintain the pinned engine tile ordering, rectangular tile proportions, fallback mappings and artwork provenance. Do not bundle new third-party artwork without verified redistribution rights.

Every selectable tileset has one recipe in `assets/tiles/recipes/`, one PNG and
one provenance receipt. Use the shared compiler above for export and manifest
registration; source preparation modules do not publish assets. A tileset may
stand alone with any name, and rendering capabilities are declared in metadata.
See `docs/TILESETS.md` for adding a recipe and testing an isolated output.

Use lowercase names with hyphens for future tileset files. Recommended naming:

- PNG: `<family>-<edition>.png`, such as
  `lantern-classic.png` or `soot-and-brass-modern.png`.
- Recipe: `<family>-<edition>.json`, such as `lantern-classic.json`.
- Output receipt: `<family>/<edition>-provenance.json`.

A standalone tileset may omit the edition: `<family>.png`, `<family>.json`, and
`<family>/provenance.json`. Keep engine compatibility in the recipe and manifest,
and artwork revision in the recipe's `version` field. Before updating the engine,
check its tile catalog and ordering to decide whether remapping, new artwork or
regeneration is needed. A version change alone does not require new PNG names. Use
the same edition labels throughout a family. Names do not determine rendering
capabilities, and a second edition is optional. Keep published tileset IDs stable
so saved display choices survive filename and artwork updates.

Use `tools/tileset-preview/index.html` as the basic starting point for rendering and reviewing every new tileset. Its tileset selector reads the compiled manifest automatically. Reuse its actual game renderer, room, crowding, directional door, bar and shared-wall scenes. Keep Classic/Modern comparisons where applicable and retain the explicit distinction between illustrative fixtures and live engine verification.

## Verification

Run the checks relevant to the change. Node.js is required only for the focused JavaScript tests; it is not a player dependency.

```sh
python3 scripts/test-character-rules.py
python3 scripts/test-engine.py
python3 scripts/test-actions.py
python3 scripts/test-context.py
python3 scripts/test-item-menus.py
python3 scripts/test-recovery.py
node web/input.test.js
python3 scripts/test-native.py --gender female
python3 scripts/test-native.py --gender male
python3 scripts/verify-bundle.py
```

- Engine/protocol changes: engine tests and affected input or recovery tests, followed by a rebuilt app and native integration test.
- UI changes: relevant input tests and visual inspection; exercise gameplay changes in the packaged native app.
- Packaging changes: rebuild and verify the bundle. Test the native app if launch, resources or process handling changed.
- Documentation-only changes: inspect the content, links and commands; do not rerun unrelated gameplay suites.

The native test needs a logged-in macOS desktop session and uses isolated data under `.artifacts/`. Do not run it against user saves. Inspect failed diagnostics before changing tests. Prefer assertions about independently observable behavior over tests that mirror implementation details.

Record meaningful verification and its limits in `docs/VERIFICATION.md`. An Intel slice passing structural checks does not demonstrate Intel gameplay; a deployment target does not demonstrate execution on every supported macOS release. Ad-hoc signing is not Developer ID signing or notarization.

## Version control and releases

Commit maintained source, scripts, documentation, shipped tile assets, mappings, provenance, licenses and the application icon. Exclude `dist/`, `.build/`, `.artifacts/`, `engine/runtime/`, downloaded `vendor/` trees, caches and local game data. Do not force-add generated bundles or test saves.

Keep release applications, ZIP archives and checksums outside Git history. They can be distributed as release attachments. Update `native/Info.plist` for a new app version, verify the built bundle, then create the corresponding archive and checksum. Never publish or push unless requested.

For project-original Modern tilesets, use the shared seven-tier creature catalog in `assets/tiles/creature-scale.json` and `creature_scale.py`: Tiny, Small, Standard, Large, Very Large, Huge, Massive. Every creature has one assigned tier across all Modern artwork. Preserve aspect ratio without width caps reducing tier height. Classic creatures remain one square; do not impose this policy on third-party tilesets.

Within each original artwork family, Classic and Modern must share identical walls, doors, floors, objects, and architectural rendering. Only creature/statue display sizing differs between editions.

## Agent skills

### Issue tracker

Work is tracked in GitHub Issues on the fork `lukethan/atlas`, not upstream. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels, each named after its role (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `CONTEXT.md` plus `docs/adr/`. See `docs/agents/domain.md`.
