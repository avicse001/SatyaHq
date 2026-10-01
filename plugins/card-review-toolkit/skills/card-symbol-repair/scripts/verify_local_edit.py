"""Verify that a raster edit changes only the allowed mask pixels.
Hardened with safe image decoding, error handling, and shared core logic.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add common directory to sys.path
common_dir = Path(__file__).resolve().parents[2] / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

try:
    from satya_core import verify_raster_edit
except ImportError:
    # Graceful fallback if imported without package
    from PIL import Image, ImageOps
    import numpy as np

    def verify_raster_edit(before_path, after_path, mask_path):
        try:
            with Image.open(before_path) as img:
                before = np.array(ImageOps.exif_transpose(img).convert("RGBA"))
            with Image.open(after_path) as img:
                after = np.array(ImageOps.exif_transpose(img).convert("RGBA"))
            with Image.open(mask_path) as img:
                allowed = np.array(ImageOps.exif_transpose(img).convert("L")) > 0
        except Exception as e:
            return {"ok": False, "error": str(e), "changed_pixels": 0, "outside_mask_pixels": 0, "change_bounds_xyxy_exclusive": None}

        if before.shape != after.shape or allowed.shape != before.shape[:2]:
            return {"ok": False, "error": "Image or mask dimensions differ", "changed_pixels": 0, "outside_mask_pixels": 0, "change_bounds_xyxy_exclusive": None}

        changed = np.any(before != after, axis=2)
        y, x = np.where(changed)
        outside = int(np.count_nonzero(changed & ~allowed))
        return {
            "ok": outside == 0,
            "changed_pixels": int(changed.sum()),
            "outside_mask_pixels": outside,
            "change_bounds_xyxy_exclusive": [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1] if x.size else None,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", help="Path to original/before raster image")
    parser.add_argument("after", help="Path to edited/after raster image")
    parser.add_argument("--mask", required=True, help="Path to binary authorization mask image")
    args = parser.parse_args()

    report = verify_raster_edit(args.before, args.after, args.mask)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
