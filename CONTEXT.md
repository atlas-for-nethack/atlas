# Atlas for NetHack

Atlas is a desktop interface around the real NetHack 5.0 engine. A host program starts the engine and shows the shared web interface.

## Language

**Engine**:
The NetHack 5.0 program with the Atlas window port. It owns all game state and talks to the host over a line-based protocol.
_Avoid_: backend, server, core

**Host**:
The desktop program that starts the engine and shows the interface. The Mac host is Swift. The Windows and Linux host is Electron.
_Avoid_: shell, wrapper, app (when the host specifically is meant)

**Interface**:
The shared HTML, CSS and JavaScript in `web/` that every host loads.
_Avoid_: frontend, renderer, UI layer

**Bridge**:
The message path between the interface and the host. Each host provides it under one host-neutral name.
_Avoid_: IPC, channel

**Mode**:
One of the four ways to play: Standard, Beginner, Explore or Pauper. Each mode keeps its own saves, bones and scores.
_Avoid_: variant, game type

**Mode folder**:
The folder that holds one mode's saves, bones, scores and sysconf, inside the data folder.
_Avoid_: profile, namespace

**Data folder**:
The per-user folder named `NetHack Atlas/5.0` that holds all mode folders. Tests point it elsewhere with `ATLAS_DATA_DIR`.
_Avoid_: save directory, userData
