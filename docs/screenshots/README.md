# Screenshot provenance

These unaltered captures show the game view of the Atlas 1.0.0 native application
running the real NetHack 5.0.0 engine. They were captured with WebKit's view
snapshot API, which excludes the desktop, menu bar, Dock and other windows.
All saves were disposable and isolated from player data.

- `lantern-modern.png`: the native scene from `scripts/test-lantern-gameplay.py
  --native --tileset lantern-modern`. The room is constructed inside NetHack
  for the test, and the captured movement uses an ordinary game command.
- `soot-and-brass-sokoban.png`: NetHack's stage 2, layout 1 Sokoban level,
  restored in the native app with the room-shape capture harness. The developer
  save uses wizard map reveal and a level 30 character for inspection.

Lantern and Soot & Brass tilesets by the NetHack Atlas project, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The interface, artwork and NetHack content retain their respective terms in
the [license map](../../LICENSES.md).
