"""Harvest reusable images for the Pompeii episode.
Sources: Wikimedia Commons (via 2400px thumbnails, the only size this server may fetch),
Art Institute of Chicago (public-domain IIIF). Records credits for the description.
Usage: python3 fetch.py queries.txt   (one query per line; 'aic:' prefix also searches AIC)
Output: build/img/pool/*.jpg, build/img/catalog.json {query: [entries]}
"""
import json, os, re, sys, time, html, hashlib
import requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, 'build', 'img', 'pool'); CAT = os.path.join(ROOT, 'build', 'img', 'catalog.json')
S = requests.Session(); S.headers.update({'User-Agent': 'WorldAncientDisastersResearch/1.0 (documentary production; python-requests)'})
OK_LIC = re.compile(r'^(public domain|pd|cc0|cc by(-sa)?|cc-by|attribution|no restrictions)', re.I)
BAD = re.compile(r'\b(nc|nd)\b|fair use|non-free', re.I)

def get(url, **kw):
    for i in range(8):
        try:
            r = S.get(url, timeout=60, **kw)
            if r.status_code in (200, 404): return r
            if r.status_code == 429:
                w = min(int(r.headers.get('retry-after') or 60), 300); print(f'   429 wait {w}s', flush=True); time.sleep(w + 3); continue
        except Exception as e:
            print('   err', e, flush=True)
        time.sleep(4 * (i + 1))
    return None

def clean(s): return html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()[:160]

def commons(q, n):
    r = get('https://commons.wikimedia.org/w/api.php', params={'action': 'query', 'format': 'json', 'generator': 'search',
            'gsrnamespace': 6, 'gsrsearch': f'{q} filetype:bitmap', 'gsrlimit': n, 'prop': 'imageinfo',
            'iiprop': 'url|extmetadata|size|mime', 'iiurlwidth': 2400})
    out = []
    if not r: return out
    for p in sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99)):
        ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
        lic = clean(md.get('LicenseShortName', {}).get('value', ''))
        if not OK_LIC.match(lic) or BAD.search(lic): continue
        if ii.get('width', 0) < 1400 or ii.get('mime') not in ('image/jpeg', 'image/png', 'image/tiff'): continue
        out.append({'title': p['title'][5:], 'source': 'Wikimedia Commons', 'license': lic,
                    'artist': clean(md.get('Artist', {}).get('value', '')) or 'Unknown', 'page': ii.get('descriptionurl'),
                    'dl': (ii.get('thumburl') or '').split('?')[0], 'w': ii.get('width'), 'h': ii.get('height')})
    return out

def aic(q, n):
    r = get('https://api.artic.edu/api/v1/artworks/search', params={'q': q, 'limit': n * 3,
            'fields': 'id,title,artist_display,is_public_domain,image_id,date_display'})
    out = []
    for a in (r.json().get('data', []) if r else []):
        if a.get('is_public_domain') and a.get('image_id'):
            out.append({'title': f"{a['title']} ({a.get('date_display','')})", 'source': 'Art Institute of Chicago', 'license': 'CC0 (AIC public domain)',
                        'artist': clean(a.get('artist_display', '')), 'page': f"https://www.artic.edu/artworks/{a['id']}",
                        'dl': f"https://www.artic.edu/iiif/2/{a['image_id']}/full/1686,/0/default.jpg", 'w': 0, 'h': 0})
        if len(out) >= n: break
    return out

def main():
    os.makedirs(POOL, exist_ok=True)
    cat = json.load(open(CAT)) if os.path.exists(CAT) else {}
    for line in open(sys.argv[1], encoding='utf-8'):
        q = line.strip()
        if not q or q.startswith('#'): continue
        use_aic = q.startswith('aic:'); q = q[4:].strip() if use_aic else q
        if q in cat: continue
        ents = commons(q, 12) + (aic(q, 5) if use_aic else [])
        got = []
        for e in ents:
            if not e['dl']: continue
            fn = hashlib.md5(e['dl'].encode()).hexdigest()[:16] + '.jpg'; path = os.path.join(POOL, fn)
            if not os.path.exists(path):
                time.sleep(1.5)
                r = get(e['dl'])
                if not r or r.status_code != 200 or len(r.content) < 20000 or not r.headers.get('content-type', '').startswith('image'): continue
                open(path, 'wb').write(r.content)
            e['file'] = fn; got.append(e)
        cat[q] = got; json.dump(cat, open(CAT, 'w'), indent=1, ensure_ascii=False)
        print(f'{len(got):3d}  {q}', flush=True); time.sleep(2)

if __name__ == '__main__':
    main()
