#!/usr/bin/env python3
"""Compile and register one or more tileset recipes. Requires Pillow."""
import argparse
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipes', nargs='*', type=Path,
                        help='Recipe JSON paths; defaults to all assets/tiles/recipes/*.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'assets/tiles',
                        help='Use an isolated directory for generated PNGs, receipts and manifest')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('atlas_tileset_compiler', ROOT/'assets/tiles/compiler.py')
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    try:
        entries = compiler.build(args.recipes or sorted((ROOT/'assets/tiles/recipes').glob('*.json')),
                                 args.output_dir)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Tileset build failed: {error}\n')
    for entry in entries:
        print(f'Built {entry["name"]}: {entry["file"]} ({entry["count"]} tile cells)')


if __name__ == '__main__':
    main()
