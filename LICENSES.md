# License map

Atlas for NetHack uses Atlas as its short name. Existing copyright and artwork
attribution notices identify its creator as the NetHack Atlas project; those
notices and their grants remain in force under the new product name.

These terms cover project-original material;
upstream notices and the exceptions below remain in force.

| Directory or material | License |
| --- | --- |
| `native/` source/configuration and `web/` interface code | MIT; `native/AppIcon.icns` is CC BY 4.0; NetHack-derived restriction tables in `web/character.js` retain NGPL |
| `scripts/`, original build/configuration helpers in `engine/`, Python tools and recipe configuration in `assets/tiles/`, and preview code in `tools/` | MIT; embedded/emitted upstream source retains its upstream terms |
| `engine/winatelier.c`, direct NetHack modifications, and Lua loaded/executed inside NetHack | NGPL |
| Lua executed by Atlas itself | MIT; none is currently present |
| Original artwork in `assets/tiles/`, including Lantern, Soot & Brass, regional and procedural pixels | CC BY 4.0; official NetHack tiles and NetHack-derived catalogs/mappings remain NGPL |
| Original documentation in `docs/`, `tools/`, `README.md`, `AGENTS.md`, and this map | CC BY 4.0; quoted upstream material and license texts retain their terms |
| Pinned third-party sources in `vendor/` and the app's `Contents/Resources/Source/` | NetHack: NGPL; upstream Lua: MIT; original notices retained |

Full terms: [MIT](docs/MIT-LICENSE.txt), [NGPL](assets/tiles/sources/NGPL.txt),
[CC BY 4.0](assets/tiles/sources/CC-BY-4.0.txt). The scoped grants are in
[LICENSE.txt](LICENSE.txt); detailed exceptions and execution paths are in
[COMPONENT-LICENSES.md](docs/COMPONENT-LICENSES.md).

Contributors must offer original submissions under the license assigned to
their component and preserve upstream/third-party notices. The MIT grant
does not limit NGPL obligations applicable to NetHack, its derivatives, or a
combined distribution.

Lua runtime: **Copyright (C) 1994-2025 Lua.org, PUC-Rio.** Authors:
R. Ierusalimschy, L. H. de Figueiredo, W. Celes. Its complete copyright and
permission notice is retained in [LUA-LICENSE.txt](docs/LUA-LICENSE.txt).

NetHack: **Copyright 1985-2026 by Stichting Mathematisch Centrum and
M. Stephenson.** Individual upstream notices remain in the included source.
The full NGPL and engine license accompany the app. Our dated modification
notices and updated source inventory are in [ENGINE_FORK.md](docs/ENGINE_FORK.md).

Tile credit: **Lantern and Soot & Brass tilesets by the NetHack Atlas project,
licensed under CC BY 4.0.** Link [the license](https://creativecommons.org/licenses/by/4.0/)
and indicate changes when sharing modified artwork. NetHack Classic artwork
retains the NetHack DevTeam and contributing artists' NGPL notices.
