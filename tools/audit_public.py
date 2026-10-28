"""Enumerate the explicit public package and reject private paths or source media."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    '.gitattributes', '.gitignore', '.nojekyll', 'README.md', 'WORKFLOW.md',
    'book-overview.html', 'index.html', 'references.html', 'source-map.html',
    'numerical-lab.html', 'numerical_lab.py', 'requirements.txt',
    'source-manifest.json', 'source-map.json', 'source-validation-summary.json',
    'content-inventory.json', 'completion.json', 'editorial-review-summary.json',
    'course-review.json', 'chapter-code-validation.json', 'reader-validation.json',
    'package-validation.json', 'public-package-validation.json',
    'source-free-validation.json', 'publication-validation.json',
}
TOOL_FILES = {'tools/'+name for name in (
    'build_book.py', 'check_chapter_code.py', 'update_metadata.py',
    'validate_books.py', 'audit_public.py', 'verify_source_free.py',
    'verify_publication.py')}
ASSET_FILES = {'assets/'+name for name in (
    'book.css', 'book.js', 'lab.js', 'site-preview.png', 'mathjax-tex-svg.js',
    'mathjax-LICENSE', 'input/tex/extensions/boldsymbol.js',
    'input/tex/extensions/cancel.js', 'input/tex/extensions/mathtools.js')}


def public_files(root=ROOT):
    result, errors = [], []
    for relative in sorted(ROOT_FILES | TOOL_FILES | ASSET_FILES):
        path = root / relative
        if path.is_file():
            result.append(path)
    for path in sorted(root.glob('chapter-*')):
        if path.name in ROOT_FILES:
            continue
        if re.fullmatch(r'chapter-\d{2}-[a-z0-9-]+\.(?:html|meta\.json)', path.name):
            result.append(path)
        else:
            errors.append('Unexpected chapter path: '+path.name)
    allowed = {p.relative_to(root).as_posix() for p in result}
    for pattern in ('chapter-??-*.html', 'chapter-??-*.meta.json'):
        if len(list(root.glob(pattern))) != 20:
            errors.append('Expected 20 files matching '+pattern)
    for relative in ('README.md', 'index.html', 'source-manifest.json',
                     'editorial-review-summary.json', 'assets/site-preview.png',
                     'assets/mathjax-tex-svg.js', 'assets/mathjax-LICENSE'):
        if relative not in allowed:
            errors.append('Missing required public file: '+relative)
    for path in root.iterdir():
        if path.is_file() and path.name not in allowed and path.name != 'README.txt':
            errors.append('Unrecognized root file: '+path.name)
    for path in result:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            errors.append('Public path escapes package: '+str(path.relative_to(root)))
        if path.suffix in ('.html', '.json', '.md', '.py'):
            source = path.read_bytes().decode('utf-8-sig')
            if re.search(r'[A-Z]:[\\/](?:Users|home)[\\/]|file:///[A-Za-z]|/(?:home|Users)/[A-Za-z0-9]', source):
                errors.append('Private absolute path: '+path.name)
            if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,})', source):
                errors.append('Credential-like string: '+path.name)
    if errors:
        raise ValueError('\n'.join(errors))
    return sorted(set(result))


def main():
    files = public_files()
    report = {'passed': True, 'file_count': len(files),
              'files': [p.relative_to(ROOT).as_posix() for p in files],
              'excluded': ['work/', 'README.txt', '.git/', '.venv/', '__pycache__/'],
              'scope': 'Explicit public inventory and private-path/credential-pattern checks; '
                       'not a general security audit.'}
    (ROOT / 'public-package-validation.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Public package:', len(files), 'files; privacy inventory passed')


if __name__ == '__main__':
    main()
