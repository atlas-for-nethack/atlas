#!/usr/bin/env python3
"""Compare every original regular file against the pinned NetHack release.

Read-only for engine sources and game data. Write an optional local report;
reject missing, unclassified or unexpected changes, including new source files.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = '2959b7886aac76185b90aea0c9f80d14343f604de0ae96b3dd2a760f7ab3bde9'
MODIFIED = {'src/allmain.c', 'win/shim/winshim.c'}
GENERATED = {'src/tile.c', 'include/date.h', 'include/nhlua.h'}
SOURCE_DIRS = ('src', 'include', 'dat', 'win', 'sys', 'util')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit(archive, tree):
    archive_hash = digest(archive.read_bytes())
    if archive_hash != ARCHIVE_SHA256:
        raise ValueError('NetHack release archive checksum mismatch')
    spec = importlib.util.spec_from_file_location('atlas_beginner_patch', ROOT/'engine/apply-beginner-patch.py')
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)
    entries, changed, unchanged = {}, [], 0
    with tarfile.open(archive, 'r:gz') as upstream:
        for member in upstream:
            if not member.isfile():
                continue
            relative = Path(member.name).relative_to('NetHack-5.0.0')
            if '..' in relative.parts or relative.is_absolute():
                raise ValueError('Unexpected release archive path')
            name = relative.as_posix()
            original = upstream.extractfile(member).read()
            path = tree/relative
            if not path.is_file():
                raise ValueError('Missing upstream file: '+name)
            current = path.read_bytes()
            entries[name] = {'upstreamSha256': digest(original), 'currentSha256': digest(current)}
            if name == 'src/allmain.c':
                expected = patch.apply_text(original.decode()).encode()
            elif name == 'win/shim/winshim.c':
                expected = (ROOT/'engine/winatelier.c').read_bytes()
                notices = original.decode().split('\n\n', 1)[0]
                if not expected.decode().startswith(notices + '\n'):
                    raise ValueError('Shim replacement dropped upstream notices')
                if 'Modified by the NetHack Atlas project:' not in expected.decode():
                    raise ValueError('Shim replacement lacks modification notice')
            else:
                expected = original
            if current != expected:
                raise ValueError('Unrecorded or unexpected upstream change: '+name)
            if current != original:
                changed.append(name)
            else:
                unchanged += 1
    if set(changed) != MODIFIED:
        raise ValueError('Expected the two documented upstream modifications')
    hint = tree/'sys/unix/hints/atelier'
    if not hint.is_file() or hint.read_bytes() != (ROOT/'engine/hints').read_bytes():
        raise ValueError('Atlas build hint missing or inconsistent')
    generated = []
    for directory in SOURCE_DIRS:
        for path in (tree/directory).rglob('*'):
            if not path.is_file() or path.suffix not in ('.c', '.h', '.lua'):
                continue
            name = path.relative_to(tree).as_posix()
            if name in entries:
                continue
            if name not in GENERATED:
                raise ValueError('Unclassified added engine source: '+name)
            generated.append(name)
    record = {'upstream': 'NetHack 5.0.0', 'archiveSha256': archive_hash,
              'originalFileCount': len(entries), 'unchangedFileCount': unchanged,
              'modifiedFiles': sorted(changed), 'files': entries,
              'addedIntegrationFiles': ['sys/unix/hints/atelier'],
              'generatedSources': sorted(generated),
              'scope': 'All original regular files; generated sources are listed, not gameplay forks. No saves or binaries examined.'}
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT/'vendor/nethack-500-src.tgz')
    parser.add_argument('--tree', type=Path, default=ROOT/'vendor/NetHack-5.0.0')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        record = audit(args.archive, args.tree)
    except (ValueError, OSError) as error:
        parser.exit(1, 'FAIL: '+str(error)+'\n')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(record, indent=2)+'\n')
    print(f"PASS: {record['unchangedFileCount']} unchanged upstream files; "
          f"{len(record['modifiedFiles'])} documented modifications; "
          'Atlas build hint verified.')


if __name__ == '__main__':
    main()
