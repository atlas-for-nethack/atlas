# Six monster crop repairs

Generated with the built-in image generation tool. Reference images are original project artwork: `assets/tiles/lantern/production-sources/reference-concept.png` and the generated role/pet contact sheet. Recreate the contact sheet under `.artifacts/` with `prepare_roles.py`; `roles-pets-sheet.png` is retained unchanged.

## Exact prompt

```text
Use case: stylized-concept.
Asset: six original Lantern NetHack Atlas monster sprites repairing a prior source sheet's crop overlap.
Generate ONE landscape raster image, target1536x1024, EXACTLY3 equal columns and2 equal rows. Six independent full-body sprites, no other art. Grid edges at exact thirds of width and halves of height; no gutters, borders, labels or text. Each sprite including its horn, tail, segmented body, wings and antennae must lie entirely within the central65% of its own cell, with generous blank padding on every side. Absolutely no crossing cell edges or clipping.
The supplied original Lantern concept and production role/pet review establish the visual style: chunky clear pixel-art silhouettes, charcoal outlines, restrained earthy/jewel colors, warm cream highlights, coherent detail designed for64x64 gameplay cells. Match the approved original dog and the new production pets' proportions and pixel language. No isometric view, no painted smoothness, no soft vector art, no modern cartoon, no excessive fine texture.
Backdrop is flat opaque dark green RGB(24,34,33) across the whole canvas. No floor, no cast shadow, no room, no framing, no gradient, no vignette, no transparency. Never copy the reference review's floor or labels; reference images provide style only.
Exact row-major contents:
Row1 column1: BLACK UNICORN. Elegant horse-shaped quadruped, charcoal-black coat with subtle cool slate highlights, a single clearly visible pale horn on its forehead, four horse legs, complete mane and flowing tail. Side view facing right, calm readable pose. Not a pegasus, no wings. Keep horn and tail comfortably inside cell.
Row1 column2: BABY LONG WORM. Small tan earthworm-like segmented worm, short gently curved body, simple tiny round mouth at one end, no eyes or legs or antennae. Naturally small relative to the adult worms. Entire body and tail visible.
Row1 column3: BABY PURPLE WORM. Small lavender-purple segmented worm with tiny open round mouth, short gently curved body. No legs, no tentacles. Naturally small relative to adult purple worm. Entire body and tail visible.
Row2 column1: LONG WORM. Large tan-beige segmented worm, entire long body curled into a compact S-like curve that fits the cell, modest round dark mouth at lifted head, no eyes, no legs or antennae. Give substantial body thickness and clear segmentation. No missing tail or cut-off body.
Row2 column2: PURPLE WORM. Large purple segmented worm with raised front showing a round toothed mouth, the complete rear body curled around below it in one coherent compact shape. No legs or tentacles. Larger and more threatening than the small purple baby above. Keep whole tail visible.
Row2 column3: XAN. Small green flying blood-feeding insect, a long narrow proboscis pointing forward, six tiny legs, two clear pale wings and slim segmented abdomen. Side/three-quarter view, coherent readable insect silhouette. Distinct from an ant or bee. Complete wings and antennae inside cell.
No surrounding objects or decorative marks. Preserve all six exact placements and anatomy. This is original artwork for our project, not a reproduction of an existing game's tiles.
```
