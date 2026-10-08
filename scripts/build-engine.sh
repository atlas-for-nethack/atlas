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
case "$(uname -s)" in MINGW*|MSYS*) WINDOWS=1 ;; *) WINDOWS=0 ;; esac
[ "$WINDOWS" = 0 ] || python3 engine/apply-windows-patch.py "$SOURCE"
python3 scripts/audit-engine-fork.py
cd "$SOURCE"
if [ ! -f lib/lua-5.4.8/src/lua.h ]; then
  mkdir -p lib
  tar xzf "$ROOT/vendor/lua-5.4.8.tar.gz" -C lib
fi
if [ "$WINDOWS" = 1 ]; then
  # Windows, from Git Bash with llvm-mingw on PATH. Upstream's Windows makefile
  # builds the generators, game data, static Lua and recover.exe; the
  # maintained fragment links the game with the Atlas port. Local arch only.
  (cd src && mingw32-make -f ../sys/windows/GNUmakefile -f ../../../engine/windows.mk \
    INTERNET_AVAILABLE=N USE_LUADLL=N SKIP_NETHACKW=Y DEBUGINFO=N SOUND_LIBRARIES= \
    cc="clang -c" cxx="clang++ -c" ld=clang -j8 atlas)
  RUNTIME="$ROOT/engine/runtime"
  cp binary/nethack.exe binary/recover.exe binary/nhdat500 dat/license dat/symbols \
    dat/opthelp doc/Guidebook.txt "$RUNTIME/"
  # Upstream ignores HOME and NETHACKDIR on Windows. A portable sysconf beside
  # the executable keeps every file in that folder, so each runtime needs its
  # own copy of the executable. Startup also expects the templates.
  { cat "$ROOT/engine/sysconf"; echo 'PORTABLE_DEVICE_PATHS=1'; } > "$RUNTIME/sysconf"
  cp "$RUNTIME/sysconf" "$RUNTIME/sysconf.template"
  cp "$RUNTIME/symbols" "$RUNTIME/symbols.template"
  echo '# Atlas: options come from NETHACKOPTIONS.' > "$RUNTIME/nethackrc.template"
  touch "$RUNTIME/record" "$RUNTIME/logfile" "$RUNTIME/xlogfile" "$RUNTIME/perm"
  printf '\nBuilt engine/runtime/nethack.exe and bundled data.\n'
  exit 0
fi
sh sys/unix/setup.sh sys/unix/hints/atelier
# The single maintained hint targets macOS. On Linux, pass the same build
# choices without the macOS deployment flags; no second hint file is installed.
MAKEVARS=()
if [ "$(uname -s)" = Linux ]; then
  MAKEVARS=(CC=cc 'CFLAGS=-O2 -g -I../include -DSHIM_GRAPHICS -DNOTTYGRAPHICS -DTILES_IN_GLYPHMAP -DDEFAULT_WINDOW_SYS=\"shim\" -DHACKDIR=\".\" -DDLB -DNOMAIL -DNOSHELL' SYSCFLAGS=-DLUA_USE_POSIX LFLAGS=)
  ENGINE_ARCH=native
fi
make -j8 all ${MAKEVARS[@]+"${MAKEVARS[@]}"}
make nhtiles.bmp ${MAKEVARS[@]+"${MAKEVARS[@]}"}
# The upstream recover rule does not depend on Makefile/linker flags.
make -C util -W recover.o recover ${MAKEVARS[@]+"${MAKEVARS[@]}"}
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
if [ "$(uname -s)" = Darwin ]; then
  codesign --force --sign - "$ROOT/engine/runtime/nethack"
  codesign --force --sign - "$ROOT/engine/runtime/recover"
fi
cp dat/nhdat dat/license dat/symbols "$ROOT/engine/runtime/"
cp "$ROOT/engine/sysconf" "$ROOT/engine/runtime/sysconf"
mkdir -p "$ROOT/engine/runtime/save"
touch "$ROOT/engine/runtime/record" "$ROOT/engine/runtime/logfile" "$ROOT/engine/runtime/xlogfile" "$ROOT/engine/runtime/perm"
printf '\nBuilt engine/runtime/nethack and bundled data.\n'
