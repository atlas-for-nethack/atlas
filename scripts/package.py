#!/usr/bin/env python3
"""Clean Atlas staging, recursive payload inspection and pinned source handling.

Only regular files/directories are supported in Atlas payloads. A symlink is
rejected rather than followed, including archive symlinks and hard links. This
keeps excluded metadata from entering through alternate names or link targets.
Python's archive writers do not copy macOS resource forks or extended attributes.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINS_FILE = Path(__file__).with_name('source-pins.json')
SOURCE_ROOTS = ('native', 'web', 'engine', 'scripts', 'tools', 'docs', 'README.md', 'AGENTS.md', 'LICENSE.txt', 'LICENSES.md', '.gitignore')
RESOURCE_ROOTS = ('web', 'assets', 'tools', 'docs', 'README.md', 'AGENTS.md', 'LICENSE.txt', 'LICENSES.md')
SOURCE_INVENTORY = 'source-inventory.json'
MAX_ARCHIVE_DEPTH = 8
MAX_INSPECTION_ENTRIES = 20_000
MAX_INSPECTION_BYTES = 1024 * 1024 * 1024
MAX_INSPECTION_MEMBER_BYTES = 512 * 1024 * 1024


class InspectionBudget:
    def __init__(self):
        self.entries = 0
        self.bytes = 0

    def add(self, name, size):
        if size < 0 or size > MAX_INSPECTION_MEMBER_BYTES:
            raise ValueError('Payload member exceeds inspection size limit: ' + name)
        self.entries += 1
        self.bytes += size
        if self.entries > MAX_INSPECTION_ENTRIES or self.bytes > MAX_INSPECTION_BYTES:
            raise ValueError('Payload exceeds cumulative inspection budget: ' + name)


def forbidden(name):
    """Apply one component policy to trees, tar members and ZIP members."""
    return any(part.casefold() in ('.ds_store', '__pycache__', '__macosx')
               or part.startswith('._') or part.casefold().endswith(('.pyc', '.pyo'))
               for part in PurePosixPath(name.replace('\\', '/')).parts)


def clean_name(name):
    # Reject alternate separators rather than accepting a path that a different
    # extractor may interpret differently. Normal './' tar prefixes are valid.
    path = PurePosixPath(name)
    if '\\' in name or path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe payload path: ' + name)
    if forbidden(name):
        raise ValueError('Forbidden metadata/cache path: ' + name)
    return path.as_posix()


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _digest_stream(handle)


def _digest_stream(handle):
    value = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
        value.update(chunk)
    return value.hexdigest()


def source_pins():
    return json.loads(PINS_FILE.read_text())


def verify_pins(directory, pins=None):
    for name, pin in (source_pins() if pins is None else pins).items():
        path = Path(directory) / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing regular pinned source archive: ' + str(path))
        if digest(path) != pin['sha256']:
            raise ValueError('Pinned source archive checksum mismatch: ' + name)


def ensure_sources(directory, offline=False, pins=None):
    """Prefer included archives; never repair a corrupt cache silently."""
    directory = Path(directory)
    pins = source_pins() if pins is None else pins
    # Check every existing cache before downloading or altering any missing one.
    for name, pin in pins.items():
        path = directory / name
        if path.exists() or path.is_symlink():
            verify_pins(directory, {name: pin})
        elif offline:
            raise ValueError('Offline build requires included source archive: ' + name)
    directory.mkdir(parents=True, exist_ok=True)
    for name, pin in pins.items():
        path = directory / name
        if path.exists():
            continue
        descriptor, temporary = tempfile.mkstemp(prefix=name + '.', dir=directory)
        try:
            with os.fdopen(descriptor, 'wb') as output, urllib.request.urlopen(pin['url'], timeout=60) as response:
                shutil.copyfileobj(response, output)
            if digest(temporary) != pin['sha256']:
                raise ValueError('Downloaded source archive checksum mismatch: ' + name)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    verify_pins(directory, pins)


def reject_symlink_path(root, relative):
    """Reject links in every component below the supplied source root."""
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Payload source root symlink is unsupported: ' + str(root))
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Payload symlink ancestor/node is unsupported: ' + str(relative) + ' -> ' + os.readlink(path))


def tracked_files(root):
    """Use the Git index or the inventory shipped in a standalone source archive."""
    root = Path(root)
    if (root / '.git').exists():
        try:
            output = subprocess.check_output(
                ['git', '-C', str(root), 'ls-files', '--cached', '-z'], stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as error:
            raise ValueError('Cannot read the maintained Git source inventory') from error
        return set(os.fsdecode(name) for name in output.split(b'\0') if name)
    inventory = root / SOURCE_INVENTORY
    if inventory.is_symlink() or not inventory.is_file():
        raise ValueError('Maintained source staging requires a Git checkout or source inventory')
    names = json.loads(inventory.read_text())
    if not isinstance(names, list) or any(not isinstance(name, str) or clean_name(name) != name for name in names):
        raise ValueError('Invalid standalone source inventory')
    if len(names) != len(set(names)):
        raise ValueError('Duplicate standalone source inventory entry')
    return set(names)


def selected_files(root, entries, excludes=(), allowed=None):
    """Yield clean source names; do not traverse unsupported filesystem objects."""
    root = Path(root)
    seen = set()
    allowed_dirs = set()
    if allowed is not None:
        for name in allowed:
            allowed_dirs.update(str(parent) for parent in PurePosixPath(name).parents if str(parent) != '.')

    def visit(relative):
        name = relative.as_posix()
        if forbidden(name) or any(name == excluded or name.startswith(excluded + '/') for excluded in excludes):
            return
        if allowed is not None and name not in allowed and name not in allowed_dirs:
            return
        clean_name(name)
        reject_symlink_path(root, relative)
        path = root / relative
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError('Payload symlink is unsupported: ' + name + ' -> ' + os.readlink(path))
        if stat.S_ISDIR(mode):
            for child in sorted(path.iterdir()):
                yield from visit(relative / child.name)
        elif stat.S_ISREG(mode):
            if name not in seen:
                seen.add(name)
                yield name
        else:
            raise ValueError('Unsupported payload object: ' + name)

    for entry in entries:
        yield from visit(PurePosixPath(entry))


def copy_clean(root, destination, entries, excludes=(), allowed=None):
    for name in selected_files(root, entries, excludes, allowed):
        target = Path(destination) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # copyfile preserves content, copymode preserves executable bits, neither
        # copies xattrs/resource forks from the developer checkout.
        shutil.copyfile(Path(root) / name, target)
        shutil.copymode(Path(root) / name, target)


def write_tar(root, destination, entries, excludes=(), allowed=None, extra_files=None):
    with tarfile.open(destination, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
        for name in selected_files(root, entries, excludes, allowed):
            path = Path(root) / name
            member = archive.gettarinfo(str(path), arcname=name)
            member.uid = member.gid = 0
            member.uname = member.gname = ''
            with path.open('rb') as handle:
                archive.addfile(member, handle)
        for name, content in (extra_files or {}).items():
            clean_name(name)
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(content))


def _archive_kind(name, header):
    lowered = name.casefold()
    if lowered.endswith('.zip') or header.startswith(b'PK\x03\x04') or header.startswith(b'PK\x05\x06'):
        return 'zip'
    if lowered.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz')) or header.startswith((b'\x1f\x8b', b'BZh', b'\xfd7zXZ\x00')) or header[257:262] == b'ustar':
        return 'tar'
    return None


def inspect_stream(handle, name, depth=0, budget=None):
    """Inspect archives recursively without extraction or following link targets."""
    budget = InspectionBudget() if budget is None else budget
    header = handle.read(512)
    handle.seek(0)
    kind = _archive_kind(name, header)
    kinds = [kind] if kind else []
    # ZIP permits arbitrary prefixes. Detect its end directory independent of
    # filename and leading magic, then restore the stream before inspection.
    if zipfile.is_zipfile(handle) and 'zip' not in kinds:
        kinds.append('zip')
    handle.seek(0)
    if kinds and depth >= MAX_ARCHIVE_DEPTH:
        raise ValueError('Archive nesting exceeds inspection limit: ' + name)
    for kind in kinds:
        handle.seek(0)
        inspect_archive(handle, name, kind, depth, budget)


def inspect_archive(handle, name, kind, depth, budget):
    if kind == 'zip':
        with zipfile.ZipFile(handle) as archive:
            names = set()
            for member in archive.infolist():
                budget.add(name + ':' + member.filename, member.file_size)
                normalized = clean_name(member.filename)
                if normalized in names:
                    raise ValueError('Duplicate archive member: ' + name + ':' + normalized)
                names.add(normalized)
                mode = member.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if stat.S_ISLNK(mode):
                    raise ValueError('Archive symlink is unsupported: ' + name + ':' + member.filename)
                allowed = (0, stat.S_IFDIR) if member.is_dir() else (0, stat.S_IFREG)
                if kind not in allowed or (member.external_attr & 0x10 and not member.is_dir()):
                    raise ValueError('Archive special/conflicting ZIP member is unsupported: ' + name + ':' + member.filename)
                if member.is_dir():
                    continue
                with archive.open(member) as content:
                    inspect_member(content, member.filename, name, depth, budget)
    else:
        with tarfile.open(fileobj=handle, mode='r:*') as archive:
            names = set()
            for member in archive:
                budget.add(name + ':' + member.name, member.size)
                normalized = clean_name(member.name)
                if normalized in names:
                    raise ValueError('Duplicate archive member: ' + name + ':' + normalized)
                names.add(normalized)
                if not member.isdir() and not member.isfile():
                    raise ValueError('Archive link/special member is unsupported: ' + name + ':' + member.name)
                # PAX may expose metadata even when member names look clean.
                for key in member.pax_headers:
                    if 'xattr' in key.casefold() or 'apple' in key.casefold():
                        raise ValueError('Archive extended metadata is unsupported: ' + name + ':' + member.name)
                if member.isfile():
                    with archive.extractfile(member) as content:
                        inspect_member(content, member.name, name, depth, budget)


def inspect_member(content, member_name, container_name, depth, budget):
    if content.seekable():
        # tar/ZIP regular-member streams are seekable here. Inspect in place;
        # artwork is not copied to a temporary file to check ZIP end directories.
        inspect_stream(content, container_name + ':' + member_name, depth + 1, budget)
        return
    # Fail closed on excessive nonseekable input. Spool these rare streams to
    # disk so prefixed ZIPs cannot hide behind missing seek support.
    with tempfile.TemporaryFile() as temporary:
        total = 0
        for chunk in iter(lambda: content.read(1024 * 1024), b''):
            total += len(chunk)
            if total > MAX_INSPECTION_MEMBER_BYTES:
                raise ValueError('Nonseekable archive member exceeds 512 MiB inspection limit: ' + member_name)
            temporary.write(chunk)
        temporary.seek(0)
        inspect_stream(temporary, container_name + ':' + member_name, depth + 1, budget)


def inspect_payload(path, budget=None):
    path = Path(path)
    budget = InspectionBudget() if budget is None else budget
    clean_name(path.name)
    if path.is_symlink():
        raise ValueError('Payload symlink is unsupported: ' + str(path))
    if path.is_dir():
        # Unlike clean staging, verification rejects every forbidden path.
        for child in sorted(path.iterdir()):
            clean_name(child.name)
            inspect_payload(child, budget)
    elif path.is_file():
        budget.add(str(path), path.stat().st_size)
        with path.open('rb') as handle:
            inspect_stream(handle, path.name, budget=budget)
    else:
        raise ValueError('Missing or unsupported payload object: ' + str(path))


def stage_resources(root, destination):
    root, destination = Path(root), Path(destination)
    verify_pins(root / 'vendor')
    maintained = tracked_files(root)
    copy_clean(root, destination, RESOURCE_ROOTS, allowed=maintained)
    engine_destination = destination / 'engine'
    engine_destination.mkdir(parents=True, exist_ok=True)
    copy_clean(root / 'engine/runtime', engine_destination, ('nethack', 'recover', 'nhdat', 'license', 'symbols', 'sysconf'))
    source_destination = destination / 'Source'
    source_destination.mkdir(parents=True, exist_ok=True)
    copy_clean(root / 'vendor', source_destination, tuple(source_pins()))
    copy_clean(root / 'engine', source_destination, ('winatelier.c', 'apply-beginner-patch.py', 'hints', 'sysconf'))
    # Keep the standalone build script and its shared pin/policy dependencies
    # beside it for inspection. Reconstruction uses the complete source tar.
    copy_clean(root / 'scripts', source_destination, ('build-engine.sh', 'package.py', 'source-pins.json'))
    if 'native/AppIcon.icns' in maintained:
        copy_clean(root / 'native', destination, ('AppIcon.icns',))
    write_tar(root / 'vendor/NetHack-5.0.0', source_destination / 'engine-upstream-modifications.tar.gz', ('src/allmain.c', 'win/shim/winshim.c', 'sys/unix/hints/atelier'))
    inventory = (json.dumps(sorted(maintained), indent=2) + '\n').encode()
    write_tar(root, source_destination / 'atlas-source.tar.gz', SOURCE_ROOTS,
              ('engine/runtime',), allowed=maintained,
              extra_files={SOURCE_INVENTORY: inventory})


def write_zip(app, destination):
    """Write only the already inspected regular app tree, with no Apple metadata."""
    app = Path(app)
    inspect_payload(app)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for name in selected_files(app.parent, (app.name,)):
            archive.write(app.parent / name, arcname=name)
    inspect_payload(destination)


def verify_zip_matches(app, archive_path):
    app = Path(app)
    expected = set(selected_files(app.parent, (app.name,)))
    with zipfile.ZipFile(archive_path) as archive:
        files = [member.filename for member in archive.infolist() if not member.is_dir()]
        if len(files) != len(set(files)) or set(files) != expected:
            raise ValueError('Release ZIP does not contain exactly the validated app files')
        for name in files:
            stored_mode = stat.S_IMODE(archive.getinfo(name).external_attr >> 16)
            if stored_mode != stat.S_IMODE((app.parent / name).stat().st_mode):
                raise ValueError('Release ZIP changes app file permissions: ' + name)
            with archive.open(name) as content:
                if _digest_stream(content) != digest(app.parent / name):
                    raise ValueError('Release ZIP differs from validated app: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    pins = commands.add_parser('pins')
    pins.add_argument('directory', type=Path)
    pins.add_argument('--ensure', action='store_true')
    pins.add_argument('--offline', action='store_true')
    stage = commands.add_parser('stage')
    stage.add_argument('root', type=Path)
    stage.add_argument('destination', type=Path)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('path', type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == 'pins':
            if arguments.ensure:
                ensure_sources(arguments.directory, arguments.offline or os.environ.get('ATLAS_OFFLINE_BUILD') == '1')
            else:
                verify_pins(arguments.directory)
        elif arguments.command == 'stage':
            stage_resources(arguments.root, arguments.destination)
        else:
            inspect_payload(arguments.path)
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, 'FAIL: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
