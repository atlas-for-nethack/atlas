#!/usr/bin/env python3
"""Create a verified local release ZIP and checksum without publishing it."""
import sys
sys.dont_write_bytecode = True
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=package.ROOT / 'dist/Atlas.app')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output
    checksum = output.with_name(output.name + '.sha256')
    if output.exists() or checksum.exists() or output.is_symlink() or checksum.is_symlink():
        parser.exit(1, 'FAIL: Refusing to replace an existing release archive or checksum\n')
    subprocess.run([sys.executable, str(package.ROOT / 'scripts/verify-bundle.py'), '--app', str(arguments.app)], check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atlas-release.', dir=output.parent) as directory:
        staged = Path(directory) / output.name
        package.write_zip(arguments.app, staged)
        package.verify_zip_matches(arguments.app, staged)
        line = package.digest(staged) + '  ' + output.name + '\n'
        staged_checksum = Path(directory) / checksum.name
        staged_checksum.write_text(line)
        # Hard-link publication refuses an output created during validation.
        os.link(staged, output)
        try:
            os.link(staged_checksum, checksum)
        except OSError:
            output.unlink()
            raise
    print('PASS: Verified local release ZIP and SHA-256: ' + str(output))


if __name__ == '__main__':
    main()
