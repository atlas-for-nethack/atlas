/* NetHack 5.0 winshim.c    $NHDT-Date: 1596498345 2020/08/03 23:45:45 $  $NHDT-Branch: NetHack-3.7 $:$NHDT-Revision: 1.259 $ */
/* Copyright (c) Adam Powers, 2020                                */
/* NetHack may be freely redistributed.  See license for details. */

/* Modified by the NetHack Atlas project:
 * 2026-09-24: replace upstream win/shim/winshim.c with the Atlas JSON port.
 * 2026-09-28: add regional material presentation support.
 * 2026-09-29: extend named-region context and retain upstream notices here.
 * 2026-09-30: add Plane of Earth presentation context using level identity.
 * 2026-10-01: include named Mines levels in Mines presentation context.
 * 2026-10-01: select Valley of the Dead presentation by named level identity.
 * 2026-10-01: add Samurai Quest architecture context using role and branch identity.
 * 2026-10-01: select approved Medusa wall reuse by named level identity.
 * 2026-10-02: select approved Juiblex dry-ground reuse by named level identity.
 * 2026-10-02: select approved Baalzebub Gehennom reuse by named level identity.
 * 2026-10-02: retain perceived lowered drawbridge ground beneath occupants.
 * 2026-10-02: reuse existing materials by Monk, Priest, Healer and Valkyrie quest stage.
 * 2026-10-02: distinguish known Quest exterior earth from sheltered stone floors.
 * 2026-10-02: reuse natural ground on remembered shores, Quest exteriors and Gardens.
 * 2026-10-02: keep finished floors only in fully remembered regular Minetown rooms.
 * 2026-10-02: reuse approved Valley presentation on the actual named Orcus level.
 * 2026-10-05: reuse approved Gehennom ground on the actual Plane of Fire.
 * 2026-10-06: select Astral sanctuary presentation by named level identity.
 * 2026-10-06: resolve host Save by command identity and preserve valid UTF-8 JSON.
 * Maintained replacement: engine/winatelier.c. See docs/ENGINE_FORK.md.
 * NetHack Atelier JSON window port. Copyright 2026 NetHack Atlas project.
 * Distributed under the NetHack General Public License; see bundled license.
 */
#include "hack.h"
#include "dlb.h"
#include "func_tab.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define AWINDOWS 64
#define AROWS 4096
struct arow { anything identifier; char *text; char key, group; int tile; unsigned flags; };
struct awindow { int type, count; char *prompt; struct arow *rows; };
static struct awindow aw[AWINDOWS];
static char fieldnames[MAXBLSTATS][64];
static char inputline[16384];
static boolean shown[COLNO][ROWNO];
static int shown_glyph[COLNO][ROWNO];
enum amaterial { AMATERIAL_NONE, AMATERIAL_MINES, AMATERIAL_GEHENNOM,
                 AMATERIAL_VLAD, AMATERIAL_ASMODEUS, AMATERIAL_CAVEMAN,
                 AMATERIAL_CAVEMAN_GOAL, AMATERIAL_EARTH, AMATERIAL_VALLEY,
                 AMATERIAL_SAMURAI, AMATERIAL_MEDUSA, AMATERIAL_JUIBLEX,
                 AMATERIAL_BAALZ, AMATERIAL_QUEST_EARTH, AMATERIAL_PRIEST_TEMPLE,
                 AMATERIAL_MINES_BUILT, AMATERIAL_ASTRAL };
struct acell { int tile, color, ground; char character; boolean pet; enum amaterial material; };
static struct acell shown_cells[COLNO][ROWNO];
static boolean saving = FALSE;
static boolean automatic_save = FALSE;
static int pending_extcmd = -1;

/* Placement is part of new-game setup, not a player-facing world query.
 * Search without random draws, moving monsters or changing generated terrain. */
static boolean beginner_chest_path(coordxy x, coordxy y) {
    int typ;
    if (!isok(x, y) || t_at(x, y)
        || (MON_AT(x, y) && !m_at(x, y)->mtame)
        || sobj_at(BOULDER, x, y)) return FALSE;
    typ = levl[x][y].typ;
    return typ == ROOM || typ == CORR || typ == STAIRS || typ == LADDER
        || (typ == DOOR && !(levl[x][y].doormask & (D_CLOSED | D_LOCKED)));
}

static boolean beginner_chest_position(coord *where, boolean same_room,
                                      boolean empty) {
    static const int dx[] = { 0, 1, 0, -1, 1, 1, -1, -1 };
    static const int dy[] = { -1, 0, 1, 0, -1, 1, 1, -1 };
    boolean visited[COLNO][ROWNO] = {{ FALSE }};
    coord queue[COLNO * ROWNO];
    int head = 0, tail = 0, i, room = levl[u.ux][u.uy].roomno;
    queue[tail].x = u.ux; queue[tail++].y = u.uy;
    visited[u.ux][u.uy] = TRUE;
    while (head < tail) {
        coord here = queue[head++];
        int typ = levl[here.x][here.y].typ;
        if ((here.x != u.ux || here.y != u.uy)
            && (typ == ROOM || (!same_room && typ == CORR))
            && (!empty || (!OBJ_AT(here.x, here.y)
                           && !MON_AT(here.x, here.y)))) {
            *where = here;
            return TRUE;
        }
        for (i = 0; i < SIZE(dx); ++i) {
            coordxy x = here.x + dx[i], y = here.y + dy[i];
            if (!beginner_chest_path(x, y) || visited[x][y]
                || (same_room && levl[x][y].roomno != room)) continue;
            /* No diagonal door entry/exit or squeeze through blocked corners. */
            if (dx[i] && dy[i]
                && (typ == DOOR || levl[x][y].typ == DOOR
                    || (!beginner_chest_path(here.x, y)
                        && !beginner_chest_path(x, here.y)))) continue;
            visited[x][y] = TRUE;
            queue[tail].x = x; queue[tail++].y = y;
        }
    }
    return FALSE;
}

/* Called exclusively by newgame(), after ordinary role initialization,
 * rerolls and attribute adjustment, and before the first recovery checkpoint.
 * Beginner games live in a separate native-host runtime (including bones and
 * records); no saved-game layout or upstream death/combat rules are changed. */
void atlas_beginner_kit(void) {
    const char *mode = getenv("ATLAS_PLAY_MODE");
    static const struct { int type; long quantity; } kit[] = {
        { MAGIC_WHISTLE, 1L }, { POT_HEALING, 1L },
        { GOLD_PIECE, 1000L }, { FOOD_RATION, 2L }
    };
    struct obj *chest;
    coord spot;
    boolean in_room, nearby;
    int i;
    if (!mode || strcmp(mode, "beginner")) return;

    in_room = beginner_chest_position(&spot, TRUE, TRUE)
        || beginner_chest_position(&spot, TRUE, FALSE);
    nearby = in_room || beginner_chest_position(&spot, FALSE, FALSE);
    if (!nearby) {
        pline("No safe floor was found for Beginner supplies; no chest was placed.");
        return;
    }

    /* init=FALSE deliberately skips random contents, locks and traps. */
    chest = mksobj(CHEST, FALSE, FALSE);
    chest->known = chest->dknown = chest->bknown = chest->rknown = 1;
    chest->cknown = chest->lknown = chest->tknown = 1;
    chest->blessed = chest->cursed = chest->olocked = chest->otrapped = 0;
    chest = oname(chest, "Beginner supplies", ONAME_NO_FLAGS);
    for (i = 0; i < SIZE(kit); ++i) {
        struct obj *obj = mksobj(kit[i].type, FALSE, FALSE);
        obj->quan = kit[i].quantity;
        obj->blessed = obj->cursed = 0;
        obj->known = obj->dknown = obj->bknown = obj->rknown = 1;
        obj->owt = weight(obj);
        if (obj->oclass != COIN_CLASS)
            discover_object(obj->otyp, TRUE, TRUE, FALSE);
        (void) add_to_container(chest, obj);
    }
    chest->owt = weight(chest);
    place_object(chest, spot.x, spot.y);
    /* Normal rendering records only what the hero can perceive. Do not map
     * a potentially unseen fallback square just because supplies are there. */
    newsym(spot.x, spot.y);
    /* Count the gifted gold as initial funds even while in the floor chest:
     * later taking it must not inflate the separate Beginner score. */
    u.umoney0 += 1000L;
    if (in_room)
        pline("Beginner start: an unlocked, untrapped supply chest is nearby in this room.");
    else
        pline("No clear floor in this room: your supply chest is on the nearest safely reachable floor.");
    pline("Move onto the chest's square, then use Loot container to take supplies.");
    pline("Combat and permanent death are unchanged.");
}

