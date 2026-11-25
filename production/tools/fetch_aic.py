"""CC0 public-domain artworks from the Art Institute of Chicago for mood/atmosphere shots."""
import json, os, sys, time, requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'images', 'museum'); DB = os.path.join(ROOT, 'build', 'images', 'aic.json')
S = requests.Session(); S.headers['User-Agent'] = 'DocumentaryResearchBot/1.0 (educational video production)'
TOPICS = {
    'aic_sea': ['storm at sea', 'shipwreck', 'stormy sea', 'ships in a storm', 'sea coast rocks', 'Mediterranean sea'],
    'aic_ruins': ['ruins', 'temple ruins', 'ancient ruins', 'Roman ruins', 'Piranesi', 'Hubert Robert', 'ruins landscape'],
    'aic_land': ['desert', 'drought', 'barren landscape', 'wheat field', 'harvest', 'famine', 'evening landscape', 'mountain landscape', 'Egypt landscape', 'Nile'],
    'aic_fire': ['burning city', 'fire', 'conflagration', 'destruction', 'earthquake', 'volcano'],
    'aic_ancient': ['Egyptian', 'Mycenaean', 'Cypriot', 'Hittite', 'Assyrian', 'Phoenician', 'cuneiform', 'Bronze Age', 'Greek Geometric', 'Minoan'],
    'aic_people': ['refugees', 'exodus', 'migration', 'flight', 'caravan', 'revolt', 'battle'],
}
db = json.load(open(DB)) if os.path.exists(DB) else {}
seen = {r['id'] for v in db.values() for r in v}
for topic, terms in TOPICS.items():
    os.makedirs(os.path.join(OUT, topic), exist_ok=True); recs = db.get(topic, [])
    for term in terms:
        try:
            r = S.get('https://api.artic.edu/api/v1/artworks/search', params={'q': term, 'limit': 40,
                      'fields': 'id,title,image_id,artist_display,date_display,is_public_domain,thumbnail,medium_display'}, timeout=60).json()
        except Exception as e:
            print('ERR', term, e, flush=True); continue
        n = 0
        for a in r.get('data', []):
            if n >= 8: break
            if not a.get('is_public_domain') or not a.get('image_id'): continue
            key = f"aic{a['id']}"
            if key in seen: continue
            th = a.get('thumbnail') or {}
            if th.get('width') and th.get('height') and th['width'] < 900 and th['height'] < 900: continue
            url = f"https://www.artic.edu/iiif/2/{a['image_id']}/full/1686,/0/default.jpg"
            try:
                b = S.get(url, timeout=90)
                if b.status_code != 200 or len(b.content) < 40000: continue
            except Exception: continue
            open(os.path.join(OUT, topic, key + '.jpg'), 'wb').write(b.content)
            recs.append({'id': key, 'file': f'museum/{topic}/{key}.jpg', 'term': term, 'title': a.get('title', ''),
                         'date': a.get('date_display', ''), 'artist': (a.get('artist_display') or '').split('\n')[0],
                         'medium': (a.get('medium_display') or '')[:80], 'source': 'Art Institute of Chicago',
                         'license': 'CC0 (AIC public domain)', 'page': f"https://www.artic.edu/artworks/{a['id']}"})
            seen.add(key); n += 1; time.sleep(0.3)
        print(f'{topic:12s} {term:22s} +{n}', flush=True)
        db[topic] = recs; json.dump(db, open(DB, 'w'), indent=1)
print('TOTAL', sum(len(v) for v in db.values()))
