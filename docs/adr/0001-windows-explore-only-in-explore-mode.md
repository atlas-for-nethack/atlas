# Windows allows Explore mode only in the Explore mode folder

Upstream NetHack on Windows lets every game enter Explore mode, because `authorize_explore_mode` always returns TRUE. The Mac host limits Explore mode to the Explore mode folder through `EXPLORERS` in sysconf. We patch the Windows engine to honor `EXPLORERS` so that all hosts behave the same. The edit goes into the existing Windows patch of `sys/windows/windmain.c`, so the count of modified upstream files does not change.
