#!/usr/bin/env python3
"""Compose the GitHub social preview from Atlas's own icon and game capture.

Requires Pillow. Run from any directory with:
    python3 scripts/make-social-preview.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "social-preview.png"
SCALE = 2
WIDTH, HEIGHT = 1280, 640


def box(*values):
    return tuple(round(value * SCALE) for value in values)


def font(path, size, index=0):
    return ImageFont.truetype(path, round(size * SCALE), index=index)


def spaced_text(draw, position, value, face, fill, spacing):
    x, y = box(*position)
    for character in value:
        draw.text((x, y), character, font=face, fill=fill, anchor="lt")
        x += draw.textlength(character, font=face) + spacing * SCALE


canvas = Image.new("RGB", box(WIDTH, HEIGHT), "#0a1418")
pixels = canvas.load()
for y in range(canvas.height):
    for x in range(canvas.width):
        glow = max(0, 1 - ((x / SCALE - 970) / 900) ** 2 - ((y / SCALE - 265) / 700) ** 2)
        warmth = max(0, 1 - ((x / SCALE - 1190) / 870) ** 2 - ((y / SCALE - 490) / 560) ** 2)
        pixels[x, y] = (
            round(10 + 7 * glow + 4 * warmth),
            round(20 + 10 * glow + 3 * warmth),
            round(24 + 11 * glow),
        )

draw = ImageDraw.Draw(canvas)
gold = "#d8b67d"
cream = "#f0eee5"
muted = "#a8b9b4"

# The linework echoes the icon and adds depth without competing with the copy.
for radius in (195, 280, 365):
    draw.arc(box(-radius + 30, 145 - radius, radius + 30, 145 + radius),
             195, 345, fill="#1b3236", width=2 * SCALE)
draw.line(box(80, 248, 619, 248), fill="#556450", width=SCALE)
draw.line(box(80, 472, 619, 472), fill="#556450", width=SCALE)

icon = Image.open(ROOT / "native" / "AppIcon.icns").convert("RGBA")
icon = icon.resize(box(94, 94), Image.Resampling.LANCZOS)
canvas.paste(icon, box(78, 84), icon)

serif_bold = font("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", 76)
serif = font("/System/Library/Fonts/Supplemental/Georgia.ttf", 42)
sans_demi = font("/System/Library/Fonts/Avenir Next.ttc", 23, index=2)
sans_medium = font("/System/Library/Fonts/Avenir Next.ttc", 19, index=5)

draw.text(box(192, 89), "ATLAS", font=serif_bold, fill=cream, anchor="lt")
spaced_text(draw, (198, 183), "FOR NETHACK", sans_demi, gold, 3.2)

draw.text(box(80, 295), "The Dungeons of Doom", font=serif, fill=cream, anchor="lt")
draw.text(box(80, 355), "on your Mac.", font=serif, fill=cream, anchor="lt")

spaced_text(draw, (80, 501), "NETHACK 5.0", sans_medium, muted, 1.1)

# An actual native-app capture, cropped to its dungeon rather than redrawn art.
source = Image.open(ROOT / "docs" / "screenshots" / "lantern-modern.png").convert("RGB")
scene = source.crop((800, 435, 1830, 1405))
scene = ImageOps.fit(scene, box(510, 480), method=Image.Resampling.LANCZOS)
scene = ImageEnhance.Contrast(scene).enhance(1.05)
scene = ImageEnhance.Brightness(scene).enhance(1.10)
mask = Image.new("L", scene.size)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, scene.width - 1, scene.height - 1),
                                        radius=18 * SCALE, fill=255)
canvas.paste(scene, box(690, 80), mask)
draw.rounded_rectangle(box(690, 80, 1200, 560), radius=18 * SCALE,
                       outline="#ad8b59", width=2 * SCALE)

canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(OUTPUT, optimize=True)
print(OUTPUT)
