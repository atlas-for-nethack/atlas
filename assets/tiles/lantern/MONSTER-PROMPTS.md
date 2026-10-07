# Lantern monster source prompts

Generated with the built-in image generation tool. Reference: `assets/tiles/lantern/production-sources/reference-concept.png`, an original project concept. Every image is preserved unchanged; normalized cell coordinates are declared in `monster-sources.json`. Source registries pin the retained files; gameplay validation is separate.

## monsters-01

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: kobold shaman [class kobold]: small reptilian shaman with staff | leprechaun [class leprechaun] | small mimic [class mimic]: small amorphous toothed mimic creature | large mimic [class mimic]: larger amorphous toothed mimic creature | giant mimic [class mimic]: huge amorphous toothed mimic creature | wood nymph [class nymph] | water nymph [class nymph] | mountain nymph [class nymph].
Row 2: goblin [class orc] | hobgoblin [class orc] | orc [class orc] | hill orc [class orc] | Mordor orc [class orc] | Uruk-hai [class orc] | orc shaman [class orc] | orc-captain [class orc].
Row 3: rock piercer [class piercer]: hanging pointed stone shell creature | iron piercer [class piercer]: hanging pointed iron shell creature | glass piercer [class piercer]: hanging pointed glass shell creature | rothe [class quadruped]: shaggy small bovine | mumak [class quadruped]: large elephant with long tusks | leocrotta [class quadruped]: hyena-like quadruped | wumpus [class quadruped]: bulky shaggy quadruped | titanothere [class quadruped]: prehistoric rhino.
Row 4: baluchitherium [class quadruped]: tall hornless prehistoric rhino | mastodon [class quadruped] | sewer rat [class rodent] | giant rat [class rodent] | rabid rat [class rodent] | wererat (animal form) [class rodent]: ordinary four-legged rat with long tail, no human torso or clothing | rock mole [class rodent] | woodchuck [class rodent].
Row 5: cave spider [class spider] | centipede [class spider] | giant spider [class spider] | scorpion [class spider] | lurker above [class trapper]: flat hovering manta-like brown monster | trapper [class trapper]: flat brown living rug creature | pony [class unicorn] | white unicorn [class unicorn].
Row 6: gray unicorn [class unicorn] | black unicorn [class unicorn] | horse [class unicorn] | warhorse [class unicorn] | fog cloud [class vortex] | dust vortex [class vortex] | ice vortex [class vortex] | energy vortex [class vortex].
Row 7: steam vortex [class vortex] | fire vortex [class vortex] | baby long worm [class worm]: small tan segmented worm | baby purple worm [class worm] | long worm [class worm]: large tan segmented worm | purple worm [class worm] | grid bug [class xan]: tiny sparking insect | xan [class xan]: green winged insect.
Row 8: yellow light [class light] | black light [class light] | zruty [class zruty]: shaggy upright brown beast | couatl [class angel]: feathered winged serpent | Aleax [class angel]: golden armored divine warrior | Angel [class angel] | ki-rin [class angel]: golden horned horse-dragon | Archon [class angel].
```

## monsters-02

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: bat [class bat] | giant bat [class bat] | raven [class bat] | vampire bat [class bat] | plains centaur [class centaur] | forest centaur [class centaur] | mountain centaur [class centaur] | baby gray dragon [class dragon].
Row 2: baby gold dragon [class dragon] | baby silver dragon [class dragon] | baby shimmering dragon [class dragon] | baby red dragon [class dragon] | baby white dragon [class dragon] | baby orange dragon [class dragon] | baby black dragon [class dragon] | baby blue dragon [class dragon].
Row 3: baby green dragon [class dragon] | baby yellow dragon [class dragon] | gray dragon [class dragon] | gold dragon [class dragon] | silver dragon [class dragon] | shimmering dragon [class dragon] | red dragon [class dragon] | white dragon [class dragon].
Row 4: orange dragon [class dragon] | black dragon [class dragon] | blue dragon [class dragon] | green dragon [class dragon] | yellow dragon [class dragon] | stalker [class elemental]: faint translucent upright airy silhouette | air elemental [class elemental] | fire elemental [class elemental].
Row 5: earth elemental [class elemental] | water elemental [class elemental] | lichen [class fungus] | brown mold [class fungus] | yellow mold [class fungus] | green mold [class fungus] | red mold [class fungus] | shrieker [class fungus].
Row 6: violet fungus [class fungus] | gnome [class gnome] | gnome leader [class gnome] | gnomish wizard [class gnome] | gnome ruler [class gnome] | giant [class giant] | stone giant [class giant] | hill giant [class giant].
Row 7: fire giant [class giant] | frost giant [class giant] | ettin [class giant]: two-headed giant | storm giant [class giant] | titan [class giant] | minotaur [class giant] | jabberwock [class jabberwock]: strange long-necked clawed dragon | vorpal jabberwock [class jabberwock]: larger dangerous long-necked clawed dragon.
Row 8: Keystone Kop [class kop]: old-fashioned slapstick policeman with round helmet | Kop Sergeant [class kop]: old-fashioned policeman sergeant | Kop Lieutenant [class kop]: old-fashioned policeman lieutenant | Kop Kaptain [class kop]: old-fashioned policeman captain | lich [class lich] | demilich [class lich] | master lich [class lich] | arch-lich [class lich].
```

