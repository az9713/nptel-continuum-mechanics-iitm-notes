"""Rebuild and test a public-only copy without recordings, ASR or editorial work files."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from audit_public import ROOT, public_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--git', action='store_true', help='Export committed HEAD using git archive')
    args = parser.parse_args()
    parent = ROOT / 'work' / 'source-free'
    parent.mkdir(parents=True, exist_ok=True)
    export = Path(tempfile.mkdtemp(prefix='export-', dir=parent))
    files = public_files()
    commit = None
    if args.git:
        committed = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
        tracked = set(committed.decode('utf-8').strip('\0').split('\0'))
        allowed = {p.relative_to(ROOT).as_posix() for p in files}
        if tracked != allowed:
            raise ValueError('Git inventory differs from the explicit public package')
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        archive = subprocess.check_output(['git', 'archive', '--format=tar', 'HEAD'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(export, filter='data')
    else:
        for source in files:
            target = export / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    before = {p.name: sha(p) for p in export.glob('*.html')}
    commands = [
        ['tools/build_book.py'], ['tools/check_chapter_code.py'], ['numerical_lab.py'],
        ['tools/validate_books.py'] + (['--browser'] if args.browser else []),
        ['tools/audit_public.py'],
    ]
    environment = os.environ.copy()
    temporary = export / 'work' / 'tmp'
    temporary.mkdir(parents=True)
    environment.update(TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE='1')
    results = []
    for command in commands:
        run = subprocess.run([sys.executable, *command], cwd=export, env=environment,
                             capture_output=True, text=True, timeout=240)
        results.append({'command': 'python '+' '.join(command),
                        'returncode': run.returncode, 'stdout': run.stdout,
                        'stderr': run.stderr})
    changed = [name for name, digest in before.items() if sha(export / name) != digest]
    passed = not changed and all(r['returncode'] == 0 for r in results)
    report = {
        'passed': passed, 'public_file_count': len(files), 'html_count': len(before),
        'byte_identical_html_rebuild': not changed, 'changed_html': changed,
        'raw_source_files_available': False, 'browser_checks_requested': args.browser,
        'git_archive_commit': commit,
        'export_method': 'git archive HEAD' if args.git else 'fresh allowlisted file copy',
        'scope': 'A source-free export inside ignored work/; no acquisition sources or '
                 'private review reports copied. Existing Python packages and installed Chrome '
                 'are used; this is not a pristine-machine dependency installation test.',
        'html_sha256': before, 'checks': results,
    }
    (ROOT / 'source-free-validation.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Source-free export:', passed, '; byte-identical HTML:', len(before)-len(changed))
    if not passed:
        print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
