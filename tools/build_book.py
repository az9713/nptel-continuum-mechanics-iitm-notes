"""Assemble the offline reader, preserving exact authored chapter bodies."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- BOOK-CONTENT-START -->'
END = '<!-- BOOK-CONTENT-END -->'


def read(path):
    return path.read_bytes().decode('utf-8-sig')


def write(path, value):
    path.write_bytes(value.encode('utf-8'))


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def esc(value):
    return html.escape(str(value), quote=True)


def original_body(document):
    if START in document:
        content = document.split(START, 1)[1].split(END, 1)[0]
        prior = re.search(r'name="book-content-sha256" content="([a-f0-9]+)"', document)
        if prior and prior[1] != digest(content):
            raise ValueError('Content digest differs: review changes before rewrapping')
        return content
    return document


def page(title, body, chapter=False, previous=None, following=None):
    checksum = digest(body)
    nav = [('index.html', 'Chapters'), ('source-map.html', 'Source map'),
           ('references.html', 'References'), ('numerical-lab.html', 'Numerical lab')]
    links = ''.join(f'<a href="{url}">{label}</a>' for url, label in nav)
    turns = ''
    if chapter:
        back = f'<a rel="prev" href="{esc(previous)}">Previous chapter</a>' if previous else '<span>First chapter</span>'
        ahead = f'<a rel="next" href="{esc(following)}">Next chapter</a>' if following else '<span>End of edition</span>'
        turns = f'<nav class="page-turn" aria-label="Chapter navigation">{back}<a href="index.html">Chapter index</a>{ahead}</nav>'
    sidebar = '<aside class="toc" id="chapter-toc" aria-label="On this page"><h2>On this page</h2></aside>' if chapter else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><meta name="book-content-sha256" content="{checksum}">
<title>{esc(title)} · Foundations of Continuum Mechanics</title><link rel="stylesheet" href="assets/book.css">
<script>window.MathJax={{tex:{{inlineMath:[['$','$'],['\\\\(','\\\\)']],displayMath:[['$$','$$'],['\\\\[','\\\\]']],processEscapes:true}},svg:{{fontCache:'local'}},options:{{skipHtmlTags:['script','noscript','style','textarea','pre','code']}}}};</script>
<script defer src="assets/mathjax-tex-svg.js"></script><script defer src="assets/book.js"></script></head>
<body><a class="skip" href="#main">Skip to content</a><header class="site-header"><a class="brand" href="index.html">Foundations of Continuum Mechanics · NPTEL IIT Mandi</a><nav class="course-nav" aria-label="Book">{links}</nav></header>
<div class="layout{'' if chapter else ' no-toc'}">{sidebar}<main id="main"><div class="reading-tools" aria-label="Reading controls"><button id="theme-toggle" aria-pressed="false">Light theme</button><button id="text-toggle" aria-pressed="false">Larger text</button><button id="solutions-toggle" aria-pressed="false">Expand solutions</button><button id="print-page">Print with solutions</button></div>
<article id="chapter-content">{START}{body}{END}</article>{turns}</main></div><footer class="site-footer">Independent study edition. Prof. Gaurav Bhutani’s NPTEL recordings provide the topic spine. Original exposition, source limitations and verification evidence are separately recorded.</footer></body></html>'''


def build():
    manifest = json.loads(read(ROOT / 'source-manifest.json'))
    chapters = []
    for record in manifest['chapters']:
        matches = list(ROOT.glob(f'chapter-{int(record["order"]):02d}-*.html'))
        if len(matches) > 1:
            raise ValueError('More than one file for a chapter')
        chapters.append((record, matches[0] if matches else None))
    available = [p for _, p in chapters if p]
    sections, references, rows = [], {}, []
    for record, path in chapters:
        order = int(record['order'])
        headline = esc(record['title'])
        if path:
            index = available.index(path)
            body = original_body(read(path))
            write(path, page(record['title'], body, True,
                             available[index-1].name if index else None,
                             available[index+1].name if index+1 < len(available) else None))
            headline = f'<a href="{esc(path.name)}">{headline}</a>'
            sidecar = path.with_suffix('.meta.json')
            meta = json.loads(read(sidecar)) if sidecar.exists() else {}
            sections.extend(dict(s, chapter=path.name) for s in meta.get('sections', []))
            for ref in meta.get('references', []):
                references[ref['url']] = ref
        recordings_here = [r for r in manifest['lectures'] if r['chapter_order'] == order]
        def lesson_key(recording):
            number = re.match(r'Lecture (\d+)', recording['label'])
            return (0, int(number[1])) if number else (1, recording['playlist_position'])
        recordings_here.sort(key=lesson_key)
        recordings = ' · '.join(f'<a href="{esc(r["url"])}">{esc(r["label"])}</a>' for r in recordings_here)
        rows.append(f'<li data-lecture><h2>{order:02d}. {headline}</h2><span class="status">{esc(record["chapter_status"])}</span><p class="lecture-meta">{recordings}</p></li>')
    overview = read(ROOT / 'book-overview.html') if (ROOT / 'book-overview.html').exists() else ''
    index_body = f'''<h1>Foundations of Continuum Mechanics</h1><p class="lead">An independent textbook rewrite of Prof. Gaurav Bhutani’s NPTEL course at IIT Mandi.</p>
<p>{len(manifest['lectures'])} playlist items · 60 numbered lessons · {len(available)} available chapters. The repository name retains the original workspace label; IIT Madras is the NPTEL coordinating institute, while the instructor and course are at IIT Mandi.</p>
<p>Read the <a href="WORKFLOW.md">production workflow</a> and <a href="completion.json">completion record</a> for source and review boundaries.</p>
<div class="search-tools"><label class="search-label" for="lecture-search">Search chapters</label><input id="lecture-search" type="search" placeholder="Search chapters and topics"><p id="search-status" role="status" aria-live="polite">{len(chapters)} chapters shown</p></div><ol class="lecture-list">{''.join(rows)}</ol>{overview}'''
    write(ROOT / 'index.html', page('Chapter index', index_body))
    source_rows = []
    for row in sections:
        values = [row.get('chapter'), row.get('section'), row.get('video_id'),
                  f"{row.get('start')}–{row.get('end')} s", row.get('lecture_material'),
                  row.get('research_extension'), row.get('teaching_construction')]
        source_rows.append('<tr>' + ''.join(f'<td>{esc(v or "")}</td>' for v in values) + '</tr>')
    inventory = ''.join(f'<tr><td>{r["playlist_position"]}</td><td><a href="{esc(r["url"])}">{esc(r["title"])}</a></td><td>{esc(r["duration"])}</td><td>{r["chapter_order"]}</td><td>{esc(r["source_status"])}</td></tr>' for r in manifest['lectures'])
    source_body = '<h1>Recording and section map</h1><p>The original playlist order is retained below. Chapters follow numbered course order so that lesson 11 precedes transformations and elasticity precedes viscoelasticity. The two lesson-6 uploads are both retained. Four live discussions receive separate chapters. Machine ASR is fallible; timestamps locate related discussion and do not attribute every derivation to the lecturer.</p>'
    source_body += '<h2>Every playlist item</h2><table><thead><tr><th>Position</th><th>Recording</th><th>Seconds</th><th>Chapter</th><th>Source status</th></tr></thead><tbody>' + inventory + '</tbody></table>'
    source_body += '<h2>Section provenance</h2><table><thead><tr><th>Chapter</th><th>Section</th><th>Video</th><th>Span</th><th>Lecture material</th><th>Research extension</th><th>Original construction</th></tr></thead><tbody>' + ''.join(source_rows) + '</tbody></table>'
    write(ROOT / 'source-map.html', page('Source map', source_body))
    write(ROOT / 'source-map.json', json.dumps({'sections': sections}, indent=2)+'\n')
    ref_body = '<h1>Primary references</h1><p>Recording anchors, external sources, and original teaching derivations have separate roles. Exact source-access scope is recorded in the chapter sidecars.</p><ul>'
    ref_body += ''.join(f'<li><a href="{esc(u)}">{esc(r["title"])}</a><p>{esc(r["supports"])}</p></li>' for u, r in references.items()) + '</ul>'
    write(ROOT / 'references.html', page('References', ref_body))
    lab = ROOT / 'numerical-lab.html'
    if lab.exists():
        write(lab, page('Numerical laboratory', original_body(read(lab))))
    print(f'Built {len(available)} chapters and reader navigation')


if __name__ == '__main__':
    build()
