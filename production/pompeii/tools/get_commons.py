import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__)); import commons as C
from PIL import Image
want = {
 'wc_sommer_dog': ("File:Giorgio Sommer (Italian, born Germany - (Cast of a Dog Killed by the Eruption of Mount Vesuvius, Pompeii) - Google Art Project.jpg", "Cast of a Dog Killed by the Eruption of Vesuvius", "Giorgio Sommer", "1863", "albumen print photograph"),
 'wc_sommer_imp': ("File:Sommer, Giorgio (1834-1914) - n. 1279 - Impronte umane (Pompei).png", "Impronte umane (Human Impressions), Pompeii", "Giorgio Sommer", "1873", "albumen print photograph"),
 'wc_sommer_1863': ("File:Sommer, Giorgio (1834-1914) - Bodies found in Pompeii (1863).jpg", "Bodies found in Pompeii", "Giorgio Sommer", "1863", "albumen print photograph"),
 'wc_cast_sit': ("File:Cast sitting victim Pompeii.jpg", "Cast of a seated victim, Pompeii", "Jebulon", "2015", "photograph"),
 'wc_cast_vic': ("File:Cast victim eruptions Pompeii.jpg", "Cast of a victim of the eruption, Pompeii", "Jebulon", "2015", "photograph"),
 'wc_scavi': ("File:Sommer, Giorgio (1834-1914) - n. 10800 - Pompei - Scavi nuovi.jpg", "Pompeii, new excavations", "Giorgio Sommer", "before 1914", "albumen print photograph"),
 'wc_foro': ("File:Sommer, Giorgio (1834-1914) - n. 1201 - Pompei, Foro Civile.JPG", "Pompeii, the Forum", "Giorgio Sommer", "19th century", "albumen print photograph"),
 'wc_elmore': ("File:Alfred Elmore - Pompeii, A.D. 79 - Google Art Project.jpg", "Pompeii, A.D. 79", "Alfred Elmore", "1878", "oil painting"),
 'wc_fiorelli': ("File:Giuseppe Fiorelli.jpg", "Giuseppe Fiorelli", "", "19th century", "photograph"),
}
IMG = os.path.join(os.path.dirname(__file__), '..', '..', 'build', 'images')
db_p = os.path.join(IMG, 'commons.json'); db = json.load(open(db_p)) if os.path.exists(db_p) else {'p_commons': []}
have = {r['id'] for r in db['p_commons']}
for k, (t, title, artist, date, medium) in want.items():
    if k in have: continue
    out = os.path.join(IMG, 'commons', k + '.jpg')
    v = list(C.info(t).values())[0]; time.sleep(8)
    if not os.path.exists(out):
        for i in range(8):
            r = C.S.get(v['thumb'] or v['url'], timeout=120)
            if r.status_code == 200: open(out, 'wb').write(r.content); break
            time.sleep(20 * (i + 1))
    if t.lower().endswith('.png'): Image.open(out).convert('RGB').save(out, quality=92)
    db['p_commons'].append(dict(id=k, file=f'commons/{k}.jpg', term='commons', title=title, date=date, culture='', period='', artist=artist,
                                medium=medium, source='Wikimedia Commons', license=v['lic'], page=v['page']))
    json.dump(db, open(db_p, 'w'), indent=1); print(k, v['lic'], os.path.getsize(out), flush=True); time.sleep(10)
print('COMMONS_DONE')
