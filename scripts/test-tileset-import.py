#!/usr/bin/env python3
"""Compile the shared Swift import policy; use bounded fixtures and native memory samples."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]


def chunk(kind, value):
    return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))


def png(path, width, height, depth=8, color=6, animated=False, metadata_only=False):
    signature = b'\x89PNG\r\n\x1a\n'
    header = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color, 0, 0, 0))
    palette = chunk(b'PLTE', b'\x10\x70\xd0\xf0\xc0\x20') + chunk(b'tRNS', b'\xff\x80') if color == 3 else b''
    pixel = b'\x00' if color == 3 else (b'\x20\x80\xc0\x80' if depth == 8 else b'\x20\x00\x80\x00\xc0\x00\x80\x00')
    compressed = zlib.compress((b'\0' + pixel * width) * height) if not metadata_only else zlib.compress(b'\0')
    animation = b''
    if animated:
        animation = chunk(b'acTL', struct.pack('>II', 2, 0))
        animation += chunk(b'fcTL', struct.pack('>IIIIIHHBB', 0, width, height, 0, 0, 1, 10, 0, 0))
    result = signature + header + palette + animation + chunk(b'IDAT', compressed)
    if animated:
        result += chunk(b'fcTL', struct.pack('>IIIIIHHBB', 1, width, height, 0, 0, 1, 10, 0, 0))
        result += chunk(b'fdAT', struct.pack('>I', 2) + compressed)
    path.write_bytes(result + chunk(b'IEND', b''))


def bmp(path, width, height, palette=False):
    bits = 8 if palette else 24
    colors = b'\x10\x70\xd0\0\xf0\xc0\x20\0' if palette else b''
    row = (b'\x00' if palette else b'\xc0\x80\x20') * width
    row += b'\0' * ((-len(row)) % 4)
    raster = row * height
    offset = 14 + 40 + len(colors)
    header = b'BM' + struct.pack('<IHHI', offset + len(raster), 0, 0, offset)
    dib = struct.pack('<IiiHHIIiiII', 40, width, height, 1, bits, 0, len(raster), 0, 0, 2 if palette else 0, 0)
    path.write_bytes(header + dib + colors + raster)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true', help='Also measure conversion/reload of largest shipped atlas')
    args = parser.parse_args()
    (ROOT / '.artifacts').mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='tileset-import-', dir=ROOT / '.artifacts'))
    fixtures = run / 'fixtures'; fixtures.mkdir()
    png(fixtures / 'mini.png', 8, 8)
    for name, w, h in [('rectangular.png', 15, 25), ('rgba32.png', 32, 32), ('rgba64.png', 64, 64)]:
        png(fixtures / name, w * 48, h * 48)
    png(fixtures / 'palette.png', 768, 768, color=3)
    png(fixtures / 'rgba16.png', 768, 768, depth=16)
    bmp(fixtures / 'rgb.bmp', 768, 768)
    bmp(fixtures / 'palette.bmp', 768, 768, palette=True)
    png(fixtures / 'oversized.png', 65544, 8, metadata_only=True)
    png(fixtures / 'zero.png', 0, 8, metadata_only=True)
    png(fixtures / 'animated.png', 8, 8, animated=True)
    (fixtures / 'invalid.png').write_bytes(b'not an image')
    (fixtures / 'not-png.gif').write_bytes(b'GIF89a\x01\0\x01\0\x80\0\0\0\0\0\xff\xff\xff\x2c\0\0\0\0\x01\0\x01\0\0\x02\x02\x44\x01\0\x3b')
    executable = run / 'tileset-import-test'
    subprocess.run(['xcrun', 'swiftc', '-O', '-module-cache-path', str(ROOT / '.build/import-module-cache'),
                    str(ROOT / 'native/TilesetImport.swift'), str(ROOT / 'scripts/tileset-import-tests.swift'),
                    '-o', str(executable)], check=True)
    result = subprocess.run([str(executable), str(fixtures)], text=True, capture_output=True, timeout=60)
    (run / 'tests.log').write_text(result.stdout + result.stderr)
    print(result.stdout)
    assert result.returncode == 0, (result.returncode, result.stderr, run)
    record = {'passed': True, 'helperSHA256': hashlib.sha256((ROOT / 'native/TilesetImport.swift').read_bytes()).hexdigest(),
              'tests': str(run / 'tests.log'), 'benchmarks': []}
    if args.benchmark:
        manifest = json.loads((ROOT / 'assets/tiles/manifest.json').read_text())
        entries = manifest if isinstance(manifest, list) else manifest['tilesets']
        def area(entry):
            with (ROOT / 'assets/tiles' / entry['file']).open('rb') as stream:
                header = stream.read(24)
            w, h = struct.unpack('>II', header[16:24])
            return w * h
        largest = max(entries, key=area)
        source = ROOT / 'assets/tiles' / largest['file']
        command = ['/usr/bin/time', '-l', str(executable), 'benchmark', str(source),
                   str(run / 'benchmark-import.json'), str(largest['tileWidth']), str(largest['tileHeight'])]
        measured = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (run / 'benchmark.log').write_text(measured.stdout + measured.stderr)
        assert measured.returncode == 0, (measured.returncode, measured.stderr, run)
        record['benchmarks'].append({'atlas': largest['id'], 'pixels': area(largest),
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'result': json.loads(measured.stdout), 'nativeTimeLog': str(run / 'benchmark.log'),
            'limitation': 'Native helper conversion and reload peak, not the full app or WebKit peak'})
    (run / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Evidence:', run)


if __name__ == '__main__':
    main()