## monsters-03

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: kobold mummy [class mummy] | gnome mummy [class mummy] | orc mummy [class mummy] | dwarf mummy [class mummy] | elf mummy [class mummy] | human mummy [class mummy] | ettin mummy [class mummy]: two-headed mummy | giant mummy [class mummy].
Row 2: red naga hatchling [class naga] | black naga hatchling [class naga] | golden naga hatchling [class naga] | guardian naga hatchling [class naga] | red naga [class naga] | black naga [class naga] | golden naga [class naga] | guardian naga [class naga].
Row 3: ogre [class ogre] | ogre leader [class ogre] | ogre tyrant [class ogre] | gray ooze [class pudding] | brown pudding [class pudding] | green slime [class pudding] | black pudding [class pudding] | quantum mechanic [class quantmech]: scientist with goggles and tiny tool.
Row 4: genetic engineer [class quantmech]: scientist with vial | rust monster [class rustmonst]: four-legged rust-colored insectoid with antennae | disenchanter [class rustmonst]: long-snouted blue quadruped | garter snake [class snake] | snake [class snake] | water moccasin [class snake] | python [class snake] | pit viper [class snake].
Row 5: cobra [class snake] | troll [class troll] | ice troll [class troll] | rock troll [class troll] | water troll [class troll] | Olog-hai [class troll] | umber hulk [class umber]: hulking insect-headed biped | vampire [class vampire].
Row 6: vampire leader [class vampire] | vampire mage [class vampire] | Vlad the Impaler [class vampire] | barrow wight [class wraith] | wraith [class wraith] | Nazgul [class wraith]: black-robed spectral rider-like warrior, no movie likeness | xorn [class xorn]: three-legged rocky creature with three arms and central mouth | monkey [class yeti].
Row 7: ape [class yeti] | owlbear [class yeti]: owl-headed bear | yeti [class yeti] | carnivorous ape [class yeti] | sasquatch [class yeti] | kobold zombie [class zombie] | gnome zombie [class zombie] | orc zombie [class zombie].
Row 8: dwarf zombie [class zombie] | elf zombie [class zombie] | human zombie [class zombie] | ettin zombie [class zombie]: two-headed giant zombie | ghoul [class zombie] | giant zombie [class zombie] | skeleton [class zombie] | straw golem [class golem].
```

## monsters-04

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: paper golem [class golem] | rope golem [class golem] | gold golem [class golem] | leather golem [class golem] | wood golem [class golem] | flesh golem [class golem] | clay golem [class golem] | stone golem [class golem].
Row 2: glass golem [class golem] | iron golem [class golem] | human [class human] | wererat (human form) [class human]: ordinary human in ragged clothes, hint of ratlike face, fully human body | werejackal (human form) [class human]: ordinary human in ragged clothes, hint of sharp jackal-like face, fully human body | werewolf (human form) [class human]: ordinary human in ragged clothes, hint of rugged wolf-like face, fully human body | elf [class human] | Woodland-elf [class human].
Row 3: Green-elf [class human] | Grey-elf [class human] | elf-noble [class human] | elven monarch [class human] | doppelganger [class human]: neutral pale humanoid | shopkeeper [class human] | guard [class human] | prisoner [class human].
Row 4: Oracle [class human]: classical robed oracle | aligned cleric [class human] | high cleric [class human] | soldier [class human] | sergeant [class human] | nurse [class human] | lieutenant [class human] | captain [class human].
Row 5: watchman [class human] | watch captain [class human] | Medusa [class human]: snake-haired woman | Wizard of Yendor [class human]: dark-robed elderly powerful wizard | Croesus [class human]: rich ancient king | Charon [class human]: hooded skeletal boatman with pole | ghost [class ghost] | shade [class ghost].
Row 6: water demon [class demon] | amorous demon [class demon]: clothed alluring horned demon | horned devil [class demon] | erinys [class demon]: winged armored fury | barbed devil [class demon] | marilith [class demon]: six-armed snake-tailed warrior | vrock [class demon]: vulture-headed winged demon | hezrou [class demon]: large toad demon.
Row 7: bone devil [class demon]: bony scorpion-tailed devil | ice devil [class demon]: icy insectoid devil | nalfeshnee [class demon]: winged boar demon | pit fiend [class demon] | sandestin [class demon]: gray shape-changing demon | balrog [class demon]: fiery horned winged demon, original design | Juiblex [class demon]: formless green slime demon | Yeenoghu [class demon]: hyena demon with flail.
Row 8: Orcus [class demon]: goat-headed winged demon with skull staff | Geryon [class demon]: three-headed winged serpent demon | Dispater [class demon]: elegant horned devil with staff | Baalzebub [class demon]: insect-winged fly demon | Asmodeus [class demon]: regal red horned devil | Demogorgon [class demon]: two-headed tentacled demon | Death [class demon]: hooded skeleton with scythe | Pestilence [class demon]: sickly plague rider with staff.
```

