# Component license inventory

October 6, 2026. The owner's final choice is MIT for independently owned application/tool code, CC BY 4.0 for original artwork/documentation, and NGPL for NetHack, direct modifications and NetHack-hosted Lua. Source availability alone is not a license grant. The short directory map, copyrights and tile credit are in [LICENSES.md](../LICENSES.md).

| Component | Terms and boundary |
| --- | --- |
| Pinned NetHack 5.0.0, maintained window port and actual upstream modifications | NGPL, full text in assets/tiles/sources/NGPL.txt and the engine's license resource; dated modification notices and complete source accompany the engine |
| Pinned Lua 5.4.8 | MIT, upstream copyright/notice in docs/LUA-LICENSE.txt and supplied original source archive |
| NetHack Classic artwork and NetHack-derived names/order/catalog metadata | NGPL; no CC BY alternative for upstream-derived material |
| Original Lantern and Soot & Brass pixels, Classic/Modern editions, regional derivatives, procedural frost and Water artwork | CC BY 4.0 under the owner's final choice; full text, attribution, scope and retained sources in the family/central notices |
| Independent Swift source under `native/`, including host, recovery, import and development launchers | MIT, explicitly selected by the owner on October 6, 2026; scoped grant in [LICENSE.txt](../LICENSE.txt), full text in [MIT-LICENSE.txt](MIT-LICENSE.txt) |
| Project-original Lua executed by the Atlas app itself | MIT under the same grant; no app-hosted Lua interpreter or maintained app-hosted Lua currently exists |
| Project-original Lua loaded or executed inside NetHack, including generated test/level scripts | NGPL under the owner-selected execution-host rule; a Swift/Python launcher does not make an engine-loaded script app-hosted |
| Independent web JavaScript/HTML/CSS and original build/test/art tools | MIT under the same independent-code grant; copied NetHack fragments remain separately NGPL |
| Original build/configuration additions in `engine/hints`, `engine/sysconf`, `engine/cross.mk`, `engine/build-cross.py` | MIT; being stored under `engine/` does not make original tooling an upstream modification |
| `engine/apply-beginner-patch.py` | Original Python orchestration is MIT; embedded upstream C/header and emitted NetHack modifications retain NGPL and their notices |
| NetHack-derived restriction tables in `web/character.js` and tile/creature catalogs, ordering, mappings and copied upstream level geometry | NGPL for the derived material; original surrounding JavaScript/Python code is MIT |
| Original documentation, artwork/reference images and `native/AppIcon.icns` | CC BY 4.0, project attribution and indication of changes; copied upstream material and full license texts keep their original terms |

Individual upstream or third-party notices continue to govern their material. The artwork grant covers original rendered pixels separately from application drawing code. Historical retired artwork keeps its historical notices in the revisions that contain it.

The component grants and full license texts accompany both bundled resources and the maintained source archive. The upstream Lua runtime remains MIT and NetHack-supplied scripts retain their upstream terms. Record each new original Lua script's execution host here; a shared script intended for both hosts needs explicit component notices for each distributed use. This rule does not remove an existing third-party grant.

Contributors must offer original submissions under the license assigned to their component in LICENSES.md and retain third-party notices. The MIT grant applies only to independently authored project code. Nothing in it limits NGPL obligations applicable to NetHack, its derivatives, or a combined distribution. This clarifies scope; it does not create a conditional automatic license conversion for the repository or third-party contributions.

## Process boundary and license scope

The Swift host starts `Contents/Resources/engine/nethack` as a separate executable and communicates through pipes using the Atlas protocol. Lua is statically linked into that engine; NetHack loads its level, dungeon, quest and diagnostic scripts inside the engine process. The Swift app has no Lua runtime. The source and notices for NetHack, the maintained port and its modifications remain NGPL in the same app bundle.

The MIT grant covers independently owned app and tool code only. It does not declare the entire bundle MIT or grant rights to upstream NetHack. A process boundary alone is not a legal determination of independent works: [NGPL paragraph 2(b)](https://www.nethack.org/common/license.html) governs works containing or derived from NetHack. The [FSF's aggregation guidance](https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation) also considers communication semantics as well as mechanism, although it discusses GNU GPL rather than NGPL. This inventory records the actual architecture and owner-selected grants without certifying a standalone legal status. Matching source, dated modification notices and upstream license requirements remain part of the distribution.

No development history rewrite, signing identity or public distribution action follows from this inventory.
