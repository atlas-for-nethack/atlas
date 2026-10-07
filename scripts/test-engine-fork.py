#!/usr/bin/env python3
"""Check patch migration and fail-closed source auditing in an isolated tree."""
import importlib.util
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


patch = load('beginner_patch', ROOT/'engine/apply-beginner-patch.py')
fork = load('fork_audit', ROOT/'scripts/audit-engine-fork.py')
archive = ROOT/'vendor/nethack-500-src.tgz'
with tempfile.TemporaryDirectory(prefix='atlas-fork-') as temporary:
    tree = Path(temporary)/'NetHack-5.0.0'
    with tarfile.open(archive) as upstream:
        for member in upstream:
            if not member.isfile():
                continue
            relative = Path(member.name).relative_to('NetHack-5.0.0')
            assert not relative.is_absolute() and '..' not in relative.parts
            target = tree/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(upstream.extractfile(member).read())
    original = (tree/'src/allmain.c').read_text()
    noticed = patch.apply_text(original)
    legacy = original.replace(patch.original, patch.patched, 1)
    assert patch.apply_text(legacy) == noticed, 'Existing hook migration failed'
    assert patch.apply_text(noticed) == noticed, 'Patch is not idempotent'
    for invalid in (original.replace(patch.original, '', 1),
                    original.replace('Copyright (c)', 'Removed copyright', 1),
                    noticed.replace('atlas_beginner_kit();', 'unexpected_hook();', 1)):
        try:
            patch.apply_text(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Unexpected patch shape accepted')
    (tree/'src/allmain.c').write_text(noticed)
    (tree/'win/shim/winshim.c').write_bytes((ROOT/'engine/winatelier.c').read_bytes())
    (tree/'sys/unix/hints/atelier').write_bytes((ROOT/'engine/hints').read_bytes())
    result = fork.audit(archive, tree)
    assert result['originalFileCount'] == 1265 and result['unchangedFileCount'] == 1263
    assert set(result['modifiedFiles']) == fork.MODIFIED

    def rejected():
        try:
            fork.audit(archive, tree)
        except ValueError:
            return
        raise AssertionError('Unrecorded source change accepted')

    original_path = tree/'src/mon.c'
    saved = original_path.read_bytes()
    original_path.write_bytes(saved+b'\n/* Unrecorded modification */\n')
    rejected()
    original_path.unlink()
    rejected()
    original_path.write_bytes(saved)
    extra = tree/'src/unrecorded.c'
    extra.write_text('/* Unclassified added source */\n')
    rejected()
    extra.unlink()
    (tree/'sys/unix/hints/atelier').write_text('unexpected settings\n')
    rejected()
print('PASS: pristine/legacy patch migration, idempotence, expected inventory and rejection of unexpected source changes.')
