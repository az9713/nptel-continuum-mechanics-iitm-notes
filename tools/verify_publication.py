"""Check served book bytes, live reader behavior and the GitHub README preview."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import tempfile
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from audit_public import ROOT, public_files


def fetch(url):
    request = Request(url, headers={'User-Agent': 'Continuum-notes-publication-check/1.0',
                                    'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=40) as response:
        return response.read()


def browser_checks(base):
    from playwright.sync_api import sync_playwright
    temporary = ROOT / 'work' / 'publication-browser'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(temporary), TMP=str(temporary))
    tempfile.tempdir = str(temporary)
    pages = ['index.html', 'chapter-01-continuum-tensors-index-notation.html',
             'chapter-08-deformation-and-strain.html',
             'chapter-15-linear-fluids-and-navier-stokes.html', 'numerical-lab.html']
    results = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel='chrome')
        except Exception:
            browser = playwright.chromium.launch()
        for width in (1440, 390):
            context = browser.new_context(viewport={'width': width, 'height': 1000})
            page = context.new_page()
            for filename in pages:
                response = page.goto(base+filename)
                page.wait_for_function('!window.MathJax || !!MathJax.startup?.promise')
                page.evaluate('async () => {if(window.MathJax) await MathJax.startup.promise}')
                math_count = page.locator('mjx-container').count()
                math_errors = page.locator('mjx-merror,[data-mml-node="merror"]').count()
                overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth+2')
                page.locator('#theme-toggle').click()
                theme = page.locator('body.light').count() == 1
                page.locator('#theme-toggle').click()
                page.locator('#text-toggle').click()
                text = page.locator('body.large-text').count() == 1
                page.locator('#text-toggle').click()
                page.locator('#solutions-toggle').click()
                solutions = (page.locator('article details').count()
                             == page.locator('article details[open]').count())
                page.locator('#solutions-toggle').click()
                extra = True
                if filename == 'index.html':
                    page.locator('#lecture-search').fill('hyperelasticity')
                    extra = page.locator('[data-lecture]:visible').count() == 1
                    page.locator('#lecture-search').fill('')
                if filename == 'numerical-lab.html':
                    page.locator('#lab-shear').fill('0')
                    page.locator('#lab-angle').fill('90')
                    extra = 'ε₁₁ = -1.0000' in page.locator('#lab-metrics').inner_text()
                passed = (response.status == 200 and not overflow and not math_errors
                          and (filename == 'index.html' or math_count > 0)
                          and all((theme, text, solutions, extra)))
                results.append({'page': filename, 'width': width, 'passed': passed,
                                'math_count': math_count, 'math_errors': math_errors,
                                'horizontal_overflow': overflow, 'theme': theme,
                                'text_size': text, 'solutions': solutions,
                                'page_specific_controls': extra})
            context.close()
        browser.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='https://az9713.github.io/nptel-continuum-mechanics-iitm-notes/')
    parser.add_argument('--repo', default='https://github.com/az9713/nptel-continuum-mechanics-iitm-notes')
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    base = args.base.rstrip('/')+'/'
    exclusions = {
        'publication-validation.json': 'This report cannot contain a verifiable hash of itself.',
        'completion.json': 'Completion is finalized after the first successful publication probe.',
    }
    records = []
    for path in public_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in exclusions:
            continue
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        error, actual = None, None
        for attempt in range(3):
            try:
                actual = hashlib.sha256(fetch(base+quote(relative))).hexdigest()
                if actual == expected:
                    break
                error = 'served bytes differ'
            except Exception as exception:
                error = str(exception)
            if attempt < 2:
                time.sleep(2)
        records.append({'path': relative, 'sha256': expected, 'served_sha256': actual,
                        'passed': actual == expected, 'error': None if actual == expected else error})
    reader = browser_checks(base) if args.browser else []
    preview_error, preview = None, False
    try:
        document = BeautifulSoup(fetch(args.repo), 'html.parser')
        for image in document.find_all('img', alt='Preview of the continuum mechanics textbook'):
            link = image.find_parent('a')
            if link and link.get('href') == base:
                preview = True
    except Exception as exception:
        preview_error = str(exception)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    passed = all(r['passed'] for r in records) and preview and all(r['passed'] for r in reader)
    report = {'passed': passed, 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'base_url': base, 'repository_url': args.repo, 'payload_commit': commit,
              'served_file_count': len(records), 'files': records,
              'excluded_from_served_hashes': exclusions,
              'live_reader': reader, 'github_readme_preview_links_to_book': preview,
              'preview_error': preview_error,
              'scope': 'Exact public payload bytes, representative desktop/mobile browser controls, '
                       'and rendered GitHub README image/link. No new audiovisual or mathematical review.'}
    (ROOT / 'publication-validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Publication:', passed, '; served files:', len(records), '; live reader checks:', len(reader))
    if not passed:
        print(json.dumps({'files': [r for r in records if not r['passed']],
                          'reader': [r for r in reader if not r['passed']],
                          'preview': preview, 'preview_error': preview_error}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