static void noop(void) {}
/* A JSON string must contain Unicode, not individually widened UTF-8 bytes.
 * Reject overlong encodings, surrogates and values above U+10FFFF. Reads stop
 * at the first non-continuation byte (including NUL), so truncated C strings
 * never require looking beyond their terminator. */
static int utf8_length(const unsigned char *p) {
    int i, n;
    if (*p >= 0xc2 && *p <= 0xdf) n = 2;
    else if (*p >= 0xe0 && *p <= 0xef) n = 3;
    else if (*p >= 0xf0 && *p <= 0xf4) n = 4;
    else return 0;
    for (i = 1; i < n; ++i)
        if (p[i] < 0x80 || p[i] > 0xbf) return 0;
    if ((*p == 0xe0 && p[1] < 0xa0) || (*p == 0xed && p[1] >= 0xa0)
        || (*p == 0xf0 && p[1] < 0x90) || (*p == 0xf4 && p[1] >= 0x90))
        return 0;
    return n;
}
static void jstr(const char *s) {
    const unsigned char *p = (const unsigned char *)(s ? s : "");
    int n;
    putchar('"');
    for (; *p; ++p) {
        if (*p == '"' || *p == '\\') { putchar('\\'); putchar(*p); }
        else if (*p < 32 || *p == 127) printf("\\u%04x", *p);
        else if (*p >= 128) {
            n = utf8_length(p);
            if (n) { fwrite(p,1,n,stdout); p += n - 1; }
            else fputs("\\ufffd",stdout); /* one replacement per malformed byte */
        }
        else putchar(*p);
    }
    putchar('"');
}
static void eventtext(const char *type, const char *text) {
    printf("{\"type\":"); jstr(type); printf(",\"text\":"); jstr(text); puts("}");
}
static void inspectcell(int x, int y) {
    char buf[BUFSZ * 8] = "Unexplored"; const char *first = NULL;
    struct permonst *pm = NULL; coord cc;
    boolean throne_beneath = FALSE, remembered = FALSE;
    if (x > 0 && x < COLNO && y >= 0 && y < ROWNO && shown[x][y]) {
        cc.x = x; cc.y = y;
        do_screen_description(cc, TRUE, 0, buf, &first, &pm);
        if (!*buf) Strcpy(buf, "Unexplored");
        /* Supplement the occupant description only from upstream terrain memory.
         * Never inspect live room type, objects or an undiscovered feature. */
        remembered = !cansee(x,y) && (x != u.ux || y != u.uy);
        throne_beneath = !u.uswallow && !u.uburied
            && !glyph_is_unexplored(shown_glyph[x][y])
            && !glyph_is_nothing(shown_glyph[x][y])
            && !glyph_is_swallow(shown_glyph[x][y])
            && (!remembered || (svl.level.flags.hero_memory && levl[x][y].seenv))
            && svl.lastseentyp[x][y] == THRONE
            && !(glyph_is_cmap(shown_glyph[x][y])
                 && glyph_to_cmap(shown_glyph[x][y]) == S_throne);
    }
    printf("{\"type\":\"inspect\",\"x\":%d,\"y\":%d,\"text\":", x,y); jstr(buf);
    if (throne_beneath)
        printf(",\"beneath\":{\"name\":\"Throne\",\"remembered\":%s}", remembered ? "true" : "false");
    puts("}");
}
/* Use the live command table and bindings, including player rebindings.
 * Named commands enter the ordinary key/extended-command path so the core
 * retains responsibility for turns, restrictions, prefixes and confirmations. */
static boolean public_command(const struct ext_func_tab *entry) {
    return !(entry->flags & (INTERNALCMD | CMD_NOT_AVAILABLE))
        && (wizard || !(entry->flags & WIZMODECMD));
}
static int command_binding(const struct ext_func_tab *entry) {
    const struct Cmd_bind *bind;
    for (bind = gc.Cmd.cmdbinds; bind; bind = bind->next)
        if (bind->cmd == entry && bind->key) return bind->key;
    return 0;
}
static boolean command_selectable(const struct ext_func_tab *entry) {
    return !(entry->flags & CMD_PARAM)
        && (command_binding(entry) || (unsigned char)cmd_from_func(doextcmd));
}
static void command_key_label(unsigned char key) {
    char text[32], *p = text;
    if (key & 0x80) { Strcpy(p,"Alt+"); p += 4; key &= 0x7f; }
    if (key == 27) Strcpy(p,"Esc");
    else if (key == 32) Strcpy(p,"Space");
    else if (key == 127) Strcpy(p,"Delete");
    else if (key < 32) Sprintf(p,"Ctrl+%c",key + '@');
    else { p[0] = (char)key; p[1] = 0; }
    jstr(text);
}
static void command_catalog(void) {
    int i, count = 0;
    static boolean emitted = FALSE, last_wizard = FALSE;
    static unsigned last_serial;
    static const struct ext_func_tab *last_bindings[256];
    const struct ext_func_tab *bindings[256] = {0};
    const struct Cmd_bind *binding;
    for (binding = gc.Cmd.cmdbinds; binding; binding = binding->next)
        bindings[binding->key] = binding->cmd;
    /* Upstream serialno covers movement modes, but ordinary rebindings can
     * change without advancing it. Compare those bindings as well. */
    if (emitted && last_serial == gc.Cmd.serialno && last_wizard == wizard
        && !memcmp(last_bindings,bindings,sizeof bindings)) return;
    memcpy(last_bindings,bindings,sizeof bindings);
    emitted = TRUE; last_serial = gc.Cmd.serialno; last_wizard = wizard;
    printf("{\"type\":\"commands\",\"commands\":[");
    for (i = 0; extcmdlist[i].ef_txt; ++i) {
        const struct ext_func_tab *entry = &extcmdlist[i];
        const struct Cmd_bind *bind;
        int nkeys = 0;
        if (!public_command(entry)) continue;
        if (count++) putchar(',');
        printf("{\"name\":"); jstr(entry->ef_txt);
        printf(",\"description\":"); jstr(entry->ef_desc);
        printf(",\"keys\":[");
        for (bind = gc.Cmd.cmdbinds; bind; bind = bind->next) {
            if (bind->cmd != entry || !bind->key) continue;
            if (nkeys++) putchar(',');
            command_key_label(bind->key);
        }
        printf("],\"prefix\":%s,\"movement\":%s,\"selectable\":%s}",
               entry->flags & PREFIXCMD ? "true" : "false",
               entry->flags & MOVEMENTCMD ? "true" : "false",
               command_selectable(entry) ? "true" : "false");
    }
    puts("]}");
}
/* Context is a convenience index over perceived/remembered appearances and
 * the hero's own equipment. It must never search level.objects, hidden traps,
 * door locks or container contents to discover an opportunity. */
