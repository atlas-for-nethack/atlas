#!/usr/bin/env python3
"""Disposable regressions for staging, nested payload rejection and source caches.

No app/engine build, player files, network or platform-signing tools are used.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import io
import json
import shutil
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import package


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='atlas-packaging.')
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def file(self, name, contents=b'valid source\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return path

    def tar(self, name, members):
        path = self.root / name
        with tarfile.open(path, 'w:gz') as archive:
            for filename, data in members.items():
                member = tarfile.TarInfo(filename)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return path

    def test_clean_copy_tar_zip_preserve_required_material_and_checkout(self):
        contents = {'assets/sources/image.png': b'original source pixels',
                    'assets/LICENSE.txt': b'required notice', 'assets/build.py': b'recipe',
                    'assets/mapping.json': b'{"mapping": [1, 2]}'}
        excluded = ('assets/.DS_Store', 'assets/nested/._image.png',
                    'assets/__pycache__/build.cpython-312.pyc', 'assets/loose.pyc',
                    'assets/loose.pyo', 'assets/cache.PYC', 'assets/__MACOSX/notice')
        for name, data in contents.items():
            self.file(name, data)
        for name in excluded:
            self.file(name, b'private workstation path')
        self.file('engine/runtime/save/player', b'disposable sentinel')
        self.file('engine/winatelier.c')
        staged = self.root / 'Clean.app'
        package.copy_clean(self.root, staged, ('assets', 'engine'), ('engine/runtime',))
        expected = {*contents, 'engine/winatelier.c'}
        self.assertEqual({str(p.relative_to(staged)) for p in staged.rglob('*') if p.is_file()}, expected)
        for name, data in contents.items():
            self.assertEqual((staged / name).read_bytes(), data)
        for name in excluded:
            self.assertEqual((self.root / name).read_bytes(), b'private workstation path')
        archive = self.root / 'sources.tar.gz'
        package.write_tar(self.root, archive, ('assets', 'engine'), ('engine/runtime',))
        package.inspect_payload(archive)
        with tarfile.open(archive) as source:
            self.assertEqual(set(source.getnames()), expected)
            self.assertTrue(all(m.uid == m.gid == 0 and m.uname == m.gname == '' for m in source))
            for name, data in contents.items():
                self.assertEqual(source.extractfile(name).read(), data)
        final_zip = self.root / 'release.zip'
        package.write_zip(staged, final_zip)
        package.verify_zip_matches(staged, final_zip)
        with zipfile.ZipFile(final_zip) as release:
            self.assertFalse(any(package.forbidden(m.filename) for m in release.infolist()))

    def test_xattrs_do_not_enter_clean_copy_or_generated_archives(self):
        source = self.file('assets/notice')
        name = 'user.atlas-packaging' if sys.platform != 'darwin' else 'org.nethack.atlas.packaging-test'
        if hasattr(os, 'setxattr'):
            os.setxattr(source, name, b'harmless disposable metadata')
            attributes = os.listxattr
        elif shutil.which('xattr'):
            subprocess.run(['xattr', '-w', name, 'harmless disposable metadata', str(source)], check=True)
            attributes = lambda path: subprocess.check_output(['xattr', str(path)], text=True).splitlines()
        else:
            self.skipTest('xattr API and tool unavailable')
        staged = self.root / 'staged'
        package.copy_clean(self.root, staged, ('assets',))
        self.assertNotIn(name, attributes(staged / 'assets/notice'))
        self.assertIn(name, attributes(source))
        archive = self.root / 'source.tar.gz'
        package.write_tar(self.root, archive, ('assets',))
        with tarfile.open(archive) as payload:
            self.assertTrue(all(not any('xattr' in key for key in m.pax_headers) for m in payload))

    def test_tree_contaminants_fail_before_platform_verification(self):
        for name in ('.DS_Store', 'assets/nested/._image.png', '__pycache__/source',
                     'assets/loose.pyc', 'assets/loose.pyo', '__MACOSX/source'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                app = Path(temporary) / 'Contaminated.app'
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('harmless contamination')
                result = subprocess.run([sys.executable, str(package.ROOT / 'scripts/verify-bundle.py'), '--app', str(app)], text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Forbidden metadata/cache path', result.stderr)
                self.assertNotIn('lipo', result.stderr)

    def test_optimized_interpreter_cannot_skip_bundle_checks(self):
        result = subprocess.run(
            [sys.executable, '-O', str(package.ROOT / 'scripts/verify-bundle.py'),
             '--app', str(self.root / 'Absent.app')],
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Bundle verification requires Python assertions', result.stderr)
        self.assertNotIn('PASS:', result.stdout)

    def test_tar_zip_nested_and_disguised_contaminants_are_rejected(self):
        for bad in ('.DS_Store', 'nested/._image.png', '__pycache__/plain-source',
                    'loose.pyc', 'loose.pyo', '__MACOSX/nested/file'):
            with self.subTest(bad=bad):
                inner = self.tar('inner.tar.gz', {bad: b'harmless cache'})
                with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
                    package.inspect_payload(inner)
                outer = self.root / 'outer.zip'
                with zipfile.ZipFile(outer, 'w') as archive:
                    archive.writestr('nested/payload.bin', inner.read_bytes())
                with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
                    package.inspect_payload(outer)
                outer_tar = self.tar('outer.tar.gz', {'payload.zip': outer.read_bytes()})
                with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
                    package.inspect_payload(outer_tar)

    def test_prefixed_zip_without_zip_extension_rejected_top_level_and_nested(self):
        stream = io.BytesIO(b'prepended non-ZIP bytes\n')
        stream.seek(0, 2)
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('__pycache__/private.pyc', b'harmless fixture')
        payload = self.file('nested.bin', stream.getvalue())
        self.assertTrue(zipfile.is_zipfile(payload))
        with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
            package.inspect_payload(payload)
        outer = self.tar('outer.tar.gz', {'nested.bin': payload.read_bytes()})
        with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
            package.inspect_payload(outer)
        outer_zip = self.root / 'outer.zip'
        with zipfile.ZipFile(outer_zip, 'w') as archive:
            archive.writestr('nested.bin', payload.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Forbidden metadata/cache'):
            package.inspect_payload(outer_zip)
        stream = io.BytesIO(b'benign prefix\n')
        stream.seek(0, 2)
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('LICENSE.txt', b'required clean notice')
        clean = self.file('clean-prefixed.bin', stream.getvalue())
        package.inspect_payload(clean)

    def test_archive_inspection_budgets_each_member_and_the_whole_payload(self):
        archive = self.root / 'budget.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr('first.txt', b'x' * 600)
            output.writestr('second.txt', b'y' * 600)
        with patch.object(package, 'MAX_INSPECTION_MEMBER_BYTES', 512):
            with self.assertRaisesRegex(ValueError, 'member exceeds inspection size'):
                package.inspect_payload(archive)
        with patch.object(package, 'MAX_INSPECTION_BYTES', 1000):
            with self.assertRaisesRegex(ValueError, 'cumulative inspection budget'):
                package.inspect_payload(archive)
        with patch.object(package, 'MAX_INSPECTION_ENTRIES', 2):
            with self.assertRaisesRegex(ValueError, 'cumulative inspection budget'):
                package.inspect_payload(archive)

    def test_tool_symlink_ancestor_cannot_import_external_content(self):
        self.file('repository/tools/notice.md')
        self.file('outside/__pycache__/report.md', b'harmless private-path sentinel')
        repo = self.root / 'repository'
        (repo / 'tools/linked').symlink_to(self.root / 'outside/__pycache__', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink ancestor/node'):
            package.copy_clean(repo, self.root / 'stage', ('tools/linked/report.md',))
        with self.assertRaisesRegex(ValueError, 'symlink ancestor/node'):
            package.write_tar(repo, self.root / 'source.tar.gz', ('tools/linked/report.md',))
        self.assertFalse((self.root / 'stage/tools/linked/report.md').exists())
        self.assertEqual((self.root / 'outside/__pycache__/report.md').read_bytes(), b'harmless private-path sentinel')

    def test_unsafe_paths_links_and_extended_metadata_are_rejected(self):
        for name in ('../escape', '/absolute', 'parent\\loose.pyc'):
            payload = self.tar('bad.tar.gz', {name: b'harmless'})
            with self.assertRaisesRegex(ValueError, 'Unsafe payload path'):
                package.inspect_payload(payload)
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            path = self.root / 'link.tar.gz'
            with tarfile.open(path, 'w:gz') as archive:
                member = tarfile.TarInfo('nominally-clean')
                member.type = kind
                member.linkname = '../__pycache__/private.pyc'
                archive.addfile(member)
            with self.assertRaisesRegex(ValueError, 'link/special member'):
                package.inspect_payload(path)
        path = self.root / 'xattr.tar.gz'
        with tarfile.open(path, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
            member = tarfile.TarInfo('clean')
            member.pax_headers = {'SCHILY.xattr.com.apple.metadata': 'harmless private metadata'}
            archive.addfile(member)
        with self.assertRaisesRegex(ValueError, 'extended metadata'):
            package.inspect_payload(path)
        link_zip = self.root / 'link.zip'
        with zipfile.ZipFile(link_zip, 'w') as archive:
            member = zipfile.ZipInfo('apparently-clean')
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, '../loose.pyc')
        with self.assertRaisesRegex(ValueError, 'Archive symlink'):
            package.inspect_payload(link_zip)
        for filename, kind in [('fifo', stat.S_IFIFO), ('socket', stat.S_IFSOCK),
                               ('device', stat.S_IFCHR), ('block', stat.S_IFBLK),
                               ('directory-without-slash', stat.S_IFDIR),
                               ('regular-with-slash/', stat.S_IFREG)]:
            with self.subTest(filename=filename):
                with zipfile.ZipFile(link_zip, 'w') as archive:
                    member = zipfile.ZipInfo(filename)
                    member.create_system = 3
                    member.external_attr = (kind | 0o644) << 16
                    archive.writestr(member, b'harmless special member')
                with self.assertRaisesRegex(ValueError, 'special/conflicting ZIP member'):
                    package.inspect_payload(link_zip)
        self.file('assets/source')
        (self.root / 'assets/link').symlink_to('source')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            package.copy_clean(self.root, self.root / 'stage', ('assets',))
        with self.assertRaisesRegex(ValueError, 'symlink'):
            package.inspect_payload(self.root / 'assets')

    def test_zip_content_comparison_rejects_changes_missing_and_duplicates(self):
        app = self.root / 'Test.app'
        self.file('Test.app/Contents/Info.plist', b'independently checked content')
        clean = self.root / 'clean.zip'
        package.write_zip(app, clean)
        package.verify_zip_matches(app, clean)
        changed = self.root / 'changed.zip'
        with zipfile.ZipFile(changed, 'w') as archive:
            member = zipfile.ZipInfo('Test.app/Contents/Info.plist')
            member.external_attr = (app / 'Contents/Info.plist').stat().st_mode << 16
            archive.writestr(member, b'different')
        with self.assertRaisesRegex(ValueError, 'differs'):
            package.verify_zip_matches(app, changed)
        executable = self.file('Test.app/Contents/MacOS/Launcher', b'same executable content')
        executable.chmod(0o755)
        executable_zip = self.root / 'executable.zip'
        package.write_zip(app, executable_zip)
        package.verify_zip_matches(app, executable_zip)
        executable.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'changes app file permissions'):
            package.verify_zip_matches(app, executable_zip)
        self.file('Test.app/required-source')
        with self.assertRaisesRegex(ValueError, 'exactly'):
            package.verify_zip_matches(app, clean)
        duplicate = self.tar('duplicate.tar.gz', {'required': b'first'})
        with tarfile.open(duplicate, 'w:gz') as archive:
            for data in (b'first', b'second'):
                member = tarfile.TarInfo('required')
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'Duplicate archive member'):
            package.inspect_payload(duplicate)

    def test_public_roots_do_not_expand_through_document_links(self):
        for name in {*package.SOURCE_ROOTS, *package.RESOURCE_ROOTS}:
            if '.' in name or name == 'README.md':
                self.file(name, b'[private](.artifacts/report.md) [study](design/review.md)')
            else:
                self.file(name + '/maintained.txt')
        self.file('design/review.md', b'retired study')
        self.file('.artifacts/report.md', b'private report')
        self.file('dist/private.app/data', b'generated output')
        self.file('vendor/private-source.txt', b'download cache')
        for roots in (package.SOURCE_ROOTS, package.RESOURCE_ROOTS):
            selected = set(package.selected_files(self.root, roots))
            self.assertTrue(any(name.startswith('tools/') for name in selected))
            self.assertFalse(any(name.startswith(('design/', '.artifacts/', 'dist/', 'vendor/')) for name in selected))
        stage = self.root / 'stage'
        package.copy_clean(self.root, stage, package.RESOURCE_ROOTS)
        self.assertFalse((stage / '.artifacts').exists())
        self.assertFalse((stage / 'design').exists())

    def test_missing_public_root_fails_clearly(self):
        with self.assertRaises(FileNotFoundError):
            list(package.selected_files(self.root, ('tools',)))

    def pins(self):
        return {name: {'sha256': hashlib.sha256(data).hexdigest(), 'url': 'https://invalid.example/' + name}
                for name, data in [('nethack-500-src.tgz', b'NetHack fixture'), ('lua-5.4.8.tar.gz', b'Lua fixture')]}

    def test_cached_offline_sources_never_download(self):
        pins = self.pins()
        self.file('vendor/nethack-500-src.tgz', b'NetHack fixture')
        self.file('vendor/lua-5.4.8.tar.gz', b'Lua fixture')
        with patch('package.urllib.request.urlopen', side_effect=AssertionError('network forbidden')) as network:
            package.ensure_sources(self.root / 'vendor', offline=True, pins=pins)
            package.ensure_sources(self.root / 'vendor', pins=pins)
            network.assert_not_called()

    def test_missing_or_corrupt_cache_fails_without_network_or_repair(self):
        pins = self.pins()
        with patch('package.urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'Offline build requires'):
                package.ensure_sources(self.root / 'vendor', offline=True, pins=pins)
            network.assert_not_called()
        self.file('vendor/nethack-500-src.tgz', b'corrupt sentinel')
        with patch('package.urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                package.ensure_sources(self.root / 'vendor', pins=pins)
            network.assert_not_called()
        self.assertEqual((self.root / 'vendor/nethack-500-src.tgz').read_bytes(), b'corrupt sentinel')
        self.assertFalse((self.root / 'vendor/lua-5.4.8.tar.gz').exists())

    def test_both_pins_checked_including_cached_lua_and_symlinks(self):
        self.file('vendor/nethack-500-src.tgz', b'NetHack fixture')
        lua = self.file('vendor/lua-5.4.8.tar.gz', b'Lua fixture')
        package.verify_pins(self.root / 'vendor', self.pins())
        lua.write_bytes(b'corrupt Lua')
        with self.assertRaisesRegex(ValueError, 'lua-5.4.8.tar.gz'):
            package.verify_pins(self.root / 'vendor', self.pins())
        lua.unlink()
        lua.symlink_to(self.file('elsewhere', b'Lua fixture'))
        with self.assertRaisesRegex(ValueError, 'Missing regular pinned'):
            package.verify_pins(self.root / 'vendor', self.pins())

    def test_download_failure_does_not_publish_invalid_archive(self):
        pins = {'lua-5.4.8.tar.gz': self.pins()['lua-5.4.8.tar.gz']}
        with patch('package.urllib.request.urlopen', return_value=io.BytesIO(b'corrupt download')):
            with self.assertRaisesRegex(ValueError, 'Downloaded source archive checksum'):
                package.ensure_sources(self.root / 'vendor', pins=pins)
        self.assertEqual(list((self.root / 'vendor').iterdir()), [])
        with patch('package.urllib.request.urlopen', return_value=io.BytesIO(b'Lua fixture')):
            package.ensure_sources(self.root / 'vendor', pins=pins)
        self.assertEqual((self.root / 'vendor/lua-5.4.8.tar.gz').read_bytes(), b'Lua fixture')

    def test_failed_build_preflight_preserves_previous_complete_app(self):
        # Exercise the real entrypoint only up to its intentionally failing pin
        # preflight. No compiler, engine build or production checkout is touched.
        for name in ('build-app.sh', 'package.py', 'source-pins.json'):
            self.file('scripts/' + name, (package.ROOT / 'scripts' / name).read_bytes())
        previous = self.file('dist/Atlas.app/Contents/previous.marker', b'previous complete app sentinel')
        self.file('vendor/nethack-500-src.tgz', b'corrupt disposable source cache')
        environment = dict(os.environ, ATLAS_OFFLINE_BUILD='1', PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(['bash', str(self.root / 'scripts/build-app.sh')], env=environment, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum mismatch', result.stderr)
        self.assertEqual(previous.read_bytes(), b'previous complete app sentinel')
        self.assertFalse((self.root / 'engine/runtime').exists())
        self.assertFalse((self.root / '.build').exists())

    def test_app_build_recovers_native_engine_and_reuses_universal_runtime(self):
        # Fake compiler/build tools stop after the observable architecture
        # decision. The production script runs only in this disposable root.
        for engine_universal, recover_universal in ((False, True), (True, False), (True, True)):
            with self.subTest(engine=engine_universal, recover=recover_universal), tempfile.TemporaryDirectory(dir=self.root) as directory:
                repo = Path(directory)
                (repo / 'scripts').mkdir()
                (repo / 'scripts/build-app.sh').write_bytes((package.ROOT / 'scripts/build-app.sh').read_bytes())
                (repo / 'scripts/package.py').write_text("import sys\nassert sys.argv[1:]==['pins','vendor','--ensure']\n")
                (repo / 'scripts/build-engine.sh').write_text('printf "%s" "$ENGINE_ARCH" > engine-decision.txt\nexit 29\n')
                binaries = repo / 'engine/runtime'
                binaries.mkdir(parents=True)
                for name in ('nethack', 'recover'):
                    (binaries / name).write_text('disposable fake binary')
                    (binaries / name).chmod(0o755)
                tools = repo / 'fake-tools'
                tools.mkdir()
                (tools / 'lipo').write_text('#!/bin/bash\n[ "$#" = 3 ] && [ "$2" = -verify_arch ] || exit 98\n[ "$3" = arm64 ] && exit 0\n[ "$3" = x86_64 ] || exit 98\ncase "$1" in\n*/nethack) exit ' + str(0 if engine_universal else 1) + ';;\n*/recover) exit ' + str(0 if recover_universal else 1) + ';;\nesac\nexit 98\n')
                (tools / 'xcrun').write_text('#!/bin/bash\nprintf "compile reached" > compile-decision.txt\nexit 31\n')
                for name in ('lipo', 'xcrun'):
                    (tools / name).chmod(0o755)
                environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], ENGINE_ARCH='native', REBUILD_ENGINE='0')
                result = subprocess.run(['bash', str(repo / 'scripts/build-app.sh')], env=environment, text=True, capture_output=True)
                if engine_universal and recover_universal:
                    self.assertEqual(result.returncode, 31, result.stderr)
                    self.assertFalse((repo / 'engine-decision.txt').exists())
                    self.assertEqual((repo / 'compile-decision.txt').read_text(), 'compile reached')
                else:
                    self.assertEqual(result.returncode, 29, result.stderr)
                    self.assertEqual((repo / 'engine-decision.txt').read_text(), 'universal')
                    self.assertFalse((repo / 'compile-decision.txt').exists())

    def test_staging_resources_and_source_share_policy(self):
        fixture_files = ('native/App.swift', 'web/app.js', 'assets/tiles/LICENSES.txt',
                         'tools/tileset-preview/index.html',
                         'engine/winatelier.c', 'engine/apply-beginner-patch.py',
                         'engine/hints', 'engine/sysconf', 'scripts/build-engine.sh',
                         'scripts/package.py', 'scripts/source-pins.json',
                         'docs/SOURCE.md', 'README.md', 'AGENTS.md', 'LICENSE.txt', 'LICENSES.md', '.gitignore',
                         'vendor/NetHack-5.0.0/src/allmain.c',
                         'vendor/NetHack-5.0.0/win/shim/winshim.c',
                         'vendor/NetHack-5.0.0/sys/unix/hints/atelier')
        for name in fixture_files:
            self.file(name)
        for name in ('nethack', 'recover', 'nhdat', 'license', 'symbols', 'sysconf'):
            self.file('engine/runtime/' + name)
        self.file('vendor/nethack-500-src.tgz', b'NetHack fixture')
        self.file('vendor/lua-5.4.8.tar.gz', b'Lua fixture')
        self.file('assets/.DS_Store', b'cache sentinel')
        self.file('scripts/source.pyc', b'cache sentinel')
        self.file('assets/private.env', b'untracked private sentinel')
        self.file('docs/private-draft.md', b'untracked private sentinel')
        subprocess.run(['git', '-C', str(self.root), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '--', *fixture_files], check=True)
        destination = self.root / 'candidate/Resources'
        with patch('package.source_pins', return_value=self.pins()):
            package.stage_resources(self.root, destination)
        self.assertFalse((destination / 'assets/.DS_Store').exists())
        self.assertFalse((destination / 'assets/private.env').exists())
        self.assertFalse((destination / 'docs/private-draft.md').exists())
        self.assertEqual((destination / 'assets/tiles/LICENSES.txt').read_bytes(), b'valid source\n')
        self.assertEqual((destination / 'LICENSE.txt').read_bytes(), b'valid source\n')
        self.assertEqual((destination / 'LICENSES.md').read_bytes(), b'valid source\n')
        with tarfile.open(destination / 'Source/atlas-source.tar.gz') as archive:
            self.assertNotIn('scripts/source.pyc', archive.getnames())
            self.assertNotIn('docs/private-draft.md', archive.getnames())
            self.assertFalse(any(name.startswith('engine/runtime') for name in archive.getnames()))
            self.assertIn('scripts/source-pins.json', archive.getnames())
            self.assertIn('scripts/package.py', archive.getnames())
            self.assertIn('tools/tileset-preview/index.html', archive.getnames())
            self.assertEqual(archive.extractfile('LICENSE.txt').read(), b'valid source\n')
            self.assertEqual(archive.extractfile('LICENSES.md').read(), b'valid source\n')
            self.assertEqual(set(json.loads(archive.extractfile(package.SOURCE_INVENTORY).read())), package.tracked_files(self.root))
            with tempfile.TemporaryDirectory() as extracted:
                (Path(extracted) / package.SOURCE_INVENTORY).write_bytes(
                    archive.extractfile(package.SOURCE_INVENTORY).read())
                self.assertEqual(package.tracked_files(extracted), package.tracked_files(self.root))
                self.assertNotIn('docs/private-draft.md', package.tracked_files(extracted))
        self.assertEqual((self.root / 'assets/.DS_Store').read_bytes(), b'cache sentinel')


if __name__ == '__main__':
    unittest.main(verbosity=2)
