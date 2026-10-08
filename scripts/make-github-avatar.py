#!/usr/bin/env python3
"""Make a small-size GitHub organization avatar from the Atlas app mark.

Requires Pillow. Run with: python3 scripts/make-github-avatar.py
"""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "github-organization-avatar.png"
SIZE = 512
SCALE = 4


def scaled(values):
    return tuple(round(value * SCALE) for value in values)


image = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE))
pixels = image.load()
for y in range(image.height):
    for x in range(image.width):
        center = max(0, 1 - ((x / SCALE - 256) / 380) ** 2 - ((y / SCALE - 180) / 440) ** 2)
        pixels[x, y] = (
            round(7 + 15 * center),
            round(19 + 26 * center),
            round(23 + 29 * center),
        )

draw = ImageDraw.Draw(image)
gold = "#d2ad70"
light_gold = "#f0d498"

# A single broad arch and two steps keep the app icon recognizable at 24 px.
arch = Image.new("L", image.size)
arch_draw = ImageDraw.Draw(arch)
arch_draw.ellipse(scaled((78, 75, 434, 397)), fill=255)
arch_draw.ellipse(scaled((112, 109, 400, 363)), fill=0)
arch_draw.rectangle(scaled((0, 236, SIZE, SIZE)), fill=0)
arch_draw.rectangle(scaled((78, 236, 112, 397)), fill=255)
arch_draw.rectangle(scaled((400, 236, 434, 397)), fill=255)
image.paste(gold, (0, 0, image.width, image.height), arch)
draw.line(scaled((180, 388, 332, 388)), fill=gold, width=22 * SCALE)
draw.line(scaled((151, 439, 361, 439)), fill=gold, width=25 * SCALE)

draw.polygon(scaled((256, 161, 273, 226, 337, 245, 273, 264,
                     256, 329, 239, 264, 175, 245, 239, 226)),
             fill=light_gold)

image.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(OUTPUT, optimize=True)
print(OUTPUT)