#define CONTEXT_LIMIT 40
struct context_list { const char *names[CONTEXT_LIMIT]; int count; };
static void context_add(struct context_list *list, const char *name,
                        const char *label, const char *reason) {
    int i;
    for (i = 0; i < list->count; ++i)
        if (!strcmp(list->names[i],name)) return;
    if (list->count == CONTEXT_LIMIT) return;
    /* Hints may only name an action present and dispatchable in this build. */
    for (i = 0; extcmdlist[i].ef_txt; ++i)
        if (!strcmp(extcmdlist[i].ef_txt,name)) break;
    if (!extcmdlist[i].ef_txt || !public_command(&extcmdlist[i])
        || !command_selectable(&extcmdlist[i])) return;
    if (list->count) putchar(',');
    list->names[list->count++] = name;
    printf("{\"name\":"); jstr(name);
    printf(",\"label\":"); jstr(label);
    printf(",\"reason\":"); jstr(reason); putchar('}');
}
static boolean context_container(int object) {
    return object == CHEST || object == LARGE_BOX || object == ICE_BOX
        || object == SACK || object == OILSKIN_SACK
        || object == BAG_OF_HOLDING || object == BAG_OF_TRICKS;
}
static void context_trap(struct context_list *list, int glyph) {
    int trap;
    if (!glyph_is_trap(glyph)) return;
    trap = glyph_to_trap(glyph);
    context_add(list,"glance","Examine trap","A revealed trap nearby");
    /* These are the trap types handled by the ordinary untrap command.
     * Merely knowing a trap exists does not make every trap disarmable. */
    switch (trap) {
    case ARROW_TRAP: case DART_TRAP: case BEAR_TRAP: case WEB:
    case LANDMINE: case SQKY_BOARD:
        context_add(list,"untrap","Attempt to disarm","A revealed trap nearby");
        break;
    default: break;
    }
}
static void context_commands(void) {
    struct context_list list = { {0}, 0 };
    struct obj *obj;
    int x, y, glyph, object, symbol, typ;
    boolean locktool = FALSE, wand = FALSE, throwable = FALSE;
    boolean ranged = FALSE, spells = FALSE, reach_floor;
    printf("{\"type\":\"context\",\"commands\":[");
    if (u.uswallow || u.uburied) goto done;
    reach_floor = can_reach_floor(FALSE);
    for (obj = gi.invent; obj; obj = obj->nobj) {
        if (obj->otyp == SKELETON_KEY || obj->otyp == LOCK_PICK
            || obj->otyp == CREDIT_CARD) locktool = TRUE;
        if (obj->oclass == WAND_CLASS) wand = TRUE;
        if (obj->oclass == WEAPON_CLASS || obj->oclass == GEM_CLASS)
            throwable = TRUE;
    }
    for (x = 0; x < MAXSPELL && svs.spl_book[x].sp_id != NO_SPELL; ++x)
        if (svs.spl_book[x].sp_know > 0) spells = TRUE;

    /* The hero's foreground glyph covers the square beneath them. NetHack's
     * remembered glyph/topology retain what the hero has seen or touched,
     * including stairs underneath a displayed object. Background render glyphs
     * cannot substitute here: the core simplifies many of them to floor. */
    typ = svl.lastseentyp[u.ux][u.uy];
    glyph = levl[u.ux][u.uy].glyph;
    if (typ == STAIRS || typ == LADDER) {
        /* Only ask direction after remembered topology identifies a staircase
         * beneath the hero; never discover stairs using stairway_at alone. */
        stairway *stairs = stairway_at(u.ux,u.uy);
        if (stairs)
            context_add(&list,stairs->up ? "up" : "down",
                        stairs->up ? "Ascend" : "Descend",
                        typ == LADDER ? "Ladder underfoot" : "Stairs underfoot");
    }
    if (reach_floor && (typ == FOUNTAIN || typ == SINK)) {
        context_add(&list,"quaff",typ == FOUNTAIN ? "Drink from fountain"
                                                : "Drink from sink",
                    typ == FOUNTAIN ? "Fountain underfoot" : "Sink underfoot");
        if (gi.invent)
            context_add(&list,"dip",typ == FOUNTAIN ? "Dip into fountain"
                                                  : "Dip into sink",
                        "Choose an item to dip");
    }
    if (reach_floor && typ == THRONE)
        context_add(&list,"sit","Sit on throne","Throne underfoot");
    if (typ == ALTAR) {
        context_add(&list,"offer","Offer sacrifice","Altar underfoot");
        if (gi.invent)
            context_add(&list,"drop","Drop on altar","Choose an item to drop");
    }
    if (!Hallucination && glyph_is_object(glyph)) {
        object = glyph_to_obj(glyph);
        if (reach_floor)
            context_add(&list,"pickup","Pick up","Items underfoot");
        context_add(&list,"look","Look here","Examine what is underfoot");
        if (reach_floor && context_container(object)) {
            context_add(&list,"loot","Loot container","Container underfoot");
            context_add(&list,"tip","Tip container","Container underfoot");
            if (object == CHEST || object == LARGE_BOX) {
                context_add(&list,"untrap","Check container for traps",
                            "Container underfoot");
                if (locktool)
                    context_add(&list,"apply","Apply key or lock tool",
                                "Container underfoot; choose a tool");
            }
            if ((object == CHEST || object == LARGE_BOX)
                && u_have_forceable_weapon())
                context_add(&list,"force","Force lock",
                            "Use your wielded weapon; may break it or the container");
        }
        if (reach_floor && objects[object].oc_class == FOOD_CLASS)
            context_add(&list,"eat","Eat from ground","Food underfoot");
    }
    context_trap(&list,glyph);
    if (u.usteed)
        context_add(&list,"ride","Dismount","You are riding");

    for (x = u.ux - 1; x <= u.ux + 1; ++x)
        for (y = u.uy - 1; y <= u.uy + 1; ++y) {
            boolean pet;
            if ((x == u.ux && y == u.uy) || !isok(x,y) || !shown[x][y])
                continue;
            glyph = shown_glyph[x][y];
            if (glyph_is_cmap(glyph)) {
                symbol = glyph_to_cmap(glyph);
                if (symbol == S_vcdoor || symbol == S_hcdoor) {
                    context_add(&list,"open","Open door","Nearby closed door");
                    context_add(&list,"kick","Kick","Nearby door");
                    context_add(&list,"untrap","Check door for traps",
                                "Nearby closed door");
                    if (locktool)
                        context_add(&list,"apply","Apply key or lock tool",
                                    "Nearby closed door; choose a tool and direction");
                } else if (symbol == S_vodoor || symbol == S_hodoor) {
                    context_add(&list,"close","Close door","Nearby open door");
                    context_add(&list,"kick","Kick","Nearby door");
                } else if (symbol == S_sink) {
                    context_add(&list,"kick","Kick sink","Nearby sink");
                }
                context_trap(&list,glyph);
            } else if (!Hallucination && glyph_is_object(glyph)) {
                object = glyph_to_obj(glyph);
                if (object == CHEST || object == LARGE_BOX)
                    context_add(&list,"kick","Kick container","Nearby chest or large box");
            } else if (!Hallucination && glyph_is_monster(glyph)) {
                context_add(&list,"glance","Inspect creature","A creature nearby");
                context_add(&list,"chat","Chat","A creature nearby; choose a direction");
                pet = glyph_is_pet(glyph);
                if (pet) {
                    struct monst *mon = m_at(x,y);
                    context_add(&list,"name","Name pet","Your pet is nearby");
                    /* A saddle is externally visible, not private inventory.
                     * Require physical sight of this displayed pet, not merely
                     * telepathy/detection, before consulting visible equipment. */
                    if (!u.usteed && !Blind && mon && canseemon(mon)
                        && which_armor(mon,W_SADDLE))
                        context_add(&list,"ride","Ride pet","A visibly saddled pet nearby");
                } else if (glyph_to_mon(glyph) == PM_SHOPKEEPER) {
                    context_add(&list,"pay","Pay shopkeeper","A recognized shopkeeper nearby");
                }
            }
        }
    /* Ranged choices are last. A glyph identifies appearance, not hostility.
     * Do not recommend offensive actions merely because a pet is nearby. */
    if (!Blind && !Hallucination)
        for (x = 1; x < COLNO; ++x) for (y = 0; y < ROWNO; ++y) {
            if ((x == u.ux && y == u.uy) || !shown[x][y] || !cansee(x,y)) continue;
            glyph = shown_glyph[x][y];
            if (glyph_is_monster(glyph) && !glyph_is_pet(glyph)
                && !glyph_is_ridden_monster(glyph)
                && glyph_to_mon(glyph) != PM_SHOPKEEPER) ranged = TRUE;
        }
    if (ranged) {
        if (throwable)
            context_add(&list,"throw","Throw an item","Creature in view; choose an item and target");
        if (uquiver)
            context_add(&list,"fire","Fire from quiver","Creature in view; choose a target");
        if (wand)
            context_add(&list,"zap","Zap a wand","Creature in view; choose a wand and target");
        if (spells)
            context_add(&list,"cast","Cast a spell","Creature in view; choose a spell");
    }
 done:
    puts("]}");
}
static const char *named_command(const char *name, const char *kind) {
    int i, key = 0;
    const char *reason = "That action is unavailable.";
    if (strcmp(kind,"command") || program_state.input_state != commandInp) {
        reason = "Finish the current prompt before choosing an action.";
    } else {
        for (i = 0; extcmdlist[i].ef_txt; ++i)
            if (!strcmp(name,extcmdlist[i].ef_txt)) break;
        if (extcmdlist[i].ef_txt && public_command(&extcmdlist[i])
            && command_selectable(&extcmdlist[i])) {
            key = command_binding(&extcmdlist[i]);
            if (!key) {
                key = (unsigned char)cmd_from_func(doextcmd);
                pending_extcmd = i;
            }
            Sprintf(inputline,"key %d",key);
            return inputline;
        }
    }
    printf("{\"type\":\"commandRejected\",\"name\":"); jstr(name);
    printf(",\"text\":"); jstr(reason); puts("}");
    return NULL;
}
/* Only called while NetHack is blocked on user input. Inspection never enters
 * the command queue and therefore cannot advance the world. */
