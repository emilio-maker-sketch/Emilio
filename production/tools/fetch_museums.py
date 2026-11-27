"""Build topic pools of CC0 images from The Met Open Access (and Art Institute of Chicago).

Output: build/images/museum/<topic>/<id>.jpg and build/images/museum.json {topic: [records]}
"""
import json, os, sys, time, re
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'images', 'museum')
DB = os.path.join(ROOT, 'build', 'images', 'museum.json')
S = requests.Session(); S.headers['User-Agent'] = 'DocumentaryResearchBot/1.0 (educational video production)'

TOPICS = {
    'p_casts': ['Plaster Casts of Bodies Pompeii', 'Pompeii bodies', 'Sommer Pompeii', 'Pompeii excavation photograph', 'Pompeii Forum photograph', 'Herculaneum excavation', 'Vesuvius eruption 1872', 'Vesuvius 1822', 'stone pine', 'Roman galley relief', 'Roman ship mosaic', 'Roman warship'],
    'p_frescoes': ['Boscoreale', 'Pompeian wall painting', 'Roman fresco', 'Villa of P. Fannius Synistor', 'Boscotrecase', 'Roman wall painting fragment', 'Pompeii fresco'],
    'p_daily': ['Roman bronze lamp', 'Roman glass bottle', 'Roman bread stamp', 'Roman oil lamp', 'Roman strigil', 'Roman jewelry gold', 'Roman bracelet', 'Roman ring gold', 'Roman bronze jug', 'Roman amphora', 'Roman dice', 'Roman key', 'Roman mirror', 'Roman stylus', 'Roman wax tablet', 'Roman cooking pot', 'Roman surgical instrument'],
    'p_people': ['Roman portrait bust', 'Roman portrait head marble', 'Vespasian', 'Titus', 'Roman boy portrait', 'Roman woman portrait', 'Roman bronze statuette', 'Roman funerary relief', 'Roman gladiator', 'Roman sestertius Titus', 'denarius Vespasian'],
    'p_photos': ['Pompeii photograph', 'Giorgio Sommer', 'Herculaneum', 'Vesuvius photograph', 'Naples photograph', 'Pompeii albumen', 'Via dell Abbondanza', 'Forum Pompeii', 'Robert Rive', 'Bay of Naples photograph', 'casts Pompeii'],
    'p_vesuvius': ['Vesuvius', 'eruption of Vesuvius', 'Vesuvius erupting', 'Volaire', 'Bay of Naples', 'volcano', 'Vesuvius at night', 'Last Days of Pompeii', 'Pliny', 'Campi Phlegraei', 'Hamilton Vesuvius'],
    'p_villas': ['Roman villa', 'Roman marble table', 'Roman garden painting', 'Roman mosaic', 'Roman cubiculum', 'Roman sculpture Herculaneum', 'Villa of the Papyri', 'papyrus scroll Roman', 'Roman ship', 'Roman navy', 'Roman trireme'],
    'n_assyria': ['lamassu', 'human-headed winged bull', 'winged genie relief', 'Ashurnasirpal II', 'Nimrud', 'Northwest Palace', 'Assyrian king relief', 'Assyrian eunuch relief', 'Assyrian ivory', 'Nimrud ivory', 'Sargon II', 'Khorsabad', 'Sennacherib', 'Assyrian helmet', 'Assyrian bronze'],
    'n_tablets': ['cuneiform tablet', 'cuneiform', 'clay tablet', 'Neo-Assyrian tablet', 'Neo-Babylonian tablet', 'Old Babylonian tablet', 'cuneiform prism', 'foundation cylinder', 'school tablet', 'omen tablet', 'liver model', 'Gilgamesh', 'stylus cuneiform', 'envelope cuneiform', 'Sumerian tablet'],
    'n_babylon': ['Babylon', 'Nebuchadnezzar', 'glazed brick lion', 'Ishtar Gate', 'Processional Way', 'Babylonian lion', 'Neo-Babylonian', 'kudurru', 'cylinder seal Neo-Assyrian', 'cylinder seal', 'Achaemenid'],
    'n_prints': ['Nineveh', 'Layard', 'Assyrian Discoveries', 'Monuments of Nineveh', 'Mosul', 'Tigris', 'Babylon print', 'Fall of Nineveh', 'Assyria', 'Mesopotamia photograph', 'Baghdad photograph', 'Euphrates', 'British Museum Assyrian'],
    'amarna': ['Amarna letter', 'cuneiform tablet Amarna', 'Akhenaten', 'Amenhotep III', 'Nefertiti', 'Amarna relief', 'Tiye'],
    'egypt_kings': ['Ramesses II', 'Ramesses III', 'Merneptah', 'Seti I', 'Ramesside', 'Dynasty 19 statue', 'Dynasty 20'],
    'egypt_photos': ['Medinet Habu', 'Karnak', 'Abu Simbel', 'Luxor temple', 'Ramesseum', 'Thebes photograph', 'Nile photograph', 'Valley of the Kings', 'Deir el-Medina', 'Felix Teynard', 'Francis Frith Egypt', 'Maxime Du Camp'],
    'egypt_paintings': ['facsimile Theban tomb', 'tribute foreigners facsimile', 'Syrians facsimile', 'Keftiu', 'Nina de Garis Davies', 'Rekhmire', 'chariot facsimile', 'harvest facsimile', 'granary model'],
    'egypt_objects': ['shabti Ramesses', 'ostracon', 'scarab Amenhotep', 'New Kingdom chariot', 'Egyptian glass vessel', 'core-formed glass', 'Egyptian faience New Kingdom', 'papyrus New Kingdom', 'Egyptian bow arrows', 'Egyptian wheat'],
    'mycenaean': ['Mycenaean', 'Helladic', 'Mycenaean figurine', 'stirrup jar', 'Mycenaean krater', 'Mycenaean chariot krater', 'Mycenaean gold', 'Mycenaean kylix'],
    'minoan': ['Minoan', 'Late Minoan', 'Minoan larnax'],
    'cyprus': ['Cypriot Late Bronze Age', 'Late Cypriot', 'Base-ring', 'White Slip', 'Cypriot bronze stand', 'Cypro-Mycenaean', 'Cypriot copper', 'Enkomi', 'Cypriot cylinder seal'],
    'anatolia': ['Hittite', 'Anatolian Bronze Age', 'Hittite vessel', 'Hittite seal', 'Old Assyrian tablet', 'Kültepe', 'Anatolian figurine'],
    'mesopotamia': ['Kassite', 'kudurru', 'Middle Assyrian', 'cuneiform tablet', 'cylinder seal Mitanni', 'Mitanni', 'Babylonian'],
    'levant': ['Canaanite', 'Levantine Bronze Age', 'Ugarit', 'Syrian Late Bronze', 'Levantine ivory', 'Megiddo', 'Lachish', 'Syrian figurine bronze'],
    'bronze_metal': ['oxhide ingot', 'Bronze Age dagger', 'Bronze Age sword', 'Bronze Age axe', 'bronze spearhead', 'Bronze Age helmet', 'bronze greave', 'tin ingot'],
    'neo_assyrian': ['Assyrian relief', 'Nimrud relief', 'Ashurnasirpal', 'Neo-Assyrian'],
    'iron_age': ['Phoenician', 'Phoenician inscription', 'Neo-Hittite', 'Iron Age', 'Philistine', 'Iron Age sword', 'Luwian', 'Carchemish', 'Tell Halaf', 'Aramaic inscription'],
    'greek_after': ['Geometric krater', 'Greek Geometric', 'Protogeometric', 'Homer', 'Iliad', 'Trojan War', 'Greek alphabet inscription', 'Cypro-Geometric'],
    'sea_ships': ['ship model', 'ancient ship', 'galley', 'shipwreck', 'storm at sea', 'stormy sea', 'Mediterranean coast'],
    'ruins_mood': ['ruins', 'ruined temple', 'ancient ruins painting', 'desert landscape', 'Piranesi', 'Hubert Robert ruins', 'Claude Lorrain', 'Syria landscape', 'Anatolia landscape', 'Greece landscape', 'Mycenae', 'Troy'],
    'drought_famine': ['drought', 'famine', 'wheat field', 'harvest', 'barren landscape', 'sunset desert', 'dust storm', 'volcano eruption', 'earthquake'],
    'k_ramesses3': ['Ramesses III', 'Ramesses IV', 'Ramesside king', 'Dynasty 20 king', 'Medinet Habu relief', 'Thebes royal'],
    'k_harem': ['queen Dynasty 19', 'royal woman New Kingdom', 'New Kingdom earring', 'New Kingdom jewelry', 'cosmetic jar New Kingdom', 'mirror New Kingdom', 'kohl tube', 'wig New Kingdom', 'musician New Kingdom', 'harem'],
    'k_magic': ['magic wand', 'magical figurine', 'execration figure', 'wax figure', 'magical papyrus', 'amulet wedjat', 'Eye of Horus amulet', 'healing statue', 'magic brick'],
    'k_papyri': ['hieratic papyrus', 'papyrus Ramesside', 'scribe palette', 'scribe statue', 'ostracon hieratic', 'papyrus document'],
    'k_thebes_photos': ['Deir el-Bahari', 'Deir el Bahri', 'Valley of the Kings photograph', 'Thebes necropolis', 'Gournah', 'Qurna', 'Theban mountain', 'Colossi of Memnon', 'Luxor photograph'],
    'k_officials': ['official New Kingdom statue', 'Ramesside official', 'stela New Kingdom', 'block statue New Kingdom', 'soldier New Kingdom', 'archer Egypt', 'Nubian'],
    'k_death': ['coffin Dynasty 20', 'canopic Dynasty 20', 'shabti Dynasty 20', 'funerary papyrus', 'Book of the Dead', 'embalming', 'Anubis'],
    'archaeology': ['excavation photograph', 'archaeological excavation', 'Schliemann', 'Egypt Exploration', 'archaeologists'],
}
MAX_PER_TERM = 10