## monsters-05

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: Famine [class demon]: gaunt skeletal famine rider | mail daemon [class demon]: small winged messenger demon with envelope | djinni [class demon] | jellyfish [class eel] | piranha [class eel] | shark [class eel] | giant eel [class eel] | electric eel [class eel].
Row 2: kraken [class eel] | newt [class lizard] | gecko [class lizard] | iguana [class lizard] | baby crocodile [class lizard] | lizard [class lizard] | chameleon [class lizard] | crocodile [class lizard].
Row 3: salamander [class lizard]: fiery snake-tailed spear warrior | long worm tail [class worm_tail]: tan segmented worm tail only | archeologist [class human]: original fantasy archeologist with satchel and pick, no film likeness | barbarian [class human] | cave dweller [class human] | healer [class human] | knight [class human] | monk [class human].
Row 4: cleric [class human] | ranger [class human] | rogue [class human] | samurai [class human] | tourist [class human] | valkyrie [class human] | wizard [class human] | Lord Carnarvon [class human]: elderly explorer scholar.
Row 5: Pelias [class human]: regal elderly wizard | Shaman Karnov [class human]: tribal shaman | Earendil [class human]: noble elven warrior | Elwing [class human]: elven noblewoman | Hippocrates [class human]: ancient Greek healer | King Arthur [class human]: crowned medieval knight | Grand Master [class human]: elder monk | Arch Priest [class human]: grand robed priest.
Row 6: Orion [class human]: hooded forest hunter | Master of Thieves [class human]: elegant master thief | Lord Sato [class human]: noble samurai | Twoflower [class human]: cheerful bespectacled tourist with camera | Norn [class human]: elderly female seer | Neferet the Green [class human]: green-robed Egyptian-inspired sorceress | Minion of Huhetotl [class demon]: fiery ancient demon | Thoth Amon [class human]: dark ancient sorcerer.
Row 7: Chromatic Dragon [class dragon]: multicolored dragon | Goblin King [class orc]: crowned green goblin | Cyclops [class giant]: single-eyed giant | Ixoth [class dragon]: large red dragon | Master Kaen [class human]: powerful dark-robed monk | Nalzok [class demon]: red demon lord | Scorpius [class spider]: giant scorpion | Master Assassin [class human].
Row 8: Ashikaga Takauji [class human]: ornate samurai warlord | Lord Surtur [class giant]: huge fiery crowned giant | Dark One [class human]: dark purple hooded wizard | student [class human] | chieftain [class human] | neanderthal [class human] | High-elf [class human]: elegant elven knight | attendant [class human].
```

## monsters-00 regeneration before focused edit

```text
Use case: stylized-concept.
Asset type: original Lantern NetHack Atlas game monster sprite source atlas.
Primary request: Generate a square raster sprite sheet of EXACTLY 8 columns by 8 rows, 64 evenly sized square cells, using the supplied original Lantern concept ONLY as a style reference. No artwork from any existing third-party tileset. Target 1024x1024; any returned square resolution must preserve the exact normalized 8x8 grid.
Style: clear coarse pixel-art equivalent to 32x32 sprites enlarged with crisp square pixels; front or side view, never isometric. Match warm lantern highlights, dark charcoal outlines, muted jewel colors and readable silhouettes of the reference. Full body in each cell, centered, with generous minimum 12 percent empty padding on every side, all limbs and weapons inside its cell. Larger monsters remain fully inside their own cell. Eyes are only small pixel highlights.
Backdrop: uniform solid dark desaturated green #182221, no ground plane, no cast shadows, no texture, no gradient. No visible cell boundaries, no text, no labels, no numbers, no decorative frame, no title, no logo, no extra items. Cell edges occupy exact eighths of canvas with zero outer margin. One creature per cell only. Empty cells are blank background. Character names specify game identities, not existing film or game character likenesses; invent original designs.
Cell contents listed below in exact row-major order. Each row has exactly eight cells. Preserve ordering and class-specific anatomy. Do not merge or skip any cell.