static const char *readresponse(const char *kind) {
    for (;;) {
        int x,y;
        if (saving) {
            if (!strcmp(kind,"command")) {
                const char *result;
                saving = FALSE;
                result = named_command("save",kind);
                automatic_save = (result != NULL);
                if (result) return result;
                continue;
            }
            if (!strcmp(kind,"menu")) return "menu cancel";
            if (!strcmp(kind,"line")) return "line \033";
            return "key 27";
        }
        fflush(stdout);
        if (!fgets(inputline,sizeof inputline,stdin)) {
            /* Parent disappeared: upstream hangup machinery saves recoverable
             * state rather than leaving a spinning input loop. */
            hangup(0); return "key 27";
        }
        inputline[strcspn(inputline,"\r\n")] = '\0';
        if (sscanf(inputline,"inspect %d %d",&x,&y)==2) { inspectcell(x,y); continue; }
        if (!strncmp(inputline,"position ",9)) {
            /* Only getpos may consume mouse coordinates. Never turn a stale
             * selection click into movement or an answer to another prompt. */
            char extra;
            if (!strcmp(kind,"position") && program_state.input_state == getposInp
                && sscanf(inputline+9,"%d %d %c",&x,&y,&extra)==2
                && isok(x,y)) return inputline;
            continue;
        }
        if (!strncmp(inputline,"command ",8)) {
            const char *result = named_command(inputline + 8,kind);
            if (result) return result;
            continue;
        }
        if (!strcmp(inputline,"save")) {
            /* Before the movement loop, mandatory setup menus need not accept
             * Escape. Upstream hangup exits or saves safely at that phase. */
            if (!program_state.in_moveloop) { hangup(0); return "key 27"; }
            saving=TRUE; continue;
        }
        if (!strncmp(inputline,"key ",4) || !strncmp(inputline,"line ",5)
            || !strncmp(inputline,"menu",4)) return inputline;
    }
}
static int readkey(const char *kind) {
    const char *s = readresponse(kind);
    if (!strncmp(s,"key ",4)) return atoi(s+4);
    if (!strncmp(s,"line ",5)) return s[5] ? (unsigned char)s[5] : '\n';
    return '\033';
}
static void init(int *argc UNUSED, char **argv UNUSED) {
    setvbuf(stdout,NULL,_IOLBF,0);
    iflags.window_inited=TRUE;
    puts("{\"type\":\"hello\",\"version\":\"5.0.0\",\"protocol\":1,\"width\":80,\"height\":21}");
}
static void getln(const char *prompt,char *out) {
    const char *s;
    printf("{\"type\":\"input\",\"kind\":\"line\",\"prompt\":"); jstr(prompt); puts("}");
    s=readresponse("line");
    if (!strncmp(s,"line ",5)) { strncpy(out,s+5,BUFSZ-1); out[BUFSZ-1]=0; }
    else { out[0]='\033'; out[1]=0; }
}
static void ask(void) { char b[BUFSZ]; getln("What is your name?",b); strncpy(svp.plname,b,PL_NSIZ-1); }
static void exitwindow(const char *s) { eventtext("exit",s ? s : "Game ended."); }
static void suspendwin(const char *s UNUSED) {}
static winid create(int type) {
    int i; for(i=1;i<AWINDOWS;i++) if (!aw[i].type) { aw[i].type=type; return i; }
    panic("Too many Atelier windows"); return WIN_ERR;
}
static void clear(winid w) {
    int i; if(w<=0||w>=AWINDOWS)return;
    for(i=0;i<aw[w].count;i++) free(aw[w].rows[i].text);
    free(aw[w].rows); aw[w].rows=NULL; aw[w].count=0;
    free(aw[w].prompt); aw[w].prompt=NULL;
    if(aw[w].type==NHW_MAP) { memset(shown,0,sizeof shown); puts("{\"type\":\"clear\",\"window\":\"map\"}"); }
}
static void destroy(winid w) { clear(w); if(w>0&&w<AWINDOWS)aw[w].type=0; }
static void cursor(winid w,int x,int y) {
    if (w>0&&w<AWINDOWS&&aw[w].type==NHW_MAP)
        printf("{\"type\":\"cursor\",\"x\":%d,\"y\":%d,\"playerX\":%d,\"playerY\":%d}\n",x,y,u.ux,u.uy);
}
static void addrow(winid w,const anything *id,const char *text,char key,char group,int tile,unsigned flags) {
    struct arow *r;
    if(w<=0||w>=AWINDOWS||aw[w].count>=AROWS)return;
    aw[w].rows=realloc(aw[w].rows,(aw[w].count+1)*sizeof(struct arow));
    if(!aw[w].rows)panic("Atelier menu allocation failed");
    r=&aw[w].rows[aw[w].count++]; memset(r,0,sizeof *r);
    if(id)r->identifier=*id;
    r->text=strdup(text?text:""); r->key=key; r->group=group; r->tile=tile; r->flags=flags;
}
static void put(winid w,int attr UNUSED,const char *s) {
    if(w>0&&w<AWINDOWS&&(aw[w].type==NHW_MENU||aw[w].type==NHW_TEXT))addrow(w,NULL,s,0,0,-1,0);
    else eventtext("message",s);
}
static int getkey(void) { if(automatic_save && program_state.savefile_completed) return '\n'; puts("{\"type\":\"input\",\"kind\":\"key\",\"command\":false}"); return readkey("key"); }
static void display(winid w,boolean blocking) {
    int i;
    if(w>0&&w<AWINDOWS&&(aw[w].type==NHW_TEXT||aw[w].type==NHW_MENU)&&aw[w].count) {
        printf("{\"type\":\"input\",\"kind\":\"text\",\"prompt\":");jstr(aw[w].prompt);printf(",\"lines\":[");
        for(i=0;i<aw[w].count;i++){if(i)putchar(',');jstr(aw[w].rows[i].text);}puts("]}");readkey("key");
    } else if(blocking) getkey();
}
static void startmenu(winid w,unsigned long behavior UNUSED) { clear(w); }
static void addmenu(winid w,const glyph_info *g,const ANY_P *id,char ch,char gch,int attr UNUSED,int color UNUSED,const char *s,unsigned flags) {
    addrow(w,id,s,ch,gch,g?g->gm.tileidx:-1,flags);
}
static void endmenu(winid w,const char *s) { if(w>0&&w<AWINDOWS){free(aw[w].prompt);aw[w].prompt=strdup(s?s:"");} }
static int selectmenu(winid w,int how,MENU_ITEM_P **selected) {
    int i,n=0; char *p,*next; const char *response;
    *selected=NULL;
    printf("{\"type\":\"input\",\"kind\":\"menu\",\"prompt\":"); jstr(aw[w].prompt); printf(",\"how\":%d,\"items\":[",how);
    for(i=0;i<aw[w].count;i++){
        struct arow *r=&aw[w].rows[i]; char k[2]={r->key,0},g[2]={r->group,0};
        if(i)putchar(','); printf("{\"id\":%d,\"text\":",i);jstr(r->text);
        printf(",\"key\":");jstr(k);printf(",\"group\":");jstr(g);
        printf(",\"tile\":%d,\"selectable\":%s,\"selected\":%s}",r->tile,r->identifier.a_void?"true":"false",(r->flags&MENU_ITEMFLAGS_SELECTED)?"true":"false");
    } puts("]}");
    response=readresponse("menu");
    if(strcmp(response,"menu cancel")==0||strncmp(response,"menu",4))return -1;
    if(how==PICK_NONE)return 0;
    *selected=(menu_item*)alloc((aw[w].count+1)*sizeof(menu_item));
    p=(char*)response+4; while(*p==' ')p++;
    while(*p){long count=-1;int id=(int)strtol(p,&next,10); if(next==p)break; p=next;
        if(*p==':'){count=strtol(p+1,&next,10);p=next;}
        if(id>=0&&id<aw[w].count&&aw[w].rows[id].identifier.a_void){
            boolean duplicate=FALSE;int j;for(j=0;j<n;j++)if((*selected)[j].item.a_void==aw[w].rows[id].identifier.a_void)duplicate=TRUE;
            if(!duplicate){(*selected)[n].item=aw[w].rows[id].identifier;(*selected)[n].count=count>0?count:-1;(*selected)[n].itemflags=0;n++;}
            if(how==PICK_ONE)break;
        }
        if(*p!=',')break;p++;
    }
    if(!n){free(*selected);*selected=NULL;}return n;
}
/* Only remembered/perceived surface types may sit beneath the foreground.
 * Upstream's background argument uses current levl.typ, omits ordinary room
 * floor, and can disclose changed terrain outside sight. Do not use it here.
 * lastseentyp and waslit already survive level changes and save/restore.
 * No door/altar/stair flags or hidden objects are queried. Lowered drawbridge
 * orientation uses an exact remembered glyph, or currently visible terrain. */
