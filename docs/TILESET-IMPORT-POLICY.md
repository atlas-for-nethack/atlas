# Custom tileset resource policy

Fresh imports and startup reloads use the shared [TilesetImport.swift](../native/TilesetImport.swift) policy.
All applicable limits must pass; tile size alone is not a memory bound.

| Resource | Limit |
| --- | ---: |
| Source PNG/BMP file | 128 MiB (134,217,728 bytes) |
| Either image axis | 65,536 pixels |
| Image area | 64,000,000 pixels |
| Conservative decoded raster estimate and actual decoded row storage | 256 MiB (268,435,456 bytes) each |
| Encoded PNG | 64 MiB (67,108,864 bytes) |
| Persisted JSON | 96 MiB (100,663,296 bytes) |
| Tile width and height | Independently 8–256 pixels |
| Row-major canonical capacity | At least 2,304 tiles |

These limits bound individual files and buffers. They are **not** a 256 MiB
process-memory guarantee. Source data, decoder/encoder workspace, color
conversion, PNG bytes, base64 strings, JSON and WebKit image storage can coexist.
The native largest-shipped-atlas benchmark measured approximately 345 MB maximum
resident memory, above the individual raster cap; full application/WebKit peak
memory has not been measured by that helper.

## Import and reload

A file is opened once with nonblocking regular-file validation, inspected through
that same handle, then read in bounded chunks into an immutable `Data` snapshot.
The read loop independently stops at limit + 1 bytes, so a file growing after the
size check cannot cause an unbounded read. Decoding consumes that snapshot,
without reopening the path or using an `NSImage`/TIFF intermediate. Startup JSON
uses the same bounded read before parsing.

ImageIO raster caching is disabled when opening the source and reading metadata.
Before requesting an image, the helper checks recognized PNG/BMP type, exactly
one image, positive integral dimensions, both axes, area, complete row-major tile
geometry and component depth. Multi-image/animated sources are rejected even
if the file extension is PNG. The actual decoded width, height, component type
and `bytesPerRow × height` must also pass. All geometry products use overflow
reporting; booleans, fractions, nonfinite numbers and out-of-range integers are
not accepted as tile dimensions.

Integer PNG/BMP with up to 16 bits per component is supported. Paletted and
alpha images are permitted. The conservative metadata estimate is
`width × height × 4 × ceil(componentDepth / 8)`, so high-bit-depth images have a
stricter effective area limit under the same raster budget. Decoded floating
point components are rejected. Images above 8 bits per component are normalized
through an explicitly bounded 8-bit sRGB RGBA context; ordinary images avoid
that additional normalization buffer. This permits valid high-bit-depth PNGs
without relying on an unbounded TIFF conversion. Decoder internals and concurrent
buffers remain outside an exact process-memory guarantee.

PNG output uses an ImageIO data consumer that refuses bytes beyond its cap.
There is no uncapped application-owned encoded-PNG buffer followed by a late
size check. ImageIO may still allocate internal workspace before a consumer
refuses output; the cap does not certify all encoder allocation behavior.
Base64 expansion is checked before decoding persisted data. Reload requires the
exact `data:image/png;base64,` prefix, canonical strict base64 and a valid
single-image PNG, then repeats the shared decode/geometry policy. Persisted
high-bit-depth PNGs use the same normalization. Output JSON is checked before
persistence or publication to the renderer.

Both paths construct a new dictionary containing only `id`, `name`, `file`,
`tileWidth`, `tileHeight`, `columns`, `count` and `version`. Columns and count
are recalculated from decoded pixels; saved values are not trusted. Alternate
`path`/`url`, projected frames, regional materials and original-art rendering
extensions are omitted. Imported row-major sheets do not inherit Modern-family
creature sizing or architectural semantics. Geometry validates capacity, not
whether an arbitrary community sheet follows NetHack 5.0 artwork ordering.

Conversion and validation complete before atomic JSON persistence. Only a
successful write replaces the in-memory import and sends `tilesetImported`.
Cancellation, decode failure, budget rejection and persistence failure preserve
the previous import. An invalid startup manifest remains on disk unchanged,
is excluded from the renderer manifest, and produces a visible notice that
bundled tiles are being used. Startup does not silently delete diagnostic data.

## Verification and limits

[The focused test](../scripts/test-tileset-import.py) compiles the actual shared
helper with [Swift assertions](../scripts/tileset-import-tests.swift). Small
injectable policies exercise exact thresholds and one-unit overages without
allocating deliberately excessive rasters. Cases cover bounded reads,
non-regular files, arithmetic overflow, invalid numeric fields, metadata/type
and multi-image rejection, output-consumer limits, strict persisted data,
whitelisted reconstruction, recomputed geometry and failure preservation.
Accepted generated fixtures include 15×25 rectangular tiles, 32×32 and 64×64
sheets, paletted/alpha PNG, RGB/paletted BMP and 16-bit RGBA PNG. The compatibility
cases contain at least the canonical 2,304 tiles. They are synthetic bounded
format fixtures, not an exhaustive community-artwork survey.

```sh
python3 scripts/test-tileset-import.py
python3 scripts/test-tileset-import.py --benchmark
```

Benchmark mode converts, atomically persists and reloads the largest shipped
atlas under the default policy in a separate native helper process. It records
`/usr/bin/time -l` output, input/helper hashes, dimensions, output size and
elapsed time in a fresh `.artifacts/tileset-import-*` directory. macOS resource
accounting may require execution outside the restricted tool sandbox. A failed
accounting call must not be reported as a measured memory result.

A previous successful sample used the 2,560×11,264 Soot & Brass atlas:
28,835,840 pixels and a 23,002,983-byte PNG. Conversion plus reload took about
1.17 seconds, producing a 32,547,502-byte manifest. `/usr/bin/time -l` measured
345,260,032 bytes maximum RSS and 337,068,944 bytes peak memory footprint on this
Apple Silicon development Mac. These are one measured native-helper sample,
not upper-bound predictions for every permitted image or the WebKit renderer.
Record a new benchmark against its exact input and helper hashes when measuring a changed policy.

Packaged native selection of the valid generated custom sheet and malformed
persistence fallback passed in previous Apple Silicon application checks, including
exact save/restore and preservation of the supplied manifest bytes. Native
helper conversion covers import formats; the interactive file-picker path and
full application/WebKit peak memory were not measured by these runs. An AppKit sheet
now reports WebKit content-process termination independently of the failed
renderer. Native Game > Save Game still writes to the existing engine pipe;
there is no automatic game termination or renderer restart. Compilation and
callback implementation alone do not establish a forced isolated WebKit-process
termination test, which remains separately identified until executed.
