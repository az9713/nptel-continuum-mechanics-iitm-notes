"""Build public provenance sidecars from authored headings and curated source data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
from build_book import original_body, read

ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    manifest = json.loads((ROOT / 'source-manifest.json').read_text(encoding='utf-8'))
    source_path = ROOT / 'work' / 'source-integrity.json'
    if not source_path.is_file():
        raise SystemExit('Private acquisition evidence is absent. Keep published sidecars; '
                         'a reader rebuild uses tools/build_book.py and needs no raw sources.')
    integrity = json.loads(source_path.read_text(encoding='utf-8'))
    by_id = {r['id']: r for r in integrity}
    summary = []
    for chapter in manifest['chapters']:
        number = int(chapter['order'])
        paths = list(ROOT.glob(f'chapter-{number:02d}-*.html'))
        if len(paths) != 1:
            raise ValueError(f'Expected one chapter file for {number}')
        path = paths[0]
        body = original_body(read(path))
        soup = BeautifulSoup(body, 'html.parser')
        recordings = [r for r in manifest['lectures'] if r['chapter_order'] == number]
        source_records = []
        for recording in recordings:
            source = by_id.get(recording['id'], {})
            source_records.append({
                'video_id': recording['id'],
                'playlist_position': recording['playlist_position'],
                'lecture_label': recording['label'],
                'duration_seconds': recording['duration'],
                'decoded_audio_duration_seconds': source.get('decoded_audio_duration'),
                'complete_decoded_audio': source.get('complete_transcribed_audio', False),
                'media_sha256': source.get('audio_sha256'),
                'transcript_first_start': source.get('first_transcript_start'),
                'transcript_last_end': source.get('last_transcript_end'),
                'transcript_provenance': 'Local faster-whisper small.en machine ASR; not publisher captions',
            })
        sections = []
        for heading in soup.select('h2'):
            title = heading.get_text(' ', strip=True)
            for anchor in heading.select('.timestamp'):
                title = title.replace(anchor.get_text(' ', strip=True), '').strip()
            video = heading.get('data-video')
            sections.append({
                'section': title, 'anchor': heading.get('id'), 'video_id': video,
                'start': int(heading['data-start']) if heading.get('data-start') else None,
                'end': int(heading['data-end']) if heading.get('data-end') else None,
                'lecture_material': 'Related lecture topic located by the stated span' if video else '',
                'research_extension': 'Inspected external support is cited locally in the exposition',
                'teaching_construction': 'Expanded exposition, derivations, numerical checks and exercises are independently authored; an anchor does not attribute every statement to the recording',
            })
        references = {}
        for anchor in soup.select('a[href]'):
            url = anchor['href']
            if url.startswith('https://') and 'youtube.com' not in url:
                references[url] = {'url': url, 'title': anchor.get_text(' ', strip=True),
                                   'supports': 'Specific claim and locator are given beside the citation in '+path.name}
        metadata = {
            'chapter': number, 'title': soup.h1.get_text(' ', strip=True),
            'status': chapter['chapter_status'],
            'authored_body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
            'recordings': source_records, 'sections': sections,
            'references': list(references.values()),
            'prose_words_including_math': len(soup.get_text(' ', strip=True).split()),
            'solution_count': len(soup.select('details')),
            'executable_listing_count': len(soup.select('pre[data-run]')),
            'visual_boundary': 'No comprehensive visual transcription or full audiovisual review is claimed. ASR cannot recover every board input; uncertain inputs are qualified locally.',
        }
        dump(path.with_suffix('.meta.json'), metadata)
        summary.append({'chapter': number, 'file': path.name,
                        'body_sha256': metadata['authored_body_sha256'],
                        'words': metadata['prose_words_including_math'],
                        'solutions': metadata['solution_count'],
                        'listings': metadata['executable_listing_count']})
    for recording in manifest['lectures']:
        record = by_id.get(recording['id'], {})
        recording['source_status'] = ('Complete decoded audio and machine ASR; scientific chapter review recorded separately'
                                      if record.get('complete_transcribed_audio') else 'Source acquisition incomplete')
    dump(ROOT / 'source-manifest.json', manifest)
    dump(ROOT / 'source-validation-summary.json', {
        'recording_count': len(manifest['lectures']),
        'complete_decoded_audio_count': sum(r.get('complete_transcribed_audio', False) for r in integrity),
        'caption_acquisition': 'Caption requests failed with HTTP429; local machine ASR used',
        'method': 'Full decoded audio duration compared with playlist duration; file digests retained. Container timestamp durations can differ and are not substituted for decoded lengths.',
        'scope_limit': 'Complete audio acquisition and ASR do not by themselves establish exact recognition, board transcription or scientific correctness.',
        'recordings': [{('media_sha256' if k == 'audio_sha256' else k): v
                        for k, v in r.items() if k not in ('media_duration',)}
                       for r in integrity],
    })
    dump(ROOT / 'content-inventory.json', {
        'chapter_count': len(summary), 'chapters': summary,
        'prose_words_including_math': sum(r['words'] for r in summary),
        'worked_solution_count': sum(r['solutions'] for r in summary),
        'executable_listing_count': sum(r['listings'] for r in summary),
        'counting_note': 'Whitespace tokens include mathematical notation and code; this is a reproducible inventory, not a pure prose estimate.',
    })
    print(len(summary), 'chapter sidecars updated')


if __name__ == '__main__':
    main()
