# Production role and pet sheet

Generated with the built-in image generation tool. Style references are the project's original Lantern concept and direct extracted-subject review. These are not third-party art.

Reference paths:

- `assets/tiles/lantern/production-sources/reference-concept.png`
- A generated contact sheet of the nine extracted reference subjects. Recreate
  it under `.artifacts/` with `prepare_reference_subjects.py`; the source
  sprites and extraction record are retained alongside this prompt.

## Exact generation prompt

```text
Use case: stylized-concept.
Asset: original Lantern production character sprites for NetHack Atlas.
Create ONE square image with EXACTLY 4 equal columns and 4 equal rows, 16 independent full-body sprites. The supplied original Lantern concept and its actual extracted sprite review are the style authority. Match that exact warm lantern-lit, restrained, chunky pixel-art language: readable expressive silhouettes, charcoal outlines, warm cream face highlights, muted earthy clothing, small gold accents, modest coherent details. Match the original adventurer's proportions and detail density. No painterly blur, no smooth vector cartoon, no modern chibi/anime, no oversized heads, no extra texture noise. Pixel artwork designed to survive direct sampling to 64x64 cells, front or side view, never isometric.
Entire image backdrop: perfectly FLAT opaque dark studio green RGB(24,34,33), no scene, no ground, no shadows, no vignette, no gradient. No grid lines, borders, title, labels, letters or numbers. The two reference images are style references only; do NOT recreate their panels, room, floor, framing or typography.
Geometry: each of the sixteen cells occupies exactly one quarter of canvas width and height, no gutters or outside margins. Each full sprite, including every weapon, wingless hat, foot, tail and outline, lies within the central 65% of its cell. Leave at least 17% empty flat background on each side. Absolutely no parts cross a cell boundary. All human characters have comparable body size and a shared baseline within their own cell. Pets are naturally smaller, especially kitten and rat. Make every member of the following list once and preserve EXACT row-major ordering:
Row1:
1 archeologist: original field researcher, brown practical hat, leather satchel, short pick held by side, earth tones, not a film-character likeness.
2 barbarian: muscular rugged warrior, fur shoulder mantle, broad sword held within cell, muted tan and iron.
3 cave dweller: rough dark hair, simple fur tunic, sturdy wooden club; no caricature.
4 healer: kind practical fantasy physician, pale cream robe, green sash, medicine pouch, short staff.
Row2:
1 knight: close stylistic comparison to supplied original adventurer, rounded steel helmet, warm face, lantern in one hand and short straight sword in the other.
2 monk: shaved head, warm ochre and russet robes, wrapped hands, humble martial stance.
3 cleric: cream-and-blue clerical robe, small gold holy medallion, short mace; no invented readable symbols.
4 ranger: forest-green hood, leather boots, compact bow held vertically and quiver.
Row3:
1 rogue: charcoal hooded leather, burgundy sash, short dagger, face visible.
2 samurai: red-brown lamellar armor, simple dark helmet, single compact curved blade, calm stance.
3 tourist: cheerful ordinary traveler, short-brim tan hat, muted patterned shirt, shorts, small camera and satchel.
4 valkyrie: strong woman in restrained steel armor, blond braid, small round shield and spear cropped to fit fully within cell, no huge wings or giant horns.
Row4:
1 wizard: pointed deep-blue hat, matching robe with narrow warm-gold trim, gray beard, small wooden staff with subtle blue gem.
2 kitten: small warm orange-and-cream kitten, alert ears, complete curled tail, side-facing four-legged stance.
3 large dog: sturdy large brown-and-cream domestic dog matching the original dog family, side-facing four-legged stance, complete tail, NOT a wolf or fantasy hound.
4 giant rat: gray-brown four-legged rat with rounded ears, tiny paws and complete curling hairless tail, NOT humanoid.
This is a fresh original atlas for the approved Lantern visual direction. Every cell must be coherent with the supplied approved artwork. Do not borrow from any other game's tiles or assets.
```