static int ground_tile(coordxy x,coordxy y,int foreground) {
    int typ, symbol;
    boolean visible;
    glyph_info info;
    if (!isok(x,y) || u.uswallow || u.uburied
        || glyph_is_unexplored(foreground) || glyph_is_nothing(foreground)
        || glyph_is_swallow(foreground)) return -1;
    visible = cansee(x,y);
    if (!visible && !svl.level.flags.hero_memory) return -1;
    if (!visible && !levl[x][y].seenv && (x != u.ux || y != u.uy))
        return -1;
    typ = svl.lastseentyp[x][y];
    switch (typ) {
    case ROOM:
    /* Known floor-supported fixtures get a decorative floor, not invented
     * feature details such as stair direction or altar alignment. */
    case STAIRS: case LADDER: case FOUNTAIN: case SINK: case DOOR:
    case ALTAR: case GRAVE: case THRONE: case IRONBARS:
        symbol = S_room;
        if (!visible && (!levl[x][y].waslit || flags.dark_room))
            symbol = (flags.dark_room && iflags.use_color) ? DARKROOMSYM : S_stone;
        break;
    case CORR:
        symbol = (levl[x][y].waslit || flags.lit_corridor) ? S_litcorr : S_corr;
        if (!visible && (!levl[x][y].waslit || flags.dark_room)) symbol = S_corr;
        break;
    case ICE: symbol = S_ice; break;
    case POOL: case MOAT: symbol = S_pool; break;
    case WATER: symbol = S_water; break;
    case LAVAPOOL: symbol = S_lava; break;
    case LAVAWALL: symbol = S_lavawall; break;
    case AIR: symbol = S_air; break;
    case CLOUD: symbol = S_cloud; break;
    case DRAWBRIDGE_DOWN: {
        int remembered = foreground;
        /* lastseentyp stores the lowered surface but not its orientation.
         * Never read current bridge geometry outside sight. Upstream already
         * resolves raised spans to their remembered water/ice/floor type. */
        if (visible && levl[x][y].typ == DRAWBRIDGE_DOWN)
            remembered = back_to_glyph(x, y);
        else if (!glyph_is_cmap(remembered)
                 || (glyph_to_cmap(remembered) != S_vodbridge
                     && glyph_to_cmap(remembered) != S_hodbridge))
            remembered = levl[x][y].glyph;
        if (!glyph_is_cmap(remembered)) return -1;
        symbol = glyph_to_cmap(remembered);
        if (symbol != S_vodbridge && symbol != S_hodbridge) return -1;
        break;
    }
    default: return -1; /* unknown, walls and unsupported topology */
    }
    map_glyphinfo(x,y,cmap_to_glyph(symbol),0,&info);
    return info.gm.tileidx;
}
/* Derive ground treatments from upstream remembered terrain only. Doors are
 * thresholds even when open or broken. Unknown cells, walls, bars and clouds
 * stop floor traversal. No live unseen terrain or source room flags are read.
 * Components without an exterior seed remain conservatively unclassified.
 * The maps are transient, so save/restore and level changes need no new state. */
enum aground_flag { AGROUND_EXTERIOR = 1, AGROUND_TREE = 2,
                    AGROUND_ENCLOSED = 4, AGROUND_REGULAR = 8 };
struct aground_map { unsigned char cell[COLNO][ROWNO]; };

