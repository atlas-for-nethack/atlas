#!/usr/bin/env python3
"""Reproduce the reviewed 64px sprites from retained generated alpha sources."""
import hashlib
import json
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
for record in json.loads((HERE / 'sources.json').read_text())['sources']:
    source = HERE / record['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sourceSha256']
    with Image.open(source) as image:
        sprite = image.convert('RGBA').crop(record['sourceCrop'])
        sprite = sprite.resize((64, 64), Image.Resampling.NEAREST)
    destination = HERE / record['file']
    sprite.save(destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == record['sha256']
print('Reproduced eight reviewed transparent sprites.')
