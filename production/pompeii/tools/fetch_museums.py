"""Harvest public-domain images from The Met (v1.1 search) and the Art Institute of Chicago.
Usage: python3 fetch_museums.py museum_queries.txt   ('met:' or 'aic:' prefix per line)
Output: build/img/pool/*.jpg, build/img/museum_catalog.json {query: [entries]}
"""
import json, os, re, sys, time, html, hashlib, io
import requests
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, 'build', 'img', 'pool'); CAT = os.path.join(ROOT, 'build', 'img', 'museum_catalog.json')
S = requests.Session(); S.headers.update({'User-Agent': 'WorldAncientDisastersResearch/1.0 (documentary production)'})
def clean(s): return html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()[:160]

def save(url, entry):
    fn = hashlib.md5(url.encode()).hexdigest()[:16] + '.jpg'; path = os.path.join(POOL, fn)
    if not os.path.exists(path):
        try:
            r = S.get(url, timeout=120)
            if r.status_code != 200 or len(r.content) < 20000: return None
            im = Image.open(io.BytesIO(r.content)).convert('RGB')
            if max(im.size) > 3200: im.thumbnail((3200, 3200), Image.LANCZOS)
            if min(im.size) < 700: return None
            im.save(path, quality=92)
        except Exception as e:
            print('   skip', e, flush=True); return None
    entry['file'] = fn; return entry

def met(q, n):
    r = S.get('https://collectionapi.metmuseum.org/public/collection/v1.1/search', params={'q': q, 'hasImages': 'true', 'limit': n}, timeout=60).json()
    out = []
    for oid in r.get('objectIDs') or []:
        try: o = S.get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}', timeout=60).json()
        except Exception: continue
        if not (o.get('isPublicDomain') and o.get('primaryImage')): continue
        e = {'title': clean(o.get('title')), 'date': o.get('objectDate', ''), 'source': 'The Metropolitan Museum of Art', 'license': 'CC0 (Met Open Access)',
             'artist': clean(o.get('artistDisplayName')) or clean(o.get('culture')) or 'Unknown', 'page': o.get('objectURL'),
             'medium': o.get('medium', ''), 'classification': o.get('classification', '')}
        e = save(o['primaryImage'], e)
        if e: out.append(e)
        time.sleep(0.3)
    return out

def aic(q, n):
    r = S.get('https://api.artic.edu/api/v1/artworks/search', params={'q': q, 'limit': n,
              'fields': 'id,title,artist_display,is_public_domain,image_id,date_display,medium_display'}, timeout=60).json()
    out = []
    for a in r.get('data', []):
        if not (a.get('is_public_domain') and a.get('image_id')): continue
        e = {'title': clean(a['title']), 'date': a.get('date_display', ''), 'source': 'Art Institute of Chicago', 'license': 'CC0 (AIC public domain)',
             'artist': clean(a.get('artist_display')), 'page': f"https://www.artic.edu/artworks/{a['id']}", 'medium': a.get('medium_display', '')}
        e = save(f"https://www.artic.edu/iiif/2/{a['image_id']}/full/1686,/0/default.jpg", e)
        if e: out.append(e)
        time.sleep(0.5)
    return out

def main():
    os.makedirs(POOL, exist_ok=True)
    cat = json.load(open(CAT)) if os.path.exists(CAT) else {}
    for line in open(sys.argv[1], encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'): continue
        src, q = line.split(':', 1); q = q.strip(); key = f'{src}:{q}'
        if key in cat: continue
        n = 60 if src == 'met' else 40
        cat[key] = met(q, n) if src == 'met' else aic(q, n)
        json.dump(cat, open(CAT, 'w'), indent=1, ensure_ascii=False)
        print(f'{len(cat[key]):3d}  {key}', flush=True)

if __name__ == '__main__':
    main()
