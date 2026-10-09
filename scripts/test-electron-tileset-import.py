#!/usr/bin/env python3
"""Check the Electron host's tileset import with real Electron image decoding.

Build the host first (npm run build in electron/). Needs a desktop session.
"""
import json
import os
import pathlib
import struct
import subprocess
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE = ROOT / 'electron' / 'dist' / 'tileset-import.js'
ELECTRON = ROOT / 'electron/node_modules/electron/dist' / ('electron.exe' if os.name == 'nt' else 'electron')
assert MODULE.exists(), 'Build the Electron host first: cd electron && npm run build'

HARNESS = '''
const { app } = require("electron");
const fs = require("node:fs");
const [modulePath, cases] = process.argv.slice(-2);
// Exit on any harness error instead of showing a blocking dialog.
process.on("uncaughtException", (error) => { console.error(error); app.exit(1); });
const importer = require(modulePath);
app.whenReady().then(() => {
  const results = JSON.parse(fs.readFileSync(cases, "utf8")).map(([kind, file, width, height, saveTo]) => {
    try {
      const tile = kind === "convert" ? importer.convert(file, width, height) : importer.reload(file);
      if (saveTo) importer.persist(tile, saveTo);
      const { file: data, ...fields } = tile.manifest;
      return { ok: true, fields, depth: Buffer.from(data.split(",")[1], "base64")[24] };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  });
  console.log("RESULTS " + JSON.stringify(results));
  app.quit();
});
'''


def chunk(kind, value):
    return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))


def png(path, width, height, depth=8, animated=False):
    pixel = b'\x20\x80\xc0\x80' if depth == 8 else b'\x20\x00\x80\x00\xc0\x00\x80\x00'
    data = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, 6, 0, 0, 0))
    if animated:
        data += chunk(b'acTL', struct.pack('>II', 2, 0))
    data += chunk(b'IDAT', zlib.compress((b'\0' + pixel * width) * height)) + chunk(b'IEND', b'')
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + data)


with tempfile.TemporaryDirectory(prefix='atlas-electron-tiles-') as temporary:
    work = pathlib.Path(temporary)
    official = ROOT / 'assets' / 'tiles' / 'official.png'
    saved, tampered = work / 'imported-tileset.json', work / 'tampered.json'
    png(work / 'deep.png', 384, 384, depth=16)
    png(work / 'animated.png', 384, 384, animated=True)
    png(work / 'small.png', 64, 64)
    (work / 'sheet.bmp').write_bytes(b'BM' + bytes(60))
    cases = [
        ['convert', str(official), 16, 16, str(saved)],
        ['convert', str(official), 32, 32],
        ['convert', str(official), True, 16],
        ['convert', str(work / 'deep.png'), 8, 8],
        ['convert', str(work / 'animated.png'), 8, 8],
        ['convert', str(work / 'small.png'), 8, 8],
        ['convert', str(work / 'sheet.bmp'), 16, 16],
    ]
    (work / 'harness.cjs').write_text(HARNESS)

    def run(batch):
        (work / 'cases.json').write_text(json.dumps(batch))
        result = subprocess.run([str(ELECTRON), str(work / 'harness.cjs'), str(MODULE), str(work / 'cases.json')],
                                text=True, capture_output=True, input='', timeout=60)
        assert 'RESULTS ' in result.stdout, (result.stdout, result.stderr)
        return json.loads(result.stdout.split('RESULTS ', 1)[1])

    # The first case persists the sheet that the reload cases read.
    first = run(cases)
    stored = json.loads(saved.read_text())
    stored['file'] = stored['file'][:-4] + '!!!!'
    tampered.write_text(json.dumps(stored))
    second = run([['reload', str(saved), 0, 0], ['reload', str(tampered), 0, 0]])

good, wrong_size, boolean, deep, animated, small, bmp = first
reloaded, broken = second
assert good['ok'] and good['fields'] == {'id': 'custom', 'name': 'official', 'tileWidth': 16, 'tileHeight': 16,
                                         'columns': 40, 'count': good['fields']['count'], 'version': '5.0.0'}, good
assert good['fields']['count'] >= 2304, good
assert reloaded == good, (reloaded, good)
assert not wrong_size['ok'] and 'at least 2304' in wrong_size['error'], wrong_size
assert not boolean['ok'] and 'whole numbers' in boolean['error'], boolean
assert deep['ok'] and deep['depth'] == 8 and deep['fields']['count'] == 2304, deep
assert not animated['ok'] and 'single-image' in animated['error'], animated
assert not small['ok'] and 'at least 2304' in small['error'], small
assert not bmp['ok'] and 'PNG' in bmp['error'], bmp
assert not broken['ok'] and 'base64' in broken['error'], broken
print('PASS Electron tileset import: sheet imported, saved and reloaded; 16-bit normalized to 8-bit; '
      'wrong tile size, boolean size, animation, BMP, incomplete sheet and tampered save refused')
