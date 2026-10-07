# Tile sources and permission evidence

These records identify the bundled sources and their licenses; they do not grant
additional rights.

## Project-original artwork

Original Lantern and Soot & Brass artwork uses CC BY 4.0. Current scope and
attribution are in the [Lantern notice](../lantern/LICENSE.txt) and
[Soot & Brass notice](../soot-and-brass/LICENSE.txt). Retained original images,
generation prompts, extraction recipes and current source hashes are documented
in the [Lantern](../lantern/README.md) and [Soot & Brass](../soot-and-brass/README.md)
source guides. The NetHack-derived catalog and size metadata retains NGPL,
separately from the original image pixels.

The [full CC BY 4.0 license](CC-BY-4.0.txt) was downloaded from Creative Commons'
[official plain-text legal code](https://creativecommons.org/licenses/by/4.0/legalcode.txt).
License-file SHA-256:
`9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411`.
The catalog's NetHack-derived names, appearances and ordering retain NGPL,
separately from the new image pixels.

## Official NetHack 5.0 tiles

The [NetHack General Public License](NGPL.txt) is reproduced byte-for-byte from
`NetHack-5.0.0/dat/license` in the
[official complete 5.0.0 source archive](https://www.nethack.org/download/5.0.0/nethack-500-src.tgz).
Archive SHA-256:
`2959b7886aac76185b90aea0c9f80d14343f604de0ae96b3dd2a760f7ab3bde9`.
License-file SHA-256:
`93a3ae2cb8dee482daddfaebe53bcffe5b114b603def19b4dca21621cbc5a747`.
The [upstream license page](https://www.nethack.org/common/license.html) also
publishes these terms.

The source tile definitions are `win/share/monsters.txt`, `objects.txt` and
`other.txt` inside that archive. From the repository root, `./scripts/build-engine.sh`
downloads and checks the archive, extracts it under `vendor/`, and produces
`vendor/NetHack-5.0.0/dat/nhtiles.bmp`. The build requires macOS and Xcode
Command Line Tools. Then regenerate the NetHack Classic PNG using Pillow:

```sh
python3 scripts/build-tilesets.py assets/tiles/recipes/official.json
```

No source image changes are made to the official tiles; format conversion and
blank-row trimming are dated in [LICENSES.txt](../LICENSES.txt).

NGPL paragraphs 1 and 2 require retained notices, the license and modification
notices. Paragraph 3 requires complete source or, for noncommercial
distribution only, full information for obtaining it from an appropriate
archive site when distributing executable/object forms. A Git checkout keeps
the pinned retrieval information above; the built app includes the complete
NetHack archive and Atlas modifications, as described in
[source distribution](../../../docs/SOURCE.md). An archive URL is not a
substitute for accompanying source when relying on paragraph 3(a), including
commercial distribution.
