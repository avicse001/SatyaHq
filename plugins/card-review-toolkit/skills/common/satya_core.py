"""SatyaHQ Core Utilities: Security, Performance, and Geometry Verification.
Preserves backward compatibility while hardening card review operations.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import PIL
from PIL import Image, ImageOps

VERSION = "2.0.0"
SYSTEM_NAME = "SatyaHQ"

# Security: limit maximum decompression bomb size to 100 million pixels (e.g. 10,000 x 10,000)
SAFE_MAX_IMAGE_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = SAFE_MAX_IMAGE_PIXELS
MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB


def stream_sha256(path: Union[str, Path], chunk_size: int = 65536) -> str:
    """Calculate SHA-256 hash using streaming chunks to minimize memory consumption."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found for hashing: {p}")
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_resolve_path(base_dir: Union[str, Path], target_path: Union[str, Path]) -> Path:
    """Resolve target_path and ensure it resides within base_dir.
    
    Prevents path traversal attacks (e.g. ../ or symlink escapes).
    """
    base = Path(base_dir).resolve()
    target = Path(target_path)
    if not target.is_absolute():
        resolved = (base / target).resolve()
    else:
        resolved = target.resolve()
        
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal detected: {target_path} is outside base directory {base}")
    return resolved


def safe_load_image(path: Union[str, Path], preserve_alpha: bool = False) -> Image.Image:
    """Safely load an image with EXIF orientation and security validations.
    
    Protects against decompression bombs, path issues, and file size limits.
    """
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Image file does not exist: {p}")
    
    file_size = p.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size {file_size} bytes exceeds maximum allowed limit {MAX_FILE_SIZE_BYTES} bytes")
    if file_size == 0:
        raise ValueError(f"Image file is empty (0 bytes): {p}")

    try:
        with Image.open(p) as img:
            img.draft(None, None)  # triggers metadata read
            width, height = img.size
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid image dimensions: {width}x{height}")
            if width * height > SAFE_MAX_IMAGE_PIXELS:
                raise ValueError(f"Image dimensions {width}x{height} exceed maximum safety threshold")

            transposed = ImageOps.exif_transpose(img)
            if preserve_alpha and transposed.mode in ("RGBA", "LA", "P"):
                return transposed.convert("RGBA")
            return transposed.convert("RGB")
    except PIL.Image.DecompressionBombError as e:
        raise ValueError(f"Decompression bomb safety triggered: {e}") from e
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to decode image {p.name}: {e}") from e


def atomic_write_text(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
    """Atomic text write using temporary file and atomic replace."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}_{hashlib.md5(p.name.encode()).hexdigest()[:8]}.tmp")
    try:
        tmp.write_text(content, encoding=encoding)
        tmp.replace(p)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def atomic_write_json(path: Union[str, Path], data: Any, indent: int = 2) -> None:
    """Atomic JSON write with UTF-8 encoding and clean formatting."""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    atomic_write_text(path, content, encoding="utf-8")


def atomic_write_image(path: Union[str, Path], image: Image.Image, format: str = "PNG") -> None:
    """Atomic image save to prevent partially written or corrupt files."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}_{hashlib.md5(p.name.encode()).hexdigest()[:8]}.tmp")
    try:
        image.save(tmp, format=format)
        tmp.replace(p)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def safe_validate_quad(points: Any, size: Tuple[int, int]) -> np.ndarray:
    """Validate 4 clockwise convex corner coordinates within image bounds."""
    w, h = size
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid image size for geometry validation: {w}x{h}")
    q = np.asarray(points, dtype=np.float32)
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise ValueError("Corners must be four finite [x,y] points: TL, TR, BR, BL.")
    if np.any(q < 0) or np.any(q[:, 0] > w - 1) or np.any(q[:, 1] > h - 1):
        raise ValueError("Corners outside EXIF-oriented image.")
    edges = [q[(i + 1) % 4] - q[i] for i in range(4)]
    cross = [float(edges[i][0] * edges[(i + 1) % 4][1] - edges[i][1] * edges[(i + 1) % 4][0]) for i in range(4)]
    if min(cross) <= 0 or cv2.contourArea(q) < w * h * 0.05:
        raise ValueError("Corners must be clockwise, convex and enclose at least 5% of image.")
    if q[0, 1] + q[1, 1] >= q[2, 1] + q[3, 1] or q[0, 0] + q[3, 0] >= q[1, 0] + q[2, 0]:
        raise ValueError("Corner order must start at top left.")
    return q


