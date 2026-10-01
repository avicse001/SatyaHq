# Card Review Toolkit → SatyaHQ v2.0.0

**Latest version: 2.0.0** (upgraded from 1.5.2)

SatyaHQ extends the existing Card Review Toolkit with a full-image, evidence-based comparison pipeline while preserving all v1.5.2 features unchanged.

## Quick Start

### SatyaHQ Two-Image Comparison
Supply both images and let the engine do the heavy lifting:

```
"Use $satyahq to compare my original (RAW) and enhanced (IMPROVED) card."
```

The first image is always treated as RAW; the second as IMPROVED. If roles are ambiguous, the agent will ask.

### Existing Skills (unchanged)
- `$card-proofreader` — full text, numeric, and symbol audit
- `$card-text-repair` — localized pixel-level text corrections
- `$card-symbol-repair` — source-matched icon compositing

## Install

```sh
codex plugin marketplace add raakshassh/card-review-toolkit
codex plugin add card-review-toolkit@card-review
```

Install base dependencies:
```sh
python -m pip install -r requirements.txt
```

Install OCR dependencies (optional):
```sh
python -m pip install -r plugins/card-review-toolkit/skills/card-proofreader/requirements-ocr.txt
```

Install SSIM support (optional, for perceptual scoring):
```sh
python -m pip install scikit-image
```

## What's New in v2.0.0 (SatyaHQ)

### New: Full-Image Comparison Engine
`skills/satyahq/scripts/compare_engine.py`

- **Image Integrity**: SHA-256 hashes, dimensions, format, alpha, EXIF orientation
- **Pixel-Level Analysis**: exact diff count, per-channel, heatmap, changed-pixel mask, side-by-side, diff overlay, annotated crops
- **Perceptual Similarity**: SSIM scoring (when scikit-image is installed). A high SSIM score does NOT rule out small critical changes.
- **Alignment-Aware**: ORB/SIFT feature-based registration for misaligned or different-dimension image pairs
- **Region Statistics**: 4×4 grid breakdown of where changes occur
- **Evidence Files**: all comparison images saved to a dedicated output directory
- **PASS/FAIL/NEEDS_REVIEW/NOT_RUN** verdict with full justification

### Bug Fixes
| Bug | Fixed |
|-----|-------|
| Unicode numeric regex corruption (`âˆ'`, `Ã—` garbled) | ✅ Fixed — now uses native Python Unicode escapes `\u2212`, `\u00d7` |
| `10×` and `10` silently considered equal | ✅ Fixed — regression test proves they are distinct |
| `−50` (Unicode minus) not captured as number | ✅ Fixed — both U+2212 and U+2013 captured as sign prefix |
| Path traversal in OCR evidence path | ✅ Fixed — `validate()` resolves and checks path stays within evidence dir |
| `verify_local_edit.py` crashes on missing files | ✅ Fixed — both copies now return structured error dict without exception |
| `propose_quad()` division by zero on zero-dimension images | ✅ Fixed in `satya_core.safe_propose_quad()` |
| Non-streaming SHA-256 (memory waste on large files) | ✅ Fixed — streaming 64 KB chunks in all hashing functions |
| No decompression bomb guard on image load | ✅ Fixed — 100 MP max enforced at load time |
| No maximum file size guard | ✅ Fixed — 250 MB hard limit on image files |
| Non-atomic JSON writes (corrupt on crash) | ✅ Fixed — atomic `.tmp` → `replace()` in all write paths |

### Security Improvements
- Path traversal prevention on OCR evidence file resolution
- File size limits (250 MB) before loading
- Decompression bomb guard (`Image.MAX_IMAGE_PIXELS = 100_000_000`)
- Structured error returns (no unhandled exceptions that crash callers)
- Symlink-aware path resolution

### Test Coverage
- **Baseline**: 23 tests (all pass, unchanged)
- **New**: 35 additional tests in `tests/test_satyahq.py`
- **Total**: 58 tests, all passing

## File Structure

```
plugins/card-review-toolkit/
├── .codex-plugin/plugin.json          (v2.0.0)
├── skills/
│   ├── card-proofreader/              (preserved + hardened)
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── audit_engine.py        (unchanged)
│   │   │   └── text_inventory.py      (regex fixed, path traversal fixed)
│   │   └── references/
│   ├── card-symbol-repair/            (preserved + hardened)
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── find_icons.py          (unchanged)
│   │   │   └── verify_local_edit.py   (hardened, shared core)
│   │   └── assets/icons/gif/          (175 icons, unchanged)
│   ├── card-text-repair/              (preserved + hardened)
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── verify_local_edit.py   (hardened, shared core)
│   ├── satyahq/                       (NEW)
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml
│   │   └── scripts/
│   │       └── compare_engine.py
│   └── common/                        (NEW shared utilities)
│       ├── __init__.py
│       └── satya_core.py
tests/
├── test_audit_engine.py               (8 tests, unchanged)
├── test_text_inventory.py             (15 tests, unchanged)
└── test_satyahq.py                    (35 new tests)
```

## SatyaHQ Workflow (Manual)

```sh
# Run the comparison engine directly:
python plugins/card-review-toolkit/skills/satyahq/scripts/compare_engine.py \
    RAW_IMAGE.png IMPROVED_IMAGE.png \
    --output work/satyahq-evidence

# View the JSON report:
cat work/satyahq-evidence/satyahq-report.json

# Evidence images in the same directory:
#   direct-heatmap.png         — JET colormap of pixel differences
#   direct-changed-mask.png    — binary changed-pixel mask
#   direct-side-by-side.png    — RAW | IMPROVED side-by-side
#   direct-diff-overlay.png    — amplified absolute difference
#   direct-annotated-improved.png — IMPROVED with change bounding box
#   direct-diff-crop.png       — zoom into the changed region
```

## Verdict Statuses

| Status | Meaning |
|--------|---------|
| `PASS` | All mandatory checks completed, no critical mismatches, all rules satisfied |
| `FAIL` | A required rule was violated or a confirmed critical mismatch was found |
| `NEEDS_REVIEW` | Uncertainty or ambiguous evidence requires human verification |
| `NOT_RUN` | A required check could not execute (missing file, corrupt image, etc.) |

PASS is **never** issued when:
- A mandatory check was skipped or returned NOT_RUN
- An unresolved critical mismatch exists
- The proofreader audit ledger is incomplete

## Limitations and Remaining Considerations

1. **OCR is a candidate, not ground truth** — visual reconciliation always required
2. **SSIM is global** — high SSIM does not rule out a single changed digit
3. **Alignment confidence varies** — low-feature or very similar images may not align reliably; reported as NEEDS_REVIEW
4. **scikit-image is optional** — SSIM unavailable without it; comparison still works
5. **RapidOCR is optional** — visual fallback explicitly documented when unavailable
6. **Version constraint**: `rapidocr==3.9.2` is pinned in `requirements-ocr.txt`; test against newer versions before upgrading
7. **`/SatyaHq` as a native slash command** — the host (Codex) does not expose native slash-command registration to plugin SKILL.md files. The workflow is invoked via `$satyahq` in the skill prompt, or by asking: `"Use SatyaHQ to compare these two images"`. No false registration claim is made.

## Earlier Versions

See original README content for v1.1–v1.5.2 release notes. All earlier functionality is preserved intact.
