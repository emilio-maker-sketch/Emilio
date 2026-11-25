"""Search Wikimedia Commons + The Met Open Access for every [v: query] in the script.

Keeps only reusable licenses, downloads ~2400px versions, records credits.
Output: build/images/pool/*.jpg, build/images/catalog.json  {query: [ {file, title, source, license, artist, url} ]}
"""
import json, os, re, glob, hashlib, time, html, sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, 'build', 'images', 'pool')
CAT = os.path.join(ROOT, 'build', 'images', 'catalog.json')
UA = {'User-Agent': 'DocumentaryResearchBot/1.0 (educational video production; python-requests)'}
OK_LIC = re.compile(r'^(public domain|pd|cc0|cc by(-sa)? ?\d|cc-by(-sa)?-?\d|cc by-sa|cc by \d|attribution|no restrictions)', re.I)
BAD = re.compile(r'(nc|nd|fair use|non-free)', re.I)
S = requests.Session(); S.headers.update(UA)
_get = S.get
def _retry_get(url, **kw):
    for i in range(6):
        try:
            r = _get(url, **kw)
            if r.status_code == 200 or r.status_code == 404: return r
            if r.status_code == 429:
                wait = int(r.headers.get('retry-after', '60') or 60)
                print(f'  429, waiting {wait}s', flush=True); time.sleep(min(wait, 900) + 5); continue
        except Exception as e:
            if i == 5: raise
        time.sleep(3 * (i + 1))
    return r
S.get = _retry_get

def clean(s):
    s = re.sub(r'<[^>]+>', '', s or ''); return html.unescape(s).strip()[:160]

def commons(q, n=14):
    r = S.get('https://commons.wikimedia.org/w/api.php', params={
        'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6,
        'gsrsearch': f'{q} filetype:bitmap', 'gsrlimit': n, 'prop': 'imageinfo',
        'iiprop': 'url|extmetadata|size|mime', 'iiurlwidth': 1920}, timeout=40)
    out = []
    pages = sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    for p in pages:
        ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
        lic = clean(md.get('LicenseShortName', {}).get('value', ''))
        if not OK_LIC.match(lic) or BAD.search(lic): continue
        if ii.get('width', 0) < 1200 or ii.get('mime') not in ('image/jpeg', 'image/png', 'image/tiff'): continue
        out.append({'title': p['title'][5:], 'source': 'Wikimedia Commons', 'license': lic,
                    'artist': clean(md.get('Artist', {}).get('value', '')) or 'Unknown',
                    'page': ii.get('descriptionurl'), 'dl': ii.get('thumburl') or ii.get('url'),
                    'w': ii.get('width'), 'h': ii.get('height')})
    return out

def met(q, n=4):
    r = S.get('https://collectionapi.metmuseum.org/public/collection/v1.1/search',
              params={'q': q, 'hasImages': 'true', 'limit': n * 3}, timeout=40).json()
    out = []
    for oid in (r.get('objectIDs') or [])[:n * 3]:
        o = S.get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}', timeout=40).json()
        if o.get('isPublicDomain') and o.get('primaryImage'):
            out.append({'title': f"{o.get('title','')} ({o.get('culture') or o.get('department','')}, {o.get('objectDate','')})",
                        'source': 'The Metropolitan Museum of Art', 'license': 'CC0 (Met Open Access)',
                        'artist': 'The Metropolitan Museum of Art', 'page': o.get('objectURL'),
                        'dl': o['primaryImage'], 'w': 0, 'h': 0})
        if len(out) >= n: break
        time.sleep(0.1)
    return out

def queries():
    qs = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'script', '*.md'))):
        for m in re.finditer(r'^\[v: ([^\]]+)\]', open(f, encoding='utf-8').read(), re.M):
            if m.group(1) not in qs: qs.append(m.group(1))
    return qs

def main():
    os.makedirs(POOL, exist_ok=True)
    cat = json.load(open(CAT)) if os.path.exists(CAT) else {}
    extra = sys.argv[1:]
    for q in (extra or queries()):
        if q in cat and not extra: continue
        try:
            cands = commons(q)
            if any(k in q for k in ('pottery', 'vase', 'figurine', 'bronze', 'ingot', 'tablet', 'cypriot', 'mycenaean', 'egyptian', 'hittite', 'scarab', 'dagger', 'sword', 'statue', 'relief', 'stele', 'seal', 'glass')):
                cands += met(q)
        except Exception as e:
            print('ERR', q, e, flush=True); continue
        got = []
        for c in cands:
            fn = hashlib.md5(c['dl'].encode()).hexdigest()[:12] + '.jpg'
            path = os.path.join(POOL, fn)
            if not os.path.exists(path):
                try:
                    b = S.get(c['dl'], timeout=90)
                    if b.status_code != 200 or len(b.content) < 20000: continue
                    open(path, 'wb').write(b.content)
                except Exception: continue
                time.sleep(1.2)
            c['file'] = fn; got.append(c)
        cat[q] = got
        print(f'{len(got):2d}  {q}', flush=True)
        json.dump(cat, open(CAT, 'w'), indent=1)

if __name__ == '__main__':
    main()
