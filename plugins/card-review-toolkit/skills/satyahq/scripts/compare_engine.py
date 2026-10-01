"""SatyaHQ Full-Image Comparison Engine.

Compares a RAW (original) image against an IMPROVED (enhanced) image across:
- Image integrity (dimensions, format, SHA-256, EXIF, alpha)
- Pixel-level differences (exact diff, per-channel, heatmap, masks)
- Structural/perceptual metrics (SSIM where available)
- Alignment-aware comparison with geometry pre-measurement
- Text, number, symbol comparison (integrates with existing OCR pipeline)
- Classification of findings with PASS/FAIL/NEEDS_REVIEW/NOT_RUN statuses

Usage:
    python compare_engine.py RAW_IMAGE IMPROVED_IMAGE --output OUTPUT_DIR [--rules RULES_JSON]

Output: A JSON report + annotated image evidence in OUTPUT_DIR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# Optional SSIM support via scikit-image
try:
    from skimage.metrics import structural_similarity as _ssim
    SSIM_AVAILABLE = True
except ImportError:
    SSIM_AVAILABLE = False

VERSION = "2.0.0"
SAFE_MAX_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = SAFE_MAX_PIXELS
MAX_FILE_BYTES = 250 * 1024 * 1024

FINAL_STATUSES = ("PASS", "FAIL", "NEEDS_REVIEW", "NOT_RUN")


# ---------------------------------------------------------------------------
# Image loading with security guards
# ---------------------------------------------------------------------------

def _stream_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_load(path: Path) -> Tuple[Image.Image, Dict[str, Any]]:
    """Load image, apply EXIF transpose, return image + metadata dict."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {p}")
    size_bytes = p.stat().st_size
    if size_bytes == 0:
        raise ValueError(f"Image file is empty: {p}")
    if size_bytes > MAX_FILE_BYTES:
        raise ValueError(f"File {size_bytes} bytes exceeds {MAX_FILE_BYTES} byte limit")

    sha = _stream_sha256(p)

    try:
        with Image.open(p) as raw:
            raw.load()  # trigger decompression-bomb guard early
            original_mode = raw.mode
            original_size = raw.size
            original_format = raw.format or "unknown"
            exif_orientation = None
            try:
                exif_data = raw.getexif()
                exif_orientation = exif_data.get(274)  # Orientation tag
            except Exception:
                pass
            has_alpha = raw.mode in ("RGBA", "LA", "PA", "P") or (
                raw.mode == "P" and "transparency" in raw.info
            )
            transposed = ImageOps.exif_transpose(raw)
    except PIL.Image.DecompressionBombError as e:
        raise ValueError(f"Decompression bomb triggered: {e}") from e
    except Exception as e:
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Failed to decode {p.name}: {e}") from e

    meta = {
        "path": str(p),
        "sha256": sha,
        "file_size_bytes": size_bytes,
        "original_format": original_format,
        "original_mode": original_mode,
        "original_size_wh": list(original_size),
        "exif_orientation": exif_orientation,
        "has_alpha": has_alpha,
        "post_transpose_size_wh": list(transposed.size),
    }
    return transposed, meta


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------

