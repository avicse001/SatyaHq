# Card Review Toolkit

Includes card-proofreader, card-text-repair, and card-symbol-repair, with 175 candidate PNG icons.

## Use

Attach the original and enhanced images and identify their roles. Ask: "Use card-proofreader to compare these cards and label confirmed errors with the collector number."

After reviewing findings, ask: "Use card-text-repair to fix these approved text errors, preserving previous fixes, font fidelity, and surrounding texture."

For symbols, ask: "Use card-symbol-repair to prepare source-matched previews for these approved symbol errors."

Proofreading does not authorize repairs. Assets are unverified candidates until compared to the current source. Source blur can limit exact font or symbol recovery. No automatic detection service or Card Review Studio app is included.

## Dependencies

Python with Pillow and NumPy for local edits and pixel checks; OpenCV when a repair needs registration or inpainting. No separate API key is required by the bundled scripts. Agent usage still follows the host account's limits.

All skill resources are bundled using relative paths. Keep the entire folder together, including the hidden .codex-plugin directory. The ZIP is a plugin source package; extract it before using a local-plugin installation workflow.

The proofreader includes local OCR candidate extraction and exact text/number comparison. Install `skills/card-proofreader/requirements-ocr.txt` once. Initial model downloads may be needed; no card upload or API key is required. OCR output must be visually reconciled, with an explicit fallback when unavailable. Both footer corners and auxiliary codes are mandatory checks.
