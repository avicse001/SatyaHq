---
name: card-text-repair
description: Repair specified letters, diacritics, punctuation, or digits in raster card images using Python while preserving nearby colors, texture, and unrelated pixels. Use for localized text corrections, especially AI-enhancement errors with an original reference. Not for proofreading-only requests or general image generation.
---

# Card Text Repair

Make small, reviewable raster edits with Python (Pillow, NumPy, and OpenCV when needed). This workflow is for pixel-local corrections, not regenerating a card. Preserve the latest accepted edits, original dimensions, and all pixels outside the explicitly defined repair masks. A user can override the Python workflow explicitly.

Every text repair includes restoring its immediate surroundings by default. Treat mismatched background color, rectangular patches, halos, seams, and disrupted texture caused by the repair as unfinished work. Blend the repaired area into the surrounding card while preserving neighboring text and artwork; the user does not need to request this separately. Include the necessary local background and feathering in the repair mask, keeping its bounds limited to the affected area.

Alignment with neighboring text is also part of every repair by default. Match the repaired glyphs or words to the local baseline, x-height/capital height, slant, and word spacing using unchanged words on the same line and the original reference. Judge the baseline from comparable letters, not the top of accents or the bottom of descenders. If a repaired phrase sits higher or lower than the rest of its line, correct that offset locally and restore the vacated background. Preserve intentional source layout and leave unrelated text in place; do not resize or reposition a whole line to hide a local mismatch. Recheck alignment at native scale and enlarged scale before delivery.

## Establish the edit

- Identify the enhanced/edit target, original reference, and latest accepted output. Continue from the latest accepted output; do not lose earlier fixes.
- Inspect the actual images before deciding what is wrong. A supposed missing umlaut may have become a slanted accent, and removing punctuation also requires removing its outline.
- Crop the affected word and enough surrounding background to understand the letter baseline, white outline, and foil pattern. View an enlarged crop and the native-scale result; nearest-neighbor enlargement helps locate individual pixels, while smooth enlargement helps assess appearance.
- Correct only the requested, visually confirmed text. Do not silently audit or rewrite other words. For ambiguous spelling, use the original rather than inventing a correction.
- Keep source files untouched. Use work/ for scripts, crops, masks, and intermediate alignment. Save successive deliverables as lossless PNGs in the task's output directory.

## Choose a local repair

Prefer reusing actual image evidence over rendering a replacement word.

### Font fidelity across the affected passage

Before editing, compare the original and enhanced lettering at comparable local text height. Inspect the full affected sentence or paragraph, including every line, rather than checking only the corrected word. Existing enhanced lettering is not automatically a trustworthy font donor: verify it against the original first. Compare distinctive glyph construction (serifs, terminals, counters, and letter proportions), stroke weight/contrast, italic slant, x-height/capital height, width, kerning, word spacing, and line spacing. Account for source blur and perspective; do not diagnose a different font from sharpness or apparent weight alone.

Reuse verified matching glyphs or a clean, aligned source-text patch when source resolution supports it. If rendering is necessary, inspect candidate lettering alongside the source and unchanged neighboring words before using it. A font with the same general category, such as bold serif italic, is not enough to establish a match. Never claim an exact font identification from a vague visual resemblance, and never silently substitute an approximate font or distort individual letters to force a fit.

For font replacement, build a comparison of plausible font families and their actual weights/styles using the complete affected phrase. Compare at the intended final pixel size and at a common baseline/x-height; enlargement is a secondary check. Use distinctive glyphs and punctuation to distinguish candidates, then check overall word widths, spacing, stroke contrast, and rendering sharpness. Separate a wrong typeface from a wrong weight, size, tracking, or antialiasing choice. Do not choose a font solely because it is installed or because a general guide associates it with that card era; verify the specific language, card region, and visible source. If the needed font is missing and downloading is authorized, seek the identified font from its foundry or a legitimate distributor, and report any actual access or licensing blocker.

Do not upscale blurred source lettering as a shortcut for identifying a font when it would leave the repaired phrase visibly softer than its neighbors. Source-pixel transfer is suitable only when its resolution and rendering quality support the target. Reusing authentic but visibly degraded letter shapes is not a successful font repair. Before delivering a replacement passage, compare it with both the source and neighboring text at native size; reject mismatched sharpness, weight, proportions, or spacing even if spelling and pixel-locality checks pass. Preserve a rejected attempt as a separate draft if useful, but resume subsequent edits from the last accepted version, never from the rejected draft.

If a user flags the font of a whole sentence, treat the full sentence across all its lines as the correction scope; a one-word fix does not resolve it. Keep its typography consistent and preserve its exact content. If the available source cannot support a confident match, explain the limitation and request a sharper source or verified font information; label any proposed approximation explicitly and obtain the user's acceptance before applying it. Preserve the latest accepted card while that question is unresolved.

