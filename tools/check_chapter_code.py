"""Execute authored Python listings and compare their displayed output."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def main():
    temporary_root = ROOT / 'work' / 'code-checks'
    temporary_root.mkdir(parents=True, exist_ok=True)
    records = []
    for chapter in sorted(ROOT.glob('chapter-*.html')):
        soup = BeautifulSoup(chapter.read_text(encoding='utf-8'), 'html.parser')
        for listing in soup.select('pre[data-run]'):
            identity = listing['data-run']
            code = listing.get_text()
            expected = soup.select_one(f'pre[data-output="{identity}"]')
            if expected is None:
                raise ValueError(f'{chapter.name}: output missing for {identity}')
            with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
                result = subprocess.run([sys.executable, '-I', '-c', code],
                                        cwd=directory, capture_output=True,
                                        text=True, timeout=90)
            passed = result.returncode == 0 and result.stdout.strip() == expected.get_text().strip()
            records.append({'chapter': chapter.name, 'listing': identity,
                            'code_sha256': hashlib.sha256(code.encode()).hexdigest(),
                            'returncode': result.returncode, 'passed': passed,
                            'stdout': result.stdout, 'stderr': result.stderr})
            print(chapter.name, identity, 'PASS' if passed else 'FAIL')
    report = {'scope': 'Actual isolated execution of authored listings; numerical checks are not a proof audit.',
              'passed': bool(records) and all(r['passed'] for r in records),
              'listing_count': len(records), 'results': records}
    (ROOT / 'chapter-code-validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
