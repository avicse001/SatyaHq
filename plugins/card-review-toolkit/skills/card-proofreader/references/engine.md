# Shared audit engine

Run commands from this skill's directory, or use an absolute path to its script. Dependencies: Python, Pillow, NumPy, OpenCV. The engine prepares evidence; it does not identify mistakes or run a vision model/OCR service.

```sh
python scripts/audit_engine.py prepare ORIGINAL ENHANCED --cache WORK/audit-cache
```

Default to `grid-v1` for every new pair. It uses a fixed 2-column, 5-row overlapping grid and covers the entire card. Use `--template standard-v1` or `--template full-art-v1` only when the user selected that layout or an existing pair manifest already locked it. These templates also cover the entire card, with narrower footer bands. Do not choose a different template merely to make a new chat's crops look better.

The result gives an absolute manifest path, preparation time, and cache status. Open `geometry.png`, then the ordered `sheet-*.png` files. Rectified sheets are navigation and first-pass comparison views, not original pixels. The native crops contain unchanged EXIF-oriented pixels with coordinates and polygons for both files.

## Geometry lock

Automatic outlines are proposals, never confidence-certified detections. Check all four corners against both full images. If an outline cuts into the card or includes substantial margins, supply corrected corners:

```json
{
  "original": [[240, 90], [1040, 85], [1035, 1195], [235, 1185]],
  "enhanced": [[0, 0], [1061, 0], [1061, 1481], [0, 1481]]
}
```

These numbers illustrate syntax only, never reusable coordinates. Coordinates refer to EXIF-oriented images, clockwise TL, TR, BR, BL. Save the geometry JSON in the task's work directory and rerun with `--geometry PATH`. A new key resets review coverage. If geometry cannot be aligned reliably, keep the audit incomplete and use the source images to resolve it; never clear regions on mismatched crops.

The cache key includes both file hashes, script hash/version, template, geometry, and imaging-library versions. Same inputs/configuration/runtime produce identical crops. Arbitrary chat sessions can only reuse a cache when its files are accessible; share the preparation folder or run with the same locked geometry. Different models may still judge ambiguous details differently. Cache hits verify every prepared artifact hash and preserve the review file; corruption fails closed instead of reusing stale judgments.

## Inspect and record in one batch

Edit `review.json` after visual inspection; preparation never fills checked statuses. Use `geometry_confirmed: true` only after opening the outline preview. Set independent identity readings for both images, each with `card_id` and `evidence`; use literal `unresolved` for an unreadable collector ID. Include card name if readable.

Each region entry needs `opened: true`, an evidence note, and an inventory of all its printed items. Overlap duplicates can reference the same inspected item ID and evidence; do not double-count findings. A region without printed content uses `no_printed_content: true` and an evidence note. Artwork-only status requires actual inspection, not a template assumption.

Example of one inspected text item (not a prefilled finding):

```json
{
  "opened": true,
  "evidence": "Viewed sheet and native close-up; inventoried the credit.",
  "items": [{
    "id": "credit", "kind": "text",
    "original": "Illus.", "enhanced": "illus.",
    "original_case": "Ullll-", "enhanced_case": "lllll-",
    "evidence": "Source initial undotted full-height I; target dotted i.",
    "checks": {
      "characters": "checked", "case": "different", "marks": "checked",
      "punctuation_spacing": "checked", "symbols": "not applicable"
    }
  }]
}
```

Valid check values: `checked`, `different`, `unresolved`, `not applicable`. Explain unresolved/not-applicable checks in evidence. Symbol items use `kind: symbol` and describe inner and outer shapes. Every occurrence needs its own item ID. Record each confirmed finding once in top-level `findings`, with item ID, both source coordinates, exact difference and evidence; uncertain candidates stay separate from confirmed findings.

```sh
python scripts/audit_engine.py detail MANIFEST r05c1
python scripts/audit_engine.py check MANIFEST REVIEW
```

`detail` creates fixed overlapping 3x nearest-neighbor tiles from both native crops. Use it only for regions whose symbols/words are too small, clipped across boundaries, ambiguous, or suspected to differ. Open relevant generated tiles; file creation is not inspection. Native crops and original coordinates are the evidence for findings and repair handoffs. Do not use rectified coordinates directly on the enhanced source.

`check` checks source/artifact hashes, geometry confirmation, independent IDs, and per-region/item coverage. Nonzero exit means incomplete bookkeeping. It cannot know whether a reviewer overlooked an item, falsely claimed inspection, or misread a letter. An audit with unresolved details may be complete but cannot claim full fidelity.

## Text and numeric completion gate

Follow [text inventory](text-inventory.md) after preparation. Full-card and enlarged-footer OCR candidates must be reconciled to independently verified text items. The checker also requires a numeric category inventory and digit-review evidence. Literal character, token and ordered-number comparisons run even if manually entered statuses say matched. Missing OCR can use the documented explicit visual fallback; missing transcription cannot.

## Two-minute target

Aim for roughly 20 seconds preparation/geometry, 60 seconds sheet inspection, and 40 seconds targeted details/reporting. These are planning targets, not measured guarantees. Preparation time is reported separately from end-to-end review time. Batch independent image opens and record evidence once. Install OCR dependencies once during setup; avoid repeated installation, web lookup or icon-library loading during routine audits. Do not rerun unchanged preparation or inspect unrelated icon candidates.

At two minutes, either finish with a supported verdict or give a brief progress update explaining the remaining detail, then continue. If the user explicitly imposed a hard deadline, return a partial report with pending region IDs. Never convert pending work to checked to meet the clock. Run local OCR when available; if unavailable, document the visual extraction fallback. OCR is never proof.
