#!/usr/bin/env python3
"""Apply the single new-game hook to the checksum-pinned generated source.

Keep this idempotent for incremental builds, and reject an unexpected source
shape rather than silently shipping an engine without the starter kit.
"""
from pathlib import Path
import sys

original = """    if (flags.legacy) {
        com_pager(u.uroleplay.pauper ? "pauper_legacy" : "legacy");
    }

    urealtime.realtime = 0L;"""
patched = """#ifdef SHIM_GRAPHICS
    /* Atlas Beginner supplies: new games only, after rerolls and ordinary
       carrying-attribute adjustment, before the recovery checkpoint. */
    {
        extern void atlas_beginner_kit(void);
        atlas_beginner_kit();
    }
#endif

""" + original

upstream_header = """/* NetHack 5.0\tallmain.c\t$NHDT-Date: 1771213100 2026/02/15 19:38:20 $  $NHDT-Branch: NetHack-3.7 $:$NHDT-Revision: 1.286 $ */
/* Copyright (c) Stichting Mathematisch Centrum, Amsterdam, 1985. */
/*-Copyright (c) Robert Patrick Rankin, 2012. */
/* NetHack may be freely redistributed.  See license for details. */
"""
change_notice = """
/* Modified by the NetHack Atlas project:
 * 2026-09-24: call atlas_beginner_kit() for optional new-game supplies.
 * 2026-09-29: add this dated modification notice; no further gameplay change.
 * See docs/ENGINE_FORK.md in the accompanying Atlas source distribution.
 * Distributed under the NetHack General Public License.
 */
"""


def apply_text(text):
    """Accept pristine, previously hooked or already noticed pinned source."""
    if not text.startswith(upstream_header):
        raise ValueError('Unexpected upstream allmain.c copyright header')
    if text.count(patched) == 1 and text.count("atlas_beginner_kit();") == 1:
        pass
    elif text.count(original) == 1 and "atlas_beginner_kit" not in text:
        text = text.replace(original, patched, 1)
    else:
        raise ValueError('Unexpected upstream newgame source')
    if text.startswith(upstream_header + change_notice):
        if text.count(change_notice) != 1:
            raise ValueError('Duplicate Atlas modification notice')
    elif 'Modified by the NetHack Atlas project:' in text:
        raise ValueError('Unexpected Atlas modification notice')
    else:
        text = text.replace(upstream_header, upstream_header + change_notice, 1)
    return text


if __name__ == '__main__':
    source = Path(sys.argv[1]) / "src" / "allmain.c"
    text = source.read_text()
    try:
        result = apply_text(text)
    except ValueError as error:
        raise SystemExit(f"Refusing to patch {source}: {error}") from error
    if result != text:
        source.write_text(result, newline='\n')
