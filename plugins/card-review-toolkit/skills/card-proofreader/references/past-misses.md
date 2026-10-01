# Past misses: what to inspect and how

Read this before a review. These examples explain inspection methods, not expected findings. Compare current paired pixels independently before applying an example. Do not assume that a previous error exists in a new image, and do not limit inspection to these words or cards. Confirmed here means observed in the historical pair, not an independently labelled benchmark. User-reported concerns remain unverified until their specific paired features are examined.

## Repeatable glyph inspection

1. Open corresponding native crops with adjacent text visible. Adjust display scale using nearby letter height and account for perspective. Do not compare raw pixel lengths between differently sized images.
2. For each letter/digit, compare its top, middle and bottom: upper hooks/terminals, crossbars, vertical/diagonal stems, counters, loops, lower tails and serifs.
3. Compare ascender/descender lengths relative to the local baseline and nearby letter height. Use more than one nearby glyph when establishing the baseline. For an italic f, inspect both the upper hook and lower extension, not just its recognized identity.
4. Compare weight, slant, width, spacing and baseline against the SAME occurrence in the other image. Neighbours supply scale/context, not the source of truth for font style.
5. Check literal spelling, digits, punctuation and accents separately. Then record the precise observed feature and both crop locations. If native pixels cannot resolve a feature, describe that uncertainty rather than reconstructing the expected glyph.

## Historical examples

| Case and evidence status | What was observed/reported | How to inspect the same failure class |
| --- | --- | --- |
| Piepi 77/130 — confirmed in paired close-ups | Auxiliary code `DPBP#037` became `DPBP#097`, while collector `77/130` matched. | Inventory both footer corners and every auxiliary code. Read each digit independently; compare the middle digit's open curves versus closed loop. Preserve the leading zero. |
| Ns Zorua 189 — confirmed in paired images | `wortkarges` became `vorlarges` in the final description line. | Read the word as an ordered sequence of glyphs. Compare internal strokes and letter count rather than recognizing a plausible sentence. Inspect the full final line, not only its opening words. |
| Psiana V 180/203 — confirmed in paired close-ups | Credit `Illustr. sowsow` became `Illust. sowsow`. | Inspect the final letter immediately before punctuation. Compare each character and the abbreviation's ending; OCR may still identify the illustrator correctly. |
| Loturzel 032/203 — confirmed spacing difference in paired close-ups | `Illustr. Teeziro` became `Illustr.Teeziro`. | Inspect the period-to-T gap relative to nearby character spacing in each image. Separate a lost word gap from global scaling or ordinary kerning. |
| Pixi 3/123 — confirmed visible stroke-shape difference in targeted crops | The glyph after `Nimm` appeared as a plain upright stroke in the original and with an angled top in the enhanced image. | Inspect the glyph's top terminal independently of its OCR value. Record the shape change; do not claim `I → 1` unless the source proves character identity. |
| Pixi 3/123, `Gehör` — user-reported typography concern; not confirmed as a font substitution | The user requested checking the same word across the pair. | Compare G/e/h/ö/r construction, slant and proportions in matched crops. Differences from neighbouring words alone are insufficient; source resolution may leave this unresolved. |
| Porygon2, `aus`, character a — user-reported legibility concern; collector ID unavailable in screenshot | The a was reported as blurred/unclear. | Inspect the a's counter and stem in native pixels. Flag local legibility even if context makes the word guessable. A single screenshot does not prove the enhancement caused it. |
| Sonnkern 85/123, italic f strokes — user-reported length difference; not yet verified in paired native close-ups | The user reported longer f strokes in the original. | Locate each corresponding f occurrence, compare upper hooks and lower extensions relative to local letter height/baseline, and account for scaling. Record only supported differences; keep blur-limited stroke ends unresolved. |

Include unchanged controls when testing: an intentionally different font already present in the original and faithfully reproduced is not an error; a globally enlarged but proportionally matching glyph is not a font change. A reported example is a test lead, not a reason to prefill a finding. Test results on these known examples do not measure blind detection accuracy.
