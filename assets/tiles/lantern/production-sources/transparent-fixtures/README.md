# Transparent Lantern fixtures

Eight local overrides remove baked-in backing from four traps and enclosed
background from four bows. Classic and Modern use identical pixels. Physical
stone rims, pressure plates and trapdoors keep their own artwork.

Artwork uses **CC-BY-4.0**, credited to **NetHack Atlas project**. See
[the family notice](../../LICENSE.txt). No third-party artwork was used as an
editing reference.

`*-source.png` files retain the built-in image tool outputs with their original
alpha channels. [Exact prompts](TRANSPARENCY-PROMPTS.md) describe the edits.
`sources.json` pins source and output hashes and extraction bounds.

`prepare.py` crops declared transparent margins and resizes to 64 pixels with
nearest-neighbor sampling. It does not color-key, repaint or regenerate art.
Recorded crops preserve the subject sizes of the three smaller trap sources.

Run from the repository root with Python and Pillow:

```sh
python3 assets/tiles/lantern/production-sources/transparent-fixtures/prepare.py
python3 scripts/build-tilesets.py assets/tiles/recipes/lantern-classic.json assets/tiles/recipes/lantern-modern.json
python3 scripts/test-transparent-fixtures.py
```

The test checks retained source hashes, shipped pixels, edition parity and
visible underlying floors through transparent interior areas. These artwork
checks require separate native gameplay verification.
