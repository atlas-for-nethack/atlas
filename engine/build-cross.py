#!/usr/bin/env python3
"""Cross-compile target code while keeping upstream generators native."""
import concurrent.futures
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'vendor' / 'NetHack-5.0.0'
architecture = sys.argv[1]
assert architecture in ('arm64', 'x86_64')
target = SOURCE / 'targets' / architecture
target.mkdir(parents=True, exist_ok=True)
base = ['clang', '-arch', architecture, '-mmacosx-version-min=13.0', '-O2', '-g']
config = ['-I../include', '-DSHIM_GRAPHICS', '-DNOTTYGRAPHICS', '-DTILES_IN_GLYPHMAP',
          '-DDEFAULT_WINDOW_SYS="shim"', '-DHACKDIR="."', '-DDLB', '-DNOMAIL', '-DNOSHELL']

def compile_lua(source):
    destination = target / ('lua-' + source.stem + '.o')
    if not destination.exists() or source.stat().st_mtime > destination.stat().st_mtime:
        subprocess.run(base + ['-DLUA_USE_POSIX', '-c', str(source), '-o', str(destination)], check=True)
    return destination

lua_sources = [p for p in (SOURCE / 'lib' / 'lua-5.4.8' / 'src').glob('*.c') if p.name not in ('lua.c', 'luac.c')]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    objects = list(executor.map(compile_lua, lua_sources))
subprocess.run(['ar', 'rcs', str(target / 'liblua.a')] + [str(p) for p in objects], check=True)
subprocess.run(['make', '-j8', '-C', str(SOURCE / 'src'), '-f', 'Makefile', '-f',
                str(ROOT / 'engine' / 'cross.mk'), 'CROSS_ARCH=' + architecture, 'TARGETPFX=../targets/' + architecture + '/', 'WINOBJ=../targets/' + architecture + '/winshim.o ../targets/' + architecture + '/tile.o', 'nethack'], check=True)
recover_objects = []
for filename, defines in [('recover.c', []), ('../src/version.c', ['-DMINIMAL_FOR_RECOVER']), ('panic.c', [])]:
    output = target / ('recover-' + pathlib.Path(filename).stem + '.o')
    subprocess.run(base + config + defines + ['-c', filename, '-o', str(output)], cwd=SOURCE / 'util', check=True)
    recover_objects.append(str(output))
subprocess.run(base + recover_objects + [str(target / 'hacklib.o'), '-o', str(target / 'recover')], check=True)