Row 1: giant ant [class ant] | killer bee [class ant] | soldier ant [class ant] | fire ant [class ant] | giant beetle [class ant] | queen bee [class ant] | acid blob [class blob] | quivering blob [class blob].
Row 2: gelatinous cube [class blob] | chickatrice [class cockatrice] | cockatrice [class cockatrice] | pyrolisk [class cockatrice]: fiery cockatrice bird, two bird legs, wings, beak; NOT a dog | jackal [class dog] | fox [class dog] | coyote [class dog] | werejackal (animal form) [class dog]: ordinary quadruped jackal, four paws, no clothing, no human torso.
Row 3: little dog [class dog] | dingo [class dog] | dog [class dog] | large dog [class dog] | wolf [class dog] | werewolf (animal form) [class dog]: ordinary quadruped wolf, four paws, no clothing, no human torso | winter wolf cub [class dog] | warg [class dog].
Row 4: winter wolf [class dog] | hell hound pup [class dog] | hell hound [class dog] | Cerberus [class dog] | gas spore [class eye] | floating eye [class eye] | freezing sphere [class eye] | flaming sphere [class eye].
Row 5: shocking sphere [class eye] | beholder [class eye] | kitten [class feline] | housecat [class feline] | jaguar [class feline] | lynx [class feline] | panther [class feline] | large cat [class feline].
Row 6: tiger [class feline] | displacer beast [class feline] | gremlin [class gremlin] | gargoyle [class gremlin]: unwinged crouching stone gargoyle | winged gargoyle [class gremlin]: winged stone gargoyle | hobbit [class humanoid] | dwarf [class humanoid] | bugbear [class humanoid].
Row 7: dwarf leader [class humanoid] | dwarf ruler [class humanoid] | mind flayer [class humanoid] | master mind flayer [class humanoid] | manes [class imp]: small pale potbellied demon, NOT lion | homunculus [class imp] | imp [class imp] | lemure [class imp].
Row 8: quasit [class imp] | tengu [class imp] | blue jelly [class jelly] | spotted jelly [class jelly] | ochre jelly [class jelly] | kobold [class kobold] | large kobold [class kobold] | kobold leader [class kobold].
CRITICAL final framing instruction: The first generated attempt packed sprites too tightly and clipped outer fire and wings. For this version every entire sprite including its outline, glow, wings and weapon MUST occupy only the central 60% of each individual cell. Leave the surrounding 20% on ALL FOUR sides purely blank flat #182221. There must be visible empty background between all neighbors and between outer sprites and canvas edges. Row6 cell4 gargoyle has NO WINGS AT ALL. Row6 cell5 winged gargoyle has wings. Do not output transparency; fill the entire canvas background solid #182221.
```

## monsters-00 final focused edit

Reference image for this edit was the regenerated sheet, preserved as a generation intermediate outside the workspace. The committed result contains this edit.

```text
Use case: precise-object-edit. Edit the supplied original Lantern monster sprite sheet. Preserve the entire exact 8x8 grid, every other sprite, flat dark green #182221 background, square dimensions and padding. Change ONLY the third and fourth cells of the eighth (bottom) row. These are blue jelly and spotted jelly land-dwelling amorphous blobs, NOT aquatic jellyfish. Replace their mushroom-like jellyfish caps and tentacles with low smooth rounded gelatinous blob silhouettes resting flat at their cell bottoms, matching the ochre jelly blob in bottom row cell5. Cell3 is translucent blue slime blob; cell4 is purple-blue slime blob with pink spots. No legs or tentacles or caps on either. Keep both entirely centered within their existing own cells. No other changes. No transparency.
```

## monsters-06 final 4 by 4 sheet

```text
Use case: stylized-concept. Generate an original Lantern pixel-art game sprite atlas matching the supplied original concept reference. Square canvas with EXACTLY4columns and4rows of equal square cells,16cells total; cell edges lie at exact quarters of the image, zero outer margin. Background uniformly flat opaque dark green #182221, no labels or text or visible grid lines or title. Each sprite is entirely centered within its own cell with at least20%empty background padding on all four sides. Crisp coarse32pixelgame-sprite look, charcoal outlines, muted warm lantern highlights, front or side view, not isometric. Full bodies including all weapons. Exact row-major contents: Row1: page (young medieval assistant holdingbook andlantern); abbot (eldermonk withstaff); acolyte (junior robedcleric); hunter (green hood, bow). Row2: thug (ragged outlaw withknife); ninja (blackclothes, short sword); roshi (elder martialarts teacher withstaff); guide (explorer withhat andwalkingstick). Row3: warrior (armored knight withsword andlantern); apprentice (young purplehatted wizard withstaff); small pale dotted question-mark-like outline marker only, no creature (invisible monster uncertainty symbol); BLANKBACKGROUND. Row4: BLANKBACKGROUND; BLANKBACKGROUND; BLANKBACKGROUND; BLANKBACKGROUND. Important geometry: the three occupied rows must each occupy exactly ONEQUARTER of image height; fourth row is completely blank. No transparency. Only the supplied original concept as style reference; do not copy thirdpartytiles or filmcharacters.
```
