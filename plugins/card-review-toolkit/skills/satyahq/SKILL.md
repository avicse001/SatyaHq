---
name: satyahq
description: |
  SatyaHQ — two-image card comparison workflow. Upload a RAW (original) image and
  an IMPROVED (enhanced) image to receive a complete, evidence-based comparison report
  covering integrity, pixel-level differences, perceptual similarity, text and numeric
  changes, icon/symbol changes, and geometry differences.
  The first image is always treated as RAW; the second as IMPROVED.
  If either image is missing or roles are ambiguous, ask the user — never guess.
---

# SatyaHQ Card Comparison Workflow

SatyaHQ extends the Card Review Toolkit v1.5.2 with a full-image, evidence-based
comparison pipeline. It wraps the existing `card-proofreader`, `card-symbol-repair`,
and `card-text-repair` skills, adds pixel-level and perceptual analysis, and produces
a structured verdict report.

## Activating the Workflow

Ask the user to supply exactly **two card images** in this order:
1. **Image 1 — RAW / ORIGINAL**: the reference source card.
2. **Image 2 — IMPROVED / ENHANCED**: the edited or AI-enhanced card.

If the user does not label the images, or if it is ambiguous which is RAW and which is
IMPROVED, **ask explicitly**. Never guess roles.

## Step-by-Step Procedure

### Step 1 — Identify and Validate Images

- Confirm both images are present and readable.
- Record filenames or attachment IDs.
- Ask the user to confirm which is RAW and which is IMPROVED if not clear.
- Note: the RAW image is the ground truth; the IMPROVED image is the subject of audit.

### Step 2 — Run the Comparison Engine

Run the bundled comparison engine:

```sh
python scripts/compare_engine.py RAW_IMAGE IMPROVED_IMAGE \
    --output WORK_DIR/satyahq-evidence \
    [--rules rules.json]
```

This produces `satyahq-report.json` plus annotated evidence files in the output directory.

**Do not modify the RAW image.** If the engine cannot run, report `NOT_RUN` and explain why.

### Step 3 — Read the Integrity Summary

From the report `integrity` section, report:
- SHA-256 hashes of both files.
- Whether dimensions match. If not, report the delta.
- Whether EXIF orientation changed.
- Whether alpha channel presence changed.
- Whether format or color mode changed.

State clearly: different SHA-256 hashes do not alone prove different visible content.
Different dimensions may indicate cropping.

### Step 4 — Report Pixel-Level Findings

From the `pixel_comparison` or `aligned_pixel_comparison` section:
- Number and percentage of changed pixels.
- Maximum and mean channel difference.
- Bounding box of the changed region.
- Direct link to heatmap, diff overlay, side-by-side, and annotated evidence images.

**Important**: a small number of changed pixels in a critical area (e.g., a digit) is more
significant than a large number in a decorative background area. Do not dismiss small changes
as irrelevant.

### Step 5 — Report Perceptual Similarity

From the `perceptual` section:
- SSIM grayscale score, if available.
- Note clearly: SSIM is a *global* perceptual estimate. A high SSIM does **not** rule out a
  small but critical content change (e.g., a changed card number or symbol).
- Distinguish SSIM from exact pixel comparison.

### Step 6 — Run Card Proofreader (Text and Numeric)

Call `card-proofreader` on this RAW/IMPROVED pair following its full protocol:
- Run `audit_engine.py prepare` to produce crops and sheets.
- Inspect all regions for text, numbers, symbols.
- Run `text_inventory.py` for OCR extraction (if available) or document visual fallback.
- Run `audit_engine.py check` to validate the review ledger.

Report all text, numeric, and symbol findings found, including the final `check` verdict.

### Step 7 — Classify and Summarize All Findings

Classify every finding using the following statuses:
- `PASS` — All mandatory checks completed and all specified acceptance rules satisfied.
- `FAIL` — A required rule was violated or a confirmed critical mismatch exists.
- `NEEDS_REVIEW` — Relevant uncertainty or ambiguous evidence remains.
- `NOT_RUN` — A required check could not be executed.

**Never issue PASS when**:
- A mandatory check was skipped or produced `NOT_RUN`.
- Required evidence is missing, corrupt, or invalid.
- An unresolved critical mismatch exists (e.g., changed digit in a collector number).
- The proofreader audit is incomplete.

### Step 8 — Present the Final Verdict Report

Provide a structured report with the following sections:
1. **Card Identity**: card name and verified original ID (or `unresolved`).
2. **Image Integrity**: SHA-256, dimensions, format, alpha, EXIF orientation.
3. **Pixel-Level Differences**: count, percentage, bounding box, evidence images.
4. **Perceptual Similarity**: SSIM score and interpretation caveat.
5. **Text and Numeric Findings**: each confirmed/unresolved difference with location.
6. **Symbol and Icon Findings**: each confirmed/unresolved difference.
7. **Geometry and Alignment**: whether alignment was needed and its confidence.
8. **Overall Verdict**: one of PASS / FAIL / NEEDS_REVIEW / NOT_RUN with justification.
9. **Evidence Files**: list of generated evidence images (heatmap, overlays, crops).
10. **Limitations**: any checks that could not run and why.

## Final Statuses

| Status | Meaning |
|--------|---------|
| `PASS` | All mandatory checks satisfied, no unresolved critical mismatches |
| `FAIL` | A required rule violated or confirmed critical mismatch confirmed |
| `NEEDS_REVIEW` | Uncertainty or ambiguity requires human verification |
| `NOT_RUN` | A required check could not execute (missing dependency, corrupt image, etc.) |

## Integration with Existing Skills

- Use `card-proofreader` for the complete text, number, and symbol audit.
- Use `card-symbol-repair` if approved symbol repair is requested after audit.
- Use `card-text-repair` if approved text repair is requested after audit.
- SatyaHQ does not authorize repairs; it audits. Repairs follow separate approval.

## Handling Missing or Ambiguous Inputs

- If only one image is supplied: ask for the missing image. Do not proceed.
- If image roles are ambiguous: ask the user to confirm which is RAW. Do not guess.
- If an image is corrupt or unreadable: report `NOT_RUN` for that image's checks.
- If the comparison engine fails: report `NOT_RUN` and explain the error.

## Dependencies

The comparison engine requires: Python, Pillow, NumPy, OpenCV (cv2).
Optional: scikit-image for SSIM. RapidOCR for OCR candidates.
All bundled scripts require no external API key.