static boolean remembered_terrain_known(int x, int y) {
    if (!isok(x, y)) return FALSE;
    if (!cansee(x, y) && !svl.level.flags.hero_memory) return FALSE;
    return levl[x][y].seenv || (x == u.ux && y == u.uy);
}
static boolean remembered_dry_ground(int typ) {
    return typ == ROOM || typ == CORR || typ == STAIRS || typ == LADDER
        || typ == GRAVE || typ == ALTAR || typ == THRONE
        || typ == FOUNTAIN || typ == SINK;
}
static boolean remembered_room_surface(int typ) {
    return remembered_dry_ground(typ) || typ == POOL || typ == MOAT
        || typ == WATER || typ == ICE || typ == LAVAPOOL || typ == LAVAWALL;
}
static boolean remembered_boundary(int x, int y) {
    int typ;
    if (!remembered_terrain_known(x, y)) return FALSE;
    typ = svl.lastseentyp[x][y];
    return IS_WALL(typ) || typ == SDOOR || typ == DOOR;
}
static void remembered_ground_map(struct aground_map *result) {
    boolean visited[COLNO][ROWNO];
    coord queue[COLNO * ROWNO];
    static const int dx[] = { 0, 1, 0, -1 }, dy[] = { -1, 0, 1, 0 };
    int pass, x, y, i, head, tail;
    memset(result, 0, sizeof *result);
    /* First connect dry ground to remembered natural surroundings. Then
     * separately prove complete wall/door enclosures, including water inside
     * Medusa's buildings. A positive enclosure beats an interior pool seed. */
    for (pass = 0; pass < 2; ++pass) {
        memset(visited, 0, sizeof visited);
        for (x = 1; x < COLNO; ++x) for (y = 0; y < ROWNO; ++y) {
            int xmin = x, xmax = x, ymin = y, ymax = y;
            unsigned char treatment = 0;
            boolean enclosed = TRUE, regular;
            if (visited[x][y] || !remembered_terrain_known(x, y)
                || !(pass ? remembered_room_surface(svl.lastseentyp[x][y])
                          : remembered_dry_ground(svl.lastseentyp[x][y])))
                continue;
            head = 0; tail = 1; visited[x][y] = TRUE;
            queue[0].x = x; queue[0].y = y;
            while (head < tail) {
                coord here = queue[head++];
                if (here.x < xmin) xmin = here.x;
                if (here.x > xmax) xmax = here.x;
                if (here.y < ymin) ymin = here.y;
                if (here.y > ymax) ymax = here.y;
                if (!pass && (here.x == 1 || here.x == COLNO - 1
                              || here.y == 0 || here.y == ROWNO - 1))
                    treatment |= AGROUND_EXTERIOR;
                for (i = 0; i < 4; ++i) {
                    int nx = here.x + dx[i], ny = here.y + dy[i], typ;
                    boolean surface;
                    if (!remembered_terrain_known(nx, ny)) {
                        enclosed = FALSE;
                        continue;
                    }
                    typ = svl.lastseentyp[nx][ny];
                    if (!pass) {
                        if (typ == TREE) treatment |= AGROUND_TREE | AGROUND_EXTERIOR;
                        if (typ == POOL || typ == MOAT || typ == WATER)
                            treatment |= AGROUND_EXTERIOR;
                    }
                    surface = pass ? remembered_room_surface(typ)
                                   : remembered_dry_ground(typ);
                    if (surface) {
                        if (!visited[nx][ny]) {
                            visited[nx][ny] = TRUE;
                            queue[tail].x = nx; queue[tail++].y = ny;
                        }
                    } else if (!remembered_boundary(nx, ny)) {
                        enclosed = FALSE;
                    }
                }
            }
            if (pass) {
                regular = enclosed && tail == (xmax - xmin + 1) * (ymax - ymin + 1)
                    && remembered_boundary(xmin - 1, ymin - 1)
                    && remembered_boundary(xmax + 1, ymin - 1)
                    && remembered_boundary(xmin - 1, ymax + 1)
                    && remembered_boundary(xmax + 1, ymax + 1);
                treatment = (enclosed ? AGROUND_ENCLOSED : 0)
                    | (regular ? AGROUND_REGULAR : 0);
            }
            for (i = 0; i < tail; ++i)
                result->cell[queue[i].x][queue[i].y] |= treatment;
        }
    }
}
static unsigned char remembered_ground_flags(coordxy x, coordxy y,
                                             const struct aground_map *map) {
    struct aground_map temporary;
    if (!map) {
        remembered_ground_map(&temporary);
        map = &temporary;
    }
    return map->cell[x][y];
}
static boolean quest_earth_ground(coordxy x, coordxy y,
                                  const struct aground_map *map) {
    unsigned char treatment;
    if (!remembered_terrain_known(x, y)
        || !remembered_dry_ground(svl.lastseentyp[x][y])) return FALSE;
    treatment = remembered_ground_flags(x, y, map);
    return (treatment & AGROUND_EXTERIOR) && !(treatment & AGROUND_ENCLOSED);
}
/* The level's visual family is independent of hidden cell terrain.
 * Other named maps and the invocation approach retain their existing appearance.
 * Never inspect the vibrating square or any undiscovered feature here. */
