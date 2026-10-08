#!/usr/bin/env python3
"""Apply the Windows startup fixes to the checksum-pinned generated source.

Windows builds only. The upstream Windows main assumes the GUI or console tty
port, and its portable sysconf check fails on the second startup pass. Keep
this idempotent for incremental builds, and reject an unexpected source shape
rather than silently shipping an engine that uses the player's own NetHack
folders.
"""
from pathlib import Path
import sys

NOTICE_END = """ * See docs/ENGINE_FORK.md in the accompanying Atlas source distribution.
 * Distributed under the NetHack General Public License.
 */
"""

PATCHES = {
    'sys/windows/windmain.c': {
        'header': """/* NetHack 5.0\twindmain.c\t$NHDT-Date: 1693359653 2023/08/30 01:40:53 $  $NHDT-Branch: keni-crashweb2 $:$NHDT-Revision: 1.189 $ */
/* Copyright (c) Derek S. Ray, 2015. */
/* NetHack may be freely redistributed.  See license for details. */
""",
        'notice': """
/* Modified by the NetHack Atlas project:
 * 2026-10-08: default to the build's DEFAULT_WINDOW_SYS when only the shim
 *             window port is compiled, instead of assuming GUI or tty.
""" + NOTICE_END,
        'edits': [
            ("""#elif defined(TTY_GRAPHICS)
            "tty";
#endif""", """#elif defined(TTY_GRAPHICS)
            "tty";
#elif defined(SHIM_GRAPHICS)
            DEFAULT_WINDOW_SYS;
#endif"""),
            ("""#else
        windowtype = "tty";
#endif""", """#elif defined(SHIM_GRAPHICS) && !defined(TTY_GRAPHICS)
        windowtype = DEFAULT_WINDOW_SYS;
#else
        windowtype = "tty";
#endif"""),
        ],
    },
    'sys/windows/windsys.c': {
        'header': """/* NetHack 5.0\twindsys.c\t$NHDT-Date: 1710949760 2024/03/20 15:49:20 $  $NHDT-Branch: NetHack-5.0 $:$NHDT-Revision: 1.95 $ */
/* Copyright (c) NetHack PC Development Team 1993, 1994 */
/* NetHack may be freely redistributed.  See license for details. */
""",
        'notice': """
/* Modified by the NetHack Atlas project:
 * 2026-10-08: read the portable sysconf by its full path on every startup
 *             pass; the second pass prefixed it with the earlier sysconf
 *             folder and fell back to the per-user NetHack folders.
""" + NOTICE_END,
        'edits': [
            ("""        config_error_init(TRUE, tmppath, FALSE);
        /* ... and _must_ parse correctly. */
        if (read_config_file(tmppath, set_in_sysconf)
            && sysopt.portable_device_paths)
            retval = TRUE;
        (void) config_error_done();""", """        config_error_init(TRUE, tmppath, FALSE);
        /* ... and _must_ parse correctly. */
        {
            /* tmppath is already complete; fqname() must not prefix it */
            char *save_sysconf_prefix = gf.fqn_prefix[SYSCONFPREFIX];

            gf.fqn_prefix[SYSCONFPREFIX] = (char *) 0;
            if (read_config_file(tmppath, set_in_sysconf)
                && sysopt.portable_device_paths)
                retval = TRUE;
            gf.fqn_prefix[SYSCONFPREFIX] = save_sysconf_prefix;
        }
        (void) config_error_done();"""),
        ],
    },
}


def apply_text(name, text):
    """Accept pristine, previously patched or already noticed pinned source."""
    patch = PATCHES[name]
    header, notice = patch['header'], patch['notice']
    if not text.startswith(header):
        raise ValueError('Unexpected upstream copyright header')
    for original, patched in patch['edits']:
        if text.count(patched) == 1:
            continue
        if text.count(original) != 1:
            raise ValueError('Unexpected upstream source')
        text = text.replace(original, patched, 1)
    if text.startswith(header + notice):
        if text.count('Modified by the NetHack Atlas project:') != 1:
            raise ValueError('Duplicate Atlas modification notice')
    elif 'Modified by the NetHack Atlas project:' in text:
        raise ValueError('Unexpected Atlas modification notice')
    else:
        text = text.replace(header, header + notice, 1)
    return text


if __name__ == '__main__':
    tree = Path(sys.argv[1])
    for name in PATCHES:
        source = tree / name
        text = source.read_bytes().decode()
        try:
            result = apply_text(name, text)
        except ValueError as error:
            raise SystemExit(f"Refusing to patch {source}: {error}") from error
        if result != text:
            source.write_bytes(result.encode())