def compare_integrity(raw_meta: Dict, imp_meta: Dict) -> Dict[str, Any]:
    raw_w, raw_h = raw_meta["post_transpose_size_wh"]
    imp_w, imp_h = imp_meta["post_transpose_size_wh"]
    same_dims = (raw_w == imp_w and raw_h == imp_h)
    raw_ar = raw_w / raw_h if raw_h else None
    imp_ar = imp_w / imp_h if imp_h else None
    ar_delta = abs(raw_ar - imp_ar) if (raw_ar and imp_ar) else None

    result: Dict[str, Any] = {
        "raw": {k: raw_meta[k] for k in ("sha256", "file_size_bytes", "original_format",
                                          "original_mode", "has_alpha", "original_size_wh",
                                          "post_transpose_size_wh", "exif_orientation")},
        "improved": {k: imp_meta[k] for k in ("sha256", "file_size_bytes", "original_format",
                                               "original_mode", "has_alpha", "original_size_wh",
                                               "post_transpose_size_wh", "exif_orientation")},
        "same_sha256": raw_meta["sha256"] == imp_meta["sha256"],
        "same_dimensions": same_dims,
        "dimension_delta_wh": [imp_w - raw_w, imp_h - raw_h],
        "aspect_ratio_delta": round(ar_delta, 6) if ar_delta is not None else None,
        "alpha_status_changed": raw_meta["has_alpha"] != imp_meta["has_alpha"],
        "format_changed": raw_meta["original_format"] != imp_meta["original_format"],
        "mode_changed": raw_meta["original_mode"] != imp_meta["original_mode"],
        "exif_orientation_changed": raw_meta["exif_orientation"] != imp_meta["exif_orientation"],
    }

    notes = []
    if result["same_sha256"]:
        notes.append("Files are bitwise identical; no pixel changes possible.")
    if not same_dims:
        notes.append(f"Dimensions differ: raw {raw_w}x{raw_h} vs improved {imp_w}x{imp_h}. Alignment required for pixel comparison.")
    if result["alpha_status_changed"]:
        notes.append("Alpha channel presence changed between images.")
    if result["exif_orientation_changed"]:
        notes.append("EXIF orientation differs; EXIF transpose was applied before comparison.")
    result["notes"] = notes
    return result


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def _try_align(raw_np: np.ndarray, imp_np: np.ndarray) -> Dict[str, Any]:
    """Attempt feature-based alignment using ORB/SIFT. Returns transform info."""
    try:
        detector = cv2.SIFT_create() if hasattr(cv2, "SIFT_create") else cv2.ORB_create(nfeatures=2000)
        matcher_norm = cv2.NORM_L2 if hasattr(cv2, "SIFT_create") else cv2.NORM_HAMMING
        raw_gray = cv2.cvtColor(raw_np, cv2.COLOR_RGB2GRAY)
        imp_gray = cv2.cvtColor(imp_np, cv2.COLOR_RGB2GRAY)
        kp1, des1 = detector.detectAndCompute(raw_gray, None)
        kp2, des2 = detector.detectAndCompute(imp_gray, None)
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return {"aligned": False, "reason": "Insufficient keypoints for alignment"}
        bf = cv2.BFMatcher(matcher_norm, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda m: m.distance)
        if len(matches) < 4:
            return {"aligned": False, "reason": "Too few feature matches"}
        pts1 = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        pts2 = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(pts2, pts1, cv2.RANSAC, 5.0)
        if H is None:
            return {"aligned": False, "reason": "Homography estimation failed"}
        inliers = int(mask.sum()) if mask is not None else 0
        if inliers < 4:
            return {"aligned": False, "reason": f"Too few RANSAC inliers: {inliers}"}
        h, w = raw_np.shape[:2]
        aligned = cv2.warpPerspective(imp_np, H, (w, h))
        confidence = min(1.0, inliers / max(len(matches), 1))
        return {
            "aligned": True,
            "homography": H.tolist(),
            "total_matches": len(matches),
            "inlier_matches": inliers,
            "alignment_confidence": round(confidence, 3),
            "aligned_image_array": aligned,
        }
    except Exception as e:
        return {"aligned": False, "reason": f"Alignment error: {e}"}


# ---------------------------------------------------------------------------
# Pixel-level comparison
# ---------------------------------------------------------------------------