static enum amaterial regional_material(coordxy x, coordxy y, int foreground,
                                        const struct aground_map *map) {
    if (u.uswallow || u.uburied
        || glyph_is_unexplored(foreground) || glyph_is_nothing(foreground)
        || glyph_is_swallow(foreground))
        return AMATERIAL_NONE;
    if (In_V_tower(&u.uz)) return AMATERIAL_VLAD;
    if (Is_asmo_level(&u.uz)) return AMATERIAL_ASMODEUS;
    if (Is_valley(&u.uz) || on_level(&u.uz, &orcus_level)) return AMATERIAL_VALLEY;
    if (Is_medusa_level(&u.uz))
        return quest_earth_ground(x, y, map) ? AMATERIAL_QUEST_EARTH : AMATERIAL_MEDUSA;
    if (Is_juiblex_level(&u.uz)) return AMATERIAL_JUIBLEX;
    if (Is_baal_level(&u.uz)) return AMATERIAL_BAALZ;
    if (Role_if(PM_CAVE_DWELLER) && In_quest(&u.uz))
        return Is_nemesis(&u.uz) ? AMATERIAL_CAVEMAN_GOAL : AMATERIAL_CAVEMAN;
    if (Role_if(PM_SAMURAI) && In_quest(&u.uz)) {
        if ((Is_qstart(&u.uz) || Is_qlocate(&u.uz)) && quest_earth_ground(x, y, map))
            return AMATERIAL_QUEST_EARTH;
        return AMATERIAL_SAMURAI;
    }
    /* Persistent role/stage identities choose existing art. Remembered natural
     * components distinguish exterior earth from finished built floors. */
    if (In_quest(&u.uz)) {
        if (Role_if(PM_ARCHEOLOGIST)) {
            if ((Is_qstart(&u.uz) || Is_qlocate(&u.uz)) && quest_earth_ground(x, y, map))
                return AMATERIAL_QUEST_EARTH;
            return AMATERIAL_NONE;
        }
        if (Role_if(PM_KNIGHT)) {
            if (Is_qstart(&u.uz))
                return quest_earth_ground(x, y, map) ? AMATERIAL_QUEST_EARTH : AMATERIAL_NONE;
            return AMATERIAL_CAVEMAN;
        }
        if (Role_if(PM_BARBARIAN)) {
            if (Is_qstart(&u.uz) || Is_qlocate(&u.uz))
                return quest_earth_ground(x, y, map) ? AMATERIAL_QUEST_EARTH : AMATERIAL_NONE;
            return AMATERIAL_CAVEMAN;
        }
        if (Role_if(PM_RANGER)) {
            if (Is_qstart(&u.uz) || (!Is_qlocate(&u.uz) && !Is_nemesis(&u.uz)
                                    && u.uz.dlevel < qlocate_level.dlevel))
                return remembered_terrain_known(x, y)
                    && remembered_dry_ground(svl.lastseentyp[x][y])
                    ? AMATERIAL_QUEST_EARTH : AMATERIAL_NONE;
            return AMATERIAL_CAVEMAN;
        }
        if (Role_if(PM_TOURIST)) {
            if (Is_qstart(&u.uz))
                return quest_earth_ground(x, y, map) ? AMATERIAL_QUEST_EARTH : AMATERIAL_NONE;
            if (Is_qlocate(&u.uz) || Is_nemesis(&u.uz)) return AMATERIAL_NONE;
            return AMATERIAL_CAVEMAN;
        }
        if (Role_if(PM_WIZARD)) {
            if ((Is_qstart(&u.uz) || Is_qlocate(&u.uz)) && quest_earth_ground(x, y, map))
                return AMATERIAL_QUEST_EARTH;
            return AMATERIAL_NONE;
        }
        if (Role_if(PM_MONK)) {
            if (Is_qstart(&u.uz) && quest_earth_ground(x, y, map))
                return AMATERIAL_QUEST_EARTH;
            if (Is_qlocate(&u.uz)) return AMATERIAL_CAVEMAN;
            if (Is_nemesis(&u.uz)) return AMATERIAL_GEHENNOM;
            return AMATERIAL_NONE;
        }
        if (Role_if(PM_CLERIC)) {
            if ((Is_qstart(&u.uz) || Is_qlocate(&u.uz))
                && quest_earth_ground(x, y, map)) return AMATERIAL_QUEST_EARTH;
            if (Is_qlocate(&u.uz)) return AMATERIAL_PRIEST_TEMPLE;
            if (Is_nemesis(&u.uz)) return AMATERIAL_GEHENNOM;
            return AMATERIAL_NONE;
        }
        if (Role_if(PM_HEALER)) {
            if (Is_qstart(&u.uz) || Is_qlocate(&u.uz))
                return quest_earth_ground(x, y, map) ? AMATERIAL_QUEST_EARTH : AMATERIAL_NONE;
            return AMATERIAL_CAVEMAN;
        }
        if (Role_if(PM_VALKYRIE)) {
            if (Is_qstart(&u.uz)) return AMATERIAL_NONE;
            if (Is_nemesis(&u.uz)) return AMATERIAL_BAALZ;
            if (u.uz.dlevel <= qlocate_level.dlevel) return AMATERIAL_CAVEMAN;
            return AMATERIAL_GEHENNOM;
        }
    }
    if (Is_earthlevel(&u.uz)) return AMATERIAL_EARTH;
    if (Is_firelevel(&u.uz)) return AMATERIAL_GEHENNOM;
    if (Is_astralevel(&u.uz)) return AMATERIAL_ASTRAL;
    if (In_mines(&u.uz)) {
        s_level *special = Is_special(&u.uz);
        if (special && !strncmp(special->proto, "minetn", 6)
            && remembered_terrain_known(x, y)
            && remembered_dry_ground(svl.lastseentyp[x][y])
            && (remembered_ground_flags(x, y, map) & AGROUND_REGULAR))
            return AMATERIAL_MINES_BUILT;
        return AMATERIAL_MINES;
    }
    if (Is_special(&u.uz)) return AMATERIAL_NONE;
    if (In_hell(&u.uz) && !Invocation_lev(&u.uz)) return AMATERIAL_GEHENNOM;
    /* Ordinary Garden evidence is a remembered tree bordering this known
     * floor component. Water, swamp, room type and hidden contents never seed
     * this rule; named landmarks and every other branch already returned. */
    if (u.uz.dnum == oracle_level.dnum && !In_hell(&u.uz)
        && remembered_terrain_known(x, y)
        && remembered_dry_ground(svl.lastseentyp[x][y])
        && (remembered_ground_flags(x, y, map) & AGROUND_TREE))
        return AMATERIAL_QUEST_EARTH;
    return AMATERIAL_NONE;
}
static void emit_cell(coordxy x,coordxy y) {
    const struct acell *cell = &shown_cells[x][y];
    char c[2]={cell->character,0};
    printf("{\"type\":\"cell\",\"x\":%d,\"y\":%d,\"tile\":%d,\"glyph\":%d,\"char\":",x,y,cell->tile,shown_glyph[x][y]);jstr(c);
    printf(",\"color\":%d,\"pet\":%s",cell->color,cell->pet?"true":"false");
    if (cell->ground >= 0) printf(",\"groundTile\":%d",cell->ground);
    if (cell->material == AMATERIAL_MINES) printf(",\"material\":\"mines\"");
    else if (cell->material == AMATERIAL_GEHENNOM) printf(",\"material\":\"gehennom\"");
    else if (cell->material == AMATERIAL_VLAD) printf(",\"material\":\"vlad\"");
    else if (cell->material == AMATERIAL_ASMODEUS) printf(",\"material\":\"asmodeus\"");
    else if (cell->material == AMATERIAL_CAVEMAN) printf(",\"material\":\"caveman\"");
    else if (cell->material == AMATERIAL_CAVEMAN_GOAL) printf(",\"material\":\"caveman-goal\"");
    else if (cell->material == AMATERIAL_EARTH) printf(",\"material\":\"earth\"");
    else if (cell->material == AMATERIAL_VALLEY) printf(",\"material\":\"valley\"");
    else if (cell->material == AMATERIAL_SAMURAI) printf(",\"material\":\"samurai\"");
    else if (cell->material == AMATERIAL_MEDUSA) printf(",\"material\":\"medusa\"");
    else if (cell->material == AMATERIAL_JUIBLEX) printf(",\"material\":\"juiblex\"");
    else if (cell->material == AMATERIAL_BAALZ) printf(",\"material\":\"baalz\"");
    else if (cell->material == AMATERIAL_QUEST_EARTH) printf(",\"material\":\"quest-earth\"");
    else if (cell->material == AMATERIAL_PRIEST_TEMPLE) printf(",\"material\":\"priest-temple\"");
    else if (cell->material == AMATERIAL_MINES_BUILT) printf(",\"material\":\"mines-built\"");
    else if (cell->material == AMATERIAL_ASTRAL) printf(",\"material\":\"astral\"");
    puts("}");
}
static void glyph(winid w UNUSED,coordxy x,coordxy y,const glyph_info *g,const glyph_info *bg UNUSED) {
    struct acell *cell;
    if (!isok(x,y)) return;
    shown[x][y]=TRUE; shown_glyph[x][y]=g->glyph;
    cell = &shown_cells[x][y];
    cell->tile=g->gm.tileidx; cell->character=(char)g->ttychar;
    cell->color=g->gm.sym.color; cell->pet=(g->gm.glyphflags&MG_PET)!=0;
    cell->ground=ground_tile(x,y,g->glyph);
    cell->material=regional_material(x,y,g->glyph,NULL);
    emit_cell(x,y);
}
/* Core foreground deduplication can hide a surface-only change (or a late
 * memory/lighting update). Refresh only changed layers at command boundaries,
 * reusing the exact foreground already emitted, without advancing turns. */
static void refresh_ground(void) {
    int x,y,ground;
    enum amaterial material;
    struct aground_map ground_map;
    /* Upstream finishes memory updates before this ordinary input boundary.
     * Share one transient snapshot across the refresh; never retain it across
     * turns, redraws, level changes, save or restore. */
    remembered_ground_map(&ground_map);
    for (x=1;x<COLNO;++x) for (y=0;y<ROWNO;++y) if (shown[x][y]) {
        ground=ground_tile(x,y,shown_glyph[x][y]);
        material=regional_material(x,y,shown_glyph[x][y],&ground_map);
        if (ground != shown_cells[x][y].ground || material != shown_cells[x][y].material) {
            shown_cells[x][y].ground=ground;
            shown_cells[x][y].material=material;
            emit_cell(x,y);
        }
    }
}
static void raw(const char *s){eventtext("message",s);}
/* The core marks these contexts before calling the window port. Unlike
 * matching English prompt text, this covers custom direction questions too. */
static void input_context(void) {
    boolean direction = (program_state.input_state == getdirInp);
    boolean targeting = (program_state.input_state == getposInp);
    char self[2] = {(char)gc.Cmd.spkeys[NHKF_GETDIR_SELF], 0};
    printf(",\"direction\":%s,\"targeting\":%s",direction?"true":"false",targeting?"true":"false");
    printf(",\"directionKeys\":"); jstr(gc.Cmd.dirchars);
    if(direction) { printf(",\"selfKey\":"); jstr(self); }
}
static int poskey(coordxy *x,coordxy *y,int *mod) {
    boolean command = (program_state.input_state == commandInp);
    boolean targeting = (program_state.input_state == getposInp);
    const char *response;
    int tx,ty;
    static boolean menu_defaults_applied = FALSE;
    /* menu_style is saved, unlike force_invmenu. Upgrade old saved UI settings
     * after restore, once per launch; later deliberate option changes still work. */
    if (command && !menu_defaults_applied) {
        if (iflags.force_invmenu) flags.menu_style = MENU_FULL;
        menu_defaults_applied = TRUE;
    }
    /* A movement prefix can reject the extended-command key before extcmd()
     * consumes our index. It must never leak into a later manual # command. */
    pending_extcmd = -1;
    /* A refused/failed host save must not auto-confirm a later manual save. */
    if (command) automatic_save = FALSE;
    if (command) { refresh_ground(); command_catalog(); context_commands(); }
    printf("{\"type\":\"input\",\"kind\":\"key\",\"command\":%s",command?"true":"false");
    input_context(); puts("}");
    if (!targeting) return readkey(command?"command":"key");
    response = readresponse("position");
    if (sscanf(response,"position %d %d",&tx,&ty)==2) {
        *x = (coordxy)tx; *y = (coordxy)ty; *mod = CLICK_1;
        return 0; /* upstream getpos handles the selected location */
    }
    if (!strncmp(response,"key ",4)) return atoi(response+4);
    return '\033';
}
static int prev(void){return 0;}
/* NetHack uses '#' plus yn_number for quantity prompts. A dedicated line
 * response makes the complete number editable without spending a game turn. */
