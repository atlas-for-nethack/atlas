# NetHack engine integration

This is the real NetHack 5.0.0 engine, downloaded from the official release and pinned by SHA-256. `scripts/build-engine.sh` verifies the source archive, installs the custom window port, compiles static Lua 5.4.8 (also checksum pinned), builds NetHack and its game database, and produces Universal 2 executables in `engine/runtime/`.

See [the living engine fork record](../docs/ENGINE_FORK.md) for the exact upstream modifications, dated notices and NGPL source payload. `python3 scripts/audit-engine-fork.py` checks the prepared source tree against the pinned release; engine builds and app source packaging run this audit automatically.

Build prerequisites are Xcode Command Line Tools, Python 3, and network access on the first build. No Homebrew libraries are required by the application. Set `ENGINE_ARCH=native` when building only the local architecture during development. Generated source/build files live under `vendor/`; custom maintained code stays here. `winatelier.c` replaces upstream `win/shim/winshim.c` only in the build tree. It does not replace or reimplement gameplay.

`apply-beginner-patch.py` applies an idempotent, fail-closed new-game hook to the pinned source's `src/allmain.c`. With `ATLAS_PLAY_MODE=beginner`, the port places the fixed supply chest on nearby reachable floor away from the stairs after normal character initialization and before the first checkpoint. Standard launch and all restore paths bypass the gift. The host isolates Beginner saves, bones and scores in a separate runtime. This is a deliberate starting-condition customization, with normal object, carrying, combat and death behavior retained. See `docs/protocol.md` for the kit and mode contract.

`cross.mk` and `build-cross.py` use native upstream generators while compiling separate target objects and static Lua objects. This allows an Apple Silicon host without Rosetta to produce the Intel slice. Both slices link for macOS 13.0. Binary signatures are ad hoc; distribution signing/notarization is a separate packaging concern.

See `docs/protocol.md` for process launch, JSON event fields, input commands, game isolation, and interrupted-game recovery. The upstream NetHack license remains in the source archive and runtime. Lua's MIT terms are preserved in the vendored Lua header and should accompany distribution notices.

Validation: `python3 scripts/test-engine.py` runs the real bundled engine against temporary game data. Its checks cover gameplay, visibility-limited inspection without consuming turns, menus, saves/restoration, prompt cancellation, parent disappearance, and crash recovery. Intel gameplay execution needs separate hardware or Rosetta.
