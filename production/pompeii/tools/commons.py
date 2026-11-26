"""Wikimedia Commons helper with polite retry. usage: commons.py info 'File:A|File:B'  |  commons.py search 'query'  |  commons.py get 'File:X' out.jpg"""
import json, sys, time, requests
S = requests.Session(); S.headers['User-Agent'] = 'AncientWorldFilesResearch/1.0 (educational documentary; contact via channel)'
API = 'https://commons.wikimedia.org/w/api.php'
def call(params):
    for i in range(8):
        r = S.get(API, params=dict(params, format='json'), timeout=40)
        if r.status_code == 200 and r.text.startswith('{'): return r.json()
        time.sleep(15 * (i + 1))
    raise SystemExit('commons: gave up')
def info(titles):
    d = call({'action': 'query', 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 2000, 'titles': titles})
    out = {}
    for p in d['query']['pages'].values():
        if 'imageinfo' not in p: continue
        ii = p['imageinfo'][0]; m = ii['extmetadata']; g = lambda k: (m.get(k, {}).get('value', '') or '')
        out[p['title']] = dict(w=ii['width'], h=ii['height'], url=ii['url'], thumb=ii.get('thumburl'), lic=g('LicenseShortName'),
                               artist=g('Artist'), date=g('DateTimeOriginal'), desc=g('ImageDescription')[:200], page=ii.get('descriptionurl'))
    return out
if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'search':
        d = call({'action': 'query', 'list': 'search', 'srnamespace': 6, 'srlimit': 25, 'srsearch': sys.argv[2]})
        for x in d['query']['search']: print(x['title'])
    elif cmd == 'info':
        for k, v in info(sys.argv[2]).items():
            import re; a = re.sub('<[^>]+>', '', v['artist'])[:50]; print(k[5:], v['w'], v['h'], '|', v['lic'], '|', a, '|', re.sub('<[^>]+>', '', v['date'])[:30])
    elif cmd == 'get':
        v = list(info(sys.argv[2]).values())[0]
        for i in range(6):
            r = S.get(v['thumb'] or v['url'], timeout=120)
            if r.status_code == 200: open(sys.argv[3], 'wb').write(r.content); break
            time.sleep(15 * (i + 1))
        json.dump(v, open(sys.argv[3] + '.json', 'w'), indent=1); print('saved', sys.argv[3], v['lic'])