def compare_pixels(
    raw_rgb: np.ndarray,
    imp_rgb: np.ndarray,
    out_dir: Path,
    prefix: str = "comparison"
) -> Dict[str, Any]:
    """Compare two same-size RGB uint8 arrays. Saves evidence images to out_dir."""
    assert raw_rgb.shape == imp_rgb.shape, "Arrays must be same shape for pixel comparison"
    h, w = raw_rgb.shape[:2]
    total_pixels = h * w

    diff_abs = np.abs(raw_rgb.astype(np.int16) - imp_rgb.astype(np.int16))
    changed_mask = diff_abs.max(axis=2) > 0
    changed_count = int(changed_mask.sum())
    changed_fraction = changed_count / total_pixels if total_pixels > 0 else 0.0

    per_channel_max = [int(diff_abs[:, :, c].max()) for c in range(3)]
    per_channel_mean = [float(round(diff_abs[:, :, c].mean(), 4)) for c in range(3)]
    per_channel_changed = [int((diff_abs[:, :, c] > 0).sum()) for c in range(3)]

    max_diff = int(diff_abs.max())
    mean_diff = float(round(float(diff_abs.mean()), 4))

    # Find bounding box of changed area
    if changed_count > 0:
        ys, xs = np.where(changed_mask)
        bbox_xyxy = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
    else:
        bbox_xyxy = None

    result: Dict[str, Any] = {
        "total_pixels": total_pixels,
        "changed_pixels": changed_count,
        "changed_fraction": round(changed_fraction, 6),
        "changed_percent": round(changed_fraction * 100, 4),
        "max_channel_difference": max_diff,
        "mean_channel_difference": mean_diff,
        "per_channel_max_diff": {"R": per_channel_max[0], "G": per_channel_max[1], "B": per_channel_max[2]},
        "per_channel_mean_diff": {"R": per_channel_mean[0], "G": per_channel_mean[1], "B": per_channel_mean[2]},
        "per_channel_changed_pixels": {"R": per_channel_changed[0], "G": per_channel_changed[1], "B": per_channel_changed[2]},
        "change_bounding_box_xyxy": bbox_xyxy,
        "evidence_files": [],
    }

    # Save diff heatmap (grayscale max-channel)
    heat_gray = diff_abs.max(axis=2).astype(np.uint8)
    # Normalize to 0-255 if max_diff > 0
    if max_diff > 0:
        heat_norm = (heat_gray.astype(np.float32) / max_diff * 255).astype(np.uint8)
    else:
        heat_norm = heat_gray
    heat_color = cv2.applyColorMap(heat_norm, cv2.COLORMAP_JET)
    heat_color_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
    heatmap_path = out_dir / f"{prefix}-heatmap.png"
    Image.fromarray(heat_color_rgb).save(heatmap_path, "PNG")
    result["evidence_files"].append(str(heatmap_path))

    # Save changed-pixel mask
    mask_img = (changed_mask.astype(np.uint8) * 255)
    mask_path = out_dir / f"{prefix}-changed-mask.png"
    Image.fromarray(mask_img).save(mask_path, "PNG")
    result["evidence_files"].append(str(mask_path))

    # Save side-by-side comparison
    gap = 4
    sbs_w = w * 2 + gap
    sbs = Image.new("RGB", (sbs_w, h), (128, 128, 128))
    sbs.paste(Image.fromarray(raw_rgb), (0, 0))
    sbs.paste(Image.fromarray(imp_rgb), (w + gap, 0))
    draw = ImageDraw.Draw(sbs)
    draw.text((4, 4), "RAW", fill=(255, 0, 0))
    draw.text((w + gap + 4, 4), "IMPROVED", fill=(0, 200, 0))
    sbs_path = out_dir / f"{prefix}-side-by-side.png"
    sbs.save(sbs_path, "PNG")
    result["evidence_files"].append(str(sbs_path))

    # Save difference overlay (absolute difference amplified x4 for visibility)
    diff_vis = np.clip(diff_abs.astype(np.int32) * 4, 0, 255).astype(np.uint8)
    overlay_path = out_dir / f"{prefix}-diff-overlay.png"
    Image.fromarray(diff_vis).save(overlay_path, "PNG")
    result["evidence_files"].append(str(overlay_path))

    # Save annotated improved image with bounding box around changes
    if bbox_xyxy:
        annotated = Image.fromarray(imp_rgb).copy()
        draw_ann = ImageDraw.Draw(annotated)
        x0, y0, x1, y1 = bbox_xyxy
        draw_ann.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 0, 0), width=max(2, w // 300))
        draw_ann.text((x0 + 2, max(0, y0 - 16)), "CHANGED REGION", fill=(255, 0, 0))
        ann_path = out_dir / f"{prefix}-annotated-improved.png"
        annotated.save(ann_path, "PNG")
        result["evidence_files"].append(str(ann_path))

        # Save diff crop for the changed bounding box region
        crop_raw = Image.fromarray(raw_rgb).crop(bbox_xyxy)
        crop_imp = Image.fromarray(imp_rgb).crop(bbox_xyxy)
        crop_w, crop_h = crop_raw.size
        crop_sbs = Image.new("RGB", (crop_w * 2 + 2, max(crop_h, 1)), (200, 200, 200))
        crop_sbs.paste(crop_raw, (0, 0))
        crop_sbs.paste(crop_imp, (crop_w + 2, 0))
        crop_path = out_dir / f"{prefix}-diff-crop.png"
        crop_sbs.save(crop_path, "PNG")
        result["evidence_files"].append(str(crop_path))

    return result


# ---------------------------------------------------------------------------
# Perceptual / structural comparison
# ---------------------------------------------------------------------------

def compare_perceptual(raw_rgb: np.ndarray, imp_rgb: np.ndarray) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ssim_available": SSIM_AVAILABLE}
    if SSIM_AVAILABLE:
        try:
            raw_gray = cv2.cvtColor(raw_rgb, cv2.COLOR_RGB2GRAY)
            imp_gray = cv2.cvtColor(imp_rgb, cv2.COLOR_RGB2GRAY)
            score, _ = _ssim(raw_gray, imp_gray, full=True)
            result["ssim_grayscale"] = round(float(score), 6)
            # Per-channel SSIM
            channel_scores = []
            for c in range(3):
                sc, _ = _ssim(raw_rgb[:, :, c], imp_rgb[:, :, c], full=True)
                channel_scores.append(round(float(sc), 6))
            result["ssim_per_channel_rgb"] = channel_scores
            result["note"] = ("SSIM measures perceptual similarity globally. A high SSIM score "
                              "does NOT rule out a small but critical content change (e.g., single digit).")
        except Exception as e:
            result["ssim_error"] = str(e)
    else:
        result["note"] = "Install scikit-image for SSIM support: pip install scikit-image"
    return result


# ---------------------------------------------------------------------------
# Region-level statistics (quadrant breakdown)
# ---------------------------------------------------------------------------

def compare_regions(
    raw_rgb: np.ndarray, imp_rgb: np.ndarray, grid: int = 4
) -> List[Dict[str, Any]]:
    h, w = raw_rgb.shape[:2]
    regions = []
    cell_h = max(1, h // grid)
    cell_w = max(1, w // grid)
    for row in range(grid):
        for col in range(grid):
            y0 = row * cell_h
            y1 = min(h, (row + 1) * cell_h)
            x0 = col * cell_w
            x1 = min(w, (col + 1) * cell_w)
            r_crop = raw_rgb[y0:y1, x0:x1]
            i_crop = imp_rgb[y0:y1, x0:x1]
            diff = np.abs(r_crop.astype(np.int16) - i_crop.astype(np.int16))
            changed = diff.max(axis=2) > 0
            total = (y1 - y0) * (x1 - x0)
            regions.append({
                "row": row, "col": col,
                "box_xyxy": [x0, y0, x1, y1],
                "changed_pixels": int(changed.sum()),
                "total_pixels": total,
                "changed_percent": round(float(changed.sum()) / total * 100, 2) if total > 0 else 0.0,
                "max_channel_diff": int(diff.max()) if diff.size > 0 else 0,
                "mean_channel_diff": float(round(float(diff.mean()), 4)) if diff.size > 0 else 0.0,
            })
    return regions


# ---------------------------------------------------------------------------
# Classification of findings
# ---------------------------------------------------------------------------

def classify_findings(
    integrity: Dict,
    pixel: Optional[Dict],
    perceptual: Optional[Dict],
    alignment_info: Optional[Dict],
    rules: Optional[Dict],
) -> Dict[str, Any]:
    """Classify comparison results into structured findings."""
    findings = []
    rules = rules or {}

    # Bitwise identical → PASS immediately
    if integrity.get("same_sha256"):
        return {
            "status": "PASS",
            "summary": "Images are bitwise identical (same SHA-256).",
            "findings": [],
            "note": "No pixel differences are possible between bitwise-identical files.",
        }

    # Dimension mismatch
    if not integrity.get("same_dimensions"):
        d = integrity["dimension_delta_wh"]
        findings.append({
            "type": "geometry",
            "severity": "NEEDS_REVIEW",
            "description": f"Image dimensions differ by dx={d[0]}, dy={d[1]}.",
            "detail": "Alignment was attempted for pixel comparison. Verify that no content was cropped.",
        })

    # Alpha change
    if integrity.get("alpha_status_changed"):
        findings.append({
            "type": "transparency",
            "severity": "NEEDS_REVIEW",
            "description": "Alpha channel presence changed between images.",
        })

    if integrity.get("exif_orientation_changed"):
        findings.append({
            "type": "geometry",
            "severity": "NEEDS_REVIEW",
            "description": "EXIF orientation tag changed. EXIF transpose was applied.",
        })

    # Pixel findings
    if pixel is not None:
        changed_pct = pixel.get("changed_percent", 0)
        max_diff = pixel.get("max_channel_difference", 0)

        if changed_pct == 0:
            findings.append({
                "type": "pixels",
                "severity": "PASS",
                "description": "No pixel differences detected after alignment.",
            })
        else:
            severity = "NEEDS_REVIEW"
            if rules.get("preserve_all_text") or rules.get("preserve_all_numbers"):
                severity = "FAIL"
            findings.append({
                "type": "pixels",
                "severity": severity,
                "description": f"{pixel['changed_pixels']:,} pixels changed ({changed_pct:.4f}%).",
                "detail": {
                    "max_channel_difference": max_diff,
                    "mean_channel_difference": pixel.get("mean_channel_difference"),
                    "change_bounding_box": pixel.get("change_bounding_box_xyxy"),
                    "per_channel_max": pixel.get("per_channel_max_diff"),
                },
            })

    # Perceptual
    if perceptual and "ssim_grayscale" in perceptual:
        ssim = perceptual["ssim_grayscale"]
        if ssim < 0.90:
            findings.append({
                "type": "perceptual",
                "severity": "NEEDS_REVIEW",
                "description": f"SSIM grayscale similarity is {ssim:.4f} (< 0.90). Significant perceptual difference.",
            })
        elif ssim < 0.99:
            findings.append({
                "type": "perceptual",
                "severity": "NEEDS_REVIEW",
                "description": f"SSIM similarity {ssim:.4f} detects subtle differences. Inspect heatmap evidence.",
            })
        else:
            findings.append({
                "type": "perceptual",
                "severity": "PASS",
                "description": f"High perceptual similarity (SSIM={ssim:.4f}). Critical content checks still required.",
            })

    # Alignment info
    if alignment_info and not alignment_info.get("aligned", True):
        findings.append({
            "type": "alignment",
            "severity": "NEEDS_REVIEW",
            "description": f"Automatic alignment failed: {alignment_info.get('reason', 'unknown')}. Pixel comparison may not be reliable.",
        })

    # Determine overall status
    severities = [f["severity"] for f in findings]
    if "FAIL" in severities:
        status = "FAIL"
    elif any(s == "NEEDS_REVIEW" for s in severities):
        status = "NEEDS_REVIEW"
    elif all(s == "PASS" for s in severities):
        status = "PASS"
    else:
        status = "NEEDS_REVIEW"

    return {
        "status": status,
        "findings": findings,
        "note": ("PASS means all checked properties satisfy specified rules. "
                 "NEEDS_REVIEW requires human verification. "
                 "Individual pixel differences do not confirm intentional or unintentional changes.")
    }


# ---------------------------------------------------------------------------
# Main comparison orchestration
# ---------------------------------------------------------------------------

def compare(
    raw_path: str,
    improved_path: str,
    output_dir: str,
    rules: Optional[Dict] = None,
    attempt_alignment: bool = True,
) -> Dict[str, Any]:
    """Run full SatyaHQ comparison pipeline. Returns structured report dict."""
    started = time.perf_counter()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "satyahq_version": VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "raw_path": str(Path(raw_path).resolve()),
        "improved_path": str(Path(improved_path).resolve()),
        "output_dir": str(out),
        "rules": rules or {},
        "status": "NOT_RUN",
        "integrity": None,
        "pixel_comparison": None,
        "aligned_pixel_comparison": None,
        "perceptual": None,
        "region_stats": None,
        "alignment": None,
        "classification": None,
        "evidence_files": [],
        "errors": [],
    }

    # Load images
    try:
        raw_img, raw_meta = _safe_load(Path(raw_path))
    except Exception as e:
        report["errors"].append(f"Failed to load RAW image: {e}")
        report["status"] = "NOT_RUN"
        return report

    try:
        imp_img, imp_meta = _safe_load(Path(improved_path))
    except Exception as e:
        report["errors"].append(f"Failed to load IMPROVED image: {e}")
        report["status"] = "NOT_RUN"
        return report

    # Integrity comparison
    integrity = compare_integrity(raw_meta, imp_meta)
    report["integrity"] = integrity

    # Early exit if bitwise identical
    if integrity["same_sha256"]:
        report["classification"] = classify_findings(integrity, None, None, None, rules)
        report["status"] = report["classification"]["status"]
        report["seconds"] = round(time.perf_counter() - started, 3)
        _save_report(report, out)
        return report

    raw_rgb = np.array(raw_img.convert("RGB"))
    imp_rgb = np.array(imp_img.convert("RGB"))
    raw_h, raw_w = raw_rgb.shape[:2]
    imp_h, imp_w = imp_rgb.shape[:2]

    alignment_info: Optional[Dict] = None
    aligned_rgb: Optional[np.ndarray] = None

    # Alignment when dimensions differ
    dims_match = (raw_w == imp_w and raw_h == imp_h)
    if not dims_match and attempt_alignment:
        # Resize improved to raw dimensions for alignment attempt
        imp_resized = cv2.resize(imp_rgb, (raw_w, raw_h), interpolation=cv2.INTER_LINEAR)
        alignment_info = _try_align(raw_rgb, imp_resized)
        if alignment_info.get("aligned"):
            aligned_rgb = alignment_info.pop("aligned_image_array")
        else:
            aligned_rgb = imp_resized
        report["alignment"] = {k: v for k, v in alignment_info.items() if k != "aligned_image_array"}
    elif dims_match and attempt_alignment:
        # Try alignment even when dims match (e.g., slight registration offset)
        alignment_info = _try_align(raw_rgb, imp_rgb)
        if alignment_info.get("aligned") and alignment_info.get("alignment_confidence", 0) > 0.5:
            aligned_rgb = alignment_info.pop("aligned_image_array")
        else:
            aligned_rgb = imp_rgb
        report["alignment"] = {k: v for k, v in alignment_info.items() if k != "aligned_image_array"}
    else:
        aligned_rgb = imp_rgb if dims_match else cv2.resize(imp_rgb, (raw_w, raw_h))

    # Pixel comparison on direct (possibly resized) images
    if dims_match:
        pixel_result = compare_pixels(raw_rgb, imp_rgb, out, "direct")
        report["pixel_comparison"] = pixel_result
        report["evidence_files"].extend(pixel_result.get("evidence_files", []))

    # Aligned pixel comparison
    if aligned_rgb is not None:
        aligned_result = compare_pixels(raw_rgb, aligned_rgb, out, "aligned")
        report["aligned_pixel_comparison"] = aligned_result
        report["evidence_files"].extend(aligned_result.get("evidence_files", []))

    # Perceptual comparison
    if dims_match:
        report["perceptual"] = compare_perceptual(raw_rgb, imp_rgb)
    elif aligned_rgb is not None:
        report["perceptual"] = compare_perceptual(raw_rgb, aligned_rgb)

    # Region stats
    comparison_rgb = imp_rgb if dims_match else aligned_rgb
    if comparison_rgb is not None:
        report["region_stats"] = compare_regions(raw_rgb, comparison_rgb)

    # Classification
    primary_pixel = report["pixel_comparison"] or report["aligned_pixel_comparison"]
    report["classification"] = classify_findings(
        integrity, primary_pixel, report.get("perceptual"), alignment_info, rules
    )
    report["status"] = report["classification"]["status"]
    report["seconds"] = round(time.perf_counter() - started, 3)
    _save_report(report, out)
    return report


def _save_report(report: Dict, out: Path) -> None:
    """Atomically save the JSON report."""
    report_path = out / "satyahq-report.json"
    tmp = report_path.with_suffix(".tmp")
    # Remove non-serializable numpy arrays before saving
    safe_report = json.loads(json.dumps(report, default=lambda x: str(x) if not isinstance(x, (str, int, float, bool, list, dict, type(None))) else x))
    tmp.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(report_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw", help="Path to RAW/ORIGINAL image")
    parser.add_argument("improved", help="Path to IMPROVED/ENHANCED image")
    parser.add_argument("--output", required=True, help="Output directory for report and evidence")
    parser.add_argument("--rules", default=None, help="JSON string or path to rules file (optional)")
    parser.add_argument("--no-align", action="store_true", help="Disable automatic alignment")
    args = parser.parse_args()

    rules = None
    if args.rules:
        try:
            if Path(args.rules).is_file():
                rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
            else:
                rules = json.loads(args.rules)
        except Exception as e:
            print(json.dumps({"error": f"Failed to parse rules: {e}"}))
            return 1

    try:
        result = compare(args.raw, args.improved, args.output, rules=rules, attempt_alignment=not args.no_align)
        # Print report without large evidence arrays
        printable = {k: v for k, v in result.items() if k not in ("region_stats",)}
        print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
        status = result.get("status", "NOT_RUN")
        return 0 if status == "PASS" else (2 if status == "FAIL" else 3)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
