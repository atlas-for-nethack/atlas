# Atlas for NetHack interface

The interface is an offline HTML/CSS/JavaScript presentation layer inside a native macOS WKWebView. All real gameplay comes from the bundled NetHack 5.0 process; JavaScript never simulates dungeon rules. No CDN, JavaScript framework, external font or network connection is needed.

## Design

A charcoal and forest-green workspace uses warm copper accents, serif titles, quiet typography and pixel-crisp artwork. The adventurer panel holds status and inventory, the central pane reserves the largest area for the dungeon, and field notes explain the hovered cell. An adventure journal keeps the last 300 messages. The illustrated welcome screen is generated entirely with CSS.

The built-in Lantern Classic, Lantern Modern, Soot & Brass Modern, Soot & Brass Classic and NetHack Classic tilesets use the exact 5.0 tile ordering. Custom imports retain their rectangular tile proportions. The settings pane exposes a readable ASCII fallback, tile import dimensions, grid display and follow-player behavior. Artist attribution and licensing appear alongside the selected tileset. Imported images persist atomically under the app's private Application Support directory; the selected tileset identifier is a small local preference. Native imports do not depend on browser storage quotas.

Lantern Classic is the default tileset. Original Lantern and Soot & Brass artwork
uses CC BY 4.0, with attribution to the NetHack Atlas project, a license link and
indication of changes. NetHack Classic remains under NGPL. See
[the component license map](../LICENSES.md) for code and metadata terms.
Saved preferences for unavailable bundled sets fall back to Lantern Classic;
custom imports remain available. Soot & Brass Modern offers directional walls,
doors and iron bars.
Soot & Brass Classic keeps the same architecture but bounds creatures, statues,
items and effects to one square. Lantern Modern keeps Lantern terrain and uses
the same shared monster-size policy. Both Modern editions' larger creatures rise above their logical floor squares. Movement, targeting
and inspection stay anchored to those squares; outlines are drawn above the art.
Known floors are drawn before raised terrain and creatures, with foreground
ordered by ground contact. The canvas reserves space for artwork at map edges.
In a projected set, other perceived foreground artwork fades to 35% opacity where
their artwork overlaps the hovered or targeted logical square, or the hero's
square when neither is active. The focused subject remains opaque. This includes
overhanging doors, walls, bars and statues as well as creatures, making covered
squares inspectable without changing hitboxes or inventing hidden information.
Artwork confined to its own square retains its normal opacity.
Lantern starts at 64 pixels per movement square. Its floor texture marks that
square, and transparent subjects reveal only engine-supplied perceived ground.
Both Lantern editions share the same textured stone walls and upright oak doors.
Raised artwork retains its reference proportions above each square. Door frames
follow adjacent displayed walls: narrow on the sides and shallow along the bottom
rim. Opening a door preserves that frame and connects the floor only toward
known adjacent surfaces. These appearances do not alter movement or perception.

Character creation offers male/female sex and alignment choices, each defaulting to Let fate decide. Available races, sexes and alignments follow the bundled engine's role and race restrictions in `web/character.js`. Selecting a role or race automatically fills mandatory choices (for example, female Valkyries and human lawful Knights); invalid optional choices must be selected again. The form explains mandatory selections and validates the combination before launch.

The play-mode selector defaults to Standard. Beginner adds an unlocked, untrapped supply chest on nearby reachable floor, away from the stairs: 1,000 gold, an identified uncursed magic whistle, two food rations and an identified uncursed healing potion. Role equipment, attributes and permanent death are unchanged. The player moves onto the chest and chooses what to take through the normal Loot container action. The chest avoids adding weight to the initial carried inventory.

Explore is the third Play mode choice. Its creation copy and persistent badge identify it as non-scoring. The Explore guide explains the native wishing wand, declining death and the keep-save prompt on restoration. It has separate saved-game labels and storage, normal role gear, and no Beginner supply chest.

Beginner games show a persistent mode badge and an accessible guide explaining Loot, Apply for the whistle, Eat for rations and Quaff for healing. The whistle brings existing pets on the current level nearby; it neither creates pets nor retrieves them from other levels. Opening the guide sends no gameplay input. Saved-game labels include mode, and continuing a save uses that saved mode regardless of the creation selector. Same-name Standard and Beginner saves remain distinct.