def met_search(term):
    r = S.get('https://collectionapi.metmuseum.org/public/collection/v1.1/search',
              params={'q': term, 'hasImages': 'true', 'limit': 60}, timeout=40)
    return (r.json().get('objectIDs') or []) if r.status_code == 200 else []

def met_obj(oid):
    for i in range(4):
        r = S.get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}', timeout=40)
        if r.status_code == 200: return r.json()
        time.sleep(2 * (i + 1))
    return {}

def main():
    db = json.load(open(DB)) if os.path.exists(DB) else {}
    seen = {r['id'] for t in db.values() for r in t}
    topics = sys.argv[1:] or list(TOPICS)
    for topic in topics:
        os.makedirs(os.path.join(OUT, topic), exist_ok=True)
        recs = db.get(topic, [])
        for term in TOPICS[topic]:
            n = 0
            for oid in met_search(term):
                if n >= MAX_PER_TERM: break
                key = f'met{oid}'
                if key in seen: continue
                o = met_obj(oid)
                if not o.get('isPublicDomain') or not o.get('primaryImage'): continue
                path = os.path.join(OUT, topic, f'{key}.jpg')
                try:
                    b = S.get(o['primaryImage'], timeout=120)
                    if b.status_code != 200 or len(b.content) < 30000: continue
                    open(path, 'wb').write(b.content)
                except Exception:
                    continue
                rec = {'id': key, 'file': f'museum/{topic}/{key}.jpg', 'term': term, 'title': o.get('title', ''),
                       'date': o.get('objectDate', ''), 'culture': o.get('culture', ''), 'period': o.get('period', ''),
                       'artist': o.get('artistDisplayName', ''), 'medium': o.get('medium', '')[:80],
                       'source': 'The Metropolitan Museum of Art', 'license': 'CC0 (Met Open Access)', 'page': o.get('objectURL', '')}
                recs.append(rec); seen.add(key); n += 1
                time.sleep(0.15)
            print(f'{topic:16s} {term:30s} +{n}', flush=True)
            db[topic] = recs
            json.dump(db, open(DB, 'w'), indent=1)
    print('TOTAL', sum(len(v) for v in db.values()))

if __name__ == '__main__':
    main()