def safe_propose_quad(im: Image.Image) -> Tuple[np.ndarray, str]:
    """Conservative geometric proposal with strict zero-division and degeneracy guards."""
    w, h = im.size
    if w <= 0 or h <= 0:
        raise ValueError(f"Cannot propose quad on zero-dimension image: {w}x{h}")

    aspect_ratio = float(w) / float(h)
    if 0.69 <= aspect_ratio <= 0.74:
        return np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]), "card-shaped full-frame proposal"

    max_dim = max(w, h)
    if max_dim <= 0:
        return np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]), "full-frame fallback"

    scale = min(1.0, 900.0 / float(max_dim))
    scaled_w, scaled_h = max(1, round(w * scale)), max(1, round(h * scale))
    a = np.array(im.resize((scaled_w, scaled_h)))
    if a.size == 0 or len(a.shape) < 2:
        return np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]), "full-frame fallback"

    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if len(a.shape) == 3 else a
    edge = cv2.Canny(gray, 40, 120)
    edge = cv2.morphologyEx(edge, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edge, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: List[Tuple[float, np.ndarray]] = []

    for contour in contours:
        arc_len = cv2.arcLength(contour, True)
        if arc_len <= 0:
            continue
        poly = cv2.approxPolyDP(contour, 0.025 * arc_len, True)
        if len(poly) != 4 or not cv2.isContourConvex(poly):
            continue
        pts = poly[:, 0, :].astype(np.float32) / (scale if scale > 0 else 1.0)
        center = pts.mean(axis=0)
        angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
        pts = pts[np.argsort(angles)]
        pts = np.roll(pts, -int(np.argmin(pts.sum(axis=1))), axis=0)
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)

        width = (np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[3])) / 2.0
        height = (np.linalg.norm(pts[3] - pts[0]) + np.linalg.norm(pts[2] - pts[1])) / 2.0
        if height <= 0:
            continue

        quad_aspect = width / height
        area = cv2.contourArea(pts)
        if 0.55 <= quad_aspect <= 0.85 and area >= w * h * 0.3:
            try:
                safe_validate_quad(pts, (w, h))
                candidates.append((area, pts))
            except ValueError:
                pass

    if candidates:
        candidates.sort(key=lambda x: (-x[0], tuple(x[1].flatten())))
        return candidates[0][1], "detected proposal"

    return np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]), "full-frame fallback; may include photo margins"


def verify_raster_edit(
    before_path: Union[str, Path],
    after_path: Union[str, Path],
    mask_path: Union[str, Path]
) -> Dict[str, Any]:
    """Verify that a raster edit changes only authorized mask pixels.
    
    Robust error handling returns structured error dicts without uncaught crashes.
    """
    for label, path in [("before", before_path), ("after", after_path), ("mask", mask_path)]:
        p = Path(path)
        if not p.is_file():
            return {
                "ok": False,
                "error": f"Required {label} image does not exist: {path}",
                "changed_pixels": 0,
                "outside_mask_pixels": 0,
                "change_bounds_xyxy_exclusive": None
            }

    try:
        with Image.open(before_path) as image:
            before_img = ImageOps.exif_transpose(image).convert("RGBA")
            before = np.array(before_img)
        with Image.open(after_path) as image:
            after_img = ImageOps.exif_transpose(image).convert("RGBA")
            after = np.array(after_img)
        with Image.open(mask_path) as image:
            mask_img = ImageOps.exif_transpose(image).convert("L")
            allowed = np.array(mask_img) > 0
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to load or parse image: {e}",
            "changed_pixels": 0,
            "outside_mask_pixels": 0,
            "change_bounds_xyxy_exclusive": None
        }

    if before.shape != after.shape or allowed.shape != before.shape[:2]:
        return {
            "ok": False,
            "error": f"Image or mask dimensions differ: before {before.shape}, after {after.shape}, mask {allowed.shape}",
            "changed_pixels": 0,
            "outside_mask_pixels": 0,
            "change_bounds_xyxy_exclusive": None
        }

    changed = np.any(before != after, axis=2)
    y, x = np.where(changed)
    outside = int(np.count_nonzero(changed & ~allowed))
    total_changed = int(changed.sum())

    report: Dict[str, Any] = {
        "ok": outside == 0,
        "changed_pixels": total_changed,
        "outside_mask_pixels": outside,
        "total_image_pixels": int(before.shape[0] * before.shape[1]),
        "change_bounds_xyxy_exclusive": (
            [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            if x.size else None
        ),
    }

    if total_changed > 0:
        diff_array = np.abs(before.astype(int) - after.astype(int))
        report["max_channel_difference"] = int(diff_array.max())
        report["mean_channel_difference"] = float(round(float(diff_array[changed].mean()), 2))
    else:
        report["max_channel_difference"] = 0
        report["mean_channel_difference"] = 0.0

    return report
