# Focused regression cases

Use these cases when maintaining the skill. Compare visible source evidence before consulting an expected result; text-only exercises test comparison logic, not visual recognition. Never carry a finding from these examples into another card's audit.

| Original | Enhanced | Required outcome |
| --- | --- | --- |
| `Illus. Yuka Morii` | `illus. Yuka Morii` | Credit character 1 changes `I -> i`; `Ullll-` versus `lllll-`. Spelling equivalence must not suppress the finding. |
| `LEDYBA` | `Ledyba` | Positions 2–6 change uppercase to lowercase. |
| `Pokémon` | `PokéMon` | Internal character 5 changes `m -> M`; checking initials alone fails. |
| `Illus.` | `Illus.` in a heavier italic font | No confirmed content change from weight or slant alone. |
| `zusätzlich` | `zusátzlich` | `ä -> á`: two dots versus one acute stroke; an unchanged case pattern does not clear the accent check. |
| `10×` | `10x` | Different printed multiplication/letter marks; unchanged digits do not clear the symbol check. |
| Credit first glyph unreadable | Clearly printed `illus.` | Case unresolved; do not infer original `I` from expected wording. |
| Any region with case `not checked` | Other checks complete | Audit incomplete; do the missing check before a completed verdict. |
| All crops saved, one credit crop unopened | Other items compared | Audit incomplete; a saved crop is not evidence of inspection. |
| Three repeated energy icons | Only the first icon inspected | Audit incomplete; each occurrence needs paired-region or native detail inspection. |
| Original has no footer dot | Enhanced has an extra footer dot | Inventory the enhanced-only mark and compare its expected original location. |
| A line spans several regions or detail tiles | A punctuation mark falls between crops | Coverage incomplete; overlapping crops must cover that mark and surrounding spaces. |
| Card name `Ledyba`, species `NR. 165`, collector number `71/123` | Collector number `71/123` | Label the findings and annotated output `Ledyba — card 71/123`; do not use `165` as the card ID. |
| Collector number `071/123` | Collector number `071/123` | Preserve the leading zero and full identifier in the report, including a no-errors verdict. |
| Collector number `71/123` | Collector number `71/128` | Use original ID `71/123` to label the audit; report the verified enhanced-number discrepancy explicitly. |
| Collector number unreadable | Collector number `71/123` | Label original card ID unresolved and enhanced reading `71/123`; do not claim the original ID was verified. |

The user-supplied Ledyba pair on 2026-09-24 supports the first case: the photographed original's credit begins with undotted capital `I`; the enhanced credit begins with dotted lowercase `i`. These historical observations do not establish that the rest of either card matches. Retest against available raw images, never a remembered transcription alone.

## Engine regressions

- Identical files/configuration/runtime: crop hashes match across cold runs; second preparation reuses the verified cache.
- A changed pixel, geometry, template, engine or runtime: new cache key and blank coverage.
- A modified cached image: preparation rejects the cache.
- Missing review, unchecked marks, or unconfirmed geometry: completion fails.
- Different case with an empty findings list: full fidelity cannot be established.
- Every supported template covers all normalized pixels; region overlaps prevent seam omissions.
- Native crops equal corresponding EXIF-oriented source pixel arrays.
- An inner artwork contour misses border copyright: reject the outline and lock corrected geometry.

On the available Zorua 189 fixture, manual inspection of the new grid retains the credit case discrepancy, `wortkarges` versus `vorlarges`, and distorted promo lettering. This is a preparation/visibility regression, not an independent blind accuracy evaluation.

## Numeric inventory regression

- Piepi collector `77/130` matches, but auxiliary bottom-left `DPBP#037` becomes `DPBP#097`: report the auxiliary code change, not a collector error.
- A numeric category or digit-review evidence is missing: incomplete, even when every region is marked opened.
- A reviewer marks text checked despite unequal literal transcriptions: computed difference still prevents full fidelity.
- `035` versus `35`, `20+` versus `20`, and repeated `20` occurrences remain distinct.
- An OCR candidate is omitted from reconciliation, or its evidence hash changes: incomplete.
- Real OCR on the supplied Piepi pair extracted both code readings in its full and footer passes. Unit tests separately exercise comparator logic; neither is a broad blind accuracy benchmark.