Modal engine prompts include a **What just happened** panel showing messages emitted since the latest ordinary command wait. It preserves action feedback across intermediate menus and naming prompts, including scrolls, spellbooks and potions. Messages remain in engine order and appear as plain text, with a scrollable panel for long output. A repeated copy of the current question is omitted. The next ordinary command wait clears the prompt context, while the journal retains its history. Direction prompts remain nonmodal. Naming, empty answers and Escape still use the normal engine responses.

Location selection keeps the dungeon visible and shows a white selection cursor separately from the gold hero marker. Click a tile to choose it, or move the cursor using arrow keys (Home/PgUp/End/PgDn for diagonals) and press Enter or Select. Escape or Cancel leaves selection through NetHack. The same controls serve pet naming, examination and other location requests; NetHack decides whether the selected location is valid. Map focus is restored after intermediate dialogs, and arrow bindings honor numeric and telephone keypad modes.

The Experience section shows the hero's level, current total XP, next-level XP threshold and a progress bar measured from the current level's starting threshold. The engine supplies all values, including when its traditional XP field is hidden or the hero is polymorphed. At maximum level the bar is full, with current XP and a Maximum level label. The bar exposes numeric progress and a descriptive value to assistive technology.

The ordinary location subtitle uses already disclosed engine status and regional
materials to describe broad branch context. Quest and plane status names take
precedence over shared artwork. Mines, Vlad's Tower and Gehennom material can
identify those broad branches, but named boss/special-level materials do not
become named location labels. Where existing events cannot distinguish the
branch, including ordinary Dungeons of Doom and Sokoban levels, the subtitle
uses neutral exploration text. Development playtests retain their explicit
Test start label. Map clearing removes the previous material evidence.

Tileset selection invalidates all older image-load callbacks, including after
switching to ASCII. While the selected image loads, the map uses readable glyphs
and the label identifies the pending choice. A current load failure selects
ASCII consistently in the display, picker and stored preference. Stale failures
do not replace a later success or display an error for a discarded choice.

## Native bridge

The host calls `window.receiveNative(event)` with one event, a JSON string or an ordered event array. Interface actions use `window.webkit.messageHandlers.nethack.postMessage(...)`. See `protocol.md` for engine events.

Additional host events:

- `boot`: `version`, `tilesets`, `name`, `hasSave`, `savedGames`, optional `selfTest`.
- `started`: the native process successfully launched.
- `exit`: engine text or native `code`, `hasSave`, `detail`.
- `error`: a human-readable `text`.
- `tilesetImported`: a complete `tileset` including an image data URL and tile dimensions.

Gameplay buttons are enabled only at an engine command prompt. Direct keyboard input remains available at noncommand prompts for directions and acknowledgements. Direction prompts use a compact bar below the map without covering or dimming the dungeon. Arrow keys and compass buttons follow the engine's active keypad bindings, with diagonals, self and vertical directions available. Escape is passed through to NetHack; it cannot undo a spell that the engine has already committed. Other input dialogs block ordinary gameplay and implement line, yes/no, menu and text input separately. Escape routes the correct cancellation response to the engine. Menu rows support click selection, accelerator keys and multiple selections. Atlas launches with NetHack's `force_invmenu` and `menustyle:full`, so item prompts such as Read, Quaff, Wear, Apply, Drop and Dip show named choices immediately, even for a single candidate. The engine supplies the action heading, suitable items, unknown-item descriptions, hands/self alternatives and list-everything option. Quantities use the existing menu count controls. Old saves receive full menu style at the first command prompt; later deliberate option changes remain possible. Recognized hand, hide/spin and all/quantity choices receive semantic labels from the engine. Freeform symbol or letter entry remains a keyboard prompt with explicit instructions. Confirmations retain their existing cancellation behavior.

The Actions picker (⌘K) uses the live engine command catalog and current key bindings. Search matches words in command names, descriptions and shortcuts, with name prefixes listed first. Arrow keys browse results; Enter selects and Escape closes. Opening, filtering and closing spend no turns. Commands that require an engine-supplied parameter remain visible as shortcut references. Selecting an action closes the picker before NetHack asks for an item or direction.

