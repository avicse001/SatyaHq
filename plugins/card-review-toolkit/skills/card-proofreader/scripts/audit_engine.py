"""Deterministic preparation and evidence bookkeeping, not automatic proofreading."""
import argparse
import hashlib
import json
import math
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import text_inventory

import cv2
import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageOps

VERSION = '1.5.0'
SIZE = (1000, 1400)
CHECKS = ('characters', 'case', 'marks', 'punctuation_spacing', 'symbols')
STATUSES = ('checked', 'different', 'unresolved', 'not applicable')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB')


def validate_quad(points, size):
    q = np.asarray(points, dtype=np.float32)
    w, h = size
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise ValueError('Corners must be four finite [x,y] points: TL, TR, BR, BL.')
    if np.any(q < 0) or np.any(q[:, 0] > w - 1) or np.any(q[:, 1] > h - 1):
        raise ValueError('Corners outside EXIF-oriented image.')
    edges = [q[(i+1)%4]-q[i] for i in range(4)]
    cross = [float(edges[i][0]*edges[(i+1)%4][1]-edges[i][1]*edges[(i+1)%4][0]) for i in range(4)]
    if min(cross) <= 0 or cv2.contourArea(q) < w*h*.05:
        raise ValueError('Corners must be clockwise, convex and enclose at least 5% of image.')
    if q[0, 1]+q[1, 1] >= q[2, 1]+q[3, 1] or q[0, 0]+q[3, 0] >= q[1, 0]+q[2, 0]:
        raise ValueError('Corner order must start at top left.')
    return q


def propose_quad(im):
    """Conservative geometric proposal; always requires visual confirmation."""
    w, h = im.size
    # An already card-shaped canvas is safer than an inner artwork contour
    # which could omit border printing. Still a visually checked proposal.
    if .69 <= w/h <= .74:
        return np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]]), 'card-shaped full-frame proposal'
    scale = min(1, 900/max(w, h))
    a = np.array(im.resize((round(w*scale), round(h*scale))))
    edge = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), 40, 120)
    edge = cv2.morphologyEx(edge, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edge, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        poly = cv2.approxPolyDP(contour, .025*cv2.arcLength(contour, True), True)
        if len(poly) != 4 or not cv2.isContourConvex(poly):
            continue
        pts = poly[:, 0, :].astype(np.float32)/scale
        center = pts.mean(axis=0)
        pts = pts[np.argsort(np.arctan2(pts[:, 1]-center[1], pts[:, 0]-center[0]))]
        pts = np.roll(pts, -int(np.argmin(pts.sum(axis=1))), axis=0)
        pts[:, 0] = np.clip(pts[:, 0], 0, w-1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h-1)
        width = (np.linalg.norm(pts[1]-pts[0])+np.linalg.norm(pts[2]-pts[3]))/2
        height = (np.linalg.norm(pts[3]-pts[0])+np.linalg.norm(pts[2]-pts[1]))/2
        area = cv2.contourArea(pts)
        if .55 <= width/height <= .85 and area >= w*h*.3:
            try:
                validate_quad(pts, (w, h))
                candidates.append((area, pts))
            except ValueError:
                pass
    if candidates:
        candidates.sort(key=lambda x: (-x[0], tuple(x[1].flatten())))
        return candidates[0][1], 'detected proposal'
    return np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]]), 'full-frame fallback; may include photo margins'


def regions(template):
    # Each template covers the ENTIRE card. No artwork region is silently omitted.
    breaks = {'standard-v1': [0, .14, .32, .50, .66, .80, .90, 1],
              'full-art-v1': [0, .14, .35, .57, .76, .84, .90, .95, 1],
              'grid-v1': [0, .2, .4, .6, .8, 1]}[template]
    result = []
    for row, (top, bottom) in enumerate(zip(breaks, breaks[1:])):
        for col in range(2):
            result.append((f'r{row+1:02}c{col+1}', [max(0, col*.5-.015), max(0, top-.012),
                                                   min(1, (col+1)*.5+.015), min(1, bottom+.012)]))
    return result


def bounds(box):
    return [math.floor(box[0]*SIZE[0]), math.floor(box[1]*SIZE[1]),
            math.ceil(box[2]*SIZE[0]), math.ceil(box[3]*SIZE[1])]


def crop_pair(images, inverses, box, out, prefix):
    b = bounds(box)
    corners = np.float32([[b[0], b[1]], [b[2]-1, b[1]], [b[2]-1, b[3]-1], [b[0], b[3]-1]])
    result = {}
    for role, im in images.items():
        points = cv2.perspectiveTransform(corners[None], inverses[role])[0]
        x0, y0 = np.floor(points.min(axis=0)).astype(int)
        x1, y1 = np.ceil(points.max(axis=0)).astype(int)+1
        raw_box = [max(0, int(x0)), max(0, int(y0)), min(im.width, int(x1)), min(im.height, int(y1))]
        path = f'{prefix}-{role}-native.png'
        im.crop(raw_box).save(out/path)
        result[role] = {'native_crop': path, 'source_box': raw_box, 'source_polygon': points.tolist()}
    return result