static boolean getcount(int first) {
    char initial[2] = {first >= '0' && first <= '9' ? (char)first : 0, 0};
    const char *response, *digits, *scan; char *end; long value;
    for (;;) {
        printf("{\"type\":\"input\",\"kind\":\"line\",\"purpose\":\"count\",\"prompt\":\"How many?\",\"default\":");
        jstr(initial); puts("}");
        response = readresponse("line");
        if (!strcmp(response,"key 27")) return FALSE;
        if (strncmp(response,"line ",5)) continue;
        digits = response + 5;
        if (digits[0] == '\033') return FALSE;
        if (!*digits) digits = initial;
        for (scan = digits; *scan >= '0' && *scan <= '9'; ++scan) {}
        errno = 0; value = strtol(digits,&end,10);
        if (*digits && !*scan && !*end && errno != ERANGE && value >= 0) {
            yn_number = value; return TRUE;
        }
        eventtext("message","Enter a non-negative whole number.");
    }
}
/* Match the core's response identities, not English prompt text or arbitrary
 * inventory letters. Keep our existing confirmation/cancellation semantics. */
static void choice_labels(const char *choices) {
    if (choices == rightleftchars)
        printf(",\"choiceLabels\":{\"r\":\"Right hand\",\"l\":\"Left hand\"}");
    else if (choices == hidespinchars)
        printf(",\"choiceLabels\":{\"h\":\"Hide\",\"s\":\"Spin a web\",\"q\":\"Cancel\"}");
    else if (choices == ynaqchars || choices == ynNaqchars)
        printf(",\"choiceLabels\":{\"y\":\"Yes\",\"n\":\"No\",\"a\":\"All\",\"q\":\"Cancel\",\"#\":\"Choose quantity\"}");
}
static char yn(const char *q,const char *choices,char def){
    char d[2]={def,0};int ch;
    if(automatic_save && !strcmp(q,"Really save?")) return 'y';
    yn_number = 0L;
    for(;;){
        /* Every rejected response starts a fresh advertised input wait. The
         * host may already have disabled its prompt after submitting a key. */
        printf("{\"type\":\"input\",\"kind\":\"yn\",\"prompt\":");jstr(q);printf(",\"choices\":");jstr(choices);printf(",\"default\":");jstr(d);choice_labels(choices);input_context();puts("}");
        ch=readkey("yn");
        if(!choices||!choices[0]) return (char)ch;
        if(ch=='\n'||ch=='\r'||ch==' ')ch=def?def:'\n';
        if(ch=='\033'){if(choices&&strchr(choices,'q'))return 'q';if(choices&&strchr(choices,'n'))return 'n';return def?def:'\033';}
        if(strchr(choices,'#') && (ch=='#' || (ch>='0' && ch<='9'))) {
            if(getcount(ch)) return yn_number ? '#' : 'n';
            continue;
        }
        if(ch && strchr(choices,ch))return (char)ch;
    }
}
static int extcmd(void){char b[BUFSZ];int i;if(pending_extcmd>=0){i=pending_extcmd;pending_extcmd=-1;return i;}getln("Extended command",b);for(i=0;extcmdlist[i].ef_txt;i++)if(!strcmpi(b,extcmdlist[i].ef_txt))return i;return -1;}
static void numberpad(int state UNUSED){}
static void enablefield(int field,const char *name,const char *fmt UNUSED,boolean enable UNUSED){if(field>=0&&field<MAXBLSTATS){strncpy(fieldnames[field],name?name:"",63);}}
static void updatestatus(int field,genericptr_t ptr,int changed UNUSED,int percent,int color UNUSED,unsigned long *masks UNUSED){
    char b[128];const char *value;
    if(field<0){
        /* Report the hero's XP even when showexp is off or polymorph hides
         * the ordinary experience status fields. Thresholds belong to NetHack. */
        printf("{\"type\":\"statusFlush\",\"experience\":{\"level\":%d,\"points\":%ld,\"start\":%ld,\"next\":",
               u.ulevel,u.uexp,newuexp(u.ulevel-1));
        if(u.ulevel<MAXULEV) printf("%ld",newuexp(u.ulevel));
        else printf("null");
        puts("}}");return;
    }
    if(field>=MAXBLSTATS)return;
    if(field==BL_CONDITION){snprintf(b,sizeof b,"%lu",ptr?*(unsigned long*)ptr:0UL);value=b;}
    else value=ptr?(const char*)ptr:"";
    printf("{\"type\":\"status\",\"field\":%d,\"name\":",field);jstr(fieldnames[field]);printf(",\"value\":");jstr(value);printf(",\"percent\":%d}\n",percent);
}
static void inventory(int arg UNUSED){}
static win_request_info *control(winid w UNUSED,int request UNUSED,win_request_info *info){return info;}
#ifdef CLIPPING
static void clip(int x UNUSED,int y UNUSED){}
#endif
struct window_procs shim_procs={
 .name="shim",.wp_id=wp_shim,
 .wincap=WC_COLOR|WC_HILITE_PET|WC_ASCII_MAP|WC_TILED_MAP|WC_PLAYER_SELECTION|WC_POPUP_DIALOG,
 .wincap2=WC2_FLUSH_STATUS|WC2_HILITE_STATUS|WC2_DARKGRAY,
 .has_color={1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1},
 .win_init_nhwindows=init,.win_player_selection=genl_player_selection,.win_askname=ask,.win_get_nh_event=noop,
 .win_exit_nhwindows=exitwindow,.win_suspend_nhwindows=suspendwin,.win_resume_nhwindows=noop,
 .win_create_nhwindow=create,.win_clear_nhwindow=clear,.win_display_nhwindow=display,.win_destroy_nhwindow=destroy,
 .win_curs=cursor,.win_putstr=put,.win_putmixed=genl_putmixed,.win_display_file=genl_display_file,
 .win_start_menu=startmenu,.win_add_menu=addmenu,.win_end_menu=endmenu,.win_select_menu=selectmenu,
 .win_message_menu=genl_message_menu,.win_mark_synch=noop,.win_wait_synch=noop,
#ifdef CLIPPING
 .win_cliparound=clip,
#endif
 .win_print_glyph=glyph,.win_raw_print=raw,.win_raw_print_bold=raw,.win_nhgetch=getkey,.win_nh_poskey=poskey,
 .win_nhbell=noop,.win_doprev_message=prev,.win_yn_function=yn,.win_getlin=getln,.win_get_ext_cmd=extcmd,
 .win_number_pad=numberpad,.win_delay_output=noop,.win_outrip=genl_outrip,.win_preference_update=genl_preference_update,
 .win_getmsghistory=genl_getmsghistory,.win_putmsghistory=genl_putmsghistory,
 .win_status_init=noop,.win_status_finish=noop,.win_status_enablefield=enablefield,.win_status_update=updatestatus,
 .win_can_suspend=genl_can_suspend_no,.win_update_inventory=inventory,.win_ctrl_nhwindow=control
};
