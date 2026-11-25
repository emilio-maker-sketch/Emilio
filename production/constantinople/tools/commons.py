"""Free real photos / public-domain art from Wikimedia Commons, with license and credit recorded.

  python3 tools/commons.py search "query"            # list candidates (index, size, license, title)
  python3 tools/commons.py get SHOT_ID "query" N     # download candidate N as build/photos/<shot>.jpg
Credits go to build/photos/credits.json (used for the description and credits file).
"""
import os, re, sys, json, html, time, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'photos')
UA = {'User-Agent': 'DocumentaryResearchBot/1.0 (educational documentary; python-requests)'}
OK = re.compile(r'(public domain|^pd|cc0|cc by|cc-by|attribution)', re.I)
BAD = re.compile(r'(\bnc\b|-nc|\bnd\b|-nd|fair use|non-free)', re.I)

def clean(s): return html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()

def search(q, n=15):
    for i in range(5):
        r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=40, params={
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6,
            'gsrsearch': f'{q} filetype:bitmap', 'gsrlimit': n, 'prop': 'imageinfo',
            'iiprop': 'url|extmetadata|size', 'iiurlwidth': 2400})
        if r.status_code == 200: break
        time.sleep(5 * (i + 1))
    pages = sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    out = []
    for p in pages:
        ii = p['imageinfo'][0]; m = ii.get('extmetadata', {})
        lic = clean(m.get('LicenseShortName', {}).get('value', ''))
        if not OK.search(lic) or BAD.search(lic): continue
        out.append({'title': p['title'], 'w': ii['width'], 'h': ii['height'], 'license': lic,
                    'artist': clean(m.get('Artist', {}).get('value', ''))[:120],
                    'url': ii.get('thumburl') if ii['width'] > 2400 and ii.get('thumburl') else ii['url'], 'page': ii['descriptionurl']})
    return out

def main():
    if sys.argv[1] == 'search':
        for i, c in enumerate(search(sys.argv[2])):
            print(i, f"{c['w']}x{c['h']}", c['license'], '|', c['title'][5:90])
    elif sys.argv[1] == 'get':
        shot, q, n = sys.argv[2], sys.argv[3], int(sys.argv[4])
        c = search(q)[n]; os.makedirs(OUT, exist_ok=True)
        ext = os.path.splitext(c['url'])[1].lower() or '.jpg'
        path = os.path.join(OUT, shot + ('.png' if ext == '.png' else '.jpg'))
        for old in (os.path.join(OUT, shot + '.jpg'), os.path.join(OUT, shot + '.png')):
            if os.path.exists(old): os.remove(old)
        for i in range(5):
            r = requests.get(c['url'], headers=UA, timeout=120)
            if r.ok and r.headers.get('content-type', '').startswith('image/'): break
            time.sleep(10 * (i + 1))
        else: raise SystemExit(f'download failed {r.status_code} {c["url"]}')
        data = r.content
        open(path, 'wb').write(data)
        cf = os.path.join(OUT, 'credits.json')
        cr = json.load(open(cf)) if os.path.exists(cf) else {}
        cr[shot] = c; json.dump(cr, open(cf, 'w'), indent=1, ensure_ascii=False)
        print('saved', path, c['license'], c['title'])

if __name__ == '__main__': main()