def prepare(original, enhanced, cache, template='grid-v1', geometry=None):
    started = time.perf_counter()
    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    files = {'original': Path(original), 'enhanced': Path(enhanced)}
    key_data = {'engine': VERSION, 'script_hash': digest(__file__), 'template': template,
                'inputs': {k: digest(v) for k, v in files.items()}, 'geometry': geometry,
                'runtime': {'pillow': PIL.__version__, 'opencv': cv2.__version__, 'numpy': np.__version__}}
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    out = Path(cache)/key
    manifest_path = out/'manifest.json'
    if manifest_path.exists():
        m = read(manifest_path)
        if m.get('key') == key and m.get('artifacts') and all((out/p).is_file() and digest(out/p) == h for p, h in m['artifacts'].items()):
            return {'manifest': str(manifest_path.resolve()), 'cache_hit': True, 'seconds': round(time.perf_counter()-started, 3)}
        raise ValueError('Cached artifacts changed or missing. Use a fresh cache directory; do not trust prior review.')
    out.mkdir(parents=True, exist_ok=True)
    images = {k: load(v) for k, v in files.items()}
    warped, inverses, mapping = {}, {}, {}
    dest = np.float32([[0, 0], [SIZE[0]-1, 0], [SIZE[0]-1, SIZE[1]-1], [0, SIZE[1]-1]])
    overview = Image.new('RGB', (1000, 760), 'white')
    for n, (role, im) in enumerate(images.items()):
        if geometry is not None:
            q, method = validate_quad(geometry[role], im.size), 'supplied geometry'
        else:
            q, method = propose_quad(im)
        transform = cv2.getPerspectiveTransform(q, dest)
        inverses[role] = np.linalg.inv(transform)
        warped[role] = Image.fromarray(cv2.warpPerspective(np.array(im), transform, SIZE))
        warped[role].save(out/f'{role}-aligned.png')
        display = im.copy()
        draw = ImageDraw.Draw(display)
        draw.line([tuple(x) for x in q]+[tuple(q[0])], fill='red', width=max(2, im.width//250))
        display.thumbnail((490, 710))
        overview.paste(display, (n*500, 30))
        ImageDraw.Draw(overview).text((n*500+5, 5), role+' - inspect card outline', fill='black')
        mapping[role] = {'corners': q.tolist(), 'method': method, 'inverse': inverses[role].tolist(),
                         'size': list(im.size), 'path': str(files[role].resolve())}
    overview.save(out/'geometry.png')
    items = []
    for rid, box in regions(template):
        evidence = crop_pair(images, inverses, box, out, rid)
        for role in images:
            path = f'{rid}-{role}-aligned.png'
            warped[role].crop(bounds(box)).save(out/path)
            evidence[role]['aligned_crop'] = path
        items.append({'id': rid, 'box': box, 'evidence': evidence})
    # Two paired rows/page, thumbnails NEVER stand in for unreadable native evidence.
    sheets = []
    for start in range(0, len(items), 2):
        selected = items[start:start+2]
        heights = [bounds(i['box'])[3]-bounds(i['box'])[1]+35 for i in selected]
        sheet = Image.new('RGB', (1100, sum(heights)), '#dddddd')
        y = 0
        for item, height in zip(selected, heights):
            for n, role in enumerate(images):
                ImageDraw.Draw(sheet).text((n*550+4, y+2), item['id']+' '+role, fill='black')
                sheet.paste(warped[role].crop(bounds(item['box'])), (n*550+4, y+25))
            y += height
        name = f'sheet-{start//2+1:02}.png'
        sheet.save(out/name)
        sheets.append(name)
    artifacts = {p.name: digest(p) for p in sorted(out.glob('*.png'))}
    m = {'key': key, 'provenance': key_data, 'mapping': mapping, 'geometry_status': 'needs visual confirmation',
         'sheets': sheets, 'regions': items, 'artifacts': artifacts,
         'note': 'Preparation is not inspection. Native crops are EXIF-oriented, unwarped pixel evidence.'}
    write(manifest_path, m)
    review_path = out/'review.json'
    if not review_path.exists():
        write(review_path, {'key': key, 'geometry_confirmed': False, 'identity': {}, 'regions': {}, 'findings': []})
    return {'manifest': str(manifest_path.resolve()), 'cache_hit': False, 'seconds': round(time.perf_counter()-started, 3), 'sheets': len(sheets)}


def check(manifest, review):
    m, r = read(manifest), read(review)
    issues = []
    if r.get('key') != m['key']:
        issues.append('Review belongs to a different preparation.')
    out = Path(manifest).parent
    for p, h in m['artifacts'].items():
        if not (out/p).is_file() or digest(out/p) != h:
            issues.append('Missing/changed evidence: '+p)
    for role, info in m['mapping'].items():
        if not Path(info['path']).is_file() or digest(info['path']) != m['provenance']['inputs'][role]:
            issues.append('Source missing/changed: '+role)
    if r.get('geometry_confirmed') is not True:
        issues.append('Geometry has not been visually confirmed.')
    for role in ['original', 'enhanced']:
        identity = r.get('identity', {}).get(role, {})
        if not identity.get('card_id') or not identity.get('evidence'):
            issues.append('Missing independent card ID reading/evidence: '+role)
    pending, unresolved, differences = [], [], []
    for region in m['regions']:
        rid = region['id']
        entry = r.get('regions', {}).get(rid, {})
        if not entry.get('opened') or not entry.get('evidence'):
            pending.append(rid)
            continue
        if entry.get('no_printed_content') is True:
            continue
        entries = entry.get('items', [])
        if not entries:
            pending.append(rid)
        for item in entries:
            if not item.get('id') or not item.get('evidence') or any(item.get('checks', {}).get(c) not in STATUSES for c in CHECKS):
                pending.append(rid)
            if item.get('kind') == 'text' and any(k not in item for k in ['original', 'enhanced', 'original_case', 'enhanced_case']):
                pending.append(rid)
            if 'unresolved' in item.get('checks', {}).values():
                unresolved.append(rid+':'+str(item.get('id')))
            if 'different' in item.get('checks', {}).values():
                differences.append(rid+':'+str(item.get('id')))
    if pending:
        issues.append('Unexamined/incomplete regions: '+', '.join(sorted(set(pending))))
    # Identity uncertainty also prevents a full-fidelity verdict.
    for role, identity in r.get('identity', {}).items():
        if identity.get('card_id') == 'unresolved':
            unresolved.append(role+':card ID')
    text_report = text_inventory.validate(m, r, out)
    protocol = text_inventory.verify_protocol(m, r)
    issues.extend(protocol['issues'])
    unresolved.extend(protocol['unresolved'])
    issues.extend(text_report['issues'])
    unresolved.extend(text_report['unresolved'])
    differences.extend(x['id'] for x in text_report['literal_differences'])
    return {'complete': not issues, 'full_fidelity_established': not issues and not unresolved and not differences and not r.get('findings'),
            'text_comparison': text_report,
            'legibility_flags': protocol['legibility_flags'],
            'typography_flags': protocol['typography_flags'],
            'regions': len(m['regions']), 'unexamined_regions': sorted(set(pending)),
            'unresolved': unresolved, 'different_items': differences, 'issues': issues,
            'note': 'Checks evidence bookkeeping, not whether visual judgments are correct.'}


def detail(manifest, region_id):
    m = read(manifest)
    region = next((x for x in m['regions'] if x['id'] == region_id), None)
    if region is None:
        raise ValueError('Unknown region ID')
    out = Path(manifest).parent
    result = []
    for role in ['original', 'enhanced']:
        path = out/region['evidence'][role]['native_crop']
        if digest(path) != m['artifacts'][path.name]:
            raise ValueError('Native evidence changed')
        im = load(path)
        # Bounded, overlapping native tiles; no text is dropped between tiles.
        for y in range(0, im.height, 120):
            for x in range(0, im.width, 260):
                crop = im.crop((x, y, min(x+300, im.width), min(y+160, im.height)))
                name = f'{region_id}-{role}-detail-{y:04}-{x:04}.png'
                crop.resize((crop.width*3, crop.height*3), Image.Resampling.NEAREST).save(out/name)
                result.append(str(out/name))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('original'); p.add_argument('enhanced')
    p.add_argument('--cache', required=True)
    p.add_argument('--template', choices=['grid-v1', 'standard-v1', 'full-art-v1'], default='grid-v1')
    p.add_argument('--geometry', help='JSON with original/enhanced TL,TR,BR,BL corners in EXIF-oriented pixels')
    p = sub.add_parser('check'); p.add_argument('manifest'); p.add_argument('review')
    p = sub.add_parser('detail'); p.add_argument('manifest'); p.add_argument('region')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.original, args.enhanced, args.cache, args.template, read(args.geometry) if args.geometry else None)
        elif args.command == 'check':
            result = check(args.manifest, args.review)
        else:
            result = detail(args.manifest, args.region)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == 'check' and not result['complete'] else 0
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
