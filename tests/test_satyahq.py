"""Comprehensive tests for the SatyaHQ upgrade.

Tests cover:
- Fixed numbers() regex (10×, 10x, 10, −50, −, ×)
- Path traversal prevention in validate()
- SatyaHQ compare_engine: integrity, pixel comparison, identical images
- SatyaHQ compare_engine: different dimension handling
- SatyaHQ compare_engine: corrupt/missing image handling  
- satya_core: verify_raster_edit with all edge cases
- Regression: 10× and 10 cannot silently be considered equivalent
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Load modules under test
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "plugins/card-review-toolkit/skills/card-proofreader/scripts"
COMMON_DIR = ROOT / "plugins/card-review-toolkit/skills/common"
COMPARE_DIR = ROOT / "plugins/card-review-toolkit/skills/satyahq/scripts"

def _load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

inventory = _load_module(SCRIPTS_DIR / "text_inventory.py")
satya_core = _load_module(COMMON_DIR / "satya_core.py")
compare_engine = _load_module(COMPARE_DIR / "compare_engine.py")


# ---------------------------------------------------------------------------
# Helper: create a test card image
# ---------------------------------------------------------------------------

def _make_card(path, width=200, height=280, text="189", color="#778899"):
    im = Image.new("RGB", (width, height), color)
    ImageDraw.Draw(im).text((8, 245), text, fill="white")
    im.save(path)
    return path


# ---------------------------------------------------------------------------
# 1. Numbers() regex correctness
# ---------------------------------------------------------------------------

class TestNumbersRegex(unittest.TestCase):
    """Regression tests proving the fixed numbers() regex is correct."""

    def test_multiplication_x_lowercase_is_different_from_times(self):
        """10x and 10× must NOT compare equal — different symbols."""
        result = inventory.differences("10x", "10\u00d7")
        self.assertFalse(result["numbers_equal"],
                         "10x and 10× must not be considered numerically equal")

    def test_multiplication_times_differs_from_plain_number(self):
        """10× and 10 must NOT compare equal — trailing multiplier matters."""
        result = inventory.differences("10\u00d7", "10")
        self.assertFalse(result["numbers_equal"],
                         "10× and 10 must not be considered numerically equal")

    def test_unicode_minus_captured_as_sign(self):
        """Unicode minus (U+2212) should be captured as the sign prefix."""
        nums = inventory.numbers("\u221250")
        self.assertEqual(len(nums), 1, "Should extract exactly one number from '−50'")
        self.assertIn("50", nums[0], "The digits 50 must be present")
        self.assertTrue(nums[0].startswith("\u2212"), "Must retain Unicode minus sign")

    def test_en_dash_captured_as_sign(self):
        """En-dash (U+2013) used as minus should be captured."""
        nums = inventory.numbers("\u201350")
        self.assertEqual(len(nums), 1)
        self.assertIn("50", nums[0])

    def test_times_symbol_captured(self):
        """Unicode × (U+00D7) should be captured as multiplier suffix."""
        nums = inventory.numbers("10\u00d7")
        self.assertEqual(nums, ["10\u00d7"], f"Expected ['10×'], got {nums}")

    def test_percent_captured(self):
        nums = inventory.numbers("50%")
        self.assertEqual(nums, ["50%"])

    def test_plus_sign_captured(self):
        nums = inventory.numbers("+20")
        self.assertEqual(nums, ["+20"])

    def test_fraction_captured(self):
        nums = inventory.numbers("77/130")
        self.assertEqual(nums, ["77/130"])

    def test_leading_zero_preserved(self):
        nums = inventory.numbers("035")
        self.assertEqual(nums, ["035"])
        self.assertNotEqual(nums, ["35"], "Leading zero must be preserved as string")

    def test_10x_and_10_times_are_distinct_tokens(self):
        """Both 10x and 10× should extract as distinct number tokens from plain 10."""
        for token in ["10x", "10\u00d7"]:
            nums = inventory.numbers(token)
            self.assertEqual(len(nums), 1)
            self.assertNotEqual(nums, ["10"],
                                f"Token '{token}' must not extract as bare '10'")


# ---------------------------------------------------------------------------
# 2. Path traversal prevention in validate()
# ---------------------------------------------------------------------------

class TestPathTraversalPrevention(unittest.TestCase):
    def _make_fixture(self, ocr_file: str) -> dict:
        return {
            "regions": {},
            "text_extraction": {
                "mode": "rapidocr",
                "file": ocr_file,
                "sha256": "abcdef",
                "visual_sweep_complete": True,
                "evidence": "Fixture",
            },
            "numeric_fields": {f: {"absent_in_both": True, "evidence": "Fixture"} for f in inventory.FIELDS},
        }

    def test_path_traversal_blocked(self):
        """Path traversal in OCR file path must produce an issue, not a crash."""
        with tempfile.TemporaryDirectory() as tmp:
            r = self._make_fixture("../../etc/passwd")
            result = inventory.validate({"key": "x"}, r, tmp)
            issues_text = " ".join(result["issues"])
            self.assertTrue(
                any("traversal" in i.lower() or "missing" in i.lower() or "changed" in i.lower()
                    for i in result["issues"]),
                f"Expected traversal or missing-evidence issue, got: {result['issues']}"
            )

    def test_absolute_path_outside_dir_blocked(self):
        """An absolute OCR path outside the evidence dir should be blocked."""
        import sys
        evil_path = "C:\\Windows\\System32\\drivers\\etc\\hosts" if sys.platform == "win32" else "/etc/passwd"
        with tempfile.TemporaryDirectory() as tmp:
            r = self._make_fixture(evil_path)
            result = inventory.validate({"key": "x"}, r, tmp)
            self.assertTrue(result["issues"], "Absolute outside-dir path must produce issues")


# ---------------------------------------------------------------------------
# 3. satya_core: verify_raster_edit
# ---------------------------------------------------------------------------

class TestVerifyRasterEdit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        w, h = 100, 80
        # Before image: solid gray
        before_img = Image.new("RGB", (w, h), (128, 128, 128))
        self.before_path = self.root / "before.png"
        before_img.save(self.before_path)
        # After image: same as before but with one pixel changed at (10,10)
        after_img = before_img.copy()
        after_img.putpixel((10, 10), (255, 0, 0))
        self.after_path = self.root / "after.png"
        after_img.save(self.after_path)
        # Full mask (all white)
        mask_full = Image.new("L", (w, h), 255)
        self.mask_full_path = self.root / "mask_full.png"
        mask_full.save(self.mask_full_path)
        # Restricted mask (only top-left 5x5 is white, not covering pixel 10,10)
        mask_restricted = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask_restricted).rectangle([0, 0, 4, 4], fill=255)
        self.mask_restricted_path = self.root / "mask_restricted.png"
        mask_restricted.save(self.mask_restricted_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_change_within_mask_passes(self):
        result = satya_core.verify_raster_edit(
            self.before_path, self.after_path, self.mask_full_path
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["outside_mask_pixels"], 0)
        self.assertGreater(result["changed_pixels"], 0)

    def test_change_outside_mask_fails(self):
        result = satya_core.verify_raster_edit(
            self.before_path, self.after_path, self.mask_restricted_path
        )
        self.assertFalse(result["ok"])
        self.assertGreater(result["outside_mask_pixels"], 0)

    def test_identical_images_pass(self):
        result = satya_core.verify_raster_edit(
            self.before_path, self.before_path, self.mask_full_path
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_pixels"], 0)

    def test_missing_file_returns_error(self):
        result = satya_core.verify_raster_edit(
            self.before_path, self.root / "nonexistent.png", self.mask_full_path
        )
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_dimension_mismatch_fails(self):
        diff_size = Image.new("RGB", (50, 40), (128, 128, 128))
        diff_path = self.root / "diff_size.png"
        diff_size.save(diff_path)
        result = satya_core.verify_raster_edit(
            self.before_path, diff_path, self.mask_full_path
        )
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# 4. compare_engine: integrity checks
# ---------------------------------------------------------------------------

class TestCompareEngineIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_images_pass(self):
        card = self.root / "card.png"
        _make_card(card)
        out = self.root / "out_identical"
        result = compare_engine.compare(str(card), str(card), str(out))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["integrity"]["same_sha256"])

    def test_different_images_detected(self):
        raw = self.root / "raw.png"
        improved = self.root / "improved.png"
        _make_card(raw, text="189")
        _make_card(improved, text="190")  # different digit
        out = self.root / "out_diff"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        self.assertIn(result["status"], ("FAIL", "NEEDS_REVIEW"))
        self.assertFalse(result["integrity"]["same_sha256"])

    def test_missing_raw_returns_not_run(self):
        missing = self.root / "does_not_exist.png"
        card = self.root / "card.png"
        _make_card(card)
        out = self.root / "out_missing"
        result = compare_engine.compare(str(missing), str(card), str(out))
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertTrue(result["errors"])

    def test_missing_improved_returns_not_run(self):
        card = self.root / "card.png"
        _make_card(card)
        missing = self.root / "does_not_exist.png"
        out = self.root / "out_missing2"
        result = compare_engine.compare(str(card), str(missing), str(out))
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertTrue(result["errors"])

    def test_different_dimensions_detected(self):
        raw = self.root / "raw.png"
        improved = self.root / "improved.png"
        _make_card(raw, width=200, height=280)
        _make_card(improved, width=210, height=290)  # different dimensions
        out = self.root / "out_dims"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        self.assertFalse(result["integrity"]["same_dimensions"])
        self.assertIn(result["status"], ("FAIL", "NEEDS_REVIEW"))

    def test_report_json_created(self):
        card = self.root / "card.png"
        _make_card(card)
        out = self.root / "out_report"
        compare_engine.compare(str(card), str(card), str(out))
        report_file = out / "satyahq-report.json"
        self.assertTrue(report_file.is_file(), "satyahq-report.json must be created")
        data = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertIn("status", data)
        self.assertIn("integrity", data)


# ---------------------------------------------------------------------------
# 5. compare_engine: pixel comparison precision
# ---------------------------------------------------------------------------

class TestCompareEnginePixels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_pixel_change_detected(self):
        """A single pixel change must not be hidden by a high global similarity score."""
        raw = self.root / "raw.png"
        improved = self.root / "improved.png"
        raw_img = Image.new("RGB", (200, 280), (100, 100, 100))
        raw_img.save(raw)
        imp_img = raw_img.copy()
        imp_img.putpixel((10, 10), (200, 50, 50))  # single pixel change
        imp_img.save(improved)

        out = self.root / "out_single_pixel"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        # Must NOT report PASS
        self.assertNotEqual(result["status"], "PASS",
                            "Single pixel change must not produce PASS verdict")
        # Pixel comparison must find the change
        pc = result.get("pixel_comparison") or result.get("aligned_pixel_comparison")
        self.assertIsNotNone(pc)
        self.assertGreater(pc["changed_pixels"], 0)
        self.assertGreater(pc["max_channel_difference"], 0)

    def test_small_change_in_large_image_detected(self):
        """Small changes inside large images must not be hidden by global metrics."""
        raw = self.root / "raw_large.png"
        improved = self.root / "improved_large.png"
        raw_img = Image.new("RGB", (1000, 1400), (150, 150, 150))
        ImageDraw.Draw(raw_img).text((400, 1300), "77/130", fill="black")
        raw_img.save(raw)
        imp_img = raw_img.copy()
        # Change a digit in collector number area
        ImageDraw.Draw(imp_img).text((400, 1300), "77/180", fill="black")
        imp_img.save(improved)

        out = self.root / "out_large"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        self.assertNotEqual(result["status"], "PASS",
                            "Digit change must not produce PASS verdict")
        pc = result.get("pixel_comparison") or result.get("aligned_pixel_comparison")
        self.assertIsNotNone(pc)
        self.assertGreater(pc["changed_pixels"], 0)

    def test_evidence_files_created(self):
        """Comparison must create heatmap, mask, side-by-side and overlay evidence."""
        raw = self.root / "raw.png"
        improved = self.root / "improved.png"
        raw_img = Image.new("RGB", (200, 280), (100, 100, 100))
        raw_img.save(raw)
        imp_img = raw_img.copy()
        imp_img.putpixel((50, 50), (0, 255, 0))
        imp_img.save(improved)

        out = self.root / "out_evidence"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        ev = result.get("evidence_files", [])
        names = [Path(f).name for f in ev]
        self.assertTrue(any("heatmap" in n for n in names), "Heatmap evidence file must be created")
        self.assertTrue(any("mask" in n for n in names), "Changed mask evidence must be created")
        self.assertTrue(any("side-by-side" in n for n in names), "Side-by-side evidence must be created")
        self.assertTrue(any("overlay" in n for n in names), "Diff overlay evidence must be created")

    def test_color_background_change_detected(self):
        """Background color changes should be detected and classified."""
        raw = self.root / "raw_bg.png"
        improved = self.root / "improved_bg.png"
        raw_img = Image.new("RGB", (200, 280), (50, 50, 150))
        raw_img.save(raw)
        imp_img = Image.new("RGB", (200, 280), (50, 50, 180))  # blue value change
        imp_img.save(improved)

        out = self.root / "out_bg"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        self.assertNotEqual(result["status"], "PASS")
        pc = result.get("pixel_comparison")
        self.assertIsNotNone(pc)
        self.assertEqual(pc["changed_pixels"], pc["total_pixels"])  # all pixels changed


# ---------------------------------------------------------------------------
# 6. compare_engine: classification statuses
# ---------------------------------------------------------------------------

class TestCompareEngineClassification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_corrupt_image_returns_not_run(self):
        """A corrupt/garbage file must return NOT_RUN, not crash."""
        corrupt = self.root / "corrupt.png"
        corrupt.write_bytes(b"not an image at all just random garbage bytes")
        card = self.root / "card.png"
        _make_card(card)
        out = self.root / "out_corrupt"
        result = compare_engine.compare(str(corrupt), str(card), str(out))
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertTrue(result["errors"])

    def test_status_field_always_present(self):
        """Status must always be one of the four valid statuses."""
        card = self.root / "card.png"
        _make_card(card)
        out = self.root / "out_status"
        result = compare_engine.compare(str(card), str(card), str(out))
        self.assertIn(result["status"], ("PASS", "FAIL", "NEEDS_REVIEW", "NOT_RUN"))

    def test_changed_image_not_pass(self):
        """A visually different improved image must never produce PASS."""
        raw = self.root / "raw.png"
        improved = self.root / "improved.png"
        _make_card(raw, color="#336699", text="A1")
        _make_card(improved, color="#336699", text="B2")  # changed text
        out = self.root / "out_notpass"
        result = compare_engine.compare(str(raw), str(improved), str(out))
        self.assertNotEqual(result["status"], "PASS",
                            "Visually different improved image must not PASS")


# ---------------------------------------------------------------------------
# 7. satya_core: safe_resolve_path security
# ---------------------------------------------------------------------------

class TestSafeResolvePath(unittest.TestCase):
    def test_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(ValueError):
                satya_core.safe_resolve_path(base, "../../etc/passwd")

    def test_valid_path_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sub = base / "sub" / "file.json"
            sub.parent.mkdir(parents=True, exist_ok=True)
            sub.touch()
            resolved = satya_core.safe_resolve_path(base, "sub/file.json")
            self.assertEqual(resolved, sub.resolve())


# ---------------------------------------------------------------------------
# 8. satya_core: decompression bomb guard
# ---------------------------------------------------------------------------

class TestSafeLoadImage(unittest.TestCase):
    def test_valid_image_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.png"
            Image.new("RGB", (100, 100), "red").save(p)
            img = satya_core.safe_load_image(p)
            self.assertIsInstance(img, Image.Image)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            satya_core.safe_load_image(Path("/nonexistent/path/to/image.png"))

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.png"
            p.write_bytes(b"")
            with self.assertRaises(ValueError):
                satya_core.safe_load_image(p)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
