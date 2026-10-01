# Full text extraction and numeric reconciliation

After preparing and visually confirming geometry, run:

```sh
python scripts/text_inventory.py MANIFEST --output PREPARATION_FOLDER/ocr.json --language de
```

Install `requirements-ocr.txt` once if necessary. RapidOCR runs locally with a multilingual recognition model (choose the card language, e.g. `de` for German); its initial run may download model weights. It does not upload card images. Record installation/model errors honestly. If OCR cannot run, use independent visual transcription of both images and explicitly record `mode: visual` and `ocr_unavailable_reason`; do not claim machine OCR ran. The same literal comparison and numeric gate still apply. No API key is required.

OCR runs independently on each aligned full card and an enlarged footer. It saves literal candidate text, confidence, aligned polygons, input hashes and timing. These are candidate readings, never findings or completed inspection. Duplicate full/footer detections remain in the evidence and may map to the same reviewed item. Low confidence, empty detections and disagreement are reasons to inspect pixels. High confidence is not permission to skip verification. OCR can miss German accents and tiny foil-obscured codes. Use source-space native crops for evidence and corrections.

Inventory the union of printed text in both images into the existing `review.json` region items. Use stable item IDs and independently transcribed `original`/`enhanced` strings; an empty string means visually confirmed absence, not unreadability. Preserve all visible characters, punctuation, signs, leading zeros, spaces and line breaks. Keep unresolved readings accompanied by unresolved checks. Do not normalize words, parse numbers as floats, sort numbers, or deduplicate repeated printed occurrences. For text crossing grid boundaries, transcribe the complete line once and reference the same identical item from overlapping regions. Visually add text that OCR failed to detect, including text inside badges and both footer corners.

Add top-level extraction evidence:

```json
{
  "text_extraction": {
    "mode": "rapidocr",
    "file": "ocr.json",
    "sha256": "HASH_RETURNED_BY_EXTRACTION",
    "visual_sweep_complete": true,
    "evidence": "Describe the sheets/crops actually inspected for omissions.",
    "resolutions": {
      "original:full:0": {
        "disposition": "mapped", "item_ids": ["title"],
        "evidence": "Describe how this candidate was verified/corrected against native pixels."
      }
    }
  }
}
```

Each candidate requires a resolution: `mapped` to existing text item IDs or `not_printed_text` with visual evidence (e.g. detected artwork). Never reject an unreadable real inscription as artwork. Every numeric item also requires `numeric_review: checked|different|unresolved` and `numeric_evidence` identifying the paired native crops inspected digit by digit. Text comparisons are computed by the checker independently of manually entered checked labels; a literal difference cannot silently become a match.

Add top-level `numeric_fields` entries for all seven categories:

- `collector_number`: full collector ID, independently matching each identity reading.
- `other_footer_codes`: all additional codes, such as DPBP, at either corner.
- `copyright_year`: every printed copyright year.
- `hp_level`: HP and level occurrences.
- `species_measurements`: species/dex number, height and weight.
- `attack_numbers`: damage and every number in rule/attack text, including repeats.
- `weakness_resistance`: numeric modifiers in both areas.

Each category needs `item_ids: [...]` and `evidence`. If absent in both images, use `absent_in_both: true` with evidence of the inspected area. Do not mark absent merely because OCR found nothing. Cards with an illegible code still need an unresolved inventory item. Symbols/energy counts retain their separate visual inspection requirements.

Run `audit_engine.py check MANIFEST REVIEW`. It returns exact character/token edits, ordered numeric strings and coverage issues. Literal differences may include line wrapping or uncertainty; reopen pixels and decide what is an actual content error before reporting. The checker prevents missing declared categories and unreconciled OCR detections from passing, but cannot prove a human/AI inventory captured every visible glyph. A complete ledger is not a guarantee of flawless recognition.
