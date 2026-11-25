"""Parse the Constantinople script format.

Each chapter file: '# TITLE' line, then paragraphs. A paragraph is one narration line
followed by shot lines:  > SIZE | MOVE | KIND | GRADE | @ref,@ref | description
KIND: vid (AI video), still (AI still + local camera move), map (local map), card (local type card).
"""
import glob, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {'vid', 'still', 'map', 'card'}

def load_bible():
    return json.load(open(os.path.join(ROOT, 'bible.json')))

def parse_file(path):
    cid = os.path.basename(path)[:-3]
    title, paras = None, []
    for n, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.strip()
        if not line: continue
        if line.startswith('# '): title = line[2:].strip(); continue
        if line.startswith('>'):
            f = [x.strip() for x in line[1:].split('|')]
            if len(f) != 6: raise SystemExit(f'{path}:{n}: shot needs 6 fields, got {len(f)}')
            size, move, kind, grade, refs, desc = f
            if kind not in KINDS: raise SystemExit(f'{path}:{n}: bad kind {kind!r}')
            if not paras: raise SystemExit(f'{path}:{n}: shot before any narration')
            paras[-1]['shots'].append({'size': size, 'move': move, 'kind': kind, 'grade': grade,
                                       'refs': [r.lstrip('@') for r in refs.split(',') if r.strip()],
                                       'desc': desc, 'line': n})
        else:
            paras.append({'text': line, 'shots': []})
    return {'id': cid, 'title': title, 'paras': paras}

def chapters():
    return [parse_file(f) for f in sorted(glob.glob(os.path.join(ROOT, 'script', '*.md')))]
