# Seven-step inspection protocol

1. **Cover the whole card in fixed order.** Confirm geometry, then open every manifest region in order, including overlap, both footer corners and regions that appear to contain only artwork. Preserve the region IDs; do not invent a new crop layout.
2. **Read independently.** Read and record all visible print in the original before reading the enhanced counterpart. OCR is a candidate list. Never paste one role's transcription into the other, infer a blurred glyph from the other image, or correct text to a familiar sentence. Preserve case, accents, punctuation, line breaks and numeric formatting.
3. **Inventory the union.** Give each printed occurrence a stable item ID and its location/evidence. Account for lines, isolated words, badges, credits, all numeric fields and symbols. Repeated print requires separate occurrence IDs; overlap of the same occurrence may reuse its ID. Add OCR omissions. An empty transcription means visibly absent print, not an unreadable region. Inspect the expected location on the image where an item is absent.
4. **Compare exactly.** Run the engine's literal character/token and ordered numeric comparisons. Preserve zeros, signs, decimal separators and prefixes. Do not rely on semantic similarity: `wortkarges` versus `vorlarges` and `DPBP#037` versus `DPBP#097` are differences even if the phrase or card identity seems familiar.
5. **Verify all characters against pixels.** Read each word letter by letter and every number digit by digit on both images, even when OCR agrees. Check first/middle/final characters and punctuation explicitly. Open native close-ups for small, clipped, ambiguous or suspect print; inspect both footer codes in close-up every time. If a source remains illegible, record uncertainty instead of guessing. Symbols still need their separate inner/outer-shape inspection.
6. **Reconcile backwards.** Sweep manifest regions in reverse order, from footer to header. On each image compare the visible print to the inventory, adding any omitted occurrence and checking additions/deletions. Record each role's reconciliation independently, including artwork-only regions. Uncertain completeness is unresolved, never verified.
7. **Gate the verdict.** Run `audit_engine.py check`. Missing protocol evidence blocks completion. Unresolved readings or inventory coverage block full fidelity even if literal strings match. Literal discrepancies require pixel review before becoming confirmed findings. A finished audit can report unresolved evidence but cannot say "all clear." Accuracy takes precedence over the two-minute target.

## Ledger additions (v1.3)

Each text item retains `original` and `enhanced` and adds `readings`:

```json
{
  "readings": {
    "original": {"literal": "DPBP#037", "status": "verified", "character_pass": true, "evidence": "Original native footer crop and location; each digit inspected."},
    "enhanced": {"literal": "DPBP#097", "status": "verified", "character_pass": true, "evidence": "Enhanced native footer crop and location; each digit inspected."}
  }
}
```

Populate this only after inspection. Allowed reading statuses: `verified`, `absent`, `unresolved`. `literal` must equal that role's transcription. `absent` requires an empty literal and evidence of the corresponding blank location. For unresolved glyphs, retain a descriptive placeholder and specify the uncertainty in evidence. `character_pass: true` records that the pass was performed, not that every glyph was resolved.

Every region adds `inventory_reconciliation`, with `original` and `enhanced` records containing `status: verified|unresolved`, `item_ids` listing all region item IDs (including symbols and counterparts absent in one role), and role-specific `evidence`. Artwork-only regions use empty lists after visual inspection. IDs represent the paired union, not just OCR detections.

Top-level `reverse_sweep` contains `region_ids` in exactly reversed manifest order and `evidence` describing the reconciliation. Old ledgers need actual new inspection; never backfill flags merely to pass validation. These are auditable declarations, not proof that an AI saw every glyph. Do not promise zero missed errors or call a software unit test an image-recognition benchmark.

## Letter legibility (v1.4)

Every role's text reading also requires `legibility: clear|concern|absent`. Use `absent` only with reading status `absent`. Inspect native pixels before setting clear; equal OCR/literal readings do not establish sharp or distinguishable glyphs. Flag a locally blurred/merged/clipped character even when its identity remains readable. If identity itself is uncertain, reading status must also be unresolved.

For a concern, add a nonempty `legibility_concerns` array. Each entry needs `location` (word plus character position, or crop coordinates), `description` (what is visually obscured), and `evidence` (native crop/coordinates inspected). Example schema, not preverified evidence:

```json
{"legibility":"concern","legibility_concerns":[{"location":"evolution line: aus, character 1 (a)","description":"Local blur makes the inner counter indistinct.","evidence":"Path to the inspected native crop and its coordinates"}]}
```

The checker returns `legibility_flags` and blocks full fidelity for any open concern, even if literal strings match and reading status is verified. Missing legibility inspection blocks completion. Valid concern records allow a completed audit with an explicit needs-review verdict. These are reviewer-declared visual observations; this feature is not an automatic blur detector. Never silently populate clear for older reviews without new inspection.

## Paired typography (v1.5)

Each text item requires a `typography` record with `status: matched|different|unresolved|not_comparable`, `original_evidence`, `enhanced_evidence`, and `description`. Evidence must identify the corresponding native crops/locations. Description states the inspected features or the specific visible change. Review every word and digit in the item; subdivide a line when needed to localize a difference. These fields are per paired item, not a comparison with adjacent words.

Example structure for a visually established change (never prefill without inspection):

```json
{"typography":{"status":"different","original_evidence":"Original native crop: glyph after Nimm","enhanced_evidence":"Enhanced native crop: same glyph","description":"Original appears as a plain vertical stroke; enhanced has an angled top. Character identity is not inferred from this observation."}}
```

A `different` status means a confirmed visual discrepancy, not automatically a different Unicode character or identifiable font family. `unresolved` means the comparison lacks sufficient visual evidence. `not_comparable` is for a verified added/deleted occurrence; explain both locations. The checker exposes these as `typography_flags`; their statuses distinguish differences from concerns. Its full-fidelity gate blocks all three. Matching text or a readable digit must not bypass this pass. These are evidence-record checks, not an automatic font recognizer.

For concrete top/middle/bottom stroke checks and historical confirmed versus user-reported cases, read [past misses](past-misses.md). Apply the method to all current text, including unchanged controls; do not search only for the example words.
