#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
# Prefer the bundled caches, verify both on every build, and refuse network in
# explicit offline reconstruction mode before mutating the prepared tree.
python3 scripts/package.py pins vendor --ensure
mkdir -p engine/runtime
ARCHIVE=vendor/nethack-500-src.tgz
[ -d vendor/NetHack-5.0.0 ] || tar xzf "$ARCHIVE" -C vendor
SOURCE="$ROOT/vendor/NetHack-5.0.0"
python3 engine/apply-beginner-patch.py "$SOURCE"
cp engine/winatelier.c "$SOURCE/win/shim/winshim.c"
cp engine/hints "$SOURCE/sys/unix/hints/atelier"
python3 scripts/audit-engine-fork.py
cd "$SOURCE"
sh sys/unix/setup.sh sys/unix/hints/atelier
if [ ! -f lib/lua-5.4.8/src/lua.h ]; then
  mkdir -p lib
  tar xzf "$ROOT/vendor/lua-5.4.8.tar.gz" -C lib
fi
make -j8 all
make nhtiles.bmp
# The upstream recover rule does not depend on Makefile/linker flags.
make -C util -W recover.o recover
# Universal 2 by default. Cross-compiled generators remain native, so no
# Rosetta installation is needed. Set ENGINE_ARCH=native for a faster dev build.
if [ "${ENGINE_ARCH:-universal}" = universal ]; then
  if [ "$(uname -m)" = arm64 ]; then OTHER_ARCH=x86_64; else OTHER_ARCH=arm64; fi
  python3 "$ROOT/engine/build-cross.py" "$OTHER_ARCH"
  lipo -create src/nethack "targets/$OTHER_ARCH/nethack" -output "$ROOT/engine/runtime/nethack.new"
  lipo -create util/recover "targets/$OTHER_ARCH/recover" -output "$ROOT/engine/runtime/recover.new"
  mv "$ROOT/engine/runtime/nethack.new" "$ROOT/engine/runtime/nethack"
  mv "$ROOT/engine/runtime/recover.new" "$ROOT/engine/runtime/recover"
else
  install -m 755 src/nethack "$ROOT/engine/runtime/nethack"
  install -m 755 util/recover "$ROOT/engine/runtime/recover"
fi
codesign --force --sign - "$ROOT/engine/runtime/nethack"
codesign --force --sign - "$ROOT/engine/runtime/recover"
cp dat/nhdat dat/license dat/symbols "$ROOT/engine/runtime/"
cp "$ROOT/engine/sysconf" "$ROOT/engine/runtime/sysconf"
mkdir -p "$ROOT/engine/runtime/save"
touch "$ROOT/engine/runtime/record" "$ROOT/engine/runtime/logfile" "$ROOT/engine/runtime/xlogfile" "$ROOT/engine/runtime/perm"
printf '\nBuilt engine/runtime/nethack and bundled data.\n'
