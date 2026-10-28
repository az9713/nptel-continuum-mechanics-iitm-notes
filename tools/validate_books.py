"""Check coverage, body integrity, local links and actual offline reader behavior."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup
from build_book import original_body, read

ROOT = Path(__file__).resolve().parents[1]


def static_checks():
    errors = []
    manifest = json.loads((ROOT / 'source-manifest.json').read_text(encoding='utf-8'))
    durations = {r['id']: r['duration'] for r in manifest['lectures']}
    if len(durations) != 66 or len(manifest['lectures']) != 66:
        errors.append('Expected 66 distinct recording identities')
    if len(manifest['chapters']) != 20:
        errors.append('Expected 20 chapters')
    paths = sorted(ROOT.glob('*.html'))
    documents = {p: BeautifulSoup(read(p), 'html.parser') for p in paths}
    editorial_path = ROOT / 'editorial-review-summary.json'
    editorial = json.loads(read(editorial_path)) if editorial_path.exists() else None
    timestamps = 0
    for path, soup in documents.items():
        source = read(path)
        if path.name.startswith('chapter-'):
            chapter_number = int(path.name.split('-')[1])
            expected = {r['id'] for r in manifest['lectures']
                        if r['chapter_order'] == chapter_number}
            sidecar = json.loads(read(path.with_suffix('.meta.json')))
            body_sha = hashlib.sha256(original_body(source).encode('utf-8')).hexdigest()
            if body_sha != sidecar['authored_body_sha256']:
                errors.append(f'{path.name}: stale provenance sidecar digest')
            if editorial:
                review = next((r for r in editorial['chapters']
                               if r['chapter'] == chapter_number), None)
                if (not review or review['authored_body_sha256'] != body_sha
                        or len(review['reviews']) != 2
                        or any(r['verdict'] != 'accepted'
                               or r['authored_body_sha256'] != body_sha
                               for r in review['reviews'])):
                    errors.append(f'{path.name}: stale or missing scientific acceptance')
            if {r['video_id'] for r in sidecar['recordings']} != expected:
                errors.append(f'{path.name}: recording assignment differs')
            for heading in soup.select('h2[data-video]'):
                video = heading['data-video']
                start, end = int(heading['data-start']), int(heading['data-end'])
                if video not in expected or not 0 <= start < end <= durations[video]:
                    errors.append(f'{path.name}: invalid provenance span')
        ids = [x['id'] for x in soup.select('[id]')]
        if len(ids) != len(set(ids)):
            errors.append(f'{path.name}: duplicate IDs')
        try:
            original_body(source)
        except ValueError as error:
            errors.append(f'{path.name}: {error}')
        if re.search(r'[A-Z]:[\\/](?:Users|home)|file:///|/home/|/Users/', source):
            errors.append(f'{path.name}: private path')
        if re.search(r'\[(?:PROOF NEEDED|CITATION NEEDED|NUMBER NOT|AUTHOR DECISION)', source):
            errors.append(f'{path.name}: unresolved placeholder')
        for node in soup.select('[href], [src]'):
            url = node.get('href') or node.get('src')
            parsed = urlsplit(url)
            if parsed.scheme in ('mailto', 'data'):
                continue
            if parsed.netloc:
                if 'youtube.com' in parsed.netloc and parsed.query:
                    query = parse_qs(parsed.query)
                    if 't' in query:
                        video_id = query.get('v', [''])[0]
                        time = int(query['t'][0].removesuffix('s'))
                        if video_id not in durations or not 0 <= time < durations[video_id]:
                            errors.append(f'{path.name}: timestamp out of bounds {url}')
                        timestamps += 1
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_relative_to(ROOT) or not target.is_file():
                errors.append(f'{path.name}: broken local link {url}')
            elif parsed.fragment and target.suffix == '.html':
                target_soup = documents.get(target)
                if target_soup is None or target_soup.find(id=unquote(parsed.fragment)) is None:
                    errors.append(f'{path.name}: missing anchor {url}')
    return {'passed': not errors, 'html_count': len(paths),
            'timestamp_count': timestamps, 'failures': errors}


def browser_checks():
    import os
    import tempfile
    from playwright.sync_api import sync_playwright
    records, failures = [], []
    paths = [ROOT / 'index.html', *sorted(ROOT.glob('chapter-*.html')),
             ROOT / 'source-map.html', ROOT / 'references.html', ROOT / 'numerical-lab.html']
    screenshot_dir = ROOT / 'work' / 'screenshots'
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / 'work' / 'browser-tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = str(temporary)
    os.environ['TMP'] = str(temporary)
    tempfile.tempdir = str(temporary)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel='chrome')
        except Exception:
            browser = playwright.chromium.launch()
        for width in (1440, 390):
            context = browser.new_context(viewport={'width': width, 'height': 1000})
            context.route('http://**/*', lambda route: route.abort())
            context.route('https://**/*', lambda route: route.abort())
            page = context.new_page()
            page_errors = []
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            for path in paths:
                if not path.exists():
                    failures.append(f'{path.name}: missing page')
                    continue
                page.goto(path.as_uri())
                page.wait_for_function('!window.MathJax || !!MathJax.startup?.promise')
                page.evaluate('async () => {if(window.MathJax) await MathJax.startup.promise}')
                math_count = page.locator('mjx-container').count()
                expected_math = path.name.startswith('chapter-') or path.name == 'numerical-lab.html'
                math_errors = page.locator('mjx-merror, [data-mml-node="merror"]').count()
                overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
                page.locator('#theme-toggle').click()
                theme = page.locator('body.light').count() == 1
                page.locator('#theme-toggle').click()
                page.locator('#solutions-toggle').click()
                solution_count = page.locator('article details').count()
                solutions_open = page.locator('article details[open]').count() == solution_count
                page.locator('#solutions-toggle').click()
                page.locator('#text-toggle').click()
                text_size = page.locator('body.large-text').count() == 1
                page.locator('#text-toggle').click()
                extras = True
                if path.name == 'index.html':
                    page.locator('#lecture-search').fill('hyperelasticity')
                    extras = page.locator('[data-lecture]:visible').count() == 1
                    page.locator('#lecture-search').fill('')
                    extras = extras and page.locator('[data-lecture]:visible').count() == 20
                if path.name.startswith('chapter-01-'):
                    page.locator('.copy-code').first.click()
                    extras = page.locator('.copy-code').first.inner_text() == 'Copied'
                    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
                    extras = extras and page.locator('article details[open]').count() == solution_count
                    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
                    extras = extras and page.locator('article details[open]').count() == 0
                if path.name == 'numerical-lab.html':
                    page.locator('#lab-shear').fill('0')
                    page.locator('#lab-angle').fill('90')
                    metrics = page.locator('#lab-metrics').inner_text()
                    extras = ('E₂₂ = 0.0000' in metrics and 'ε₁₁ = -1.0000' in metrics
                              and 'ε₂₂ = -1.0000' in metrics)
                record = {'page': path.name, 'width': width, 'math_errors': math_errors,
                          'rendered_math_count': math_count,
                          'horizontal_overflow': overflow, 'theme': theme,
                          'solutions': solutions_open, 'text_size': text_size,
                          'page_specific_controls': extras}
                records.append(record)
                if (math_errors or overflow or (expected_math and not math_count)
                        or not all((theme, solutions_open, text_size, extras))):
                    failures.append(record)
                if path.name == 'index.html' or path.name.startswith('chapter-01-'):
                    page.screenshot(path=str(screenshot_dir / f'{path.stem}-{width}.png'), full_page=False)
            if page_errors:
                failures.append({'width': width, 'javascript_errors': page_errors})
            context.close()
        browser.close()
    return {'passed': not failures, 'scope': 'Offline Chromium, desktop and mobile widths; automated behavior, not human accessibility certification.',
            'results': records, 'failures': failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    report = static_checks()
    (ROOT / 'package-validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if args.browser:
        reader = browser_checks()
        (ROOT / 'reader-validation.json').write_text(json.dumps(reader, indent=2)+'\n', encoding='utf-8')
        print('Browser:', reader['passed'], len(reader['results']), 'page/viewport checks')
        if reader['failures']:
            print(reader['failures'])
        report['passed'] = report['passed'] and reader['passed']
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
