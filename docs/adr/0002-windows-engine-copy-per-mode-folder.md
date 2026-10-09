# One engine copy in each Windows mode folder

The Windows engine ignores `HOME` and `NETHACKDIR`. It reads its paths only from a portable sysconf next to the executable. Each mode needs its own sysconf, so the Electron host copies the bundled engine into each mode folder. Before a game starts, the host compares the copy with the bundled engine. If they differ, the host replaces the copy. Only one game runs at a time, so the copy is never in use during the replacement.

## Considered Options

- Refresh all four copies at app start. Rejected because it does file work for modes the player does not open.
- Pass paths on the command line. Not possible, because upstream ignores `-p`, `-r` and `-@` on Windows.
