"""Search candidate metadata without loading the whole image library."""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?', default='')
    parser.add_argument('--status', choices=['unverified', 'verified', 'rejected'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / 'references/icon-catalog.json').read_text(encoding='utf-8'))
    matches = [a for a in catalog['assets']
               if args.query.casefold() in (a['name'] + ' ' + a['id'] + ' ' + a['category']).casefold()
               and (args.status is None or a['status'] == args.status)]
    print(json.dumps(matches, indent=2))

if __name__ == '__main__':
    main()