**Missing letter or diacritic:** Look for an existing glyph in the same image with the same font, weight, size, and slant. Extract its ink and outline with an antialiased mask that excludes neighboring letters and background. Position it using baseline, x-height, spacing, and the reference. If no suitable glyph exists, trace or render only the missing mark. Do not describe a font identification as exact without evidence; a similar family is not a verified font file. Avoid making new dots sharper, squarer, darker, or more uniform than the source.

**Unwanted punctuation or dots:** Mask the ink and its complete pale/dark halo while protecting adjacent letters. Restore the background; painting a flat white patch over foil produces a visible smudge. Do not stretch or move the remaining word to close the gap unless requested.

**Background restoration preference:**

1. Use the corresponding unobstructed patch in the original reference when available. Align a working copy to the target, then transfer only the needed patch.
2. Otherwise clone nearby texture with compatible hue, brightness, pattern scale, and direction. Inspect the donor for stray text and symbols.
3. Use local inpainting when the area is small and the texture is simple. Inspect carefully for pale smears caused by neighboring text outlines. If it smears, replace the approach with a better donor patch instead of enlarging the blur.

For differently framed/resized references, feature matching (such as SIFT with ratio filtering and RANSAC) can estimate alignment. Prefer matches near the affected text. Visually verify local registration: many inliers do not guarantee the individual word aligns. Never warp or recolor the full edit target. If registration is poor, refine locally or use a different donor.

Keep feathering confined to the repair boundary. Count every feathered pixel as part of the mask. Maintain the background's local color and texture; color-adjust only a donor patch if needed. Never change the entire image to make a patch match.

## Verify before delivery

- Compare decoded pixel arrays against the latest accepted input. Dimensions must match. Pixels outside the allowed masks must be identical, including alpha if present. For a JPEG source, this compares decoded pixels, not compressed file bytes.
- Save the actual mask, including feathering, so the changed area can be checked. The union of masks covers all requested edits in a batch; never use a full-image mask to conceal unrelated changes.
- Run the helper with Python, Pillow, and NumPy installed:

```text
python scripts/verify_local_edit.py BEFORE AFTER --mask ALLOWED_MASK
```

Any nonzero mask pixel authorizes a change at that location. The helper reports bounds, changed pixel count, and outside-mask changes, and fails if unrelated pixels or dimensions changed. It verifies locality, not aesthetic quality or spelling.

- Inspect the saved output at full card scale and enlarged word scale. Check exact spelling and punctuation, baseline, spacing, mark shape, stroke/outline weight, texture continuity, and retention of earlier edits. A numerical pass does not make a visible patch acceptable.
- Recompare the full affected passage with the original after repair. Verify that donor or rendered letters fit the passage's font and that no word or line has acquired a different weight, slant, scale, spacing, or baseline. Record unresolved font fidelity honestly rather than describing an approximate match as exact.
- Inspect beyond the repaired glyphs: compare hue, brightness, grain/foil direction, and all patch boundaries with the neighboring background. For a repaired sentence or paragraph, check the surroundings of every affected line through the final word. Look for rectangular color bands, outlines, smudges, and accidental underlines. Inspect donor texture for rules, text, and symbols before cloning; none may leak into the repair. Revise visible repair artifacts before delivery, expanding the local mask only as needed and repeating the outside-mask verification.
- If a patch fails visually, revise from the last clean accepted input rather than stacking repairs over artifacts. If source detail cannot support an exact reconstruction, state that limitation without claiming pixel-perfect accuracy.
- Deliver a direct link to the new image, briefly name the correction, and mention retained prior fixes when relevant. Do not claim unchanged pixels unless comparison verified it.

## Examples of scope

- Restore the two dots in an umlaut without replacing the word.
- Remove a spurious comma and restore foil behind its ink and outline.
- Append a missing s using another matching s already printed on the card.
- Remove an erroneous umlaut from Kosten while keeping the correct umlaut elsewhere.

Coordinates, donor choices, and font estimates from an earlier card are not reusable constants. Reinspect each image.

## Symbol repairs

For approved printed symbol replacements, use `card-symbol-repair` when available. Pass the original reference, latest accepted output, collector card ID, and approved symbol locations. Its icon library does not establish spelling or font fidelity. Keep text and symbol masks separate, preserve accepted changes between steps, and verify the final output against their bounded union. If unavailable, report that limitation instead of inventing an icon.

## Shared audit evidence

When repair follows an audit, reuse its engine manifest and approved finding evidence. Verify the original and latest target hashes; use each finding's native source coordinates, not the rectified sheet coordinates. Do not rerun a whole-card audit to fix an approved item. If an accepted repair changed the target hash, preserve that version and recheck only the relevant donor and repair areas; earlier geometry is a navigation aid, not current pixel evidence. The audit engine is bundled with the companion card-proofreader skill.
