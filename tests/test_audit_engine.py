import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1]/'plugins/card-review-toolkit/skills/card-proofreader/scripts/audit_engine.py'
spec = importlib.util.spec_from_file_location('audit_engine', SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        im = Image.new('RGB', (200, 280), '#778899')
        ImageDraw.Draw(im).text((8, 245), 'I 189', fill='white')
        self.a, self.b = self.root/'a.png', self.root/'b.png'
        im.save(self.a); im.save(self.b)
        self.geo = {r: [[0, 0], [199, 0], [199, 279], [0, 279]] for r in ['original', 'enhanced']}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, cache='cache', **kwargs):
        return engine.prepare(self.a, self.b, self.root/cache, geometry=self.geo, **kwargs)

    def test_complete_coverage_with_overlap(self):
        for template in ['grid-v1', 'standard-v1', 'full-art-v1']:
            covered = np.zeros((1400, 1000), bool)
            for _, box in engine.regions(template):
                x0, y0, x1, y1 = engine.bounds(box)
                covered[y0:y1, x0:x1] = True
            self.assertTrue(covered.all())

    def test_determinism_cache_and_corruption(self):
        first = self.prepare()
        second = self.prepare()
        self.assertFalse(first['cache_hit']); self.assertTrue(second['cache_hit'])
        m = engine.read(first['manifest'])
        fresh = engine.read(self.prepare('fresh')['manifest'])
        self.assertEqual(m['artifacts'], fresh['artifacts'])
        out = Path(first['manifest']).parent
        (out/'sheet-01.png').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): self.prepare()

    def test_changed_input_and_template_invalidate_cache(self):
        first = self.prepare()
        im = Image.open(self.b).copy(); im.putpixel((3, 3), (255, 0, 0)); im.save(self.b)
        self.assertNotEqual(first['manifest'], self.prepare()['manifest'])
        self.assertNotEqual(self.prepare()['manifest'], self.prepare(template='standard-v1')['manifest'])

    def test_native_crops_preserve_pixels(self):
        m = engine.read(self.prepare()['manifest'])
        out = self.root/'cache'/m['key']
        original = np.array(Image.open(self.a))
        for region in m['regions']:
            e = region['evidence']['original']
            x0,y0,x1,y1 = e['source_box']
            np.testing.assert_array_equal(np.array(Image.open(out/e['native_crop'])), original[y0:y1,x0:x1])

    def test_completion_requires_review_and_marks(self):
        result = self.prepare(); p = Path(result['manifest']); m = engine.read(p)
        review = p.parent/'review.json'; r = engine.read(review)
        self.assertFalse(engine.check(p, review)['complete'])
        r['geometry_confirmed'] = True
        r['identity'] = {role: {'card_id': '189', 'evidence': 'Synthetic fixture identity'} for role in ['original', 'enhanced']}
        r['text_extraction'] = {'mode': 'visual', 'ocr_unavailable_reason': 'Synthetic unit fixture, no OCR inference', 'visual_sweep_complete': True, 'evidence': 'Synthetic fixture only'}
        r['numeric_fields'] = {f: {'absent_in_both': True, 'evidence': 'Synthetic fixture only'} for f in engine.text_inventory.FIELDS}
        r['numeric_fields']['collector_number'] = {'item_ids': ['number'], 'evidence': 'Synthetic footer'}
        for region in m['regions']:
            r['regions'][region['id']] = {'opened': True, 'evidence': 'Synthetic test only', 'no_printed_content': True}
        r['regions'][m['regions'][-1]['id']] = {'opened': True, 'evidence': 'Synthetic footer', 'items': [{
            'id': 'number', 'kind': 'text', 'typography': {'status':'matched','original_evidence':'Synthetic original','enhanced_evidence':'Synthetic enhanced','description':'Synthetic matching glyphs'},  'original': '189', 'enhanced': '189',
            'numeric_review': 'checked', 'numeric_evidence': 'Synthetic fixture',
            'original_case': '---', 'enhanced_case': '---', 'evidence': 'Synthetic fixture',
            'checks': {c: 'checked' for c in engine.CHECKS}}]}
        r['reverse_sweep'] = {'region_ids': [x['id'] for x in reversed(m['regions'])], 'evidence': 'Synthetic fixture'}
        for region in r['regions'].values():
            region['inventory_reconciliation'] = {role: {'status': 'verified', 'item_ids': [i['id'] for i in region.get('items', [])], 'evidence': 'Synthetic fixture'} for role in ['original', 'enhanced']}
            for item in region.get('items', []):
                item['readings'] = {role: {'literal': item[role], 'status': 'verified', 'legibility': 'clear', 'character_pass': True, 'evidence': 'Synthetic fixture'} for role in ['original', 'enhanced']}
        engine.write(review, r); self.assertTrue(engine.check(p, review)['complete'])
        reading = r['regions'][m['regions'][-1]['id']]['items'][0]['readings']['original']
        reading['status'] = 'unresolved'; engine.write(review, r)
        self.assertFalse(engine.check(p, review)['full_fidelity_established'])
        reading['status'] = 'verified'

        checks = r['regions'][m['regions'][-1]['id']]['items'][0]['checks']
        checks['case'] = 'different'; engine.write(review, r)
        self.assertFalse(engine.check(p, review)['full_fidelity_established'])
        checks['case'] = 'checked'
        checks['marks'] = 'not checked'; engine.write(review, r)
        self.assertFalse(engine.check(p, review)['complete'])
        checks['marks'] = 'unresolved'; engine.write(review, r)
        status = engine.check(p, review)
        self.assertTrue(status['complete']); self.assertFalse(status['full_fidelity_established'])
        r['key'] = 'other'; engine.write(review, r)
        self.assertFalse(engine.check(p, review)['complete'])

    def test_bad_geometry_rejected(self):
        for q in [[[0, 0]]*4, [[0,0],[0,279],[199,279],[199,0]], [[-1,0],[199,0],[199,279],[0,279]]]:
            with self.assertRaises(ValueError): engine.validate_quad(q, (200,280))

    def test_detail_tiles_created_and_unknown_rejected(self):
        p = self.prepare()['manifest']
        files = engine.detail(p, 'r05c1')
        self.assertTrue(files)
        self.assertTrue(all(Path(f).is_file() for f in files))
        with self.assertRaises(ValueError): engine.detail(p, 'no-such-region')

    def test_exif_orientation_and_geometry_key(self):
        im = Image.new('RGB', (40, 60), 'white')
        exif = Image.Exif(); exif[274] = 6
        f = self.root/'rotated.jpg'; im.save(f, exif=exif)
        self.assertEqual(engine.load(f).size, (60, 40))
        first = self.prepare()
        self.geo['original'][0] = [1, 1]
        self.assertNotEqual(first['manifest'], self.prepare()['manifest'])


if __name__ == '__main__':
    unittest.main()