At your fingertips considers known terrain and objects beneath the hero as well as nearby displayed features and creatures. The hero sprite no longer hides stairs from the suggestions. Underfoot actions come first; the first five suggestions are visible, with additional choices in More actions here. Matching fixed shortcuts are hidden to avoid duplicates, and Descend is shown only for known downward stairs or ladders.

Contextual labels describe the opportunity (for example, Drink from fountain) while command names and shortcuts retain their NetHack meanings. Selecting a suggestion enters the normal engine command flow, including item, direction and confirmation prompts. Suggestions describe relevant possibilities, not guaranteed success or safety. They must not reveal hidden terrain, objects, traps, locks, creature dispositions or container contents.

| Context | Actions |
| --- | --- |
| Known stairs or ladder underfoot | Ascend or descend |
| Fountain or sink underfoot | Drink and dip |
| Adjacent sink | Kick |
| Known items underfoot | Pick up and look here |
| Known container underfoot | Loot, tip and appropriate lock/tool actions |
| Known food underfoot | Eat |
| Throne or altar underfoot | Sit, or offer/drop |
| Discovered trap | Examine or attempt to disarm |
| Nearby displayed creature | Inspect and chat; pet naming and known saddled-pet riding |
| Recognized shopkeeper | Pay |
| Nearby door | Open/close, kick, check for traps and use carried lock tools |
| Perceived creature and suitable inventory/spells | Ranged actions |

Engine perception and remembered features drive these hints; the interface never inspects hidden game state. Own inventory and learned spells may refine available choices. See protocol.md for the exact knowledge boundaries and guards.

## Controls

- Arrow keys or `hjkl` move; `yubn` and Home/Page Up/End/Page Down move diagonally.
- Shift plus a direction runs. Native NetHack letter commands, Control-letter commands and Option-letter commands remain available.
- Click an adjacent tile to take one step, including diagonally. During a direction prompt, an adjacent click supplies that direction; clicking your character supplies self. Distant clicks do not start travel.
- Actions or Command-K opens the searchable command picker.
- Hover queries the engine's visible/remembered description without taking a turn.
- Command-S saves and exits. Inventory is `i`; the help button displays common commands.
- Scroll to pan, zoom with the map toolbar and use the target icon to center the adventurer.

Ordinary arrow and diagonal movement follows the engine's advertised direction
bindings, including numeric and telephone keypad modes and swapped letter
layouts. Shift runs using the matching uppercase letter or Meta numeric binding.
Direction prompts and targeting retain their ordinary navigation semantics;
Shift does not introduce running into either prompt.

## Development and verification

Run `node web/input.test.js` and `node web/app.test.js` for focused input rules,
actual renderer-handler movement and deterministic atlas callback ordering.
The latter executes the app with a controlled DOM and image loader; it does not
establish native WebKit rendering or live-engine gameplay acceptance.

Serve the repository root and open `/web/?preview=1` for the deliberately labelled illustrative fixture. It uses real bundled sprites, but is not a playable game and makes no claim to be live engine state. Open `/web/?replay=1` to render the recorded engine events in `.artifacts/game-events.json`, with a visible replay label. This is engine evidence, not live play. Opening `/web/` outside the native app shows onboarding with an instruction to open the application.

The opt-in native `--self-test` launch sets `boot.selfTest`. The interface then starts `AtlasSmoke`, verifies live cell delivery, checks live action filtering and turn-free dismissal, selects inventory through the named-action bridge, moves through the normal arrow-key handler and by clicking a diagonal neighbor, rejects distant click movement, verifies that hover changes neither position nor turn, waits exactly one turn, checks explicit neutral human Wizard creation and the selected male/female sex through the engine’s attributes screen, verifies the nonmodal direction bar and arrow response, dismisses an open-door direction prompt without a turn, rejects an invalid confirmation key without closing the prompt, cancels that prompt, uses the engine catalog’s named Save action for confirmation checks and reloads with the exact saved position and turn. Final native quit exercises the host’s binding-independent Save path and preserves the restored adventure. The smoke test does not assume that literal `S` is bound to Save. Diagnostic messages report each milestone to the native host; the final diagnostic asks it to capture the rendered game and close safely. This path cannot activate during a normal launch.

See [VERIFICATION.md](VERIFICATION.md) for performed test scope and remaining limits.
